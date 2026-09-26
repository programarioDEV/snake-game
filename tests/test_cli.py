import sys
from pathlib import Path

import pytest

from snake_arena.__main__ import build_parser, main


def test_watch_defaults_to_an_endless_series_against_the_baseline() -> None:
    args = build_parser().parse_args(["watch"])
    assert (args.agent_1, args.agent_2, args.rounds, args.delay_restart) == (
        "greedy",
        "aggressive",
        None,
        1.5,
    )


def test_watch_accepts_a_mirror_duel_with_limited_rounds() -> None:
    args = build_parser().parse_args(
        ["watch", "--agent-1", "aggressive", "--agent-2", "aggressive", "--rounds", "5", "--delay-restart", "2"]
    )
    assert (args.agent_1, args.agent_2, args.rounds, args.delay_restart) == (
        "aggressive",
        "aggressive",
        5,
        2.0,
    )


@pytest.mark.parametrize(
    "flags",
    [["--delay-restart", "0.5"], ["--delay-restart", "2.5"], ["--rounds", "0"], ["--agent-1", "human"]],
)
def test_watch_rejects_invalid_flags(flags: list[str]) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["watch", *flags])


def test_record_defaults_and_flag_validation() -> None:
    args = build_parser().parse_args(["record", "--output", "assets/showcase.gif"])
    assert (args.format, args.tick_rate, args.max_ticks, args.overlays, args.highlight_lethal) == (
        None,
        15,
        1500,
        "all",
        False,
    )
    for flags in (["--tick-rate", "0"], ["--tick-rate", "60"], ["--overlays", "path"], ["--max-ticks", "0"]):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["record", "--output", "x.gif", *flags])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["record"])


def test_record_refuses_an_output_without_a_known_format(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["record", "--output", str(tmp_path / "clip.webm")])


def test_record_writes_a_gif_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pytest.importorskip("PIL")
    target = tmp_path / "nested" / "clip.gif"
    code = main(
        ["record", "--size", "13", "--arena", "open", "--cell", "8", "--max-ticks", "12", "--output", str(target)]
    )
    data = target.read_bytes()
    assert code == 0
    assert data.startswith(b"GIF89a") and data.endswith(b";")
    assert "saved" in capsys.readouterr().out


def test_record_reports_missing_dependencies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delitem(sys.modules, "snake_arena.record.gif", raising=False)
    monkeypatch.setitem(sys.modules, "PIL", None)
    code = main(["record", "--size", "13", "--arena", "open", "--output", str(tmp_path / "clip.gif")])
    assert code == 2
    assert 'pip install "snake-arena[record]"' in capsys.readouterr().err


def test_bench_runs_a_mirror_match_headless(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["bench", "--games", "1", "--size", "15", "--arena", "open", "--agent-1", "aggressive"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "#1 Offensive AI" in out and "#2 Offensive AI" in out
