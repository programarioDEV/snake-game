from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..agents import BaseAgent, TacticalMode
from ..core import CollisionType, SnakeId
from .config import MatchConfig
from .series import SeriesStats
from .simulation import GameResult, SimulationEngine


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    config: MatchConfig
    names: tuple[str, ...]
    series: SeriesStats


def run_benchmark(
    config: MatchConfig, games: int, factories: Sequence[Callable[[], BaseAgent]]
) -> BenchmarkReport:
    engine = SimulationEngine(config, [make() for make in factories])
    series = SeriesStats(len(engine.agents))
    for offset in range(games):
        engine.reset(seed=config.seed + offset)
        series.record(engine.run())
    names = tuple(f"#{i + 1} {agent.name}" for i, agent in enumerate(engine.agents))
    return BenchmarkReport(config, names, series)


def format_report(report: BenchmarkReport) -> str:
    s = report.series
    c = report.config
    ids = [SnakeId(i) for i in range(len(report.names))]

    def row(label: str, values: Sequence[str]) -> str:
        return f"{label:<22}" + "".join(f"{v:>18}" for v in values)

    def per_decision(sid: SnakeId, value: float) -> str:
        decisions = s.agents[sid].decisions
        return f"{value / decisions:.2f}" if decisions else "-"

    lines = [
        f"{s.matches} games | {c.width}x{c.height} '{c.arena}' | seeds {c.seed}..{c.seed + s.matches - 1}",
        "",
        row("", report.names),
        row("wins", [f"{s.wins[sid]} ({s.win_rate(sid):.0%})" for sid in ids]),
        row("avg final length", [f"{s.mean_length(sid):.1f}" for sid in ids]),
        row("decide ms mean", [per_decision(sid, s.agents[sid].total_ms) for sid in ids]),
        row("decide ms max", [f"{s.agents[sid].max_ms:.2f}" for sid in ids]),
        row("A* nodes / decision", [per_decision(sid, s.agents[sid].nodes_expanded) for sid in ids]),
    ]
    for cause in CollisionType:
        lines.append(row(f"deaths {cause.name}", [str(s.deaths[(sid, cause)]) for sid in ids]))
    loops, stalls = s.endings[GameResult.DRAW_CYCLE], s.endings[GameResult.DRAW_STALEMATE]
    lines += ["", f"draws {s.draws} (loop {loops}, stalemate {stalls}) | avg ticks {s.mean_ticks:.0f}"]
    for sid in ids:
        modes = s.agents[sid].modes
        total = sum(modes.values())
        if total:
            mix = " | ".join(f"{m.value} {modes[m] / total:.0%}" for m in TacticalMode)
            lines.append(f"{report.names[sid]} modes: {mix}")
    return "\n".join(lines)
