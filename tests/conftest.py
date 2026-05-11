"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"
