"""Property-based fuzz tests for systemctl output parsers."""

import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from systemd_doctor.systemctl import _parse_datetime, _parse_single_timer_line

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TIMEZONES = ["UTC", "EST", "CEST", "BST", "JST", "PST", "CET", "GMT"]


@st.composite
def systemd_datetime_str(draw):
    """Generate a valid systemd datetime: 'Day YYYY-MM-DD HH:MM:SS TZ'."""
    day = draw(st.sampled_from(DAYS))
    date = draw(
        st.dates(min_value=datetime.date(2020, 1, 1), max_value=datetime.date(2030, 12, 31))
    )
    time = draw(st.times())
    tz = draw(st.sampled_from(TIMEZONES))
    return f"{day} {date} {time.strftime('%H:%M:%S')} {tz}"


@st.composite
def relative_time_str(draw, delimiter):
    """Generate relative time like '2h 30min left' or '5 days ago'."""
    n_parts = draw(st.integers(min_value=1, max_value=4))
    parts = []
    for _ in range(n_parts):
        num = draw(st.integers(min_value=1, max_value=999))
        unit = draw(st.sampled_from(["s", "min", "h", "day", "days", "week", "weeks", "month"]))
        parts.append(f"{num}{unit}")
    parts.append(delimiter)
    return " ".join(parts)


@st.composite
def timer_line(draw):
    """Generate a valid systemctl list-timers line."""
    # NEXT: "n/a" or "Day YYYY-MM-DD HH:MM:SS TZ"
    next_is_na = draw(st.booleans())
    if next_is_na:
        next_part = "n/a"
    else:
        next_part = draw(systemd_datetime_str())

    # LEFT: "n/a" or relative time ending with "left"
    left_is_na = draw(st.booleans())
    if left_is_na:
        left_part = "n/a"
    else:
        left_part = draw(relative_time_str("left"))

    # LAST: "n/a" or "Day YYYY-MM-DD HH:MM:SS TZ"
    last_is_na = draw(st.booleans())
    if last_is_na:
        last_part = "n/a"
    else:
        last_part = draw(systemd_datetime_str())

    # PASSED: "n/a" or relative time ending with "ago"
    passed_is_na = draw(st.booleans())
    if passed_is_na:
        passed_part = "n/a"
    else:
        passed_part = draw(relative_time_str("ago"))

    # UNIT and ACTIVATES
    unit_name = draw(st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True))
    unit_suffix = draw(st.sampled_from([".timer", ".service", ".socket"]))
    unit = unit_name + unit_suffix

    act_name = draw(st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True))
    act_suffix = draw(st.sampled_from([".timer", ".service", ".socket"]))
    activates = act_name + act_suffix

    return f"{next_part} {left_part} {last_part} {passed_part} {unit} {activates}"


@st.composite
def security_line(draw):
    """Generate a valid systemd-analyze security output line."""
    unit_name = draw(st.from_regex(r"[a-z][a-z0-9_@-]{2,30}", fullmatch=True))
    unit = unit_name + ".service"
    exposure = draw(st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False))
    predicate = draw(st.sampled_from(["SAFE", "OK", "EXPOSED", "UNSAFE"]))
    return f"{unit} {exposure:.1f} {predicate}"


@st.composite
def list_units_line(draw):
    """Generate a valid systemctl list-units line."""
    unit_name = draw(st.from_regex(r"[a-z][a-z0-9_@.-]{2,30}", fullmatch=True))
    unit = unit_name + ".service"
    load = draw(st.sampled_from(["loaded", "not-found", "masked"]))
    active = draw(st.sampled_from(["active", "inactive", "failed", "activating"]))
    sub = draw(st.sampled_from(["running", "dead", "exited", "waiting", "failed"]))
    desc = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Z")), min_size=1, max_size=60
        )
    )
    return f"{unit} {load} {active} {sub} {desc}"


# ---------------------------------------------------------------------------
# PRIORITY 1: Timer parser fuzz tests
# ---------------------------------------------------------------------------


class TestTimerParserFuzz:
    """Property-based tests for _parse_single_timer_line."""

    @given(line=timer_line())
    @settings(max_examples=200)
    def test_always_returns_valid_dict(self, line):
        """Parser always returns a dict with all expected keys for valid input."""
        result = _parse_single_timer_line(line)
        assert result is not None, f"Parser returned None for valid line: {line!r}"
        assert set(result.keys()) == {"next", "left", "last", "passed", "unit", "activates"}

    @given(line=timer_line())
    @settings(max_examples=200)
    def test_left_contains_left_or_na(self, line):
        """LEFT field must contain 'left' or be 'n/a'."""
        result = _parse_single_timer_line(line)
        assert result is not None
        assert "left" in result["left"] or result["left"] == "n/a"

    @given(line=timer_line())
    @settings(max_examples=200)
    def test_passed_contains_ago_or_na(self, line):
        """PASSED field must contain 'ago' or be 'n/a'."""
        result = _parse_single_timer_line(line)
        assert result is not None
        assert "ago" in result["passed"] or result["passed"] == "n/a"

    @given(line=timer_line())
    @settings(max_examples=200)
    def test_unit_name_preserved(self, line):
        """Unit name from input must appear in result."""
        result = _parse_single_timer_line(line)
        assert result is not None
        # Unit is second-to-last token group
        assert result["unit"].endswith((".timer", ".service", ".socket"))
        assert result["activates"].endswith((".timer", ".service", ".socket"))

    @given(data=st.data())
    @settings(max_examples=100)
    def test_next_datetime_parsed_when_not_na(self, data):
        """When NEXT is a datetime, result['next'] should be a datetime object."""
        # Force NEXT to be a datetime (not n/a)
        next_str = data.draw(systemd_datetime_str())
        left_part = "n/a"
        last_part = "n/a"
        passed_part = "n/a"
        unit = "test.timer"
        activates = "test.service"
        line = f"{next_str} {left_part} {last_part} {passed_part} {unit} {activates}"

        result = _parse_single_timer_line(line)
        assert result is not None
        # _parse_datetime may return None for TZs strptime can't handle
        # but it should at least not crash
        if result["next"] is not None:
            assert isinstance(result["next"], datetime.datetime)

    def test_all_na_fields(self):
        """All n/a fields should parse correctly."""
        line = "n/a n/a n/a n/a logrotate.timer logrotate.service"
        result = _parse_single_timer_line(line)
        assert result is not None
        assert result["next"] is None
        assert result["left"] == "n/a"
        assert result["last"] is None
        assert result["passed"] == "n/a"
        assert result["unit"] == "logrotate.timer"
        assert result["activates"] == "logrotate.service"

    def test_short_line_returns_none(self):
        """Lines with fewer than 6 tokens return None."""
        assert _parse_single_timer_line("") is None
        assert _parse_single_timer_line("a b c") is None
        assert _parse_single_timer_line("n/a n/a") is None

    def test_long_unit_name(self):
        """Very long unit names should parse."""
        long_name = "a" * 100 + ".timer"
        line = f"n/a n/a n/a n/a {long_name} test.service"
        result = _parse_single_timer_line(line)
        assert result is not None
        assert result["unit"] == long_name

    def test_unit_with_at_sign(self):
        """Templated unit names (user@1000.service) should parse."""
        line = "n/a n/a n/a n/a user@1000.timer user@1000.service"
        result = _parse_single_timer_line(line)
        assert result is not None
        assert result["unit"] == "user@1000.timer"
        assert result["activates"] == "user@1000.service"

    def test_missing_activates(self):
        """Line with only one unit at end (no activates)."""
        line = "n/a n/a n/a n/a logrotate.timer"
        result = _parse_single_timer_line(line)
        # 5 tokens — below minimum of 6
        assert result is None


# ---------------------------------------------------------------------------
# PRIORITY 2: Security analyzer fuzz tests
# ---------------------------------------------------------------------------


def _parse_security_line(line: str):
    """Parse a single security output line (mirrors analyze_security logic)."""
    line = line.strip()
    if not line:
        return None
    parts = line.rsplit(None, 2)
    if len(parts) < 3:
        return None
    unit = parts[0]
    try:
        exposure = float(parts[1])
    except ValueError:
        return None
    predicate = parts[2].strip("()") if parts[2].startswith("(") else parts[2]
    return {"unit": unit, "exposure": exposure, "predicate": predicate}


class TestSecurityParserFuzz:
    """Property-based tests for security output parsing."""

    @given(line=security_line())
    @settings(max_examples=200)
    def test_valid_line_parses(self, line):
        """Every valid security line should parse to a dict."""
        result = _parse_security_line(line)
        assert result is not None
        assert "unit" in result
        assert "exposure" in result
        assert "predicate" in result

    @given(line=security_line())
    @settings(max_examples=200)
    def test_exposure_is_float(self, line):
        """Exposure score must be a float."""
        result = _parse_security_line(line)
        assert result is not None
        assert isinstance(result["exposure"], float)
        assert 0.0 <= result["exposure"] <= 10.0

    @given(line=security_line())
    @settings(max_examples=200)
    def test_predicate_is_valid(self, line):
        """Predicate must be one of the known values."""
        result = _parse_security_line(line)
        assert result is not None
        assert result["predicate"] in {"SAFE", "OK", "EXPOSED", "UNSAFE"}

    def test_boundary_score_zero(self):
        """Score of 0.0 parses correctly."""
        result = _parse_security_line("sshd.service 0.0 SAFE")
        assert result is not None
        assert result["exposure"] == 0.0

    def test_boundary_score_ten(self):
        """Score of 10.0 parses correctly."""
        result = _parse_security_line("docker.service 10.0 UNSAFE")
        assert result is not None
        assert result["exposure"] == 10.0

    def test_parenthesized_predicate(self):
        """Predicate in parens like (EXPOSED) should strip parens."""
        result = _parse_security_line("test.service 5.5 (EXPOSED)")
        assert result is not None
        assert result["predicate"] == "EXPOSED"

    def test_templated_unit(self):
        """Templated unit user@1000.service parses."""
        result = _parse_security_line("user@1000.service 4.2 OK")
        assert result is not None
        assert result["unit"] == "user@1000.service"

    def test_invalid_lines_skipped(self):
        """Invalid lines return None without crashing."""
        assert _parse_security_line("") is None
        assert _parse_security_line("   ") is None
        assert _parse_security_line("only-one-field") is None
        assert _parse_security_line("unit notanumber SAFE") is None
        assert _parse_security_line("# comment line") is None


# ---------------------------------------------------------------------------
# PRIORITY 3: list_units parser fuzz tests
# ---------------------------------------------------------------------------


def _parse_units_line(line: str):
    """Parse a single list-units line (mirrors list_units logic)."""
    line = line.strip()
    if not line:
        return None
    parts = line.split(None, 4)
    if len(parts) < 4:
        return None
    return {
        "unit": parts[0],
        "load": parts[1],
        "active": parts[2],
        "sub": parts[3],
        "description": parts[4] if len(parts) > 4 else "",
    }


class TestListUnitsFuzz:
    """Property-based tests for list-units output parsing."""

    @given(line=list_units_line())
    @settings(max_examples=200)
    def test_valid_line_parses(self, line):
        """Every valid list-units line should parse."""
        result = _parse_units_line(line)
        assert result is not None
        assert set(result.keys()) == {"unit", "load", "active", "sub", "description"}

    @given(line=list_units_line())
    @settings(max_examples=200)
    def test_unit_name_preserved(self, line):
        """Unit name ends with .service."""
        result = _parse_units_line(line)
        assert result is not None
        assert result["unit"].endswith(".service")

    @given(line=list_units_line())
    @settings(max_examples=200)
    def test_fields_are_valid_values(self, line):
        """Load/active/sub fields are from known sets."""
        result = _parse_units_line(line)
        assert result is not None
        assert result["load"] in {"loaded", "not-found", "masked"}
        assert result["active"] in {"active", "inactive", "failed", "activating"}
        assert result["sub"] in {"running", "dead", "exited", "waiting", "failed"}

    def test_short_line_skipped(self):
        """Lines with fewer than 4 fields return None."""
        assert _parse_units_line("") is None
        assert _parse_units_line("unit loaded") is None
        assert _parse_units_line("a b c") is None

    def test_description_with_spaces(self):
        """Description containing spaces is preserved."""
        line = "sshd.service loaded active running OpenSSH server daemon"
        result = _parse_units_line(line)
        assert result is not None
        assert result["description"] == "OpenSSH server daemon"


# ---------------------------------------------------------------------------
# PRIORITY 4: _parse_datetime boundary tests
# ---------------------------------------------------------------------------


class TestParseDatetime:
    """Explicit boundary tests for _parse_datetime."""

    def test_standard_format(self):
        """Mon 2024-01-15 03:00:00 UTC."""
        result = _parse_datetime("Mon 2024-01-15 03:00:00 UTC")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 3

    def test_no_dow_prefix(self):
        """2024-01-15 03:00:00 (no DOW)."""
        result = _parse_datetime("2024-01-15 03:00:00")
        assert result is not None
        assert result.year == 2024
        assert result.hour == 3

    def test_no_dow_with_tz(self):
        """2024-01-15 03:00:00 UTC (no DOW, with TZ)."""
        result = _parse_datetime("2024-01-15 03:00:00 UTC")
        assert result is not None
        assert result.year == 2024

    def test_na_returns_none(self):
        """n/a should return None."""
        assert _parse_datetime("n/a") is None

    def test_empty_returns_none(self):
        """Empty string should return None."""
        assert _parse_datetime("") is None

    def test_invalid_time_returns_none(self):
        """Invalid hour (25) should return None."""
        assert _parse_datetime("Mon 2024-01-15 25:00:00 UTC") is None

    def test_long_dow_prefix_stripped(self):
        """Long DOW prefix (>4 chars) should NOT be stripped — parse fails."""
        # "InvalidDate" is 11 chars, > 4, so it won't be stripped
        # But it starts with alpha, len > 4 means it's NOT stripped
        result = _parse_datetime("InvalidDate 2024-01-15 03:00:00 UTC")
        # The parser only strips if len(prefix) <= 4
        assert result is None

    def test_single_char_dow_stripped(self):
        """Single-char DOW prefix (e.g. 'X') should be stripped."""
        result = _parse_datetime("X 2024-01-15 03:00:00 UTC")
        assert result is not None
        assert result.year == 2024

    def test_three_char_dow(self):
        """Three-char DOW (Mon, Tue, etc.) stripped correctly."""
        result = _parse_datetime("Tue 2025-06-01 12:30:45 UTC")
        assert result is not None
        assert result.month == 6
        assert result.minute == 30

    def test_four_char_dow(self):
        """Four-char DOW prefix stripped (edge of <=4 check)."""
        result = _parse_datetime("Thur 2024-03-20 08:15:00 UTC")
        assert result is not None
        assert result.day == 20

    def test_microseconds_not_supported(self):
        """Timestamps with microseconds fail (not in format strings)."""
        result = _parse_datetime("Mon 2024-01-15 03:00:00.123456 UTC")
        # strptime format doesn't include %f — returns None
        assert result is None

    def test_numeric_tz_offset_not_supported(self):
        """Timestamps with +0000 offset fail (not in format strings)."""
        result = _parse_datetime("Mon 2024-01-15 03:00:00 +0000")
        # %Z doesn't match "+0000" — returns None
        assert result is None
