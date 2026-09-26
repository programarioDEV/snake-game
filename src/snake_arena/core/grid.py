from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import IntEnum
from typing import NewType

# Flat index y * width + x: graph searches run on ints and precomputed tables, not coordinate tuples.
Cell = NewType("Cell", int)


class Direction(IntEnum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3

    @property
    def delta(self) -> tuple[int, int]:
        return _DELTAS[self]

    @property
    def opposite(self) -> Direction:
        return Direction((self + 2) % 4)


_DELTAS: tuple[tuple[int, int], ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))


@dataclass(frozen=True, slots=True)
class Grid:
    """Immutable 4-connected grid graph with precomputed move and adjacency tables."""

    width: int
    height: int
    obstacles: frozenset[Cell] = frozenset()
    _moves: tuple[Cell | None, ...] = field(init=False, repr=False, compare=False)
    _neighbors: tuple[tuple[Cell, ...], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.width < 2 or self.height < 2:
            raise ValueError(f"grid must be at least 2x2, got {self.width}x{self.height}")
        size = self.width * self.height
        if any(not 0 <= cell < size for cell in self.obstacles):
            raise ValueError("obstacle outside grid bounds")

        moves: list[Cell | None] = []
        for index in range(size):
            y, x = divmod(index, self.width)
            for dx, dy in _DELTAS:
                nx, ny = x + dx, y + dy
                target = Cell(ny * self.width + nx)
                reachable = (
                    0 <= nx < self.width
                    and 0 <= ny < self.height
                    and index not in self.obstacles
                    and target not in self.obstacles
                )
                moves.append(target if reachable else None)
        neighbors = tuple(
            tuple(t for t in moves[i * 4 : i * 4 + 4] if t is not None) for i in range(size)
        )
        object.__setattr__(self, "_moves", tuple(moves))
        object.__setattr__(self, "_neighbors", neighbors)

    @property
    def size(self) -> int:
        return self.width * self.height

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def cell(self, x: int, y: int) -> Cell:
        if not self.in_bounds(x, y):
            raise ValueError(f"({x}, {y}) is outside a {self.width}x{self.height} grid")
        return Cell(y * self.width + x)

    def xy(self, cell: Cell) -> tuple[int, int]:
        y, x = divmod(cell, self.width)
        return x, y

    def is_open(self, cell: Cell) -> bool:
        return 0 <= cell < self.size and cell not in self.obstacles

    def step(self, cell: Cell, direction: Direction) -> Cell | None:
        """Cell reached by one move, or None when it hits the border or an obstacle."""
        return self._moves[cell * 4 + direction]

    def neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        return self._neighbors[cell]

    @property
    def adjacency(self) -> tuple[tuple[Cell, ...], ...]:
        return self._neighbors

    def direction_between(self, a: Cell, b: Cell) -> Direction | None:
        for direction in Direction:
            if self._moves[a * 4 + direction] == b:
                return direction
        return None

    def open_cells(self) -> Iterator[Cell]:
        return (Cell(i) for i in range(self.size) if i not in self.obstacles)

    def manhattan(self, a: Cell, b: Cell) -> int:
        ay, ax = divmod(a, self.width)
        by, bx = divmod(b, self.width)
        return abs(ax - bx) + abs(ay - by)
