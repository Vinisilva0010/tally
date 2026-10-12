"""What happened to each side of a duplicated vintage.

The earlier version of this check treated a vintage with nothing left on
one side as "settled", on the assumption that an empty balance meant the
credits had been migrated away. That is backwards. An empty balance means
the credits were retired -- claimed by a buyer against their emissions.

Kielty makes the error plain: both registries issued 147,508 credits for
vintage 2025, the ACR side still holds all of them, and the CAR side holds
none. One tonne has already been claimed and an identical tonne is still
for sale. That is the worst case, not a resolved one.

So each duplicated vintage is classified by what became of both sides:

  both_available   the duplicate exists and nobody has claimed it yet
  one_claimed      one side claimed, the copy is still sellable
  both_claimed     two buyers claimed the same tonne; the harm is done

Limitation, stated rather than hidden: this dataset merges retirement and
cancellation into one column, and cancellation is exactly what a genuine
CER migration does to the source credits. Separating the two requires the
raw registry retirement tables, which Berkeley publishes alongside the
database.
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.link import find_candidates  # noqa: E402

M = 1000


def series(conn, pid, kind):
    return {
        r["year"]: r["credits_milli"]
        for r in conn.execute(
            "SELECT year, credits_milli FROM credit_year "
            "WHERE project_id=? AND kind=? AND credits_milli>0",
            (pid, kind),
        )
    }


def main() -> int:
    conn = sqlite3.connect(ROOT / "data" / "tally.sqlite")
    conn.row_factory = sqlite3.Row
    candidates, _ = find_candidates(conn)
    queue = sorted(
        (c for c in candidates if c.shared_vintages),
        key=lambda c: -c.duplicated_milli,
    )

    totals = {"both_available": 0, "one_claimed": 0, "both_claimed": 0}
    rows = []

    for c in queue:
        ia = series(conn, c.project_a, "issued_vintage")
        ib = series(conn, c.project_b, "issued_vintage")
        ra = series(conn, c.project_a, "remaining_vintage")
        rb = series(conn, c.project_b, "remaining_vintage")

        per_pair = {"both_available": 0, "one_claimed": 0, "both_claimed": 0}
        detail = []
        for y in c.shared_vintages:
            dup = ia[y] + ib[y] - max(ia[y], ib[y])
            left_open = ra.get(y, 0) > 0
            right_open = rb.get(y, 0) > 0
            if left_open and right_open:
                state = "both_available"
            elif left_open or right_open:
                state = "one_claimed"
            else:
                state = "both_claimed"
            per_pair[state] += dup
            totals[state] += dup
            detail.append(
                f"      {y}  {state:<15} duplicated {dup/M:>11,.0f}   "
                f"left {ra.get(y,0)/M:>10,.0f}  right {rb.get(y,0)/M:>10,.0f}"
            )
        rows.append((c, per_pair, detail))

    print("=" * 78)
    print("CLAIM STATUS OF EACH DUPLICATED VINTAGE")
    print("=" * 78)
    for c, per_pair, detail in rows:
        tag = "exact" if c.exact_name else "linked"
        worst = max(per_pair, key=lambda k: per_pair[k])
        print()
        print(f"  [{tag}] {c.project_a} / {c.project_b}  {c.country}  "
              f"-> mostly {worst}")
        for line in detail:
            print(line)

    print()
    print("=" * 78)
    print("TOTALS")
    print("=" * 78)
    for state in ("both_claimed", "one_claimed", "both_available"):
        print(f"  {state:<16} : {totals[state]/M:>12,.0f} credits")
    print(f"  {'all':<16} : {sum(totals.values())/M:>12,.0f} credits")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
