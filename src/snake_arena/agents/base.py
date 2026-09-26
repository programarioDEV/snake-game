from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from ..core import Cell, Direction, GameState, SnakeId


class TacticalMode(StrEnum):
    FORAGE = "FORAGE"
    INTERCEPT = "INTERCEPT"
    CONSTRICT = "CONSTRICT"
    SURVIVAL = "SURVIVAL"


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    """What an agent perceived and intended this tick; read only by overlays and benchmarks."""

    mode: TacticalMode
    utilities: Mapping[TacticalMode, float] = field(default_factory=dict)
    rationale: str = ""
    planned_path: tuple[Cell, ...] = ()
    path_cost: float | None = None
    nodes_expanded: int = 0
    opponent_goal: Cell | None = None
    opponent_path: tuple[Cell, ...] = ()
    intercept_point: Cell | None = None
    lethal_cut: Cell | None = None
    # Articulation point -> free cells left to the opponent if that cell gets sealed.
    chokepoints: Mapping[Cell, int] = field(default_factory=dict)
    # Owning SnakeId per cell, -1 for neutral or unreachable cells.
    territory: tuple[int, ...] | None = None
    territory_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    direction: Direction
    trace: DecisionTrace | None = None


class BaseAgent(ABC):
    """Strategy interface for anything that steers a snake: human input, bots or the AI."""

    @property
    def name(self) -> str:
        return type(self).__name__

    def reset(self) -> None:
        """Clears per-match memory before a new game."""

    @abstractmethod
    def decide(self, state: GameState, me: SnakeId) -> Decision: ...
