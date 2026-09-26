from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import Enum, auto

from ..analysis import (
    BLOCKED,
    UNREACHED,
    CutAnalysis,
    Source,
    VoronoiResult,
    articulation_points,
    backtrack,
    candidate_moves,
    reach_times,
    reachable_count,
    release_times,
    threat_cells,
    voronoi,
)
from ..core import Cell, Direction, GameState, Grid, Snake, SnakeId


class HeadOn(Enum):
    NONE = auto()
    FAVORABLE = auto()
    UNFAVORABLE = auto()


@dataclass(frozen=True, slots=True)
class MoveOption:
    direction: Direction
    cell: Cell | None
    lethal: bool
    head_on: HeadOn = HeadOn.NONE
    space: int = 0
    territory: int = 0
    opp_territory: int = 0
    opp_space: int = 0


@dataclass(frozen=True, slots=True)
class Situation:
    """Everything the tactical layer knows about one tick, computed once and shared by all modes."""

    grid: Grid
    me: Snake
    opponent: Snake | None
    free_at: Sequence[int]
    my_times: Sequence[int]
    my_space: int
    territory: VoronoiResult
    options: tuple[MoveOption, ...]
    food_target: Cell | None = None
    food_race_won: bool = False
    threat: frozenset[Cell] = frozenset()
    opp_space: int = 0
    cuts: CutAnalysis | None = None
    opp_goal: Cell | None = None
    opp_goal_is_food: bool = False
    opp_path: tuple[Cell, ...] = ()
    intercept: Cell | None = None
    intercept_lead: int = 0
    lethal_cut: Cell | None = None

    @property
    def my_territory(self) -> int:
        return self.territory.counts.get(self.me.id, 0)

    @property
    def opp_territory(self) -> int:
        return self.territory.counts.get(self.opponent.id, 0) if self.opponent else 0

    @property
    def territory_ratio(self) -> float:
        return self.territory.share(self.me.id)

    @property
    def longer(self) -> bool:
        return self.opponent is None or self.me.next_length > self.opponent.next_length


def perceive(state: GameState, me_id: SnakeId, *, cut_horizon: int = 10) -> Situation:
    grid = state.grid
    me = state.snake(me_id)
    rivals = state.opponents(me_id)
    opp = min(rivals, key=lambda s: (grid.manhattan(s.head, me.head), s.id)) if rivals else None
    free_at = release_times(state)
    my_times = reach_times(grid, free_at, me.head)
    my_space = reachable_count(my_times)
    mine = Source(me.id, me.head, 0, me.next_length)

    if opp is None:
        food, won = _pick_food(state.food, my_times, (), me.next_length, 0)
        return Situation(
            grid=grid,
            me=me,
            opponent=None,
            free_at=free_at,
            my_times=my_times,
            my_space=my_space,
            territory=voronoi(grid, free_at, (mine,)),
            options=tuple(
                _evaluate(grid, free_at, me, None, frozenset(), d, c)
                for d, c in candidate_moves(grid, me)
            ),
            food_target=food,
            food_race_won=won,
        )

    opp_times = reach_times(grid, free_at, opp.head)
    threat = threat_cells(grid, opp, free_at)
    cuts = articulation_points(grid, [t == 0 for t in free_at], opp.head)
    food, won = _pick_food(state.food, my_times, opp_times, me.next_length, opp.next_length)
    goal, goal_is_food = _predict_goal(grid, state.food, opp_times)
    opp_path = backtrack(grid, opp_times, opp.head, goal) if goal is not None else ()
    longer = me.next_length > opp.next_length
    intercept, lead = _intercept(opp_path, my_times, opp_times, cuts.points, longer)
    return Situation(
        grid=grid,
        me=me,
        opponent=opp,
        free_at=free_at,
        my_times=my_times,
        my_space=my_space,
        territory=voronoi(grid, free_at, (mine, Source(opp.id, opp.head, 0, opp.next_length))),
        options=tuple(
            _evaluate(grid, free_at, me, opp, threat, d, c) for d, c in candidate_moves(grid, me)
        ),
        food_target=food,
        food_race_won=won,
        threat=threat,
        opp_space=reachable_count(opp_times),
        cuts=cuts,
        opp_goal=goal,
        opp_goal_is_food=goal_is_food,
        opp_path=opp_path,
        intercept=intercept,
        intercept_lead=lead,
        lethal_cut=_lethal_cut(grid, free_at, cuts, me, opp, my_times, opp_times, cut_horizon),
    )


def _evaluate(
    grid: Grid,
    free_at: Sequence[int],
    me: Snake,
    opp: Snake | None,
    threat: frozenset[Cell],
    direction: Direction,
    cell: Cell | None,
) -> MoveOption:
    if cell is None or free_at[cell] > 1:
        return MoveOption(direction, cell, lethal=True)
    head_on = HeadOn.NONE
    if opp is not None and cell in threat:
        head_on = HeadOn.FAVORABLE if me.next_length > opp.next_length else HeadOn.UNFAVORABLE
    after = list(free_at)
    after[cell] = BLOCKED
    space = reachable_count(reach_times(grid, after, cell, 1))
    if opp is None:
        return MoveOption(direction, cell, False, head_on, space, territory=space)
    split = voronoi(
        grid,
        after,
        (Source(me.id, cell, 1, me.next_length), Source(opp.id, opp.head, 0, opp.next_length)),
    )
    return MoveOption(
        direction,
        cell,
        False,
        head_on,
        space,
        territory=split.counts[me.id],
        opp_territory=split.counts[opp.id],
        opp_space=reachable_count(reach_times(grid, after, opp.head)),
    )


def _pick_food(
    food: Collection[Cell],
    my_times: Sequence[int],
    opp_times: Sequence[int],
    my_length: int,
    opp_length: int,
) -> tuple[Cell | None, bool]:
    best: tuple[bool, int, Cell] | None = None
    for cell in food:
        mine = my_times[cell]
        if mine == UNREACHED:
            continue
        theirs = opp_times[cell] if opp_times else UNREACHED
        won = (
            theirs == UNREACHED
            or mine < theirs
            or (mine == theirs and my_length > opp_length)
        )
        key = (not won, mine, cell)
        if best is None or key < best:
            best = key
    return (best[2], not best[0]) if best else (None, False)


def _predict_goal(
    grid: Grid, food: Collection[Cell], opp_times: Sequence[int]
) -> tuple[Cell | None, bool]:
    """Nearest food for the opponent, else the reachable cell closest to the board centre."""
    reachable = [c for c in food if opp_times[c] != UNREACHED]
    if reachable:
        return min(reachable, key=lambda c: (opp_times[c], c)), True
    centre = grid.cell(grid.width // 2, grid.height // 2)
    open_cells = [Cell(c) for c, t in enumerate(opp_times) if t > 0]
    if not open_cells:
        return None, False
    return min(open_cells, key=lambda c: (grid.manhattan(c, centre), opp_times[c], c)), False


def _intercept(
    opp_path: Sequence[Cell],
    my_times: Sequence[int],
    opp_times: Sequence[int],
    chokepoints: frozenset[Cell],
    longer: bool,
) -> tuple[Cell | None, int]:
    """Earliest cell of the opponent's route we reach first, preferring chokepoints."""
    needed_lead = 0 if longer else 1
    best: tuple[bool, int, Cell] | None = None
    best_lead = 0
    for cell in opp_path:
        mine = my_times[cell]
        if mine == UNREACHED:
            continue
        lead = opp_times[cell] - mine
        if lead < needed_lead:
            continue
        key = (cell not in chokepoints, opp_times[cell], cell)
        if best is None or key < best:
            best, best_lead = key, lead
    return (best[2], best_lead) if best else (None, 0)


def _lethal_cut(
    grid: Grid,
    free_at: Sequence[int],
    cuts: CutAnalysis,
    me: Snake,
    opp: Snake,
    my_times: Sequence[int],
    opp_times: Sequence[int],
    horizon: int,
) -> Cell | None:
    """A chokepoint we win the race to whose sealing leaves the opponent less room than its length."""
    longer = me.next_length > opp.next_length
    candidates: list[tuple[int, int, Cell]] = []
    for cell, area in cuts.cut_area.items():
        mine = my_times[cell]
        if area >= opp.length or mine == UNREACHED or mine > horizon:
            continue
        theirs = opp_times[cell]
        if theirs != UNREACHED and (mine > theirs or (mine == theirs and not longer)):
            continue
        candidates.append((area, mine, cell))
    for _, mine, cell in sorted(candidates)[:3]:
        if reachable_count(reach_times(grid, free_at, cell, mine)) >= me.length:
            return cell
    return None
