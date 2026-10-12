import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.detect import MILLI  # noqa: E402
from tally.link import find_candidates  # noqa: E402

DB = ROOT / "data" / "tally.sqlite"
CSV_OUT = ROOT / "data" / "review_sheet.csv"
TXT_OUT = ROOT / "data" / "review_sheet.txt"


def verra_url(project_id: str) -> str:
    digits = project_id.replace("VCS", "").strip()
    if digits.isdigit():
        return f"https://registry.verra.org/app/projectDetail/VCS/{digits}"
    return ""


def details(conn, pid):
    return conn.execute(
        "SELECT project_id, registry, name, developer, owner, type, "
        "methodology, country, state, site_location, first_vintage, "
        "total_issued_milli, registry_documents, project_website "
        "FROM project WHERE project_id = ?",
        (pid,),
    ).fetchone()


def vintages(conn, pid):
    return {
        r["year"]: r["credits_milli"]
        for r in conn.execute(
            "SELECT year, credits_milli FROM credit_year WHERE "
            "kind='issued_vintage' AND credits_milli>0 AND project_id=? "
            "ORDER BY year",
            (pid,),
        )
    }


def link_for(row) -> str:
    for field in ("registry_documents", "project_website"):
        value = row[field]
        if value and value.strip().startswith("http"):
            return value.strip()
    return verra_url(row["project_id"])


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    candidates, _ = find_candidates(conn)

    queue = [
        c for c in candidates
        if c.shared_vintages and not c.exact_name
    ]
    queue.sort(key=lambda c: -c.duplicated_milli)

    lines = []
    rows = []
    for n, c in enumerate(queue, 1):
        a, b = details(conn, c.project_a), details(conn, c.project_b)
        va, vb = vintages(conn, c.project_a), vintages(conn, c.project_b)
        la, lb = link_for(a), link_for(b)

        lines.append("=" * 76)
        lines.append(f"PAIR {n} of {len(queue)}   "
                     f"duplicated if same project: "
                     f"{c.duplicated_milli / MILLI:,.0f} credits")
        lines.append("=" * 76)
        for side, row, link in ((" A", a, la), (" B", b, lb)):
            lines.append(f"{side}  {row['registry']}  {row['project_id']}")
            lines.append(f"     name       {row['name']}")
            lines.append(f"     developer  {row['developer'] or '-'}")
            lines.append(f"     method     {(row['methodology'] or '-')[:62]}")
            lines.append(f"     where      {row['country']}"
                         f"{' / ' + row['state'] if row['state'] else ''}"
                         f"{' / ' + row['site_location'] if row['site_location'] else ''}")
            lines.append(f"     issued     "
                         f"{row['total_issued_milli'] / MILLI:,.0f}")
            lines.append(f"     link       {link or 'no link in dataset'}")
        lines.append(f"     shared vintages:")
        for y in c.shared_vintages:
            lines.append(f"       {y}   A={va[y]/MILLI:>12,.0f}   "
                         f"B={vb[y]/MILLI:>12,.0f}")
        lines.append("")
        lines.append("     LABEL: 1 = same physical project, 0 = different, "
                     "? = cannot tell")
        lines.append("")

        rows.append({
            "pair": n, "label": "", "notes": "",
            "duplicated_credits": round(c.duplicated_milli / MILLI, 3),
            "project_a": a["project_id"], "registry_a": a["registry"],
            "name_a": a["name"], "link_a": la,
            "project_b": b["project_id"], "registry_b": b["registry"],
            "name_b": b["name"], "link_b": lb,
            "shared_vintages": " ".join(str(y) for y in c.shared_vintages),
        })

    conn.close()

    TXT_OUT.write_text("\n".join(lines), encoding="utf-8")
    with CSV_OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("\n".join(lines))
    print(f"Sheet: {TXT_OUT}")
    print(f"CSV:   {CSV_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
