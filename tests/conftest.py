import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.ingest import ingest  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "tally.sqlite"


@pytest.fixture(scope="session")
def source_path() -> Path:
    files = sorted(
        p for p in RAW_DIR.glob("*.xls*") if not p.name.startswith("~$")
    )
    if not files:
        pytest.skip(f"no spreadsheet in {RAW_DIR}")
    return files[0]


@pytest.fixture(scope="session")
def db(source_path: Path) -> sqlite3.Connection:
    ingest(source_path, DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
