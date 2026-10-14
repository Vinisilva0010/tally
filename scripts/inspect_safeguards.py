import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "safeguards_report.txt"

TARGETS = {
    "ACR Retirements": ["Corresponding Adjustment Reported",
                        "Host Country Letter of Authorization",
                        "CORSIA Double Claiming Compensation Mech",
                        "Credit Holder", "Retired On Behalf Of",
                        "Retirement Reason", "Status of Credits",
                        "Credit Serial Numbers", "Project Id", "Vintage"],
    "ACR Cancelations": ["Cancellation Reason", "Credit Holder",
                         "Corresponding Adjustment Reported",
                         "Credit Serial Numbers", "Project Id", "Vintage"],
    "CAR Retirements": ["Corresponding Adjustment", "Account Holder",
                        "Retirement Reason", "Offset Credit Serial Numbers",
                        "Project ID", "Vintage"],
    "CAR Cancellations": ["Cancellation Reason",
                          "Offset Credit Serial Numbers",
                          "Project ID", "Vintage"],
    "Gold Retirements": ["Article Six Authorization", "Using Entity",
                         "Serial Number", "GSID", "Vintage", "Credit Status"],
    "Verra VCS Retirements": ["Beneficial Owner", "Serial Number",
                              "Project ID", "Vintage", "Retirement QTY"],
    "Verra VCS Cancellations": ["Serial Number", "Project ID", "Vintage"],
}

VALUE_COLUMNS = {
    "Corresponding Adjustment Reported", "Corresponding Adjustment",
    "Cancellation Reason", "Retirement Reason", "Status of Credits",
    "Article Six Authorization", "Credit Status",
    "Host Country Letter of Authorization",
}


def squash(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip()


def main() -> int:
    path = sorted(RAW.glob("VROD-registry-files*"))[0]
    lines = []

    def out(t=""):
        lines.append(t)
        print(t)

    for sheet, wanted in TARGETS.items():
        df = pd.read_excel(path, sheet_name=sheet)
        df.columns = [squash(c) for c in df.columns]
        out("=" * 72)
        out(f"{sheet}  ->  {len(df):,} rows")
        out("=" * 72)
        for want in wanted:
            col = next((c for c in df.columns if c.startswith(want[:38])), None)
            if col is None:
                out(f"  {want[:44]:<46} COLUMN NOT FOUND")
                continue
            filled = df[col].notna().sum()
            pct = 100 * filled / len(df) if len(df) else 0
            out(f"  {col[:44]:<46} {filled:>7,} filled  {pct:>6.2f}%")
            if col in VALUE_COLUMNS and filled:
                counts = df[col].value_counts().head(8)
                for value, n in counts.items():
                    out(f"      {squash(value)[:52]:<54} {n:>7,}")
        out("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
