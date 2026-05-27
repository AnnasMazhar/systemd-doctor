"""Security subcommand — audit systemd service hardening."""

import json
import sys
from typing import Any, Dict, List

from systemd_doctor.formatting import color, table, traffic_light
from systemd_doctor.systemctl import analyze_security

_HARDENING_SUGGESTIONS: List[str] = [
    "ProtectSystem=strict",
    "NoNewPrivileges=true",
    "PrivateTmp=true",
    "ProtectHome=read-only",
]


def _suggest_hardening(unit: str) -> List[str]:
    """Return hardening directives missing for *unit*.

    Currently returns the full suggestion list for any exposed unit.
    In a production implementation this would inspect the unit's current
    drop-ins and only suggest what's missing.

    Args:
        unit: Unit name (e.g. ``"sshd.service"``).

    Returns:
        List of suggested hardening directives.
    """
    return list(_HARDENING_SUGGESTIONS)


def _fix_snippet(unit: str, directives: List[str]) -> str:
    """Generate a ``systemctl edit`` drop-in snippet for *unit*.

    Args:
        unit: Unit name.
        directives: Hardening directives to add.

    Returns:
        Shell command string that the user can copy-paste.
    """
    lines: List[str] = [
        f"# systemctl edit --drop-in=hardening.conf {unit}",
        "[Service]",
    ]
    for d in directives:
        lines.append(d)
    lines.append("")  # trailing newline
    return "\n".join(lines)


def run_security(
    min_exposure: float = 5.0,
    json_output: bool = False,
    show_fix: bool = False,
) -> int:
    """Run the ``security`` subcommand.

    Args:
        min_exposure: Minimum exposure score to flag (default 5.0).
        json_output: When ``True``, emit JSON.
        show_fix: When ``True``, emit ``systemctl edit`` commands.

    Returns:
        Exit code: 0 (all safe), 1 (exposed units found).
    """
    try:
        results = analyze_security()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    exposed = [r for r in results if r["exposure"] >= min_exposure]

    if not exposed:
        if not json_output:
            print(f"{traffic_light('ok')} All services within safe exposure limits")
        return 0

    if json_output:
        data: List[Dict[str, Any]] = []
        for r in exposed:
            entry: Dict[str, Any] = {
                "unit": r["unit"],
                "exposure": r["exposure"],
                "predicate": r["predicate"],
            }
            if show_fix:
                entry["suggestions"] = _suggest_hardening(r["unit"])
                entry["fix_command"] = _fix_snippet(r["unit"], _suggest_hardening(r["unit"]))
            data.append(entry)
        print(json.dumps(data, indent=2))
    else:
        print(
            f"{traffic_light('critical')} EXPOSED ({len(exposed)} services with "
            f"score >= {min_exposure:.1f}):"
        )

        headers = ["UNIT", "EXPOSURE", "PREDICATE"]
        rows: List[List[str]] = []
        for r in exposed:
            exp_str = f"{r['exposure']:.1f}/10"
            level = "critical" if r["exposure"] >= 8 else "yellow"
            rows.append([r["unit"], color(exp_str, level), r["predicate"]])

        print(table(headers, rows))

        if show_fix:
            print()
            for r in exposed:
                suggestions = _suggest_hardening(r["unit"])
                print(f"  {r['unit']}:")
                for s in suggestions:
                    print(f"    → Add: {s}")
                print(f"    {_fix_snippet(r['unit'], suggestions).split(chr(10))[0]}")
                print()

    return 1  # exposed = warning
