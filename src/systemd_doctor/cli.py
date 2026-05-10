"""CLI entry point for systemd-doctor."""

import argparse
import sys


def main(argv=None):
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="systemd-doctor",
        description="Fleet health CLI for systemd",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="Traffic-light summary of all units")
    subparsers.add_parser("timers", help="Overdue and failed timers")
    subparsers.add_parser("security", help="Security audit of running services")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
