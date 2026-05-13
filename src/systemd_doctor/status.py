"""Status subcommand — traffic-light summary of the entire systemd fleet."""

import datetime
import json
import sys
from typing import Any, Dict, List

from systemd_doctor.formatting import color, traffic_light
from systemd_doctor.systemctl import get_unit_restarts, list_timers, list_units


def _now() -> datetime.datetime:
    """Return the current time.

    Mock this point in tests to control time-based logic.
    """
    return datetime.datetime.now()


def _detect_crash_loops(
    units: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Check units for crash loops (>3 restarts in last 5 min).

    Returns:
        List of crash-loop dicts with keys ``unit``, ``restarts``.
    """
    now = _now()
    crash_loops: List[Dict[str, Any]] = []

    for u in units:
        unit_name = u.get("unit", "")
        if not unit_name.endswith(".service"):
            continue
        try:
            restarts, last_active = get_unit_restarts(unit_name)
        except RuntimeError:
            continue

        if restarts > 3 and last_active is not None:
            age = (now - last_active).total_seconds()
            if age <= 300:  # 5 minutes
                crash_loops.append({"unit": unit_name, "restarts": restarts})

    return crash_loops


def _check_overdue_timers(
    timers: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Identify overdue timers (next is n/a or last trigger > 2x interval).

    A timer is considered "overdue" when:
    - Its NEXT field is ``n/a`` (dead timer), OR
    - The last trigger was more than 2× the expected interval ago.

    Returns:
        List of overdue dicts with keys ``unit``, ``activates``,
        ``overdue_seconds`` (or ``None`` for dead timers), ``dead`` bool.
    """
    now = _now()
    overdue: List[Dict[str, Any]] = []

    for t in timers:
        if t["next"] is None and t["last"] is not None:
            # Dead timer — no next trigger scheduled
            overdue.append(
                {
                    "unit": t["unit"],
                    "activates": t["activates"],
                    "overdue_seconds": None,
                    "dead": True,
                }
            )
        elif t["last"] is not None and t["next"] is not None:
            # Check if last trigger was more than 2x interval ago
            interval = (t["next"] - t["last"]).total_seconds()
            if interval <= 0:
                continue
            age = (now - t["last"]).total_seconds()
            if age > 2 * interval:
                overdue.append(
                    {
                        "unit": t["unit"],
                        "activates": t["activates"],
                        "overdue_seconds": int(age - interval),
                        "dead": False,
                    }
                )

    return overdue


def run_status(json_output: bool = False) -> int:
    """Run the ``status`` subcommand.

    Args:
        json_output: When ``True``, emit JSON instead of human-readable text.

    Returns:
        Exit code: 0 (healthy), 1 (warnings), 2 (critical).
    """
    try:
        units = list_units()
        all_timers = list_timers()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    # --- Gather data ---

    failed = [u for u in units if u["active"] == "failed"]
    overdue_timers = _check_overdue_timers(all_timers)
    crash_loops = _detect_crash_loops(units)

    # --- Determine health ---

    has_failed = len(failed) > 0
    has_crash_loops = len(crash_loops) > 0
    has_overdue = len(overdue_timers) > 0

    if has_failed or has_crash_loops:
        overall_level = "critical"
    elif has_overdue:
        overall_level = "warning"
    else:
        overall_level = "ok"

    # --- Output ---

    healthy_count = len(units)

    if json_output:
        data = {
            "services": {
                "total": healthy_count,
                "failed": len(failed),
                "failed_units": [u["unit"] for u in failed],
            },
            "timers": {
                "total": len(all_timers),
                "overdue": len(overdue_timers),
                "overdue_units": [t["unit"] for t in overdue_timers],
            },
            "crash_loops": {
                "total": len(crash_loops),
                "loops": crash_loops,
            },
            "overall": overall_level,
        }
        print(json.dumps(data, indent=2, default=str))
    else:
        # Services
        failed_count = len(failed)
        services_level = "critical" if failed_count else "ok"
        failed_names = ", ".join(u["unit"] for u in failed)
        svc_msg = f"Services: {healthy_count} total"
        if failed_count:
            svc_msg += f", {color(str(failed_count), 'red')} failed ({failed_names})"
        else:
            svc_msg += ", 0 failed"
        print(f"{traffic_light(services_level)} {svc_msg}")

        # Timers
        if has_overdue:
            timer_names = ", ".join(t["unit"] for t in overdue_timers)
            print(
                f"{traffic_light('warning')} Timers: {len(overdue_timers)} overdue ({timer_names})"
            )
        else:
            print(f"{traffic_light('ok')} Timers: {len(all_timers)} timers, none overdue")

        # Crash loops
        if has_crash_loops:
            loop_msgs = [f"{cl['unit']} ({cl['restarts']} restarts)" for cl in crash_loops]
            print(
                f"{traffic_light('critical')} Crash loops: {len(crash_loops)} detected "
                f"({', '.join(loop_msgs)})"
            )
        else:
            print(f"{traffic_light('ok')} Crash loops: none detected")

    # --- Exit code ---

    if overall_level == "critical":
        return 2
    elif overall_level == "warning":
        return 1
    return 0
