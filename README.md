# systemd-doctor

[![CI](https://github.com/AnnasMazhar/systemd-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/AnnasMazhar/systemd-doctor/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/systemd-doctor.svg)](https://pypi.org/project/systemd-doctor/)
[![Python](https://img.shields.io/pypi/pyversions/systemd-doctor.svg)](https://pypi.org/project/systemd-doctor/)

Fleet health CLI for systemd. Traffic-light status, overdue timers, crash loop detection, security scoring. Zero dependencies.

## Install

```bash
pip install systemd-doctor
```

## Usage

```bash
# Traffic-light summary
$ systemd-doctor status
🟢 Services: 47 active, 0 failed
🟡 Timers: 2 overdue (plutus-scorer, weekly-research)
🟢 Crash loops: none detected

# Overdue timers with details
$ systemd-doctor timers
UNIT                    LAST RUN        OVERDUE BY    STATUS
plutus-scorer.timer     2h ago          1h 30m        🟡 WARNING
weekly-research.timer   8d ago          1d            🔴 CRITICAL
nightly-backup.timer    6h ago          —             🟢 OK

# Security audit
$ systemd-doctor security
🔴 EXPOSED (3 services):
  openclaw-gateway.service    6.5/10
    → Add: ProtectSystem=strict, PrivateTmp=true
  price-daemon.service        7.2/10
    → Add: NoNewPrivileges=true
```

## Features

- **Zero dependencies** — pure Python, uses subprocess to call systemctl
- **Instant overview** — one command shows what needs attention
- **Actionable** — tells you what to fix, not just what's broken
- **Exit codes** — 0=healthy, 1=warnings, 2=critical (use in CI/cron)

## License

MIT
