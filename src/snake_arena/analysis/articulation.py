from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from ..core import Cell, Grid


@dataclass(frozen=True, slots=True)
class CutAnalysis:
    root: Cell
    component_size: int
    cut_area: Mapping[Cell, int]

    @property
    def points(self) -> frozenset[Cell]:
        return frozenset(self.cut_area)


def articulation_points(grid: Grid, passable: Sequence[bool], root: Cell) -> CutAnalysis:
    """Iterative Tarjan rooted at root; cut_area[v] = cells still linked to root once v is removed."""
    size = grid.size
    adjacency = grid.adjacency
    disc = [-1] * size
    low = [0] * size
    subtree = [0] * size
    parent = [-1] * size
    separated: dict[Cell, int] = {}

    disc[root] = 0
    subtree[root] = 1
    timer = 1
    stack: list[tuple[Cell, Iterator[Cell]]] = [(root, iter(adjacency[root]))]
    while stack:
        node, pending = stack[-1]
        descended = False
        for neighbor in pending:
            if neighbor != root and not passable[neighbor]:
                continue
            if disc[neighbor] == -1:
                parent[neighbor] = node
                disc[neighbor] = low[neighbor] = timer
                timer += 1
                subtree[neighbor] = 1
                stack.append((neighbor, iter(adjacency[neighbor])))
                descended = True
                break
            if neighbor != parent[node]:
                low[node] = min(low[node], disc[neighbor])
        if descended:
            continue
        stack.pop()
        up = parent[node]
        if up == -1:
            continue
        low[up] = min(low[up], low[node])
        subtree[up] += subtree[node]
        if up != root and low[node] >= disc[up]:
            separated[Cell(up)] = separated.get(Cell(up), 0) + subtree[node]

    reachable = subtree[root] - 1
    cut_area = {cell: reachable - 1 - lost for cell, lost in separated.items()}
    return CutAnalysis(root, reachable, cut_area)
