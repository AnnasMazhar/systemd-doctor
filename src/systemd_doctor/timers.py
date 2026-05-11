"""Timers subcommand — detect overdue and dead systemd timers."""

import json
from typing import Any, Dict, List, Optional

from systemd_doctor.formatting import duration_human, table, traffic_light
from systemd_doctor.systemctl import list_timers


def _classify_timer(
    timer: Dict[str, Any],
    warning_seconds: float,
    critical_seconds: float,
) -> Optional[Dict[str, Any]]:
    """Classify a single timer's health level.

    Args:
        timer: Timer dict from ``list_timers()``.
        warning_seconds: Threshold above which a timer is WARNING.
        critical_seconds: Threshold above which a timer is CRITICAL.

    Returns:
        ``None`` if the timer is healthy, or a dict with keys ``unit``,
        ``activates``, ``overdue_by`` (int seconds or ``None`` for dead),
        ``status`` (``"WARNING"`` / ``"CRITICAL"``), ``dead`` bool.
    """
    if timer["next"] is None:
        return {
            "unit": timer["unit"],
            "activates": timer["activates"],
            "overdue_by": None,
            "status": "CRITICAL",
            "dead": True,
        }

    if timer["last"] is None:
        return None  # No data to judge

    now = _mock_now()  # Allows test injection via monkeypatch
    last_ts = timer["last"].timestamp()
    interval = (timer["next"] - timer["last"]).total_seconds()
    if interval <= 0:
        return None

    age = now - last_ts
    overdue = age - interval

    if overdue > critical_seconds:
        return {
            "unit": timer["unit"],
            "activates": timer["activates"],
            "overdue_by": int(overdue),
            "status": "CRITICAL",
            "dead": False,
        }
    elif overdue > warning_seconds:
        return {
            "unit": timer["unit"],
            "activates": timer["activates"],
            "overdue_by": int(overdue),
            "status": "WARNING",
            "dead": False,
        }

    return None


def _mock_now() -> float:
    """Return current time as UNIX seconds.

    Override in tests via ``monkeypatch``.
    """
    import time

    return time.time()


def run_timers(
    warning: str = "6h",
    critical: str = "24h",
    json_output: bool = False,
) -> int:
    """Run the ``timers`` subcommand.

    Args:
        warning: Human duration string for WARNING threshold.
        critical: Human duration string for CRITICAL threshold.
        json_output: When ``True``, emit JSON.

    Returns:
        Exit code: 0 (all OK), 1 (warnings), 2 (critical).
    """
    from systemd_doctor.formatting import parse_duration

    warning_secs = parse_duration(warning)
    critical_secs = parse_duration(critical)

    try:
        timers = list_timers()
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 2

    classified: List[Dict[str, Any]] = []
    for t in timers:
        result = _classify_timer(t, warning_secs, critical_secs)
        if result is not None:
            classified.append(result)

    has_critical = any(c["status"] == "CRITICAL" for c in classified)
    has_warning = any(c["status"] == "WARNING" for c in classified)

    if json_output:
        print(json.dumps(classified, indent=2))
    else:
        if not classified:
            print(f"{traffic_light('ok')} All {len(timers)} timers are on schedule")
            return 0

        headers = ["UNIT", "ACTIVATES", "OVERDUE BY", "STATUS"]
        rows: List[List[str]] = []
        for c in classified:
            overdue_str = (
                "DEAD"
                if c["dead"]
                else duration_human(float(c["overdue_by"])) if c["overdue_by"] is not None else "—"
            )
            level = "critical" if c["status"] == "CRITICAL" else "warning"
            status_str = f"{traffic_light(level)} {c['status']}"
            rows.append([c["unit"], c["activates"], overdue_str, status_str])

        print(table(headers, rows))

    if has_critical:
        return 2
    elif has_warning:
        return 1
    return 0
