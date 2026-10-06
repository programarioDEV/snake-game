import pytest
from snake_arena.core.grid import Grid

def test_grid_size_limit() -> None:
    with pytest.raises(ValueError, match="at most 256x256"):
        Grid(257, 257)
