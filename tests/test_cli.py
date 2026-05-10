"""Verify CLI entry point works."""

from systemd_doctor.cli import main


def test_no_args_shows_help(capsys):
    """No args should print help and exit 0."""
    result = main([])
    assert result == 0
    captured = capsys.readouterr()
    assert "systemd-doctor" in captured.out


def test_status_subcommand():
    """Status subcommand should parse without error."""
    result = main(["status"])
    assert result == 0
