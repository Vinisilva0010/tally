import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.features import fold  # noqa: E402

DB = ROOT / "data" / "tally.sqlite"
OUT = ROOT / "data" / "cer_report.txt"

SUFFIX = re.compile(r"\s*-?\s*cer conversion.*$", re.IGNORECASE)


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    lines = []

    def out(t=""):
        lines.append(t)

    conv = conn.execute(
        "SELECT project_id, registry, name, country, type, "
        "total_issued_milli, first_vintage FROM project "
        "WHERE LOWER(name) LIKE '%cer conversion%' "
        "   OR LOWER(developer) LIKE '%transferred from%' "
        "ORDER BY total_issued_milli DESC"
    ).fetchall()

    out("=" * 74)
    out(f"CONVERTED-CREDIT PROJECTS: {len(conv)}")
    out("=" * 74)

    # Strip the conversion suffix and look for the same name elsewhere.
    matched, unmatched = [], []
    for row in conv:
        base = fold(SUFFIX.sub("", row["name"]))
        if len(base) < 9:
            unmatched.append((row, None))
            continue
        twin = conn.execute(
            "SELECT project_id, registry, name, total_issued_milli "
            "FROM project WHERE name_norm = ? AND project_id != ? "
            "AND registry != ?",
            (base, row["project_id"], row["registry"]),
        ).fetchall()
        (matched if twin else unmatched).append((row, twin))

    out(f"  with a same-named project in another registry : {len(matched)}")
    out(f"  without one                                   : {len(unmatched)}")
    out("")

    total_overlap = 0
    out("=" * 74)
    out("MATCHED, WITH SHARED VINTAGES")
    out("=" * 74)
    for row, twins in matched:
        for twin in twins:
            va = {r["year"]: r["credits_milli"] for r in conn.execute(
                "SELECT year, credits_milli FROM credit_year WHERE "
                "kind='issued_vintage' AND credits_milli>0 AND project_id=?",
                (row["project_id"],))}
            vb = {r["year"]: r["credits_milli"] for r in conn.execute(
                "SELECT year, credits_milli FROM credit_year WHERE "
                "kind='issued_vintage' AND credits_milli>0 AND project_id=?",
                (twin["project_id"],))}
            shared = sorted(set(va) & set(vb))
            if not shared:
                continue
            dup = sum(va[y] + vb[y] - max(va[y], vb[y]) for y in shared)
            total_overlap += dup
            out("")
            out(f"  {dup/1000:>12,.0f}  {row['country']}  vintages {shared}")
            out(f"    {row['registry']:<5} {row['project_id']:<10} "
                f"{row['name'][:56]}")
            out(f"    {twin['registry']:<5} {twin['project_id']:<10} "
                f"{twin['name'][:56]}")

    out("")
    out("=" * 74)
    out("SUMMARY")
    out("=" * 74)
    out(f"  converted-credit projects        : {len(conv)}")
    out(f"  credits on them                  : "
        f"{sum(r['total_issued_milli'] for r in conv)/1000:,.0f}")
    out(f"  overlapping credits with a twin  : {total_overlap/1000:,.0f}")

    conn.close()
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[-40:]))
    print()
    print(f"Full: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
