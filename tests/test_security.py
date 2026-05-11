"""Tests for security.py — security audit logic."""

import json
from unittest import mock

from systemd_doctor.security import run_security


def _parse_security(text: str) -> list:
    """Parse security fixture text."""
    from systemd_doctor.systemctl import analyze_security

    with mock.patch("systemd_doctor.systemctl._run", return_value=text):
        return analyze_security()


def test_all_secure(mocker, fixtures_dir):
    """No exposed units → exit 0, no output."""
    security_data = (fixtures_dir / "security_output.txt").read_text()

    mocker.patch(
        "systemd_doctor.security.analyze_security",
        return_value=_parse_security(security_data),
    )

    exit_code = run_security(min_exposure=10.0, json_output=False)
    assert exit_code == 0


def test_exposed_shown(mocker, fixtures_dir):
    """Units above threshold are listed."""
    security_data = (fixtures_dir / "security_output.txt").read_text()

    mocker.patch(
        "systemd_doctor.security.analyze_security",
        return_value=_parse_security(security_data),
    )

    exit_code = run_security(min_exposure=5.0, json_output=False)
    assert exit_code == 1  # exposed units found


def test_fix_suggestions(mocker, fixtures_dir):
    """Correct directives suggested for exposed units."""
    security_data = (fixtures_dir / "security_output.txt").read_text()

    mocker.patch(
        "systemd_doctor.security.analyze_security",
        return_value=_parse_security(security_data),
    )
    from systemd_doctor.security import _suggest_hardening

    suggestions = _suggest_hardening("nginx.service")
    assert "ProtectSystem=strict" in suggestions
    assert "NoNewPrivileges=true" in suggestions
    assert "PrivateTmp=true" in suggestions
    assert "ProtectHome=read-only" in suggestions


def test_min_exposure_filter(mocker, fixtures_dir):
    """--min-exposure 7.0 filters to only high-score units."""
    security_data = (fixtures_dir / "security_output.txt").read_text()

    mocker.patch(
        "systemd_doctor.security.analyze_security",
        return_value=_parse_security(security_data),
    )

    exit_code = run_security(min_exposure=7.0, json_output=False)
    assert exit_code == 1  # postgresql 7.1 and broken-gateway 9.8 still exposed

    exit_code = run_security(min_exposure=10.0, json_output=False)
    assert exit_code == 0  # nothing >= 10


def test_fix_flag(mocker, fixtures_dir):
    """--fix generates override snippets in JSON output."""
    security_data = (fixtures_dir / "security_output.txt").read_text()

    mocker.patch(
        "systemd_doctor.security.analyze_security",
        return_value=_parse_security(security_data),
    )

    import io

    captured = io.StringIO()
    with mock.patch("sys.stdout", captured):
        exit_code = run_security(min_exposure=5.0, json_output=True, show_fix=True)

    assert exit_code == 1
    data = json.loads(captured.getvalue())
    assert len(data) >= 1
    for entry in data:
        assert "suggestions" in entry
        assert "fix_command" in entry
        assert len(entry["suggestions"]) > 0


def test_fix_snippet_format(mocker, fixtures_dir):
    """Fix snippet has expected structure."""
    from systemd_doctor.security import _fix_snippet

    snippet = _fix_snippet("nginx.service", ["ProtectSystem=strict"])
    assert "systemctl edit --drop-in=hardening.conf nginx.service" in snippet
    assert "[Service]" in snippet
    assert "ProtectSystem=strict" in snippet
