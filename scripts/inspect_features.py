import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.detect import MILLI  # noqa: E402

DB = ROOT / "data" / "tally.sqlite"

# Pairs we have already judged by hand during phase 0 and phase 2.
TRUE_PAIRS = [
    ("ACR0931", "CAR2112"), ("GS3015", "VCS900"), ("GS1588", "VCS1887"),
    ("GS1378", "VCS1886"), ("CAR495", "VCS80"), ("GS7754", "VCS924"),
    ("GS1371", "VCS783"), ("GS5064", "VCS1692"), ("GS4532", "VCS1693"),
    ("GS2405", "VCS370"), ("GS7615", "VCS1781"), ("GS23339", "VCS3881"),
    ("ACR0234", "CAR1582"),
]

FALSE_PAIRS = [
    ("ACR1064", "CAR444"), ("ACR1064", "CAR517"), ("ACR1064", "CAR509"),
    ("GS2405", "VCS1890"), ("ACR0202", "CAR2047"), ("ACR0393", "CAR2047"),
    ("ACR0695", "CAR2218"), ("GS2405", "VCS384"), ("ACR0377", "CAR973"),
    ("ACR0395", "CAR672"),
]

FIELDS = ["registry", "name", "developer", "owner", "type", "scope",
          "methodology", "methodology_version", "country", "state",
          "site_location", "first_vintage", "total_issued_milli"]


def get(conn, pid):
    row = conn.execute(
        f"SELECT {', '.join(FIELDS)} FROM project WHERE project_id = ?", (pid,)
    ).fetchone()
    return row


def vintages(conn, pid):
    rows = conn.execute(
        "SELECT year, credits_milli FROM credit_year "
        "WHERE kind='issued_vintage' AND credits_milli>0 AND project_id=? "
        "ORDER BY year",
        (pid,),
    ).fetchall()
    return {r["year"]: r["credits_milli"] for r in rows}


def show(conn, label, pairs):
    print("=" * 74)
    print(label)
    print("=" * 74)
    for a, b in pairs:
        ra, rb = get(conn, a), get(conn, b)
        if ra is None or rb is None:
            print(f"\n  {a} / {b}: NOT FOUND")
            continue
        print()
        print(f"  --- {a} ({ra['registry']})  vs  {b} ({rb['registry']}) ---")
        for f in ["name", "developer", "owner", "type", "scope",
                  "methodology", "methodology_version", "state",
                  "site_location", "first_vintage"]:
            va = str(ra[f])[:52] if ra[f] is not None else "-"
            vb = str(rb[f])[:52] if rb[f] is not None else "-"
            flag = "SAME" if (ra[f] is not None and ra[f] == rb[f]) else "diff"
            print(f"    {f:<20} [{flag}] {va}")
            print(f"    {'':<20}        {vb}")
        va, vb = vintages(conn, a), vintages(conn, b)
        shared = sorted(set(va) & set(vb))
        print(f"    vintages A           {sorted(va)}")
        print(f"    vintages B           {sorted(vb)}")
        print(f"    shared               {shared}")
        for y in shared:
            print(f"      {y}: A={va[y]/MILLI:>12,.0f}  B={vb[y]/MILLI:>12,.0f}"
                  f"  ratio={va[y]/vb[y]:.3f}" if vb[y] else "")


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # How often does each field agree, overall?
    print("=" * 74)
    print("FIELD AGREEMENT RATE ACROSS KNOWN PAIRS")
    print("=" * 74)
    for label, pairs in [("TRUE", TRUE_PAIRS), ("FALSE", FALSE_PAIRS)]:
        counts = {f: 0 for f in ["developer", "owner", "type", "scope",
                                 "methodology", "state", "first_vintage"]}
        total = 0
        for a, b in pairs:
            ra, rb = get(conn, a), get(conn, b)
            if ra is None or rb is None:
                continue
            total += 1
            for f in counts:
                if ra[f] is not None and ra[f] == rb[f]:
                    counts[f] += 1
        print(f"\n  {label} pairs ({total}):")
        for f, c in counts.items():
            print(f"    {f:<18} agrees in {c}/{total}")

    print()
    show(conn, "KNOWN TRUE PAIRS (confirmed vintage overlap)", TRUE_PAIRS[:5])
    print()
    show(conn, "KNOWN FALSE PAIRS (different projects)", FALSE_PAIRS[:5])

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
