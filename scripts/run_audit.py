import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.audit import MILLI, build  # noqa: E402


def main() -> int:
    conn = sqlite3.connect(ROOT / "data" / "tally.sqlite")
    conn.row_factory = sqlite3.Row
    run = build(conn)
    conn.close()

    print("=" * 70)
    print("AUDIT RUN")
    print("=" * 70)
    print(f"  merkle root : {run.root.hex()}")
    print(f"  findings    : {len(run.findings)}")
    print()
    for rule in sorted(k for k in run.totals if k.startswith("R")):
        t = run.totals[rule]
        print(f"  {rule}  {t['count']:>4} findings  "
              f"{t['credits_milli']/MILLI:>14,.0f} credits")
    q = run.totals["review_queue"]
    print(f"  queue {q['count']:>4} pending   "
          f"{q['credits_milli']/MILLI:>14,.0f} credits (not committed)")
    print()
    print(f"  credits evidenced as double counted: {run.credits:,.0f}")
    print()
    print("  CONFIRMED FINDINGS (R1 vintage overlap, R3 serial overlap)")
    for f in sorted(run.confirmed, key=lambda x: -x.credits_milli):
        print(f"    {f.rule}  sev {f.severity}  "
              f"{f.credits_milli/MILLI:>11,.0f}  {'|'.join(f.subjects)[:36]:<38} "
              f"{f.note[:30]}")
    print()
    print("  CONTEXT, not double counting")
    print(f"    R2  {len([f for f in run.context if f.rule == 'R2'])} projects "
          f"cleared as legitimate registry moves")
    dupes = [f for f in run.context if f.rule == 'R4']
    print(f"    R4  {len(dupes)} export duplicates in the registry files, "
          f"{sum(f.credits_milli for f in dupes)/MILLI:,.0f} credits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
