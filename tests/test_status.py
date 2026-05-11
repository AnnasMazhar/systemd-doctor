"""Tests for status.py — traffic-light summary logic."""

import json
from unittest import mock

from systemd_doctor import status


def _parse_units(text: str) -> list:
    """Parse list-units fixture text into dicts."""
    from systemd_doctor.systemctl import list_units

    with mock.patch("systemd_doctor.systemctl._run", return_value=text):
        return list_units()


def _parse_timers(text: str) -> list:
    from systemd_doctor.systemctl import list_timers

    with mock.patch("systemd_doctor.systemctl._run", return_value=text):
        return list_timers()


def test_all_healthy(mocker, fixtures_dir):
    """All healthy → exit 0, all green."""
    import datetime

    healthy_units = (fixtures_dir / "list_units_healthy.txt").read_text()
    timers_ok = (fixtures_dir / "list_timers_ok.txt").read_text()

    mock_now = datetime.datetime(2025, 1, 14, 21, 0, 0)
    mocker.patch("systemd_doctor.status._now", return_value=mock_now)
    mocker.patch("systemd_doctor.status.list_units", return_value=_parse_units(healthy_units))
    mocker.patch("systemd_doctor.status.list_timers", return_value=_parse_timers(timers_ok))
    mocker.patch("systemd_doctor.status.get_unit_restarts", return_value=(0, None))

    exit_code = status.run_status(json_output=False)
    assert exit_code == 0


def test_failed_services(mocker, fixtures_dir):
    """Failed services → exit 2, red."""
    failed_units = (fixtures_dir / "list_units_failed.txt").read_text()
    timers_ok = (fixtures_dir / "list_timers_ok.txt").read_text()

    mocker.patch("systemd_doctor.status.list_units", return_value=_parse_units(failed_units))
    mocker.patch("systemd_doctor.status.list_timers", return_value=_parse_timers(timers_ok))
    mocker.patch("systemd_doctor.status.get_unit_restarts", return_value=(0, None))

    exit_code = status.run_status(json_output=False)
    assert exit_code == 2


def test_overdue_timers(mocker, fixtures_dir):
    """Overdue timers (no failed services) → exit 1, yellow."""
    healthy_units = (fixtures_dir / "list_units_healthy.txt").read_text()
    timers_overdue = (fixtures_dir / "list_timers_overdue.txt").read_text()

    mocker.patch("systemd_doctor.status.list_units", return_value=_parse_units(healthy_units))
    mocker.patch("systemd_doctor.status.list_timers", return_value=_parse_timers(timers_overdue))
    mocker.patch("systemd_doctor.status.get_unit_restarts", return_value=(0, None))

    exit_code = status.run_status(json_output=False)
    assert exit_code == 1


def test_crash_loop(mocker, fixtures_dir):
    """Crash loop detected → exit 2, red."""
    import datetime

    healthy_units = (fixtures_dir / "list_units_healthy.txt").read_text()
    timers_ok = (fixtures_dir / "list_timers_ok.txt").read_text()

    mocker.patch("systemd_doctor.status.list_units", return_value=_parse_units(healthy_units))
    mocker.patch("systemd_doctor.status.list_timers", return_value=_parse_timers(timers_ok))
    mocker.patch(
        "systemd_doctor.status.get_unit_restarts",
        return_value=(5, datetime.datetime.now()),
    )

    exit_code = status.run_status(json_output=False)
    assert exit_code == 2


def test_json_output(mocker, fixtures_dir):
    """JSON output contains all expected keys."""
    import datetime

    healthy_units = (fixtures_dir / "list_units_healthy.txt").read_text()
    timers_ok = (fixtures_dir / "list_timers_ok.txt").read_text()

    mock_now = datetime.datetime(2025, 1, 14, 21, 0, 0)
    mocker.patch("systemd_doctor.status._now", return_value=mock_now)
    mocker.patch("systemd_doctor.status.list_units", return_value=_parse_units(healthy_units))
    mocker.patch("systemd_doctor.status.list_timers", return_value=_parse_timers(timers_ok))
    mocker.patch("systemd_doctor.status.get_unit_restarts", return_value=(0, None))

    exit_code = status.run_status(json_output=True)
    assert exit_code == 0


def test_json_output_with_failures(mocker, fixtures_dir):
    """JSON with failures has correct structure."""
    import io

    failed_units = (fixtures_dir / "list_units_failed.txt").read_text()
    timers_ok = (fixtures_dir / "list_timers_ok.txt").read_text()

    mocker.patch("systemd_doctor.status.list_units", return_value=_parse_units(failed_units))
    mocker.patch("systemd_doctor.status.list_timers", return_value=_parse_timers(timers_ok))
    mocker.patch("systemd_doctor.status.get_unit_restarts", return_value=(0, None))

    captured = io.StringIO()
    with mock.patch("sys.stdout", captured):
        exit_code = status.run_status(json_output=True)

    assert exit_code == 2
    data = json.loads(captured.getvalue())
    assert "services" in data
    assert "timers" in data
    assert "crash_loops" in data
    assert "overall" in data
    assert data["overall"] == "critical"
    assert len(data["services"]["failed_units"]) == 2
