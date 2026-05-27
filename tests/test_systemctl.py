"""Tests for systemctl.py — mock subprocess output parsing."""

import datetime

from systemd_doctor.systemctl import get_unit_restarts, list_timers, list_units


def test_list_units_parses(mocker, fixtures_dir):
    """list_units returns correct dict fields from mock output."""
    mocker.patch(
        "systemd_doctor.systemctl._run",
        return_value=(fixtures_dir / "list_units_healthy.txt").read_text(),
    )
    units = list_units()
    assert len(units) == 8
    for u in units:
        assert "unit" in u
        assert "load" in u
        assert "active" in u
        assert "sub" in u
        assert "description" in u

    sshd = [u for u in units if u["unit"] == "sshd.service"]
    assert len(sshd) == 1
    assert sshd[0]["active"] == "active"
    assert sshd[0]["sub"] == "running"


def test_list_units_empty(mocker):
    """Empty output returns empty list."""
    mocker.patch("systemd_doctor.systemctl._run", return_value="")
    assert list_units() == []


def test_list_units_failed_state(mocker, fixtures_dir):
    """list_units with state='failed' filters correctly."""
    mocker.patch(
        "systemd_doctor.systemctl._run",
        return_value=(fixtures_dir / "list_units_failed.txt").read_text(),
    )
    # The fixture has both healthy and failed units; list_units doesn't filter
    # on active state itself — it just parses whatever systemctl returns
    units = list_units()
    failed = [u for u in units if u["active"] == "failed"]
    assert len(failed) == 2
    assert failed[0]["unit"] == "failed-daemon.service"


def test_list_timers_parses_dates(mocker, fixtures_dir):
    """list_timers correctly parses datetime fields."""
    mocker.patch(
        "systemd_doctor.systemctl._run",
        return_value=(fixtures_dir / "list_timers_ok.txt").read_text(),
    )
    timers = list_timers()
    assert len(timers) == 3
    for t in timers:
        assert t["next"] is not None
        assert t["last"] is not None
        assert "unit" in t
        assert "activates" in t

    # Check specific timer
    nightly = [t for t in timers if t["unit"] == "nightly-backup.timer"]
    assert len(nightly) == 1
    assert nightly[0]["activates"] == "backup.service"


def test_list_timers_na_is_none(mocker, fixtures_dir):
    """n/a values for next/last are parsed as None."""
    mocker.patch(
        "systemd_doctor.systemctl._run",
        return_value=(fixtures_dir / "list_timers_overdue.txt").read_text(),
    )
    timers = list_timers()
    # plutus-scorer and weekly-research have n/a next
    na_timers = [t for t in timers if t["next"] is None]
    assert len(na_timers) == 2
    for t in na_timers:
        assert t["last"] is not None


def test_security_parses_scores(mocker, fixtures_dir):
    """analyze_security extracts float exposure scores."""
    mocker.patch(
        "systemd_doctor.systemctl._run",
        return_value=(fixtures_dir / "security_output.txt").read_text(),
    )
    from systemd_doctor.systemctl import analyze_security

    results = analyze_security()
    assert len(results) == 6

    nginx = [r for r in results if r["unit"] == "nginx.service"]
    assert len(nginx) == 1
    assert nginx[0]["exposure"] == 6.5
    assert nginx[0]["predicate"] == "EXPOSED"

    ok_services = [r for r in results if r["predicate"] == "OK"]
    assert len(ok_services) == 3


def test_get_unit_restarts(mocker, fixtures_dir):
    """get_unit_restarts parses NRestarts and ActiveEnterTimestamp."""
    mocker.patch(
        "systemd_doctor.systemctl._run",
        return_value=(fixtures_dir / "unit_restarts.txt").read_text(),
    )
    nrestarts, last_active = get_unit_restarts("nginx.service")
    assert nrestarts == 3
    assert last_active == datetime.datetime(2025, 1, 15, 3, 0, 0)


def test_get_unit_restarts_empty(mocker):
    """get_unit_restarts handles empty output."""
    mocker.patch("systemd_doctor.systemctl._run", return_value="")
    nrestarts, last_active = get_unit_restarts("missing.service")
    assert nrestarts == 0
    assert last_active is None
