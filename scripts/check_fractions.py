import re
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

MONEY_COLS = [
    "Total Credits Issued",
    "Total Credits Retired",
    "Total Credits Remaining",
    "Total Buffer Pool Deposits",
    "PERs",
]


def squash(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def main() -> int:
    path = sorted(p for p in RAW_DIR.glob("*.xls*") if not p.name.startswith("~$"))[0]
    df = pd.read_excel(path, sheet_name="PROJECTS", header=3)
    df.columns = [squash(c) for c in df.columns]

    print(f"FILE: {path.name}")
    print()

    for col in MONEY_COLS:
        if col not in df.columns:
            print(f"{col}: column not found")
            continue
        values = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        frac = (values - values.round()).abs()
        has_frac = frac > 1e-9
        print(f"[{col}]")
        print(f"  rows with a fractional part : {int(has_frac.sum())}")
        if has_frac.any():
            print(f"  largest fractional part     : {frac.max():.6f}")
            print(f"  sum of fractional parts     : {frac.sum():.6f}")
            sample = df.loc[has_frac, ["Project ID", "Voluntary Registry", col]].head(5)
            print(sample.to_string(index=False))
        print()

    issued = pd.to_numeric(df["Total Credits Issued"], errors="coerce").fillna(0.0)
    exact = sum((Decimal(str(v)) for v in issued), Decimal(0))
    print("[ Total Credits Issued — three ways of summing ]")
    print(f"  truncated float sum  (phase 0 method) : {int(issued.sum()):,}")
    print(f"  rounded per row then summed (ingest)  : {int(issued.round().sum()):,}")
    print(f"  exact decimal sum                     : {exact}")
    print()

    # The vintage block, same question.
    raw = pd.read_excel(path, sheet_name="PROJECTS", header=None, nrows=3)
    cols = list(df.columns)
    start = next(
        c for c in range(raw.shape[1])
        if isinstance(raw.iat[2, c], str)
        and "issued by vintage" in squash(raw.iat[2, c]).lower()
    )
    labels = [c for c in range(raw.shape[1])
              if isinstance(raw.iat[2, c], str) and squash(raw.iat[2, c])]
    stop = next(c for c in labels if c > start)
    block = df.iloc[:, [i for i in range(start, stop)
                        if re.match(r"^(19|20)\d\d(\.\d+)?$", squash(cols[i]))]]
    block = block.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    cell_frac = (block - block.round()).abs()
    print("[ issued-by-vintage block ]")
    print(f"  cells with a fractional part : {int((cell_frac > 1e-9).to_numpy().sum())}")
    print(f"  largest fractional part      : {cell_frac.to_numpy().max():.6f}")
    print(f"  truncated sum                : {int(block.to_numpy().sum()):,}")
    print(f"  rounded-cell sum             : {int(block.round().to_numpy().sum()):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
