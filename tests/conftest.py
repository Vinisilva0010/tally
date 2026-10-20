"""Shared fixtures. The database is reused between runs when it is current.

Two spreadsheets live in data/raw and must be told apart by name, not by
position: sorted alphabetically "VROD-registry-files" comes before
"Voluntary-Registry-Offsets-Database", so taking the first file in the
directory feeds the raw workbook to the aggregate ingester and fails on a
missing PROJECTS sheet.

Ingesting both workbooks takes over two minutes, which is too slow to pay
on every run. The source_file table already records the SHA-256 of each
file it was built from, so the build is skipped when those checksums
still match what is on disk. Pass --rebuild to force it.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.ingest import ingest, sha256_of  # noqa: E402
from tally.raw_ingest import ingest_raw  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "tally.sqlite"

AGGREGATE_PREFIX = "Voluntary-Registry-Offsets-Database"
REGISTRY_PREFIX = "VROD-registry-files"


def pytest_addoption(parser):
    parser.addoption(
        "--rebuild", action="store_true", default=False,
        help="rebuild the SQLite database even if it is already current",
    )


def _find(prefix: str) -> Path | None:
    matches = sorted(
        p for p in RAW_DIR.glob("*.xls*")
        if p.name.startswith(prefix) and not p.name.startswith("~$")
    )
    return matches[-1] if matches else None


def _is_current(paths: list[Path]) -> bool:
    """True when the database was built from exactly these files."""
    if not DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            stored = {
                row[0] for row in conn.execute("SELECT sha256 FROM source_file")
            }
            if not conn.execute(
                "SELECT 1 FROM credit_event LIMIT 1"
            ).fetchone() and len(paths) > 1:
                return False
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    return all(sha256_of(p) in stored for p in paths)


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
def db(request, source_path: Path, registry_files_path: Path | None):
    paths = [source_path] + (
        [registry_files_path] if registry_files_path else []
    )
    if request.config.getoption("--rebuild") or not _is_current(paths):
        ingest(source_path, DB_PATH)
        if registry_files_path is not None:
            ingest_raw(registry_files_path, DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
