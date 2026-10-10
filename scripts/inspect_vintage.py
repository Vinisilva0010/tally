import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "data" / "vintage_report.txt"

YEAR = re.compile(r"^(19[89]\d|20[0-4]\d)(\.\d+)?$")


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
    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)

    raw = pd.read_excel(path, sheet_name="PROJECTS", header=None, nrows=4)
    df = pd.read_excel(path, sheet_name="PROJECTS", header=3)

    out("=" * 70)
    out("A. FULL SHAPE AND BLOCK LABELS")
    out("=" * 70)
    out(f"  PROJECTS shape with header=3 : {df.shape[0]} rows x {df.shape[1]} cols")
    out("")
    out("  Non-empty cells in raw rows 0-2 (these carry the block labels):")
    for r in range(3):
        for c in range(raw.shape[1]):
            v = raw.iat[r, c]
            if isinstance(v, str) and clean(v):
                out(f"    row {r}, col {c:>3} : {clean(v)[:90]}")

    cols = list(df.columns)
    year_idx = [i for i, c in enumerate(cols) if YEAR.match(clean(c))]
    out("")
    out(f"  year-like columns detected : {len(year_idx)}")
    if year_idx:
        out(f"  first index {year_idx[0]}, last index {year_idx[-1]}")
        out("  names at block boundaries:")
        runs, start = [], year_idx[0]
        for a, b in zip(year_idx, year_idx[1:] + [None]):
            if b is None or b != a + 1:
                runs.append((start, a))
                if b is not None:
                    start = b
        for s, e in runs:
            out(f"    cols {s}-{e}  ({e - s + 1} cols)  "
                f"{clean(cols[s])} .. {clean(cols[e])}")

    out("")
    out("  Columns NOT year-like, by index:")
    non_year = [(i, clean(c)) for i, c in enumerate(cols) if i not in set(year_idx)]
    for i, name in non_year:
        out(f"    [{i:>3}] {name[:70]}")

    # --- B. corrected accounting identity ---
    c_id = pick(cols, "project id")
    c_name = pick(cols, "project name")
    c_reg = pick(cols, "voluntary", "registry")
    c_issued = pick(cols, "total credits", "issued")
    c_retired = pick(cols, "total credits", "retired")
    c_remaining = pick(cols, "total credits remaining")

    issued = pd.to_numeric(df[c_issued], errors="coerce").fillna(0)
    retired = pd.to_numeric(df[c_retired], errors="coerce").fillna(0)
    remaining = pd.to_numeric(df[c_remaining], errors="coerce").fillna(0)
    delta = issued - retired - remaining

    out("")
    out("=" * 70)
    out("B. CORRECTED IDENTITY: issued - retired - remaining (no buffer term)")
    out("=" * 70)
    for tol in (0, 1, 100, 10_000):
        out(f"  rows deviating by more than {tol:>7,} : {(delta.abs() > tol).sum()}")
    out(f"  largest absolute deviation          : {int(delta.abs().max()):,}")
    worst = df.loc[delta.abs().sort_values(ascending=False).head(10).index,
                   [c_id, c_name, c_reg]].copy()
    worst["delta"] = delta.loc[worst.index].astype("int64")
    out("")
    out(worst.to_string(index=False, max_colwidth=40))

    # --- C. cross-registry duplicates, quantified ---
    norm = (
        df[c_name].astype(str).str.lower()
        .str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
    )
    work = pd.DataFrame({
        "norm": norm,
        "pid": df[c_id],
        "name": df[c_name],
        "reg": df[c_reg],
        "issued": issued,
    })
    work = work[work["norm"].str.len() > 8]
    grouped = work.groupby("norm")

    both_issuing, listing_only, at_risk_total = [], 0, 0
    for key, block in grouped:
        if block["reg"].nunique() < 2:
            continue
        per_reg = block.groupby("reg")["issued"].sum()
        issuing = per_reg[per_reg > 0]
        if len(issuing) >= 2:
            at_risk = int(issuing.sum() - issuing.max())
            at_risk_total += at_risk
            both_issuing.append((key, dict(issuing.astype("int64")), at_risk))
        else:
            listing_only += 1

    out("")
    out("=" * 70)
    out("C. CROSS-REGISTRY NAME MATCHES, QUANTIFIED")
    out("=" * 70)
    out(f"  groups spanning 2+ registries            : "
        f"{sum(1 for _, b in grouped if b['reg'].nunique() >= 2)}")
    out(f"  of those, issuing in 2+ registries       : {len(both_issuing)}")
    out(f"  of those, listed twice but issuing once  : {listing_only}")
    out(f"  credits on the smaller side(s), summed   : {at_risk_total:,}")
    out("")
    out("  Top 15 by credits on the smaller side:")
    for key, per_reg, at_risk in sorted(both_issuing, key=lambda x: -x[2])[:15]:
        out(f"    {at_risk:>12,}  {key[:52]}")
        out(f"                  {per_reg}")

    report = "\n".join(lines)
    OUT.write_text(report, encoding="utf-8")
    print(f"Report saved to: {OUT}")
    print(f"Report lines   : {len(lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
