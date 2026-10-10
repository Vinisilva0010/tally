import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "data" / "overlap_report.txt"

YEAR = re.compile(r"^(19|20)\d\d(\.\d+)?$")


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def pick(columns, *needles):
    for col in columns:
        low = str(col).lower()
        if all(n.lower() in low for n in needles):
            return col
    return None


def main() -> int:
    path = sorted(p for p in RAW_DIR.glob("*.xls*") if not p.name.startswith("~$"))[0]
    raw = pd.read_excel(path, sheet_name="PROJECTS", header=None, nrows=3)
    df = pd.read_excel(path, sheet_name="PROJECTS", header=3)
    cols = list(df.columns)

    # Every block of year columns is introduced by a label on raw row 2.
    # A block therefore ends where the next label begins.
    labels = {
        c: clean(raw.iat[2, c])
        for c in range(raw.shape[1])
        if isinstance(raw.iat[2, c], str) and clean(raw.iat[2, c])
    }
    label_cols = sorted(labels)

    start = next(
        (c for c in label_cols if "issued by vintage" in labels[c].lower()), None
    )
    if start is None:
        print("Could not locate the 'issued by vintage' block label.")
        return 1

    nxt = next((c for c in label_cols if c > start), len(cols))
    block = [i for i in range(start, nxt) if YEAR.match(clean(cols[i]))]
    years = [int(float(clean(cols[i]))) for i in block]

    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)

    out("=" * 72)
    out("A. BLOCK BOUNDARIES (from the labels on raw row 2)")
    out("=" * 72)
    for c in label_cols:
        if c >= 20:
            out(f"  col {c:>3} : {labels[c][:78]}")
    out("")
    out(f"  issued-by-vintage block : cols {block[0]}-{block[-1]} "
        f"({len(block)} cols), years {years[0]}..{years[-1]}")

    c_id = pick(cols, "project id")
    c_name = pick(cols, "project name")
    c_reg = pick(cols, "voluntary", "registry")
    c_country = pick(cols, "country")
    c_type = "Type" if "Type" in cols else pick(cols, "type")
    c_issued = pick(cols, "total credits", "issued")

    vint = df.iloc[:, block].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    vint.columns = years
    total_issued = pd.to_numeric(df[c_issued], errors="coerce").fillna(0)

    # Validation: the vintage block must reconcile with the issued total.
    row_sum = vint.sum(axis=1)
    diff = (row_sum - total_issued).abs()
    out("")
    out("=" * 72)
    out("B. VALIDATION: sum of vintage block vs Total Credits Issued")
    out("=" * 72)
    for tol in (1, 100, 10_000):
        out(f"  rows differing by more than {tol:>7,} : {int((diff > tol).sum())}")
    out(f"  largest absolute difference         : {int(diff.max()):,}")
    out(f"  block grand total                   : {int(row_sum.sum()):,}")
    out(f"  Total Credits Issued grand total    : {int(total_issued.sum()):,}")
    out("  (if these do not match, the slice is wrong and everything below is void)")

    norm = (
        df[c_name].astype(str).str.lower()
        .str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
    )

    results = []
    for key, idx in df.groupby(norm).groups.items():
        if len(str(key)) <= 8:
            continue
        rows = df.loc[idx]
        if rows[c_reg].nunique() < 2:
            continue
        issuing = [i for i in idx if total_issued.loc[i] > 0]
        if len({df.loc[i, c_reg] for i in issuing}) < 2:
            continue

        per_reg: dict[str, np.ndarray] = {}
        for i in issuing:
            reg = str(df.loc[i, c_reg])
            per_reg[reg] = per_reg.get(reg, np.zeros(len(years))) + vint.loc[i].to_numpy(float)

        regs = sorted(per_reg)
        stacked = np.vstack([per_reg[r] for r in regs])
        overlap_mask = (stacked > 0).all(axis=0)
        overlap_years = [y for y, m in zip(years, overlap_mask) if m]
        duplicated = float(
            (stacked.sum(axis=0) - stacked.max(axis=0))[overlap_mask].sum()
        )

        countries = sorted({clean(df.loc[i, c_country]) for i in issuing})
        results.append({
            "key": str(key),
            "pids": [clean(df.loc[i, c_id]) for i in issuing],
            "regs": regs,
            "per_reg": {r: int(per_reg[r].sum()) for r in regs},
            "overlap_years": overlap_years,
            "duplicated": duplicated,
            "same_country": len(countries) == 1,
            "countries": countries,
            "types": sorted({clean(df.loc[i, c_type]) for i in issuing}),
        })

    hit = [r for r in results if r["overlap_years"]]
    clean_move = [r for r in results if not r["overlap_years"]]
    same_country = [r for r in hit if r["same_country"]]

    out("")
    out("=" * 72)
    out("C. SUMMARY")
    out("=" * 72)
    out(f"  pairs issuing in 2+ registries          : {len(results)}")
    out(f"  WITH overlapping vintage years          : {len(hit)}")
    out(f"    of those, same country on both sides  : {len(same_country)}")
    out(f"  WITHOUT overlap (clean registry move)   : {len(clean_move)}")
    out(f"  duplicated credits in overlapping years : "
        f"{int(sum(r['duplicated'] for r in hit)):,}")
    out(f"    restricted to same-country pairs      : "
        f"{int(sum(r['duplicated'] for r in same_country)):,}")

    out("")
    out("=" * 72)
    out("D. ALL PAIRS WITH VINTAGE OVERLAP")
    out("=" * 72)
    for r in sorted(hit, key=lambda x: -x["duplicated"]):
        yrs = r["overlap_years"]
        out("")
        out(f"  {int(r['duplicated']):>12,}  {r['key'][:58]}")
        out(f"                ids {r['pids']}  regs {r['regs']}")
        out(f"                issued per registry: {r['per_reg']}")
        out(f"                overlapping vintages: {yrs}")
        out(f"                country {r['countries']}  type {r['types']}")

    out("")
    out("=" * 72)
    out("E. CLEAN REGISTRY MOVES (no vintage overlap) — sample of 10")
    out("=" * 72)
    for r in clean_move[:10]:
        out(f"  {r['key'][:56]}  {r['regs']}  ids {r['pids']}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report saved to: {OUT}")
    print(f"Report lines   : {len(lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
