"""All subprocess interaction with systemctl/systemd-analyze.

Every function in this module shells out and parses output.  Tests should
mock this module so they never need root or a running systemd.
"""

import datetime
import subprocess
from typing import Any, Dict, List, Optional, Tuple


def _run(cmd: List[str]) -> str:
    """Run *cmd* and return decoded stdout.

    Raises ``RuntimeError`` on non-zero exit so callers can catch and
    produce graceful error messages.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"required command not found: {exc.filename}"
        ) from exc
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"command timed out: {' '.join(cmd)}")

    if result.returncode != 0:
        raise RuntimeError(
            f"{' '.join(cmd)} exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# list-units
# ---------------------------------------------------------------------------

def list_units(state: Optional[str] = None) -> List[Dict[str, str]]:
    """Return all systemd units matching an optional *state*.

    Params:
        state: Optional state filter (e.g. ``"failed"``).  When ``None``,
            returns all units.

    Returns:
        List of dicts with keys ``unit``, ``load``, ``active``, ``sub``,
        ``description``.
    """
    cmd: List[str] = [
        "systemctl", "list-units", "--all", "--no-legend", "--plain",
    ]
    if state is not None:
        cmd.extend(["--state", state])

    raw = _run(cmd)
    units: List[Dict[str, str]] = []

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split(None, 4)
        if len(parts) < 4:
            continue

        unit = parts[0]
        load = parts[1]
        active = parts[2]
        sub = parts[3]
        description = parts[4] if len(parts) > 4 else ""
        units.append(
            {"unit": unit, "load": load, "active": active, "sub": sub, "description": description}
        )

    return units


# ---------------------------------------------------------------------------
# list-timers
# ---------------------------------------------------------------------------

def list_timers() -> List[Dict[str, Any]]:
    """Return all systemd timers.

    Handles the fixed-width-ish output where NEXT/LAST are 5-token date
    timestamps ``(Mon YYYY-MM-DD HH:MM:SS TZ)`` and LEFT/PASSED have
    variable token counts delimited by the keywords ``left`` and ``ago``.

    Returns:
        List of dicts with keys ``next`` (datetime or ``None``), ``left``,
        ``last`` (datetime or ``None``), ``passed``, ``unit``, ``activates``.
    """
    raw = _run(["systemctl", "list-timers", "--all", "--no-legend"])
    timers: List[Dict[str, Any]] = []

    for line in raw.splitlines():
        timer = _parse_single_timer_line(line.strip())
        if timer is not None:
            timers.append(timer)

    return timers


def _parse_single_timer_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single line of ``systemctl list-timers --no-legend`` output.

    Field layout (variable token counts):

        NEXT (1 or 5)  LEFT (1+)  LAST (1 or 5)  PASSED (1+)  UNIT  ACTIVATES

    * NEXT / LAST: ``n/a`` (1 token) or ``Day YYYY-MM-DD HH:MM:SS TZ``
      (5 tokens).
    * LEFT contains the word ``left`` (e.g. ``"2h 30min left"``).
    * PASSED contains the word ``ago`` (e.g. ``"2 weeks ago"``).
    """
    tokens = line.split()
    n = len(tokens)
    if n < 6:
        return None

    idx = 0

    # --- NEXT ---
    if tokens[idx] == "n/a":
        next_dt: Optional[datetime.datetime] = None
        idx += 1
    else:
        if idx + 4 > n:
            return None
        next_dt = _parse_datetime(" ".join(tokens[idx : idx + 4]))
        idx += 4

    # --- LEFT (variable tokens ending with "left") ---
    left_parts: List[str] = []
    while idx < n:
        if tokens[idx] == "n/a" and not left_parts:
            left_parts.append("n/a")
            idx += 1
            break
        if tokens[idx] == "left":
            left_parts.append("left")
            idx += 1
            break
        left_parts.append(tokens[idx])
        idx += 1
    else:
        return None
    if not left_parts:
        return None
    left_str = " ".join(left_parts)

    # --- LAST ---
    if idx >= n:
        return None
    if tokens[idx] == "n/a":
        last_dt: Optional[datetime.datetime] = None
        idx += 1
    else:
        if idx + 4 > n:
            return None
        last_dt = _parse_datetime(" ".join(tokens[idx : idx + 4]))
        idx += 4

    # --- PASSED (variable tokens ending with "ago") ---
    passed_parts: List[str] = []
    while idx < n:
        if tokens[idx] == "n/a" and not passed_parts:
            passed_parts.append("n/a")
            idx += 1
            break
        if tokens[idx] == "ago":
            passed_parts.append("ago")
            idx += 1
            break
        passed_parts.append(tokens[idx])
        idx += 1
    else:
        return None
    passed_str = " ".join(passed_parts)

    # --- UNIT and ACTIVATES ---
    if idx >= n:
        return None
    unit = tokens[idx]
    idx += 1
    activates = " ".join(tokens[idx:]) if idx < n else ""

    return {
        "next": next_dt,
        "left": left_str,
        "last": last_dt,
        "passed": passed_str,
        "unit": unit,
        "activates": activates,
    }


# ---------------------------------------------------------------------------
# analyze security
# ---------------------------------------------------------------------------

def analyze_security() -> List[Dict[str, Any]]:
    """Run ``systemd-analyze security`` and parse scores.

    Returns:
        List of dicts with keys ``unit``, ``exposure`` (float), ``predicate``
        (``"SAFE"``, ``"OK"``, ``"EXPOSED"``, ``"UNSAFE"``).
    """
    raw = _run(["systemd-analyze", "security", "--no-pager"])
    units: List[Dict[str, Any]] = []

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        # Output format: "  UNIT_NAME EXPOSURE_LEVEL (PREDICATE)"
        # e.g. "  sshd.service 6.5 EXPOSED"
        parts = line.rsplit(None, 2)
        if len(parts) < 3:
            continue

        unit = parts[0]
        try:
            exposure = float(parts[1])
        except ValueError:
            continue
        predicate = parts[2].strip("()") if parts[2].startswith("(") else parts[2]

        units.append({"unit": unit, "exposure": exposure, "predicate": predicate})

    return units


# ---------------------------------------------------------------------------
# Unit restart count
# ---------------------------------------------------------------------------

def get_unit_restarts(unit: str) -> Tuple[int, Optional[datetime.datetime]]:
    """Return restart count and last active timestamp for *unit*.

    Args:
        unit: Full unit name (e.g. ``"sshd.service"``).

    Returns:
        ``(nrestarts, last_active_timestamp_or_none)``.
    """
    raw = _run(
        [
            "systemctl",
            "show",
            "-p",
            "NRestarts",
            "-p",
            "ActiveEnterTimestamp",
            unit,
        ]
    )
    nrestarts = 0
    last_active: Optional[datetime.datetime] = None

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("NRestarts="):
            val = line.split("=", 1)[1].strip()
            nrestarts = int(val) if val else 0
        elif line.startswith("ActiveEnterTimestamp="):
            val = line.split("=", 1)[1].strip()
            if val and val.lower() not in ("n/a", ""):
                last_active = _parse_datetime(val)

    return nrestarts, last_active


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_datetime(s: str) -> Optional[datetime.datetime]:
    """Try to parse a systemd-formatted datetime string.

    Handles formats like::

        Mon 2024-01-15 03:00:00 UTC
        2024-01-15 03:00:00

    Returns ``None`` when parsing fails.
    """
    # Strip leading day-of-week
    cleaned = s.strip()
    cleaned = cleaned.split(" ", 1)[-1] if " " in cleaned else cleaned

    # Try with timezone
    for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(cleaned, fmt)
            return dt
        except ValueError:
            continue

    return None
