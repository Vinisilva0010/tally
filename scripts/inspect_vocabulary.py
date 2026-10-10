import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DB = ROOT / "data" / "tally.sqlite"

PROBES = [
    ("fajina", "luohe", "ruijing", "lankao", "geothermal", "heating",
     "system", "based", "space"),
    ("kielty", "oaktown", "abandoned", "mine", "methane", "recovery"),
    ("gujarat", "karnataka", "rajasthan", "wind", "power", "project",
     "energy", "bundled", "grid", "connected"),
    ("adavikanda", "kuruwita", "huadian", "yangjiayao", "nanyang",
     "danjiang", "heqing"),
]


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT name_norm, country FROM project WHERE total_issued_milli > 0 "
        "AND LENGTH(name_norm) >= 9"
    ).fetchall()
    conn.close()

    total = len(rows)
    global_df = Counter()
    by_country: dict[str, Counter] = {}
    country_size = Counter()

    for r in rows:
        tokens = set(r["name_norm"].split())
        global_df.update(tokens)
        by_country.setdefault(r["country"], Counter()).update(tokens)
        country_size[r["country"]] += 1

    print(f"issuing projects: {total:,}")
    print(f"distinct tokens : {len(global_df):,}")
    print()
    print("=" * 74)
    print("DOCUMENT FREQUENCY OF PROBE TOKENS")
    print("=" * 74)
    print(f"{'token':<16} {'global':>8} {'global%':>8}   "
          f"{'in-country':>10} {'country%':>9}  country")
    for group in PROBES:
        print()
        for token in group:
            best_country, best_count, best_pct = "-", 0, 0.0
            for country, counter in by_country.items():
                c = counter.get(token, 0)
                if c > best_count:
                    best_country, best_count = country, c
                    best_pct = 100 * c / country_size[country]
            print(f"  {token:<14} {global_df[token]:>8,} "
                  f"{100 * global_df[token] / total:>7.2f}%   "
                  f"{best_count:>10,} {best_pct:>8.2f}%  {best_country}")

    print()
    print("=" * 74)
    print("TOP 60 MOST COMMON TOKENS OVERALL")
    print("=" * 74)
    for token, count in global_df.most_common(60):
        print(f"  {token:<22} {count:>6,}  {100 * count / total:>6.2f}%")

    print()
    print("=" * 74)
    print("HOW MANY TOKENS SURVIVE EACH CUTOFF")
    print("=" * 74)
    for pct in (0.5, 1.0, 2.0, 5.0):
        rare = sum(1 for t, c in global_df.items() if 100 * c / total < pct)
        print(f"  tokens appearing in fewer than {pct:>4.1f}% of projects: "
              f"{rare:,} of {len(global_df):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
