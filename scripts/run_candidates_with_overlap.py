import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.detect import MILLI, overlapping_vintages  # noqa: E402
from tally.link import find_candidates  # noqa: E402

DB = ROOT / "data" / "tally.sqlite"
OUT = ROOT / "data" / "review_queue.csv"


def vintages_for(conn, project_id: str) -> dict[int, int]:
    rows = conn.execute(
        "SELECT year, credits_milli FROM credit_year "
        "WHERE kind = 'issued_vintage' AND credits_milli > 0 "
        "AND project_id = ?",
        (project_id,),
    ).fetchall()
    return {r["year"]: r["credits_milli"] for r in rows}


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    pairs, stats = find_candidates(conn)

    rows = []
    for p in pairs:
        years, dup = overlapping_vintages({
            p.registry_a: vintages_for(conn, p.project_a),
            p.registry_b: vintages_for(conn, p.project_b),
        })
        if not years:
            continue
        rows.append((p, years, dup))
    conn.close()

    rows.sort(key=lambda r: -r[2])
    new = [r for r in rows if not r[0].exact_name]

    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "label", "same_project_notes", "duplicated_credits", "combined",
            "exact_name", "overlap_years", "country",
            "project_a", "registry_a", "name_a",
            "project_b", "registry_b", "name_b",
        ])
        for p, years, dup in rows:
            writer.writerow([
                "", "", round(dup / MILLI, 3), p.combined, int(p.exact_name),
                " ".join(str(y) for y in years), p.country,
                p.project_a, p.registry_a, p.name_a,
                p.project_b, p.registry_b, p.name_b,
            ])

    print("PAIRS WITH VINTAGE OVERLAP, NEW (similarity only)")
    print("=" * 72)
    for p, years, dup in new:
        print()
        print(f"  {dup / MILLI:>12,.3f}  score {p.combined:.4f}  "
              f"{p.country}  vintages {list(years)}")
        print(f"    {p.registry_a:<5} {p.project_a:<10} {p.name_a[:60]}")
        print(f"    {p.registry_b:<5} {p.project_b:<10} {p.name_b[:60]}")

    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"  candidate pairs from linking   : {len(pairs)}")
    print(f"  of those, with vintage overlap : {len(rows)}")
    print(f"    exact-name (already known)   : {len(rows) - len(new)}")
    print(f"    NEW, similarity only         : {len(new)}")
    print(f"  credits at stake in new pairs  : "
          f"{sum(r[2] for r in new) / MILLI:,.3f}")
    print()
    print(f"Review queue: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
