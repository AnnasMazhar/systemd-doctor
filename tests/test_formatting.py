"""Tests for formatting.py — colors, tables, duration parsing."""


from systemd_doctor.formatting import (
    color,
    duration_human,
    parse_duration,
    table,
    traffic_light,
)


def test_traffic_lights():
    """All 3 levels return expected emoji."""
    assert traffic_light("ok") == "\U0001f7e2"
    assert traffic_light("warning") == "\U0001f7e1"
    assert traffic_light("critical") == "\U0001f534"
    assert traffic_light("unknown") == "\u26ab"


def test_color_ansi():
    """Color wraps in ANSI codes."""
    result = color("hello", "red")
    assert result == "\x1b[31mhello\x1b[0m"


def test_color_green():
    """Green ANSI wrapping."""
    assert color("go", "green") == "\x1b[32mgo\x1b[0m"


def test_color_yellow():
    assert color("warn", "yellow") == "\x1b[33mwarn\x1b[0m"


def test_color_bold():
    assert color("bold", "bold") == "\x1b[1mbold\x1b[0m"


def test_color_unknown():
    """Unknown colour returns text unchanged."""
    assert color("text", "purple") == "text"


def test_no_color_env(monkeypatch):
    """NO_COLOR=1 strips ANSI codes."""
    monkeypatch.setenv("NO_COLOR", "1")
    result = color("hello", "red")
    assert result == "hello"
    assert "\x1b" not in result


def test_no_color_env_empty(monkeypatch):
    """NO_COLOR unset still produces ANSI."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    result = color("test", "green")
    assert "\x1b" in result


def test_duration_human_zero():
    assert duration_human(0) == "0s"


def test_duration_human_59s():
    assert duration_human(59) == "59s"


def test_duration_human_1h():
    assert duration_human(3600) == "1h"


def test_duration_human_1d_2h():
    assert duration_human(93600) == "1d 2h"


def test_duration_human_7d():
    assert duration_human(604800) == "7d"


def test_duration_human_negative():
    """Negative durations are clamped to 0."""
    assert duration_human(-10) == "0s"


def test_duration_human_1h1m():
    assert duration_human(3660) == "1h 1m"


def test_parse_duration_30m():
    assert parse_duration("30m") == 1800.0


def test_parse_duration_6h():
    assert parse_duration("6h") == 21600.0


def test_parse_duration_1d():
    assert parse_duration("1d") == 86400.0


def test_parse_duration_7d():
    assert parse_duration("7d") == 604800.0


def test_parse_duration_90s():
    assert parse_duration("90s") == 90.0


def test_parse_duration_invalid():
    """Invalid format raises ValueError."""
    import pytest

    with pytest.raises(ValueError):
        parse_duration("xyz")


def test_parse_duration_empty():
    """Empty string raises ValueError."""
    import pytest

    with pytest.raises(ValueError):
        parse_duration("")


def test_table_with_headers():
    """Table has headers, separator, and aligned rows."""
    result = table(["Name", "Age"], [["Alice", "30"], ["Bob", "25"]])
    lines = result.split("\n")
    assert len(lines) == 4  # header, separator, 2 rows
    assert lines[0] == "Name   Age"
    assert lines[2] == "Alice  30 "
    assert lines[3] == "Bob    25 "


def test_table_no_headers():
    """Table without headers works."""
    result = table([], [["a"], ["b"]])
    assert "a" in result
    assert "b" in result


def test_table_empty():
    """Empty input returns empty string."""
    assert table([], []) == ""
    assert table(["H"], []) == "H\n-"


def test_table_right_alignment():
    """Right alignment respected."""
    result = table(["A"], [["10"], ["5"]], alignments=["r"])
    lines = result.split("\n")
    assert lines[0] == " A"
    assert lines[2] == "10"
    assert lines[3] == " 5"
