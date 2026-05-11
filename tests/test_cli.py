"""Verify CLI entry point works with all subcommands."""

from systemd_doctor.cli import main


def test_no_args_shows_help(capsys):
    """No args should print help and exit 0."""
    result = main([])
    assert result == 0
    captured = capsys.readouterr()
    assert "systemd-doctor" in captured.out
    assert "status" in captured.out
    assert "timers" in captured.out
    assert "security" in captured.out


def test_status_help(capsys):
    """status --help shows flags."""
    result = main(["status", "--help"])
    assert result == 0
    captured = capsys.readouterr()
    assert "--json" in captured.out


def test_timers_help(capsys):
    """timers --help shows warning/critical flags."""
    result = main(["timers", "--help"])
    assert result == 0
    captured = capsys.readouterr()
    assert "--warning" in captured.out
    assert "--critical" in captured.out
    assert "--json" in captured.out


def test_security_help(capsys):
    """security --help shows min-exposure and fix flags."""
    result = main(["security", "--help"])
    assert result == 0
    captured = capsys.readouterr()
    assert "--min-exposure" in captured.out
    assert "--fix" in captured.out
    assert "--json" in captured.out
