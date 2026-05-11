# systemd-doctor

[![CI](https://github.com/AnnasMazhar/systemd-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/AnnasMazhar/systemd-doctor/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/systemd-doctor.svg)](https://pypi.org/project/systemd-doctor/)
[![Python](https://img.shields.io/pypi/pyversions/systemd-doctor.svg)](https://pypi.org/project/systemd-doctor/)

One command to know if your systemd fleet is healthy. Failed services, overdue timers, crash loops, security exposure — with fix suggestions.

## Install

```bash
pip install systemd-doctor
```

## Commands

### `systemd-doctor status`

Traffic-light summary of your entire fleet:

```
$ systemd-doctor status
🟢 Services: 47 total, 0 failed
🟡 Timers: 2 overdue
🟢 Crash loops: none detected
```

Exit codes: `0` = healthy, `1` = warnings, `2` = critical. Use in cron or CI.

### `systemd-doctor timers`

Find overdue and dead timers:

```
$ systemd-doctor timers
UNIT                      LAST RUN     OVERDUE BY   STATUS
plutus-scorer.timer       2h ago       1h 30m       🟡 WARNING
weekly-research.timer     8d ago       7d           🔴 CRITICAL
nightly-backup.timer      6h ago       —            🟢 OK
```

Custom thresholds:

```bash
systemd-doctor timers --warning 30m --critical 2h
```

### `systemd-doctor security`

Audit service sandboxing. Shows units with high exposure scores and suggests fixes:

```
$ systemd-doctor security
🔴 EXPOSED (3 services):
  gateway.service           6.5/10
    → ProtectSystem=strict, PrivateTmp=true
  price-daemon.service      7.2/10
    → NoNewPrivileges=true, ProtectHome=read-only

$ systemd-doctor security --fix
# gateway.service
systemctl edit gateway.service --drop-in=hardening.conf
# Add:
[Service]
ProtectSystem=strict
PrivateTmp=true
NoNewPrivileges=true
```

Filter by severity:

```bash
systemd-doctor security --min-exposure 7.0
```

## All Options

```
systemd-doctor status [--json]
systemd-doctor timers [--warning DURATION] [--critical DURATION] [--json]
systemd-doctor security [--min-exposure FLOAT] [--json] [--fix]
```

Durations accept: `30m`, `6h`, `1d`, `7d`

## JSON Output

Every subcommand supports `--json` for scripting:

```bash
$ systemd-doctor status --json
{"services": {"total": 47, "failed": 0}, "timers": {"total": 12, "overdue": 2}, "crash_loops": [], "overall": "warning"}

$ systemd-doctor timers --json | jq '.[] | select(.status == "critical")'
```

## Design

- **Zero runtime dependencies** — stdlib only (subprocess, argparse, datetime, json)
- **Single mock point** — all `systemctl` calls go through one module, making it fully testable without systemd
- **Respects `NO_COLOR`** — set `NO_COLOR=1` to disable ANSI output
- **53 tests, 82% coverage**

## Use Cases

**Cron alerting** (no Prometheus needed):
```bash
# /etc/cron.d/systemd-check
*/5 * * * * root systemd-doctor status --json | jq -e '.overall == "healthy"' || curl -s $WEBHOOK_URL
```

**Pre-commit / deploy gate:**
```bash
systemd-doctor status || exit 1
```

**Homelab dashboard:**
```bash
systemd-doctor status --json > /var/www/health.json
```

## License

MIT
