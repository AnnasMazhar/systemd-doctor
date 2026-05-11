"""CLI entry point for systemd-doctor.

Subcommands:
  status    — Traffic-light summary of all units
  timers    — Overdue and failed timers
  security  — Security audit of running services
"""

import argparse
import sys

from systemd_doctor.security import run_security
from systemd_doctor.status import run_status
from systemd_doctor.timers import run_timers


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="systemd-doctor",
        description="Fleet health CLI for systemd — traffic-light status, "
        "overdue timers, crash loops, security scoring.",
    )
    sub = parser.add_subparsers(dest="command")

    # ---- status ----
    p_status = sub.add_parser("status", help="Traffic-light summary of all units")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")

    # ---- timers ----
    p_timers = sub.add_parser("timers", help="Overdue and failed timers")
    p_timers.add_argument(
        "--warning",
        default="6h",
        help="Overdue threshold for WARNING (default: 6h)",
    )
    p_timers.add_argument(
        "--critical",
        default="24h",
        help="Overdue threshold for CRITICAL (default: 24h)",
    )
    p_timers.add_argument("--json", action="store_true", help="Output as JSON")

    # ---- security ----
    p_sec = sub.add_parser("security", help="Security audit of running services")
    p_sec.add_argument(
        "--min-exposure",
        type=float,
        default=5.0,
        help="Minimum exposure score to flag (default: 5.0)",
    )
    p_sec.add_argument("--json", action="store_true", help="Output as JSON")
    p_sec.add_argument(
        "--fix",
        action="store_true",
        help="Suggest hardening directives and systemctl edit snippets",
    )

    return parser


def main(argv: list) -> int:
    """CLI entry point — parse args and dispatch."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        # --help triggers SystemExit(0); propagate the code cleanly
        return e.code

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "status":
        return int(run_status(json_output=args.json))

    if args.command == "timers":
        return int(
            run_timers(
                warning=args.warning,
                critical=args.critical,
                json_output=args.json,
            )
        )

    if args.command == "security":
        return int(
            run_security(
                min_exposure=args.min_exposure,
                json_output=args.json,
                show_fix=args.fix,
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
