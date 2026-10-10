import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data"


def clean(name: object) -> str:
    return re.sub(r"\s+", " ", str(name)).strip()


def pick(columns: list[str], *needles: str) -> str | None:
    for col in columns:
        low = col.lower()
        if all(n.lower() in low for n in needles):
            return col
    return None


def main() -> int:
    files = sorted(p for p in RAW_DIR.glob("*.xls*") if not p.name.startswith("~$"))
    if not files:
        print(f"No spreadsheet found in {RAW_DIR}")
        return 1
    path = files[0]

    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)

    # --- Column Descriptions sheet, saved verbatim ---
    desc = pd.read_excel(path, sheet_name="Column Descriptions", header=0)
    desc.to_csv(OUT_DIR / "column_descriptions.csv", index=False)

    # --- READ FIRST sheet, saved verbatim ---
    read_first = pd.read_excel(path, sheet_name="READ FIRST", header=None)
    (OUT_DIR / "read_first.txt").write_text(
        "\n".join(
            clean(v)
            for v in read_first.iloc[:, 0].tolist()
            if isinstance(v, str) and clean(v)
        ),
        encoding="utf-8",
    )

    # --- PROJECTS ---
    df = pd.read_excel(path, sheet_name="PROJECTS", header=3)
    df.columns = [clean(c) for c in df.columns]
    cols = list(df.columns)

    c_registry = pick(cols, "voluntary", "registry")
    c_status = pick(cols, "voluntary", "status")
    c_arb_id = pick(cols, "arb", "id")
    c_poa = pick(cols, "poa", "aggregate")
    c_issued = pick(cols, "issued")
    c_retired = pick(cols, "retired")
    c_remaining = pick(cols, "remaining")
    c_buffer = pick(cols, "buffer", "deposits")
    c_name = pick(cols, "project name")
    c_country = pick(cols, "country")
    c_dev = pick(cols, "developer")

    out(f"PROJECTS rows: {len(df)}")
    out("")

    out("[ Voluntary Registry ]")
    out(df[c_registry].value_counts(dropna=False).to_string())
    out("")

    out("[ Voluntary Status ]")
    out(df[c_status].value_counts(dropna=False).head(15).to_string())
    out("")

    out("[ Cross-listing counts ]")
    out(f"  with ARB/WA ID        : {df[c_arb_id].notna().sum()}")
    out(f"  with PoA/Aggregate ID : {df[c_poa].notna().sum()}")
    out("")

    out("[ Null counts on linkage columns ]")
    for col in [c_name, c_country, c_dev, pick(cols, "methodology / protocol"),
                pick(cols, "first year")]:
        if col:
            out(f"  {col:<34} nulls: {df[col].isna().sum()}")
    out("")

    issued = pd.to_numeric(df[c_issued], errors="coerce").fillna(0)
    retired = pd.to_numeric(df[c_retired], errors="coerce").fillna(0)
    remaining = pd.to_numeric(df[c_remaining], errors="coerce").fillna(0)
    buffer_dep = pd.to_numeric(df[c_buffer], errors="coerce").fillna(0)

    out("[ Totals ]")
    out(f"  issued    : {int(issued.sum()):,}")
    out(f"  retired   : {int(retired.sum()):,}")
    out(f"  remaining : {int(remaining.sum()):,}")
    out("")

    out("[ Accounting identity: issued - retired - remaining - buffer ]")
    delta = issued - retired - remaining - buffer_dep
    for tol in (0, 1, 100, 10_000):
        out(f"  rows deviating by more than {tol:>6,}: {(delta.abs() > tol).sum()}")
    out(f"  retired > issued                   : {(retired > issued).sum()}")
    out(f"  negative remaining                 : {(remaining < 0).sum()}")
    out("")

    out("[ Same project name in more than one registry ]")
    norm = df[c_name].astype(str).str.lower().str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
    grp = df.assign(_norm=norm).groupby("_norm")[c_registry].nunique()
    dupes = grp[grp > 1]
    out(f"  normalized names spanning 2+ registries: {len(dupes)}")
    out("")

    # --- Archive ---
    arc = pd.read_excel(path, sheet_name="Archive", header=1)
    arc.columns = [clean(c) for c in arc.columns]
    a_issued = pick(list(arc.columns), "issued")
    a_retired = pick(list(arc.columns), "retired")
    arc_issued = pd.to_numeric(arc[a_issued], errors="coerce").fillna(0)
    arc_retired = pd.to_numeric(arc[a_retired], errors="coerce").fillna(0)

    out("[ Archive sheet ]")
    out(f"  archived projects                 : {len(arc)}")
    out(f"  archived with credits issued      : {(arc_issued > 0).sum()}")
    out(f"  archived with credits retired     : {(arc_retired > 0).sum()}")
    out(f"  total credits retired on archived : {int(arc_retired.sum()):,}")

    report = "\n".join(lines)
    (OUT_DIR / "profile_report.txt").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
