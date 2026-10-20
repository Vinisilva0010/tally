import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.raw_ingest import ingest_raw  # noqa: E402


def main() -> int:
    path = sorted((ROOT / "data" / "raw").glob("VROD-registry-files*"))[0]
    db = ROOT / "data" / "tally.sqlite"
    if not db.exists():
        print("build the main database first: pytest tests/test_ingest.py")
        return 1
    result = ingest_raw(path, db)
    print("rows written per sheet:")
    for sheet, n in result["rows"].items():
        print(f"  {sheet:<28} {n:>9,}")
    print(f"  {'TOTAL':<28} {sum(result['rows'].values()):>9,}")
    if result["unresolved"]:
        print()
        print("project ids not found in the aggregate database:")
        for sheet, n in result["unresolved"].items():
            print(f"  {sheet:<28} {n:>9,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
