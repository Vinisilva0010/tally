"""Read the Voluntary Registry Offsets Database into a SQLite database.

The source is a single spreadsheet whose PROJECTS sheet carries 170 columns:
scalar project attributes plus four blocks of per-year columns. Each block is
introduced by a label on raw row 2, which is how the blocks are told apart --
their headers are bare years and would otherwise be indistinguishable.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HEADER_ROW = 3
LABEL_ROW = 2
SHEET = "PROJECTS"
YEAR_RE = re.compile(r"^(19|20)\d\d(\.\d+)?$")

KNOWN_REGISTRIES = {"VCS", "GOLD", "CAR", "ACR", "ART", "ISO"}

# Maps a fragment of each block label to the `kind` stored in credit_year.
BLOCK_KINDS = {
    "issued by vintage": "issued_vintage",
    "retired or cancelled": "retired_year",
    "remaining by vintage": "remaining_vintage",
    "issued by issuance year": "issued_issue_year",
}

SCALAR_COLUMNS: dict[str, str] = {
    "Project ID": "project_id",
    "Voluntary Registry": "registry",
    "Project Name": "name",
    "Voluntary Status": "status",
    "Scope": "scope",
    "Type": "type",
    "Reduction / Removal": "reduction_removal",
    "Methodology / Protocol": "methodology",
    "Methodology Version": "methodology_version",
    "Region": "region",
    "Country": "country",
    "State": "state",
    "Project Site Location": "site_location",
    "Project Developer": "developer",
    "Project Owner": "owner",
    "First Year of Project (Vintage)": "first_vintage",
    "Total Credits Issued": "total_issued_milli",
    "Total Credits Retired": "total_retired_milli",
    "Total Credits Remaining": "total_remaining_milli",
    "Total Buffer Pool Deposits": "buffer_deposits_milli",
    "Reversals Covered by Buffer Pool": "reversals_covered_milli",
    "Reversals Not Covered by Buffer": "reversals_uncovered_milli",
    "Buffer Credits Released to Project": "buffer_released_milli",
    "PERs": "pers_milli",
    "Registry / ARB / WA": "registry_arb_wa",
    "ARB / WA Project": "arb_wa_project",
    "ARB / WA Status": "arb_wa_status",
    "ARB / WA ID": "arb_wa_id",
    "PoA / Aggregate ID": "poa_id",
    "PoA / VPA Status": "poa_status",
}

# Plain integers (a year, not an amount).
COUNT_FIELDS = {"first_vintage"}

# Credit amounts, stored as integer thousandths. See schema.sql for why.
CREDIT_FIELDS = {
    "total_issued_milli", "total_retired_milli", "total_remaining_milli",
    "buffer_deposits_milli", "reversals_covered_milli",
    "reversals_uncovered_milli", "buffer_released_milli", "pers_milli",
}

MILLI = 1000


class IngestError(RuntimeError):
    """Raised when the spreadsheet does not have the expected shape."""


@dataclass(frozen=True)
class Block:
    kind: str
    columns: list[int]
    years: list[int]


def squash(value: object) -> str:
    """Collapse whitespace; header cells contain embedded newlines."""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_name(value: str) -> str:
    """Fold a project name to a comparable key.

    Accents are stripped, anything that is not a letter or digit becomes a
    single space. Registries spell the same project differently, so this is
    deliberately aggressive; similarity matching handles the rest.
    """
    folded = unicodedata.normalize("NFKD", str(value))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_version_from(filename: str) -> str:
    match = re.search(r"v(\d{4}-\d{2})", filename)
    if not match:
        raise IngestError(f"cannot read a dataset version from {filename!r}")
    return f"v{match.group(1)}"


def find_blocks(path: Path) -> list[Block]:
    """Locate each per-year block using the labels on the raw label row."""
    raw = pd.read_excel(path, sheet_name=SHEET, header=None, nrows=HEADER_ROW)
    header = pd.read_excel(path, sheet_name=SHEET, header=HEADER_ROW, nrows=0)
    columns = [squash(c) for c in header.columns]

    labels: dict[int, str] = {}
    for col in range(raw.shape[1]):
        value = raw.iat[LABEL_ROW, col]
        if isinstance(value, str) and squash(value):
            labels[col] = squash(value).lower()

    starts = sorted(labels)
    blocks: list[Block] = []
    for fragment, kind in BLOCK_KINDS.items():
        start = next((c for c in starts if fragment in labels[c]), None)
        if start is None:
            raise IngestError(f"block label not found: {fragment!r}")
        stop = next((c for c in starts if c > start), len(columns))
        cols = [i for i in range(start, stop) if YEAR_RE.match(columns[i])]
        if not cols:
            raise IngestError(f"block {kind!r} has no year columns")
        blocks.append(
            Block(kind, cols, [int(float(columns[i])) for i in cols])
        )
    return blocks


def to_int(value: object) -> int:
    number = pd.to_numeric(value, errors="coerce")
    return 0 if pd.isna(number) else int(round(float(number)))


def to_milli(value: object) -> int:
    """Convert a credit amount to integer thousandths.

    The source reports at most three decimal places, so scaling by 1000
    and rounding once is exact for every value in the dataset.
    """
    number = pd.to_numeric(value, errors="coerce")
    return 0 if pd.isna(number) else int(round(float(number) * MILLI))


def ingest(path: Path, db_path: Path) -> dict[str, int]:
    """Load the spreadsheet into a fresh SQLite database. Returns counters."""
    frame = pd.read_excel(path, sheet_name=SHEET, header=HEADER_ROW)
    frame.columns = [squash(c) for c in frame.columns]

    missing = [c for c in SCALAR_COLUMNS if c not in frame.columns]
    if missing:
        raise IngestError(f"missing expected columns: {missing}")

    blocks = find_blocks(path)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript((Path(__file__).parent / "schema.sql").read_text())

        cur = conn.execute(
            "INSERT INTO source_file "
            "(filename, sha256, dataset_version, size_bytes, sheet_rows, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                path.name,
                sha256_of(path),
                dataset_version_from(path.name),
                path.stat().st_size,
                len(frame),
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        source_id = cur.lastrowid

        fields = ["project_id", "registry", "name", "name_norm"] + [
            dest for src, dest in SCALAR_COLUMNS.items()
            if dest not in {"project_id", "registry", "name"}
        ] + ["source_file_id"]
        placeholders = ", ".join("?" for _ in fields)

        rows = []
        for record in frame.to_dict("records"):
            values: dict[str, object] = {}
            for src, dest in SCALAR_COLUMNS.items():
                raw_value = record[src]
                if dest in CREDIT_FIELDS:
                    values[dest] = to_milli(raw_value)
                elif dest in COUNT_FIELDS:
                    values[dest] = to_int(raw_value)
                else:
                    text = squash(raw_value)
                    values[dest] = None if text in {"", "nan", "NaT"} else text
            values["name_norm"] = normalize_name(values["name"])
            values["source_file_id"] = source_id
            rows.append(tuple(values[f] for f in fields))

        conn.executemany(
            f"INSERT INTO project ({', '.join(fields)}) VALUES ({placeholders})",
            rows,
        )

        ids = frame[ "Project ID" ].map(squash).tolist()
        series: list[tuple[str, str, int, int]] = []
        for block in blocks:
            chunk = frame.iloc[:, block.columns].apply(
                pd.to_numeric, errors="coerce"
            ).fillna(0.0)
            for row_pos, project_id in enumerate(ids):
                values = chunk.iloc[row_pos].to_numpy()
                for year, amount in zip(block.years, values):
                    milli = to_milli(amount)
                    if milli:
                        series.append(
                            (project_id, block.kind, year, milli)
                        )

        conn.executemany(
            "INSERT OR REPLACE INTO credit_year "
            "(project_id, kind, year, credits_milli) VALUES (?, ?, ?, ?)",
            series,
        )
        conn.commit()
    finally:
        conn.close()

    return {"projects": len(rows), "credit_year_rows": len(series),
            "blocks": len(blocks)}
