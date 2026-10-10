import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.features import build_place_names, build_vocabulary, distinctive  # noqa: E402
from tally.link import discriminators, load_issuing_projects  # noqa: E402

PROBE = ["gujarat", "karnataka", "rajasthan", "uttarakhand", "kerala",
         "mordogan", "lalpur", "adavikanda", "kuruwita", "larimer",
         "yangjiayao", "ningxia", "huadian"]

PAIRS = [("GS2405", "VCS384"), ("GS7628", "VCS2244"),
         ("GS3906", "VCS3154"), ("GS1017", "VCS1231")]


def main() -> int:
    conn = sqlite3.connect(ROOT / "data" / "tally.sqlite")
    conn.row_factory = sqlite3.Row
    rows = load_issuing_projects(conn)

    blocks: dict[str, list] = {}
    for r in rows:
        blocks.setdefault(r["country"], []).append(r)

    names_by_country = {c: [r["name_norm"] for r in rs] for c, rs in blocks.items()}
    places = build_place_names(names_by_country)

    print(f"place names detected: {len(places)}")
    print()
    print("PROBE TOKENS")
    for token in PROBE:
        print(f"  {token:<14} in place list: {token in places}")

    india = names_by_country.get("India", [])
    print()
    print(f"India issuing projects: {len(india)}")
    for token in ["gujarat", "karnataka", "rajasthan"]:
        n = sum(1 for name in india if token in name.split())
        print(f"  {token:<12} appears in {n} of {len(india)} "
              f"= {100*n/len(india):.2f}%  "
              f"(window is 0.50%-5.00%)")

    print()
    print("PAIRS IN QUESTION")
    byid = {r["project_id"]: r for r in rows}
    for a, b in PAIRS:
        ra, rb = byid.get(a), byid.get(b)
        if not ra or not rb:
            print(f"  {a}/{b}: not in the issuing set")
            continue
        generic = build_vocabulary(names_by_country[ra["country"]])
        print()
        print(f"  --- {a} vs {b} ({ra['country']}) ---")
        print(f"    A norm   : {ra['name_norm']}")
        print(f"    B norm   : {rb['name_norm']}")
        print(f"    A markers: {sorted(discriminators(ra['name_norm'], places))}")
        print(f"    B markers: {sorted(discriminators(rb['name_norm'], places))}")
        da = distinctive(ra["name_norm"], generic)
        db = distinctive(rb["name_norm"], generic)
        print(f"    A distinct: {sorted(da)}")
        print(f"    B distinct: {sorted(db)}")
        if da and db:
            print(f"    overlap   : {len(da & db) / len(da | db):.3f}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
