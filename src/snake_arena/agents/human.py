from __future__ import annotations

from collections import deque

from ..core import Direction, GameState, SnakeId
from .base import BaseAgent, Decision


class HumanController(BaseAgent):
    """Buffers key presses so a quick double turn lands on consecutive ticks."""

    def __init__(self, buffer_size: int = 3) -> None:
        self._pending: deque[Direction] = deque(maxlen=buffer_size)

    @property
    def name(self) -> str:
        return "You"

    def push(self, direction: Direction) -> None:
        if not self._pending or self._pending[-1] != direction:
            self._pending.append(direction)

    def reset(self) -> None:
        self._pending.clear()

    def decide(self, state: GameState, me: SnakeId) -> Decision:
        snake = state.snake(me)
        while self._pending:
            direction = self._pending.popleft()
            reversal = snake.length > 1 and direction == snake.direction.opposite
            if direction != snake.direction and not reversal:
                return Decision(direction)
        return Decision(snake.direction)
