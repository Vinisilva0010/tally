import hashlib
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
REPORT = ROOT / "data" / "source_report.txt"

INTERESTING = re.compile(
    r"serial|vintage|registry|country|region|developer|proponent|owner|"
    r"methodolog|protocol|project\s*id|project\s*name|type|status|"
    r"issu|retir|cancel|credit|tonne|date|year",
    re.IGNORECASE,
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_header_row(frame: pd.DataFrame, scan_rows: int = 12) -> int:
    best_row, best_score = 0, -1
    for idx in range(min(scan_rows, len(frame))):
        row = frame.iloc[idx]
        score = sum(1 for v in row if isinstance(v, str) and v.strip())
        if score > best_score:
            best_row, best_score = idx, score
    return best_row


def main() -> int:
    files = sorted(p for p in RAW_DIR.glob("*.xls*") if not p.name.startswith("~$"))
    if not files:
        print(f"No spreadsheet found in {RAW_DIR}")
        return 1

    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)
        print(text)

    for path in files:
        out("=" * 70)
        out(f"FILE   : {path.name}")
        out(f"SIZE   : {path.stat().st_size / 1_048_576:.2f} MB")
        out(f"SHA256 : {sha256_of(path)}")

        book = pd.ExcelFile(path, engine="openpyxl")
        out(f"SHEETS : {book.sheet_names}")

        for sheet in book.sheet_names:
            frame = pd.read_excel(path, sheet_name=sheet, header=None)
            header_row = find_header_row(frame)
            headers = [
                str(v).strip()
                for v in frame.iloc[header_row].tolist()
                if isinstance(v, str) and str(v).strip()
            ]
            data_rows = len(frame) - header_row - 1

            out("")
            out("-" * 70)
            out(f"SHEET '{sheet}'")
            out(f"  header row index : {header_row}")
            out(f"  data rows        : {data_rows}")
            out(f"  columns          : {len(headers)}")
            for i, name in enumerate(headers):
                mark = " <<<" if INTERESTING.search(name) else ""
                out(f"    [{i:>3}] {name}{mark}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print()
    print(f"Report saved to: {REPORT}")
    print(f"Report lines   : {len(lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
