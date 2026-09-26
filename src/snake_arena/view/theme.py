from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from ..agents import TacticalMode

RGB = tuple[int, int, int]


def mix(a: RGB, b: RGB, t: float) -> RGB:
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def font(size: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont("consolas,dejavusansmono,menlo,couriernew", size, bold=bold)


@dataclass(frozen=True, slots=True)
class Theme:
    background: RGB = (11, 13, 18)
    board: RGB = (18, 21, 29)
    grid_line: RGB = (26, 30, 41)
    obstacle: RGB = (56, 62, 79)
    food: RGB = (255, 196, 61)
    panel: RGB = (15, 17, 24)
    panel_rule: RGB = (38, 43, 56)
    text: RGB = (226, 230, 240)
    text_dim: RGB = (122, 131, 152)
    snakes: tuple[RGB, RGB] = ((77, 163, 255), (255, 88, 102))
    dead: RGB = (66, 70, 82)
    path: RGB = (255, 160, 170)
    intercept: RGB = (255, 209, 102)
    chokepoint: RGB = (190, 130, 255)
    lethal: RGB = (255, 56, 140)
    territory_alpha: int = 44
    frontier_alpha: int = 120
    modes: dict[TacticalMode, RGB] = field(
        default_factory=lambda: {
            TacticalMode.FORAGE: (94, 214, 132),
            TacticalMode.INTERCEPT: (255, 209, 102),
            TacticalMode.CONSTRICT: (255, 56, 140),
            TacticalMode.SURVIVAL: (125, 170, 255),
        }
    )
