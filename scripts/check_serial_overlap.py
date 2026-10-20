"""Do any serial ranges overlap where they must not?

Within one registry a credit is identified by its prefix plus a number.
Two events covering the same number under the same prefix are two events
on the same credit, which is allowed only in specific combinations:
issuance then one retirement, or issuance then one cancellation. Two
retirements of the same credit, or a retirement and a cancellation of it,
mean the same tonne was disposed of twice.

This is the strongest evidence the dataset can carry: it does not infer a
duplicate from matching totals, it names the credits.
"""
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

M = 1000


def main() -> int:
    conn = sqlite3.connect(ROOT / "data" / "tally.sqlite")
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT registry, event_type, project_id, project_ref, vintage, "
        "serial_prefix, serial_start, serial_end, holder, reason, event_date "
        "FROM credit_event "
        "WHERE serial_prefix IS NOT NULL AND event_type != 'issuance' "
        "ORDER BY registry, serial_prefix, serial_start"
    ).fetchall()

    print(f"disposal events with a parsed range: {len(rows):,}")

    by_prefix: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        by_prefix[(r["registry"], r["serial_prefix"])].append(r)
    print(f"distinct (registry, prefix) groups  : {len(by_prefix):,}")

    collisions = []
    total_overlap = 0
    for (registry, prefix), events in by_prefix.items():
        if len(events) < 2:
            continue
        events.sort(key=lambda e: (e["serial_start"], e["serial_end"]))
        for i in range(len(events) - 1):
            a = events[i]
            for b in events[i + 1:]:
                if b["serial_start"] > a["serial_end"]:
                    break
                shared = min(a["serial_end"], b["serial_end"]) - b["serial_start"] + 1
                if shared > 0:
                    total_overlap += shared
                    collisions.append((registry, prefix, shared, a, b))

    print(f"overlapping disposal pairs          : {len(collisions):,}")
    print(f"credits covered twice               : {total_overlap:,}")
    print()

    collisions.sort(key=lambda c: -c[2])
    for registry, prefix, shared, a, b in collisions[:20]:
        print("=" * 72)
        print(f"  {shared:,} credits  {registry}  prefix {prefix[:46]}")
        for e in (a, b):
            print(f"    {e['event_type']:<12} {e['serial_start']}-{e['serial_end']}"
                  f"  v{e['vintage']}  {str(e['project_id'] or e['project_ref'])[:12]}")
            print(f"      holder {str(e['holder'])[:44]}  "
                  f"reason {str(e['reason'])[:30]}  date {str(e['event_date'])[:10]}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
