from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from .agents import AggressiveAIController, BaseAgent, GreedyAgent, HumanController
from .engine import ARENAS, REPETITION_LIMIT, GameResult, MatchConfig, format_report, run_benchmark
from .record.writers import FORMATS, OVERLAY_PRESETS

AGENTS: dict[str, Callable[[], BaseAgent]] = {
    "aggressive": AggressiveAIController,
    "greedy": GreedyAgent,
}


def _board_size(text: str) -> int:
    value = int(text)
    if not 2 <= value <= 100:
        raise argparse.ArgumentTypeError("must be between 2 and 100")
    return value


def _food_count(text: str) -> int:
    value = int(text)
    if not 0 <= value <= 1000:
        raise argparse.ArgumentTypeError("must be between 0 and 1000")
    return value


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _restart_delay(text: str) -> float:
    value = float(text)
    if not 1.0 <= value <= 2.0:
        raise argparse.ArgumentTypeError("must be between 1 and 2 seconds")
    return value


def _video_fps(text: str) -> int:
    value = int(text)
    if not 1 <= value <= 50:
        raise argparse.ArgumentTypeError("must be between 1 and 50 fps")
    return value


def build_parser() -> argparse.ArgumentParser:
    board = argparse.ArgumentParser(add_help=False)
    board.add_argument("--arena", choices=sorted(ARENAS), default="cross")
    board.add_argument("--size", type=_board_size, default=31, help="board side in cells")
    board.add_argument("--food", type=_food_count, default=3, help="food items on the board")
    board.add_argument("--seed", type=int, default=0, help="food seed (watch/bench: first round)")

    rules = argparse.ArgumentParser(add_help=False)
    rules.add_argument(
        "--stall-ticks", type=_positive_int, default=None, metavar="N",
        help="draw after N ticks in a row without anyone eating (default: 1.5 x board area)",
    )
    rules.add_argument(
        "--disable-cycle-detection", action="store_true",
        help=f"debug: do not draw when the same position repeats {REPETITION_LIMIT} times",
    )

    display = argparse.ArgumentParser(add_help=False)
    display.add_argument("--cell", type=int, default=22, help="cell size in pixels")

    matchup = argparse.ArgumentParser(add_help=False)
    matchup.add_argument("--agent-1", choices=sorted(AGENTS), default="greedy", help="blue snake")
    matchup.add_argument("--agent-2", choices=sorted(AGENTS), default="aggressive", help="red snake")

    parser = argparse.ArgumentParser(prog="snake-arena", description="Snake vs an offensive AI.")
    commands = parser.add_subparsers(dest="command", required=True)

    play = commands.add_parser("play", parents=[board, rules, display], help="you (blue) vs the AI (red)")
    play.add_argument("--tick-rate", type=float, default=10.0, help="simulation ticks per second")

    watch = commands.add_parser(
        "watch", parents=[board, rules, display, matchup], help="AI vs AI showcase with auto-restart"
    )
    watch.add_argument("--tick-rate", type=float, default=15.0, help="simulation ticks per second")
    watch.add_argument("--rounds", type=_positive_int, default=None, help="matches to play (default: endless)")
    watch.add_argument(
        "--delay-restart", type=_restart_delay, default=1.5, metavar="S",
        help="pause after game over before the next round, 1-2 s (default 1.5)",
    )

    record = commands.add_parser(
        "record", parents=[board, rules, display, matchup], help="render one match to GIF/MP4 without a window"
    )
    record.add_argument("--output", type=Path, required=True, help="target file, e.g. assets/showcase.gif")
    record.add_argument("--format", choices=FORMATS, default=None, help="default: from the file extension")
    record.add_argument(
        "--tick-rate", type=_video_fps, default=15, help="video fps; one frame per tick (default 15)"
    )
    record.add_argument("--max-ticks", type=_positive_int, default=1500, help="safety cap on match length")
    record.add_argument("--overlays", choices=tuple(OVERLAY_PRESETS), default="all")
    record.add_argument(
        "--highlight-lethal", action="store_true",
        help="if a lethal cut decides the match, replay that moment before the end",
    )

    bench = commands.add_parser("bench", parents=[board, rules, matchup], help="headless benchmark")
    bench.add_argument("--games", type=_positive_int, default=20)
    return parser


def match_config(args: argparse.Namespace) -> MatchConfig:
    """Board and draw-rule flags shared by every command."""
    return MatchConfig(
        width=args.size,
        height=args.size,
        arena=args.arena,
        food_count=args.food,
        seed=args.seed,
        stall_ticks=args.stall_ticks,
        detect_cycles=not args.disable_cycle_detection,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else (sys.argv[1:] or ["play"]))
    try:
        config = match_config(args)
        if args.command == "bench":
            factories = (AGENTS[args.agent_1], AGENTS[args.agent_2])
            print(format_report(run_benchmark(config, args.games, factories)))
            return 0
        if args.command == "record":
            return _record(parser, args, replace(config, max_ticks=args.max_ticks))

        from .view.app import ShowcaseOptions, run_app

        if args.command == "watch":
            agents = [AGENTS[args.agent_1](), AGENTS[args.agent_2]()]
            showcase = ShowcaseOptions(rounds=args.rounds, restart_delay=args.delay_restart)
            run_app(config, agents, tick_rate=args.tick_rate, cell=args.cell, showcase=showcase)
        else:
            run_app(config, [HumanController(), AggressiveAIController()], tick_rate=args.tick_rate, cell=args.cell)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _record(parser: argparse.ArgumentParser, args: argparse.Namespace, config: MatchConfig) -> int:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from .record.recorder import MatchRecorder, RecordOptions
    from .record.writers import RecorderDependencyError, open_writer, resolve_format

    output: Path = args.output
    try:
        fmt = resolve_format(output, args.format)
    except ValueError as exc:
        parser.error(str(exc))
    agents = [AGENTS[args.agent_1](), AGENTS[args.agent_2]()]
    options = RecordOptions(
        fps=args.tick_rate, cell=args.cell, overlays=args.overlays, highlight_lethal=args.highlight_lethal
    )
    recorder = MatchRecorder(config, agents, options)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        writer = open_writer(output, fmt, recorder.size, options.fps)
    except RecorderDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    def progress(tick: int) -> None:
        if tick % 25 == 0:
            print(f"\rrecording tick {tick}/{config.max_ticks}", end="", file=sys.stderr, flush=True)

    try:
        summary = recorder.record(writer, progress)
    finally:
        writer.close()
    print(file=sys.stderr)

    width, height = summary.size
    megabytes = output.stat().st_size / 1_000_000
    print(
        f"saved {output} | {fmt} {width}x{height} | {summary.frames} frames @ {summary.fps} fps "
        f"({summary.duration:.1f} s) | {megabytes:.2f} MB"
    )
    winner = "draw" if summary.winner is None else f"{recorder.labels[summary.winner]} wins"
    if summary.ending in (GameResult.DRAW_CYCLE, GameResult.DRAW_STALEMATE):
        winner += f" ({summary.ending})"
    line = f"{winner} after {summary.ticks} ticks"
    if summary.lethal_ending is not None:
        moment = summary.lethal_ending
        line += f" | decided by a lethal cut at tick {moment.tick}"
        line += " (replayed)" if summary.replayed else " (use --highlight-lethal to replay it)"
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
