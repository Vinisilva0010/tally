import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.detect import MILLI  # noqa: E402
from tally.link import find_candidates  # noqa: E402

TRUE_PAIRS = {
    ("ACR0931", "CAR2112"), ("GS3015", "VCS900"), ("GS1588", "VCS1887"),
    ("GS1378", "VCS1886"), ("CAR495", "VCS80"), ("GS7754", "VCS924"),
    ("GS1371", "VCS783"), ("GS5064", "VCS1692"), ("GS4532", "VCS1693"),
    ("GS2405", "VCS370"), ("GS7615", "VCS1781"), ("GS23339", "VCS3881"),
    ("ACR0234", "CAR1582"),
}


def key(c):
    return tuple(sorted((c.project_a, c.project_b)))


def main() -> int:
    conn = sqlite3.connect(ROOT / "data" / "tally.sqlite")
    conn.row_factory = sqlite3.Row
    candidates, _ = find_candidates(conn)
    conn.close()

    wanted = {tuple(sorted(p)) for p in TRUE_PAIRS}
    truths = [c for c in candidates if key(c) in wanted]
    others = [c for c in candidates if key(c) not in wanted and c.shared_vintages]

    print("=" * 74)
    print(f"CONFIRMED TRUE PAIRS FOUND: {len(truths)} of {len(wanted)}")
    print("=" * 74)
    print(f"{'pair':<24} {'cos':>5} {'tok':>5} {'dev':>5} {'yrs':>4} {'spread':>8}")
    for c in sorted(truths, key=lambda x: x.features.name_cosine):
        f = c.features
        print(f"{c.project_a + '/' + c.project_b:<24} "
              f"{f.name_cosine:>5.2f} {f.name_token_set:>5.0f} "
              f"{f.developer_sim:>5.0f} {len(c.shared_vintages):>4} "
              f"{f.vintage_ratio_spread:>8.2f}")

    cosines = [c.features.name_cosine for c in truths]
    spreads = [c.features.vintage_ratio_spread for c in truths
               if c.features.vintage_ratio_spread > 0]
    print()
    print(f"  cosine  min {min(cosines):.3f}  max {max(cosines):.3f}")
    if spreads:
        print(f"  spread  min {min(spreads):.3f}  max {max(spreads):.3f} "
              f"(over {len(spreads)} pairs with 2+ shared vintages)")
    print(f"  pairs with only one shared vintage: "
          f"{sum(1 for c in truths if len(c.shared_vintages) < 2)}")

    print()
    print("=" * 74)
    print("EFFECT OF EACH PROPOSED THRESHOLD")
    print("=" * 74)
    for cos_min in (0.70, 0.75, 0.80, 0.85):
        kept_true = sum(1 for c in truths if c.features.name_cosine >= cos_min)
        kept_other = sum(1 for c in others if c.features.name_cosine >= cos_min)
        print(f"  cosine >= {cos_min:.2f}  keeps {kept_true:>2}/13 true, "
              f"{kept_other:>4} others")
    print()
    for spread_max in (2.0, 3.0, 5.0, 10.0):
        lost = sum(
            1 for c in truths
            if 0 < c.features.vintage_ratio_spread > spread_max
        )
        cut = sum(
            1 for c in others
            if 0 < c.features.vintage_ratio_spread > spread_max
        )
        print(f"  spread <= {spread_max:>5.1f}  loses {lost}/13 true, "
              f"cuts {cut:>4} others")

    print()
    print("=" * 74)
    print("SURVIVORS WITH cosine >= 0.80 AND (spread <= 5 OR < 2 vintages)")
    print("=" * 74)
    survivors = [
        c for c in others
        if c.features.name_cosine >= 0.80
        and (c.features.vintage_ratio_spread < 0
             or c.features.vintage_ratio_spread <= 5.0)
    ]
    print(f"  count: {len(survivors)}")
    for c in sorted(survivors, key=lambda x: -x.duplicated_milli)[:30]:
        f = c.features
        print()
        print(f"  {c.duplicated_milli / MILLI:>11,.0f}  {c.country}  "
              f"yrs {list(c.shared_vintages)}")
        print(f"    {c.registry_a:<5} {c.project_a:<10} {c.name_a[:56]}")
        print(f"    {c.registry_b:<5} {c.project_b:<10} {c.name_b[:56]}")
        print(f"    cos {f.name_cosine:.2f}  dev {f.developer_sim:.0f}  "
              f"spread {f.vintage_ratio_spread}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
