import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.serials import parse  # noqa: E402

SHEETS = [
    ("ACR Retirements", "Credit Serial Numbers", "Quantity of Credits", "ACR"),
    ("ACR Issuances", "Credit Serial Numbers", "Quantity of Credits", "ACR"),
    ("ACR Cancelations", "Credit Serial Numbers", "Quantity of Credits", "ACR"),
    ("CAR Retirements", "Offset Credit Serial Numbers",
     "Quantity of Offset Credits", "CAR"),
    ("CAR Cancellations", "Offset Credit Serial Numbers",
     "Quantity of Offset Credits", "CAR"),
    ("Gold Retirements", "Serial Number", "Quantity", "GOLD"),
    ("Verra VCS Retirements", "Serial Number", "Retirement QTY", "VCS"),
    ("Verra VCS Issuances", "Serial Number", None, "VCS"),
]


def squash(v):
    return re.sub(r"\s+", " ", str(v)).strip()


def main() -> int:
    path = sorted((ROOT / "data" / "raw").glob("VROD-registry-files*"))[0]
    for sheet, serial_col, qty_col, registry in SHEETS:
        df = pd.read_excel(path, sheet_name=sheet)
        df.columns = [squash(c) for c in df.columns]
        if serial_col not in df.columns:
            print(f"{sheet}: column {serial_col!r} missing")
            continue

        rows = len(df)
        parsed_rows = 0
        total_ranges = 0
        matched = mismatched = 0
        examples = []

        qty = (
            pd.to_numeric(df[qty_col], errors="coerce")
            if qty_col and qty_col in df.columns else None
        )

        for i, raw in enumerate(df[serial_col]):
            ranges = parse(raw, registry)
            if not ranges:
                if len(examples) < 3 and str(raw) != "nan":
                    examples.append(str(raw)[:70])
                continue
            parsed_rows += 1
            total_ranges += len(ranges)
            if qty is not None and not pd.isna(qty.iloc[i]):
                counted = sum(r.count for r in ranges)
                if counted == int(qty.iloc[i]):
                    matched += 1
                else:
                    mismatched += 1

        print("=" * 68)
        print(f"{sheet}  ({rows:,} rows)")
        print(f"  parsed            : {parsed_rows:,} ({100*parsed_rows/rows:.2f}%)")
        print(f"  ranges extracted  : {total_ranges:,}")
        if qty is not None:
            checked = matched + mismatched
            if checked:
                print(f"  quantity matches  : {matched:,} of {checked:,} "
                      f"({100*matched/checked:.2f}%)")
        if examples:
            print(f"  unparsed examples : {examples}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
