import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.detect import MILLI  # noqa: E402
from tally.link import find_candidates  # noqa: E402

DB = ROOT / "data" / "tally.sqlite"
OUT = ROOT / "data" / "review_queue.csv"

FEATURES = [
    "name_cosine", "name_token_set", "developer_sim", "methodology",
    "type_match", "scope_match", "state_match", "site_overlap",
    "markers_equal", "shared_vintages", "vintage_ratio_spread",
]


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    candidates, stats = find_candidates(conn)
    conn.close()

    overlapping = [c for c in candidates if c.shared_vintages]
    new = [c for c in overlapping if not c.exact_name]

    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["label", "duplicated_credits", "exact_name", "overlap_years",
             "country", "project_a", "registry_a", "name_a",
             "project_b", "registry_b", "name_b"] + FEATURES
        )
        for c in overlapping:
            f = c.features.as_dict()
            writer.writerow(
                ["", round(c.duplicated_milli / MILLI, 3), int(c.exact_name),
                 " ".join(str(y) for y in c.shared_vintages), c.country,
                 c.project_a, c.registry_a, c.name_a,
                 c.project_b, c.registry_b, c.name_b]
                + [f[k] for k in FEATURES]
            )

    print("NEW PAIRS WITH VINTAGE OVERLAP (not exact-name), top 30")
    print("=" * 74)
    for c in new[:30]:
        f = c.features
        print()
        print(f"  {c.duplicated_milli / MILLI:>12,.0f}  {c.country}  "
              f"vintages {list(c.shared_vintages)}")
        print(f"    {c.registry_a:<5} {c.project_a:<10} {c.name_a[:58]}")
        print(f"    {c.registry_b:<5} {c.project_b:<10} {c.name_b[:58]}")
        print(f"    name {f.name_cosine:.2f}/{f.name_token_set:.0f}  "
              f"dev {f.developer_sim:.0f}  meth {f.methodology}  "
              f"state {f.state_match}  site {f.site_overlap:.2f}  "
              f"spread {f.vintage_ratio_spread}")

    print()
    print("=" * 74)
    print("SUMMARY")
    print("=" * 74)
    for key in ["projects", "countries", "compared", "name_gate_passed",
                "rejected_type", "rejected_state", "rejected_marker",
                "rejected_distinctive",
                "accepted"]:
        print(f"  {key:<20} : {stats[key]:,}")
    print(f"  {'with overlap':<20} : {len(overlapping):,}")
    print(f"  {'  exact-name':<20} : {len(overlapping) - len(new):,}")
    print(f"  {'  NEW':<20} : {len(new):,}")
    print()
    print(f"Review queue: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
