import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.detect import MILLI, Kind, run  # noqa: E402

DB = ROOT / "data" / "tally.sqlite"


def main() -> int:
    if not DB.exists():
        print(f"database not found at {DB}; run the tests once to build it")
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    findings = run(conn)
    conn.close()

    overlap = [f for f in findings if f.kind is Kind.VINTAGE_OVERLAP]
    moves = [f for f in findings if f.kind is Kind.REGISTRY_MOVE]
    total = sum(f.duplicated_milli for f in overlap)

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  cross-registry candidates      : {len(findings)}")
    print(f"  R1 vintage overlap             : {len(overlap)}")
    print(f"  R2 clean registry move         : {len(moves)}")
    print(f"  same country on both sides (R1): "
          f"{sum(1 for f in overlap if len(f.countries) == 1)}")
    print(f"  duplicated credits (milli)     : {total:,}")
    print(f"  duplicated credits             : {total / MILLI:,.3f}")
    print()
    print("=" * 70)
    print("R1 FINDINGS")
    print("=" * 70)
    for f in sorted(overlap, key=lambda x: -x.duplicated_milli):
        issued = {k: round(v / MILLI, 3) for k, v in f.issued_by_registry_milli.items()}
        print()
        print(f"  {f.duplicated_credits:>14,.3f}  sev {f.severity}  {f.display_name[:50]}")
        print(f"        ids {list(f.project_ids)}  regs {list(f.registries)}")
        print(f"        issued {issued}")
        print(f"        overlap {list(f.overlap_years)}  country {list(f.countries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
