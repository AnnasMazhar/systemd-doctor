"""Colors, tables, duration parsing — zero-dependency formatting utilities."""

import math
import os
import re
from typing import List, Optional


def traffic_light(level: str) -> str:
    """Return emoji for traffic-light level.

    Args:
        level: One of "ok", "warning", "critical".

    Returns:
        Green/yellow/red circle emoji.
    """
    return {"ok": "\U0001f7e2", "warning": "\U0001f7e1", "critical": "\U0001f534"}.get(
        level, "\u26ab"
    )


def color(text: str, c: str) -> str:
    """Wrap *text* in ANSI color codes.

    Respects the ``NO_COLOR`` environment variable (https://no-color.org/).
    Unrecognised colours are returned as-is.

    Args:
        text: The string to colour.
        c: Colour name — one of ``red``, ``green``, ``yellow``, ``bold``.

    Returns:
        ANSI-wrapped string, or plain text if ``NO_COLOR`` is set.
    """
    if os.environ.get("NO_COLOR"):
        return text

    codes = {"red": "31", "green": "32", "yellow": "33", "bold": "1"}
    code = codes.get(c)
    if code is None:
        return text
    return f"\033[{code}m{text}\033[0m"


def table(
    headers: List[str],
    rows: List[List[str]],
    alignments: Optional[List[str]] = None,
) -> str:
    """Return an aligned, space-padded table string.

    Args:
        headers: Column header strings.
        rows: List of rows, each a list of cell strings.  All rows and the
            header must have the same number of columns.
        alignments: Optional list of ``"l"`` / ``"r"`` per column (default all
            ``"l"``).

    Returns:
        Multi-line string with columns separated by two spaces.
    """
    if not headers and not rows:
        return ""

    ncols = len(headers) if headers else len(rows[0]) if rows else 0
    if alignments is None:
        alignments = ["l"] * ncols

    col_widths = [len(h) for h in headers] if headers else [0] * ncols
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    lines: List[str] = []

    if headers:
        parts: List[str] = []
        for i, h in enumerate(headers):
            if alignments[i] == "r":
                parts.append(h.rjust(col_widths[i]))
            else:
                parts.append(h.ljust(col_widths[i]))
        lines.append("  ".join(parts))

        lines.append("  ".join("-" * w for w in col_widths))

    for row in rows:
        parts = []
        for i, cell in enumerate(row):
            if alignments[i] == "r":
                parts.append(cell.rjust(col_widths[i]))
            else:
                parts.append(cell.ljust(col_widths[i]))
        lines.append("  ".join(parts))

    return "\n".join(lines)


def duration_human(seconds: float) -> str:
    """Format a duration in human-readable form.

    Args:
        seconds: Duration in seconds (floored to int internally).

    Returns:
        Compact string like ``"1h 2m"``, ``"3d"``, ``"0s"``.
    """
    secs = max(0, int(math.floor(seconds)))

    if secs == 0:
        return "0s"

    days = secs // 86400
    hours = (secs % 86400) // 3600
    minutes = (secs % 3600) // 60

    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")

    # Only show seconds when nothing larger
    if not parts:
        return f"{secs}s"

    return " ".join(parts)


_PARSE_DURATION_RE = re.compile(r"^(\d+)([smhd])$")


def parse_duration(s: str) -> float:
    """Parse a human duration string into seconds.

    Args:
        s: String like ``"30m"``, ``"6h"``, ``"1d"``, ``"7d"``, ``"90s"``.

    Returns:
        Equivalent number of seconds.
    """
    m = _PARSE_DURATION_RE.match(s.strip())
    if not m:
        raise ValueError(f"cannot parse duration: {s!r}")

    value = int(m.group(1))
    unit = m.group(2)

    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return float(value * multipliers[unit])
