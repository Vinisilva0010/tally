import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "data" / "rules_report.txt"

TARGET = re.compile(
    r"issued|retired|remaining|buffer|reversal|arb|wa|poa|aggregate|status",
    re.IGNORECASE,
)


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def pick(columns, *needles):
    for col in columns:
        low = col.lower()
        if all(n.lower() in low for n in needles):
            return col
    return None


def main() -> int:
    path = sorted(p for p in RAW_DIR.glob("*.xls*") if not p.name.startswith("~$"))[0]
    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)

    # 1. Official definitions for the credit-accounting columns
    desc = pd.read_excel(path, sheet_name="Column Descriptions", header=0)
    desc.columns = [clean(c) for c in desc.columns]
    header_col, detail_col = desc.columns[1], desc.columns[2]

    out("=" * 70)
    out("OFFICIAL COLUMN DEFINITIONS (credit accounting + cross-listing)")
    out("=" * 70)
    for _, row in desc.iterrows():
        name = clean(row[header_col])
        if name and name.lower() != "nan" and TARGET.search(name):
            body = clean(row[detail_col])
            out("")
            out(f"### {name}")
            out(body[:900])

    df = pd.read_excel(path, sheet_name="PROJECTS", header=3)
    df.columns = [clean(c) for c in df.columns]
    cols = list(df.columns)

    c_id = pick(cols, "project id")
    c_name = pick(cols, "project name")
    c_reg = pick(cols, "voluntary", "registry")
    c_issued = pick(cols, "issued")
    c_retired = pick(cols, "retired")
    c_remaining = pick(cols, "remaining")
    c_poa = pick(cols, "poa", "aggregate")
    c_arb_status = pick(cols, "arb", "status")
    c_reg_arb = pick(cols, "registry /", "arb")

    issued = pd.to_numeric(df[c_issued], errors="coerce").fillna(0)
    retired = pd.to_numeric(df[c_retired], errors="coerce").fillna(0)

    out("")
    out("=" * 70)
    out("RULE R1 — retired greater than issued")
    out("=" * 70)
    hits = df.loc[retired > issued, [c_id, c_name, c_reg]].copy()
    hits["issued"] = issued[retired > issued].astype("int64")
    hits["retired"] = retired[retired > issued].astype("int64")
    hits["gap"] = hits["retired"] - hits["issued"]
    out(hits.sort_values("gap", ascending=False).to_string(index=False, max_colwidth=46))

    out("")
    out("=" * 70)
    out("RULE R5 — do aggregate programmes appear as their own row?")
    out("=" * 70)
    ids = set(df[c_id].astype(str).str.strip())
    poa = df[c_poa].dropna().astype(str).str.strip()
    poa = poa[poa != ""]
    matched = sorted({p for p in poa.unique() if p in ids})
    out(f"  distinct aggregate IDs referenced : {poa.nunique()}")
    out(f"  of those, also present as a row   : {len(matched)}")
    out(f"  sample of matches                 : {matched[:12]}")

    out("")
    out("=" * 70)
    out("RULE R3 — compliance-market cross listing")
    out("=" * 70)
    out(f"[ {c_reg_arb} ]")
    out(df[c_reg_arb].value_counts(dropna=False).head(12).to_string())
    out("")
    out(f"[ {c_arb_status} ]")
    out(df[c_arb_status].value_counts(dropna=False).head(12).to_string())

    out("")
    out("=" * 70)
    out("RULE R4 — same project name across registries (sample)")
    out("=" * 70)
    norm = (
        df[c_name].astype(str).str.lower()
        .str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
    )
    tmp = df.assign(_norm=norm)
    counts = tmp.groupby("_norm")[c_reg].nunique()
    multi = counts[counts > 1].index
    sample = (
        tmp[tmp["_norm"].isin(multi)]
        .sort_values("_norm")[[c_id, c_name, c_reg, c_issued]]
        .head(30)
    )
    out(sample.to_string(index=False, max_colwidth=44))

    report = "\n".join(lines)
    OUT.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
