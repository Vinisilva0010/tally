"""Is an overlapping vintage still live on both sides, or was it migrated?"""
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
    queue = [c for c in candidates if c.shared_vintages]
    queue.sort(key=lambda c: -c.duplicated_milli)

    live_total = settled_total = 0
    print("=" * 76)
    print("OVERLAPPING VINTAGES: STILL OUTSTANDING ON BOTH SIDES?")
    print("=" * 76)
    print()
    print("  A vintage credited by two registries is only a live double count")
    print("  if neither side has retired or cancelled it. If the source side")
    print("  shows nothing remaining, the credits were migrated, not doubled.")

    for c in queue:
        ia = series(conn, c.project_a, "issued_vintage")
        ib = series(conn, c.project_b, "issued_vintage")
        ra = series(conn, c.project_a, "remaining_vintage")
        rb = series(conn, c.project_b, "remaining_vintage")

        live, settled = 0, 0
        detail = []
        for y in c.shared_vintages:
            both_live = min(ra.get(y, 0), rb.get(y, 0))
            dup = ia[y] + ib[y] - max(ia[y], ib[y])
            if both_live > 0:
                live += min(both_live, dup)
                state = "LIVE"
            else:
                settled += dup
                state = "settled"
            detail.append(
                f"      {y}  {state:<8} issued A={ia[y]/M:>10,.0f} "
                f"B={ib[y]/M:>10,.0f}  remaining A={ra.get(y,0)/M:>10,.0f} "
                f"B={rb.get(y,0)/M:>10,.0f}"
            )

        live_total += live
        settled_total += settled
        tag = "exact" if c.exact_name else "linked"
        print()
        print(f"  [{tag}] {c.project_a} / {c.project_b}  {c.country}")
        print(f"      live {live/M:,.0f}   settled {settled/M:,.0f}")
        for line in detail:
            print(line)

    print()
    print("=" * 76)
    print(f"  live double counting   : {live_total/M:,.0f} credits")
    print(f"  settled / migrated     : {settled_total/M:,.0f} credits")
    print("=" * 76)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
