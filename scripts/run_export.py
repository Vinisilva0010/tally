import hashlib
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.export import export  # noqa: E402

RAW = ROOT / "data" / "raw"
OUT = ROOT / "web" / "public" / "data"
RUN_ACCOUNT = "FBG6tQ5BVzK4jg3VEiHNSawZDvmdsLJG712tuWEDcuJH"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find(prefix: str) -> Path:
    return sorted(
        p for p in RAW.glob("*.xls*")
        if p.name.startswith(prefix) and not p.name.startswith("~$")
    )[-1]


def main() -> int:
    conn = sqlite3.connect(ROOT / "data" / "tally.sqlite")
    conn.row_factory = sqlite3.Row
    counts = export(
        conn, OUT, RUN_ACCOUNT,
        sha256_of(find("Voluntary-Registry-Offsets-Database")),
        sha256_of(find("VROD-registry-files")),
        "v2026-08",
    )
    conn.close()
    for name, n in counts.items():
        print(f"  {name:<10} {n:>5}")
    for f in sorted(OUT.glob("*.json")):
        print(f"  {f.name:<16} {f.stat().st_size/1024:>8.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
