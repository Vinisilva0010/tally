import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "data" / "overlap_report.txt"


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

    # Locate the "issued by vintage" block from the label on raw row 2.
    start = None
    for c in range(raw.shape[1]):
        v = raw.iat[2, c]
        if isinstance(v, str) and "issued by vintage" in v.lower():
            start = c
            break
    if start is None:
        print("Could not locate the 'issued by vintage' block label.")
        return 1

    end = start
    while end + 1 < len(cols) and re.match(r"^(19|20)\d\d(\.\d+)?$", clean(cols[end + 1])):
        end += 1

    vintage_cols = list(range(start, end + 1))
    years = [int(float(clean(cols[i]))) for i in vintage_cols]

    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)

    out("=" * 72)
    out("VINTAGE BLOCK")
    out("=" * 72)
    out(f"  columns {start}-{end} ({len(vintage_cols)} cols)")
    out(f"  years {years[0]} .. {years[-1]}")

    c_id = pick(cols, "project id")
    c_name = pick(cols, "project name")
    c_reg = pick(cols, "voluntary", "registry")
    c_country = pick(cols, "country")
    c_type = pick(cols, "^type") or "Type"
    c_issued = pick(cols, "total credits", "issued")

    vint = df.iloc[:, vintage_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    vint.columns = years

    norm = (
        df[c_name].astype(str).str.lower()
        .str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
    )
    total_issued = pd.to_numeric(df[c_issued], errors="coerce").fillna(0)

    results = []
    for key, idx in df.groupby(norm).groups.items():
        if len(str(key)) <= 8:
            continue
        block = df.loc[idx]
        if block[c_reg].nunique() < 2:
            continue
        issuing = [i for i in idx if total_issued.loc[i] > 0]
        if len({df.loc[i, c_reg] for i in issuing}) < 2:
            continue

        per_reg: dict[str, np.ndarray] = {}
        for i in issuing:
            reg = str(df.loc[i, c_reg])
            vec = vint.loc[i].to_numpy(dtype=float)
            per_reg[reg] = per_reg.get(reg, np.zeros(len(years))) + vec

        regs = sorted(per_reg)
        active = {r: (per_reg[r] > 0) for r in regs}
        overlap_mask = np.ones(len(years), dtype=bool)
        for r in regs:
            overlap_mask &= active[r]

        overlap_years = [y for y, m in zip(years, overlap_mask) if m]
        stacked = np.vstack([per_reg[r] for r in regs])
        # credits that would vanish if each overlapping vintage were counted once
        duplicated = float(
            (stacked.sum(axis=0) - stacked.max(axis=0))[overlap_mask].sum()
        )

        countries = sorted({clean(df.loc[i, c_country]) for i in issuing})
        types = sorted({clean(df.loc[i, c_type]) for i in issuing}) if c_type in df else []

        results.append({
            "key": str(key),
            "pids": [clean(df.loc[i, c_id]) for i in issuing],
            "regs": regs,
            "overlap_years": overlap_years,
            "duplicated": duplicated,
            "same_country": len(countries) == 1,
            "countries": countries,
            "types": types,
        })

    with_overlap = [r for r in results if r["overlap_years"]]
    no_overlap = [r for r in results if not r["overlap_years"]]
    same_country = [r for r in with_overlap if r["same_country"]]

    out("")
    out("=" * 72)
    out("SUMMARY")
    out("=" * 72)
    out(f"  pairs issuing in 2+ registries          : {len(results)}")
    out(f"  WITH overlapping vintage years          : {len(with_overlap)}")
    out(f"    of those, same country on both sides  : {len(same_country)}")
    out(f"  WITHOUT overlap (clean registry move)   : {len(no_overlap)}")
    out(f"  duplicated credits in overlapping years : "
        f"{int(sum(r['duplicated'] for r in with_overlap)):,}")
    out(f"    restricted to same-country pairs      : "
        f"{int(sum(r['duplicated'] for r in same_country)):,}")

    out("")
    out("=" * 72)
    out("TOP 20 BY DUPLICATED CREDITS IN OVERLAPPING VINTAGES")
    out("=" * 72)
    for r in sorted(with_overlap, key=lambda x: -x["duplicated"])[:20]:
        yrs = r["overlap_years"]
        span = f"{yrs[0]}-{yrs[-1]}" if len(yrs) > 1 else str(yrs[0])
        out("")
        out(f"  {int(r['duplicated']):>12,}  {r['key'][:58]}")
        out(f"                ids {r['pids']}  regs {r['regs']}")
        out(f"                overlapping vintages: {span} ({len(yrs)} yrs)")
        out(f"                country {r['countries']}  type {r['types']}")

    out("")
    out("=" * 72)
    out("SAMPLE OF CLEAN REGISTRY MOVES (no vintage overlap)")
    out("=" * 72)
    for r in no_overlap[:8]:
        out(f"  {r['key'][:58]}  {r['regs']}  ids {r['pids']}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report saved to: {OUT}")
    print(f"Report lines   : {len(lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
