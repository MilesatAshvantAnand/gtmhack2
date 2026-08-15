"""Shared, dependency-free local-test helpers for the Ashtree workflow."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = PROJECT_ROOT / "fixtures"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def fixture_files() -> Iterable[Path]:
    """Yield sanitized JSON fixtures in a stable order."""
    if not FIXTURES_DIR.is_dir():
        return ()
    return tuple(sorted(FIXTURES_DIR.rglob("*.json")))


def fixture_path(relative_name: str) -> Path:
    """Resolve a fixture without allowing callers to escape ``fixtures/``."""
    candidate = (FIXTURES_DIR / relative_name).resolve()
    candidate.relative_to(FIXTURES_DIR.resolve())
    return candidate


def load_fixture(relative_name: str) -> Any:
    """Load one checked-in JSON fixture; local tests never call a provider."""
    with fixture_path(relative_name).open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


try:
    import pytest
except ModuleNotFoundError:
    pytest = None
else:

    @pytest.fixture
    def project_root() -> Path:
        return PROJECT_ROOT

    @pytest.fixture
    def fixtures_dir() -> Path:
        return FIXTURES_DIR

