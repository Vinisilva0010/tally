"""Load the raw registry files into credit_event.

The aggregate database reports totals per project and vintage. These
sheets carry the individual events behind those totals: each issuance,
retirement and cancellation, with the serial range it covers, who claimed
it and the reason the registry declared.

Every registry names its columns differently, so each sheet is described
by a small configuration rather than by bespoke code. A column that a
registry does not publish is simply absent; nothing is invented to fill
the gap, because an absent safeguard field and a negative one mean
different things and must not be collapsed.

Project identifiers also differ. The aggregate database uses "GS12303"
and "VCS1904"; the raw sheets write "12303" and "1904". They are mapped
back so events join to the project table.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tally.ingest import sha256_of, squash
from tally.serials import parse as parse_serials

MILLI = 1000


@dataclass(frozen=True)
class SheetSpec:
    sheet: str
    registry: str
    event_type: str
    project_prefix: str = ""
    serial: tuple[str, ...] = ()
    quantity: tuple[str, ...] = ()
    vintage: tuple[str, ...] = ("Vintage",)
    project: tuple[str, ...] = ()
    date: tuple[str, ...] = ()
    holder: tuple[str, ...] = ()
    holder_country: tuple[str, ...] = ()
    on_behalf_of: tuple[str, ...] = ()
    reason: tuple[str, ...] = ()
    article6: tuple[str, ...] = ()
    adjustment: tuple[str, ...] = ()
    country: tuple[str, ...] = ()


SPECS: tuple[SheetSpec, ...] = (
    SheetSpec(
        "ACR Issuances", "ACR", "issuance",
        serial=("Credit Serial Numbers",),
        quantity=("Quantity of Credits",),
        project=("Project Id",),
        date=("Date Issued (GMT)",),
        country=("Project Site Country",),
    ),
    SheetSpec(
        "ACR Retirements", "ACR", "retirement",
        serial=("Credit Serial Numbers",),
        quantity=("Quantity of Credits",),
        project=("Project Id",),
        date=("Status Effective (GMT)",),
        holder=("Credit Holder",),
        holder_country=("Credit Holder Country",),
        on_behalf_of=("Retired On Behalf Of",),
        reason=("Retirement Reason",),
        adjustment=("Corresponding Adjustment Reported",),
        country=("Project Site Country",),
    ),
    SheetSpec(
        "ACR Cancelations", "ACR", "cancellation",
        serial=("Credit Serial Numbers",),
        quantity=("Quantity of Credits",),
        project=("Project Id",),
        date=("Status Effective (GMT)",),
        holder=("Credit Holder",),
        reason=("Cancellation Reason",),
        adjustment=("Corresponding Adjustment Reported",),
        country=("Project Site Country",),
    ),
    SheetSpec(
        "CAR Retirements", "CAR", "retirement",
        serial=("Offset Credit Serial Numbers",),
        quantity=("Quantity of Offset Credits",),
        project=("Project ID",),
        date=("Status Effective",),
        holder=("Account Holder",),
        reason=("Retirement Reason",),
        adjustment=("Corresponding Adjustment",),
        country=("Project Site Country",),
    ),
    SheetSpec(
        "CAR Cancellations", "CAR", "cancellation",
        serial=("Offset Credit Serial Numbers",),
        quantity=("Quantity of Offset Credits",),
        project=("Project ID",),
        date=("Status Effective",),
        reason=("Cancellation Reason",),
        country=("Project Site Country",),
    ),
    SheetSpec(
        "Gold Issuances", "GOLD", "issuance", project_prefix="GS",
        quantity=("Quantity",),
        project=("GSID",),
        date=("Issuance Date",),
        country=("Country",),
    ),
    SheetSpec(
        "Gold Retirements", "GOLD", "retirement", project_prefix="GS",
        serial=("Serial Number",),
        quantity=("Quantity",),
        project=("GSID",),
        date=("Retirement Date",),
        holder=("Using Entity",),
        reason=("Credit Status", "Use Case"),
        article6=("Article Six Authorization",),
        country=("Country",),
    ),
    SheetSpec(
        "Verra VCS Issuances", "VCS", "issuance", project_prefix="VCS",
        serial=("Serial Number",),
        quantity=("Issuance QTY", "Quantity"),
        project=("Project ID",),
        date=("Issuance Date",),
        country=("Country",),
    ),
    SheetSpec(
        "Verra VCS Retirements", "VCS", "retirement", project_prefix="VCS",
        serial=("Serial Number",),
        quantity=("Retirement QTY",),
        project=("Project ID",),
        date=("Retirement Date",),
        holder=("Beneficial Owner",),
        reason=("Retirement Reason",),
        article6=("Additional Certifications/Labels",),
        country=("Country",),
    ),
    SheetSpec(
        "Verra VCS Cancellations", "VCS", "cancellation", project_prefix="VCS",
        serial=("Serial Number",),
        quantity=("Cancellation QTY", "Quantity"),
        project=("Project ID",),
        date=("Cancellation Date",),
        country=("Country",),
    ),
)


def pick(columns: list[str], names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in columns:
            return name
    for name in names:
        for col in columns:
            if col.lower().startswith(name.lower()[:28]):
                return col
    return None


def text_of(value: object) -> str | None:
    if value is None:
        return None
    out = squash(value)
    return None if out in {"", "nan", "NaT", "None"} else out


def project_id_for(spec: SheetSpec, value: object) -> tuple[str, str | None]:
    """Returns (as printed, resolved to the aggregate database's format)."""
    raw = text_of(value)
    if raw is None:
        return "", None
    cleaned = raw.split(".")[0] if raw.replace(".", "").isdigit() else raw
    if spec.project_prefix and not cleaned.upper().startswith(spec.project_prefix):
        return raw, f"{spec.project_prefix}{cleaned}"
    return raw, cleaned


def ingest_raw(path: Path, db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript((Path(__file__).parent / "schema.sql").read_text())
        row = conn.execute(
            "SELECT id FROM source_file WHERE filename = ?", (path.name,)
        ).fetchone()
        if row is None:
            cur = conn.execute(
                "INSERT INTO source_file (filename, sha256, dataset_version, "
                "size_bytes, sheet_rows, ingested_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    path.name, sha256_of(path),
                    re.search(r"(\d{4}-\d{2})", path.name).group(1),
                    path.stat().st_size, 0,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            source_id = cur.lastrowid
        else:
            source_id = row["id"]

        conn.execute("DELETE FROM credit_event WHERE source_file_id = ?",
                     (source_id,))

        known = {r[0] for r in conn.execute("SELECT project_id FROM project")}
        counts: dict[str, int] = {}
        unresolved: dict[str, int] = {}

        for spec in SPECS:
            frame = pd.read_excel(path, sheet_name=spec.sheet)
            frame.columns = [squash(c) for c in frame.columns]
            columns = list(frame.columns)

            col = {
                field: pick(columns, names)
                for field, names in (
                    ("serial", spec.serial), ("quantity", spec.quantity),
                    ("vintage", spec.vintage), ("project", spec.project),
                    ("date", spec.date), ("holder", spec.holder),
                    ("holder_country", spec.holder_country),
                    ("on_behalf_of", spec.on_behalf_of),
                    ("reason", spec.reason), ("article6", spec.article6),
                    ("adjustment", spec.adjustment), ("country", spec.country),
                )
            }

            rows = []
            for record in frame.to_dict("records"):
                printed, resolved = project_id_for(
                    spec, record.get(col["project"]) if col["project"] else None
                )
                if resolved and resolved not in known:
                    unresolved[spec.sheet] = unresolved.get(spec.sheet, 0) + 1
                    resolved = None

                quantity = 0
                if col["quantity"]:
                    number = pd.to_numeric(record[col["quantity"]], errors="coerce")
                    quantity = 0 if pd.isna(number) else int(round(float(number) * MILLI))

                vintage = None
                if col["vintage"]:
                    number = pd.to_numeric(record[col["vintage"]], errors="coerce")
                    vintage = None if pd.isna(number) else int(number)

                serial_raw = (
                    text_of(record[col["serial"]]) if col["serial"] else None
                )
                ranges = parse_serials(serial_raw, spec.registry) if serial_raw else []

                base = (
                    spec.registry, printed, resolved, spec.event_type, vintage,
                    quantity,
                    text_of(record[col["date"]]) if col["date"] else None,
                )
                tail = (
                    text_of(record[col["holder"]]) if col["holder"] else None,
                    text_of(record[col["holder_country"]]) if col["holder_country"] else None,
                    text_of(record[col["on_behalf_of"]]) if col["on_behalf_of"] else None,
                    text_of(record[col["reason"]]) if col["reason"] else None,
                    text_of(record[col["article6"]]) if col["article6"] else None,
                    text_of(record[col["adjustment"]]) if col["adjustment"] else None,
                    text_of(record[col["country"]]) if col["country"] else None,
                    source_id,
                )

                if ranges:
                    for r in ranges:
                        rows.append(
                            base + (serial_raw, r.prefix, r.start, r.end) + tail
                        )
                else:
                    rows.append(base + (serial_raw, None, None, None) + tail)

            conn.executemany(
                "INSERT INTO credit_event (registry, project_ref, project_id, "
                "event_type, vintage, quantity_milli, event_date, serial_raw, "
                "serial_prefix, serial_start, serial_end, holder, "
                "holder_country, on_behalf_of, reason, article6_label, "
                "corresponding_adjustment, project_country, source_file_id) "
                "VALUES (" + ", ".join("?" * 19) + ")",
                rows,
            )
            counts[spec.sheet] = len(rows)

        conn.commit()
        return {"rows": counts, "unresolved": unresolved,
                "source_file_id": source_id}
    finally:
        conn.close()
