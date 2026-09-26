from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import NewType

from .grid import Cell, Direction, Grid

SnakeId = NewType("SnakeId", int)


@dataclass(frozen=True, slots=True)
class Snake:
    """Immutable snake snapshot; body[0] is the head and body[-1] the tail."""

    id: SnakeId
    body: tuple[Cell, ...]
    direction: Direction
    pending_growth: int = 0
    alive: bool = True
    _cells: frozenset[Cell] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.body:
            raise ValueError("snake body cannot be empty")
        if self.pending_growth < 0:
            raise ValueError("pending_growth cannot be negative")
        cells = frozenset(self.body)
        if len(cells) != len(self.body):
            raise ValueError("snake body overlaps itself")
        object.__setattr__(self, "_cells", cells)

    @classmethod
    def spawn(
        cls, grid: Grid, snake_id: SnakeId, head: Cell, direction: Direction, length: int
    ) -> Snake:
        """Lays the body out in a straight line behind the head."""
        if length < 1:
            raise ValueError("length must be positive")
        if not grid.is_open(head):
            raise ValueError("head must be on an open cell")
        body = [head]
        for _ in range(length - 1):
            behind = grid.step(body[-1], direction.opposite)
            if behind is None:
                raise ValueError("not enough open space behind the head")
            body.append(behind)
        return cls(snake_id, tuple(body), direction)

    @property
    def head(self) -> Cell:
        return self.body[0]

    @property
    def tail(self) -> Cell:
        return self.body[-1]

    @property
    def length(self) -> int:
        return len(self.body)

    @property
    def next_length(self) -> int:
        """Length right after the next move, which is what decides head-to-head clashes."""
        return self.length + (1 if self.pending_growth else 0)

    @property
    def cells(self) -> frozenset[Cell]:
        return self._cells

    @property
    def retained_body(self) -> tuple[Cell, ...]:
        """Cells still occupied after the next move, new head excluded; the tail stays while growing."""
        return self.body if self.pending_growth else self.body[:-1]

    def advanced(self, head: Cell, direction: Direction, extra_growth: int = 0) -> Snake:
        return Snake(
            self.id,
            (head, *self.retained_body),
            direction,
            max(self.pending_growth - 1, 0) + extra_growth,
        )

    def killed(self) -> Snake:
        return replace(self, alive=False)
