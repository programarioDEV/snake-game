from __future__ import annotations

from dataclasses import dataclass

from ..analysis import astar
from ..core import Cell, Direction, GameState, SnakeId
from .base import BaseAgent, Decision, DecisionTrace, TacticalMode
from .perception import HeadOn, MoveOption, Situation, perceive


@dataclass(frozen=True, slots=True)
class AIConfig:
    astar_weight: float = 1.25
    head_on_penalty: float = 12.0
    hysteresis: float = 0.08
    cut_horizon: int = 10
    squeeze_factor: float = 4.0
    max_expansions: int = 6000


@dataclass(frozen=True, slots=True)
class _Plan:
    direction: Direction | None
    rationale: str
    path: tuple[Cell, ...] = ()
    cost: float | None = None
    nodes: int = 0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class AggressiveAIController(BaseAgent):
    """Utility AI: scores FORAGE / INTERCEPT / CONSTRICT / SURVIVAL every tick, then plans with A*."""

    def __init__(self, config: AIConfig | None = None) -> None:
        self.config = config or AIConfig()
        self._mode: TacticalMode | None = None

    @property
    def name(self) -> str:
        return "Offensive AI"

    def reset(self) -> None:
        self._mode = None

    def decide(self, state: GameState, me: SnakeId) -> Decision:
        s = perceive(state, me, cut_horizon=self.config.cut_horizon)
        utilities = self._utilities(s)
        mode = self._select(utilities)
        self._mode = mode
        plan = self._plan(mode, s)
        option = self._safeguard(plan.direction, s)
        direction = option.direction if option is not None else s.me.direction

        rationale = plan.rationale
        if option is None:
            rationale += " | boxed in"
        elif direction != plan.direction:
            rationale += f" | safety -> {direction.name}"

        trace = DecisionTrace(
            mode=mode,
            utilities=utilities,
            rationale=rationale,
            planned_path=plan.path,
            path_cost=plan.cost,
            nodes_expanded=plan.nodes,
            opponent_goal=s.opp_goal,
            opponent_path=s.opp_path,
            intercept_point=(
                s.lethal_cut
                if mode is TacticalMode.CONSTRICT and s.lethal_cut is not None
                else s.intercept
            ),
            lethal_cut=s.lethal_cut,
            chokepoints=dict(s.cuts.cut_area) if s.cuts is not None else {},
            territory=s.territory.owner,
            territory_ratio=s.territory_ratio,
        )
        return Decision(direction, trace)

    def _utilities(self, s: Situation) -> dict[TacticalMode, float]:
        me, opp = s.me, s.opponent
        survival = _clamp((3 * me.length - s.my_space) / (2 * me.length))
        calm = 1.0 - survival

        forage = 0.0
        if s.food_target is not None:
            deficit = (opp.length - me.length) if opp is not None else 0
            hunger = _clamp((deficit + 3) / 6)
            forage = (0.35 + 0.45 * hunger) * (1.0 if s.food_race_won else 0.5) * calm

        intercept = constrict = 0.0
        if opp is not None:
            if s.intercept is not None:
                cuts_route = s.cuts is not None and s.intercept in s.cuts.cut_area
                bonus = (0.3 if cuts_route else 0.0) + (0.1 if s.longer else 0.0)
                intercept = (0.45 + bonus) * calm
            if s.lethal_cut is not None:
                constrict = 0.95 * calm
            else:
                factor = self.config.squeeze_factor
                starved = (factor * opp.length - s.opp_territory) / ((factor - 1) * opp.length)
                dominance = (s.territory_ratio - 0.55) / 0.25 if s.longer else 0.0
                constrict = 0.8 * _clamp(max(starved, dominance)) * calm

        return {
            TacticalMode.FORAGE: forage,
            TacticalMode.INTERCEPT: intercept,
            TacticalMode.CONSTRICT: constrict,
            TacticalMode.SURVIVAL: max(survival, 0.1),
        }

    def _select(self, utilities: dict[TacticalMode, float]) -> TacticalMode:
        best = max(TacticalMode, key=lambda m: utilities[m])
        previous = self._mode
        if (
            previous is not None
            and previous is not best
            and utilities[previous] > 0.0
            and utilities[best] - utilities[previous] < self.config.hysteresis
        ):
            return previous
        return best

    def _plan(self, mode: TacticalMode, s: Situation) -> _Plan:
        if mode is TacticalMode.FORAGE and s.food_target is not None:
            race = "first" if s.food_race_won else "contested"
            eta = s.my_times[s.food_target]
            return self._route(s, s.food_target, f"food {self._xy(s, s.food_target)} eta {eta} ({race})")
        if mode is TacticalMode.INTERCEPT and s.intercept is not None:
            goal = self._xy(s, s.opp_goal) if s.opp_goal is not None else "?"
            return self._route(
                s,
                s.intercept,
                f"cut opp route at {self._xy(s, s.intercept)} lead {s.intercept_lead} (opp -> {goal})",
            )
        if mode is TacticalMode.CONSTRICT:
            if s.lethal_cut is not None and s.cuts is not None and s.opponent is not None:
                area = s.cuts.cut_area[s.lethal_cut]
                return self._route(
                    s,
                    s.lethal_cut,
                    f"seal chokepoint {self._xy(s, s.lethal_cut)}: opp room {area} < len {s.opponent.length}",
                )
            return self._squeeze(s)
        return self._survive(s)

    def _route(self, s: Situation, target: Cell, rationale: str) -> _Plan:
        result = astar(
            s.grid,
            s.free_at,
            s.me.head,
            target,
            weight=self.config.astar_weight,
            penalty=self._penalties(s),
            max_expansions=self.config.max_expansions,
        )
        if not result.path:
            return _Plan(None, rationale + " [no route]", nodes=result.nodes_expanded)
        first = s.grid.direction_between(s.me.head, result.path[0])
        return _Plan(first, rationale, result.path, result.cost, result.nodes_expanded)

    def _penalties(self, s: Situation) -> list[float] | None:
        """Keeps us out of a longer rival's reach: its next cells and the ring it can pinch next."""
        if s.longer or not s.threat:
            return None
        penalty = [0.0] * s.grid.size
        for cell in s.threat:
            for ring in s.grid.neighbors(cell):
                penalty[ring] = self.config.head_on_penalty / 3
        for cell in s.threat:
            penalty[cell] = self.config.head_on_penalty
        return penalty

    def _squeeze(self, s: Situation) -> _Plan:
        viable = [
            o
            for o in s.options
            if not o.lethal and o.head_on is not HeadOn.UNFAVORABLE and o.space >= s.me.length
        ]
        if not viable:
            return _Plan(None, "squeeze: no safe envelope")
        best = min(viable, key=lambda o: (o.opp_space, o.opp_territory - o.territory, o.direction))
        worst = max(o.opp_territory for o in viable)
        return _Plan(
            best.direction,
            f"envelop: rival keeps {best.opp_territory} cells (worst move {worst}), "
            f"room {best.opp_space}",
            (best.cell,) if best.cell is not None else (),
        )

    def _survive(self, s: Situation) -> _Plan:
        me = s.me
        chase = astar(s.grid, s.free_at, me.head, me.tail, max_expansions=self.config.max_expansions)
        if chase.path:
            return _Plan(
                s.grid.direction_between(me.head, chase.path[0]),
                f"tail chase {len(chase.path)} steps, room {s.my_space}",
                chase.path,
                chase.cost,
                chase.nodes_expanded,
            )
        viable = [o for o in s.options if not o.lethal]
        if not viable:
            return _Plan(None, "no escape", nodes=chase.nodes_expanded)
        best = max(viable, key=lambda o: (o.space, o.territory, -o.direction))
        return _Plan(
            best.direction,
            f"max room {best.space}",
            (best.cell,) if best.cell is not None else (),
            nodes=chase.nodes_expanded,
        )

    def _safeguard(self, preferred: Direction | None, s: Situation) -> MoveOption | None:
        """Vetoes lethal moves, losing head-ons and pockets smaller than our body, in that order."""
        viable = [o for o in s.options if not o.lethal]
        if not viable:
            return None
        needed = min(s.me.length, max(o.space for o in viable))
        roomy = [o for o in viable if o.space >= needed]
        predicted = s.opp_path[0] if s.opp_path else None
        tiers = (
            [o for o in roomy if o.head_on is not HeadOn.UNFAVORABLE],
            [o for o in roomy if o.cell != predicted],
            roomy,
            viable,
        )
        pool = next(tier for tier in tiers if tier)
        for option in pool:
            if option.direction == preferred:
                return option
        return max(
            pool,
            key=lambda o: (
                o.territory - o.opp_territory,
                o.head_on is HeadOn.FAVORABLE,
                o.space,
                -o.direction,
            ),
        )

    @staticmethod
    def _xy(s: Situation, cell: Cell) -> str:
        x, y = s.grid.xy(cell)
        return f"({x},{y})"
