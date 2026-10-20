"""Shared fixtures. The database is built once per test session.

Two spreadsheets live in data/raw and they must be told apart by name,
not by position: sorted alphabetically, "VROD-registry-files" comes
before "Voluntary-Registry-Offsets-Database", so picking the first file
in the directory loads the raw registry workbook into the aggregate
ingester and fails on a missing PROJECTS sheet.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.ingest import ingest  # noqa: E402
from tally.raw_ingest import ingest_raw  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "tally.sqlite"

AGGREGATE_PREFIX = "Voluntary-Registry-Offsets-Database"
REGISTRY_PREFIX = "VROD-registry-files"


def _find(prefix: str) -> Path | None:
    matches = sorted(
        p for p in RAW_DIR.glob("*.xls*")
        if p.name.startswith(prefix) and not p.name.startswith("~$")
    )
    return matches[-1] if matches else None


@pytest.fixture(scope="session")
def source_path() -> Path:
    path = _find(AGGREGATE_PREFIX)
    if path is None:
        pytest.skip(f"no {AGGREGATE_PREFIX}*.xlsx in {RAW_DIR}")
    return path


@pytest.fixture(scope="session")
def registry_files_path() -> Path | None:
    return _find(REGISTRY_PREFIX)


@pytest.fixture(scope="session")
def db(source_path: Path, registry_files_path: Path | None):
    ingest(source_path, DB_PATH)
    if registry_files_path is not None:
        ingest_raw(registry_files_path, DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
