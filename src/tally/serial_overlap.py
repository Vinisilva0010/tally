"""Overlapping disposal of the same credit, within a single registry.

A credit is identified by its serial prefix plus a number. It may be
issued once and then retired or cancelled once. Two disposal events
covering the same number are two disposals of one tonne.

Not every overlap means that, though, and the difference decides whether
a finding is worth publishing. Across 501,413 disposal events the raw
files contain eight overlapping pairs, and six of them are the same
transaction exported twice: identical range, identical date, identical
holder, identical reason. ACR-US-731-2026-3316 shows the shape plainly --
one issuance of 1-74344 and two cancellations of 1-74344 by the same
holder on the same day for the same stated reason. Reporting those as
double counting would be reporting an export artefact as fraud.

A genuine overlap looks different. GS1083 in Viet Nam retires its credits
in 24 ranges that interlock exactly, with no gaps and no repeats, except
for three: 73918-78809 in April 2017, 73918-83917 in May 2018, and
78810-83917 in November 2018. The middle range covers both the others
exactly. The same 10,000 credits were retired across three events over
nineteen months.

So an overlap is only reported when the two events differ in range, date
or holder. Identical events are counted separately and surfaced as a data
quality note, because a registry exporting the same disposal twice is
worth knowing about even though it is not double counting.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum


class OverlapKind(str, Enum):
    DUPLICATE_ROW = "duplicate_row"
    REAL_OVERLAP = "real_overlap"


@dataclass(frozen=True)
class SerialCollision:
    kind: OverlapKind
    registry: str
    serial_prefix: str
    shared_credits: int
    project_id: str | None
    vintage: int | None
    left: tuple[int, int, str | None, str | None, str | None]
    right: tuple[int, int, str | None, str | None, str | None]


def _key(row) -> tuple:
    return (row["serial_start"], row["serial_end"],
            str(row["event_date"]), str(row["holder"]))


def _tuple(row) -> tuple:
    return (row["serial_start"], row["serial_end"], row["event_type"],
            row["event_date"], row["holder"])


def find_collisions(conn: sqlite3.Connection) -> list[SerialCollision]:
    """Disposal events whose serial ranges overlap inside one registry."""
    rows = conn.execute(
        "SELECT registry, event_type, project_id, project_ref, vintage, "
        "serial_prefix, serial_start, serial_end, holder, reason, event_date "
        "FROM credit_event "
        "WHERE serial_prefix IS NOT NULL AND event_type != 'issuance'"
    ).fetchall()

    grouped: dict[tuple[str, str], list] = defaultdict(list)
    for row in rows:
        grouped[(row["registry"], row["serial_prefix"])].append(row)

    found: list[SerialCollision] = []
    for (registry, prefix), events in grouped.items():
        if len(events) < 2:
            continue
        events.sort(key=lambda e: (e["serial_start"], e["serial_end"]))
        for i, left in enumerate(events[:-1]):
            for right in events[i + 1:]:
                if right["serial_start"] > left["serial_end"]:
                    break
                shared = (
                    min(left["serial_end"], right["serial_end"])
                    - right["serial_start"] + 1
                )
                if shared <= 0:
                    continue
                kind = (
                    OverlapKind.DUPLICATE_ROW if _key(left) == _key(right)
                    else OverlapKind.REAL_OVERLAP
                )
                found.append(
                    SerialCollision(
                        kind=kind,
                        registry=registry,
                        serial_prefix=prefix,
                        shared_credits=shared,
                        project_id=left["project_id"] or left["project_ref"],
                        vintage=left["vintage"],
                        left=_tuple(left),
                        right=_tuple(right),
                    )
                )
    return found


def merge_by_prefix(
    collisions: list[SerialCollision],
) -> list[SerialCollision]:
    """One entry per serial prefix, covering the union of overlaps.

    Overlaps are detected pairwise, so three ranges that overlap each
    other produce three pairs describing one event. GS1083 shows it:
    73918-78809, 73918-83917 and 78810-83917 are one 10,000-credit
    overlap reported as two pairs of 4,892 and 5,108. Adding those pairs
    happens to give the right total here, but with four overlapping
    ranges it would not -- the same credits would be counted repeatedly.

    Merging counts each credit number once, by taking the union of the
    overlapping spans rather than summing pair widths.
    """
    by_prefix: dict[tuple[str, str, OverlapKind], list[SerialCollision]] = (
        defaultdict(list)
    )
    for c in collisions:
        by_prefix[(c.registry, c.serial_prefix, c.kind)].append(c)

    merged: list[SerialCollision] = []
    for (registry, prefix, kind), group in by_prefix.items():
        spans = sorted(
            (max(a.left[0], a.right[0]), min(a.left[1], a.right[1]))
            for a in group
        )
        covered, current_start, current_end = 0, None, None
        for start, end in spans:
            if current_start is None:
                current_start, current_end = start, end
            elif start <= current_end + 1:
                current_end = max(current_end, end)
            else:
                covered += current_end - current_start + 1
                current_start, current_end = start, end
        if current_start is not None:
            covered += current_end - current_start + 1

        first = group[0]
        merged.append(
            SerialCollision(
                kind=kind,
                registry=registry,
                serial_prefix=prefix,
                shared_credits=covered,
                project_id=first.project_id,
                vintage=first.vintage,
                left=first.left,
                right=group[-1].right,
            )
        )
    return sorted(merged, key=lambda c: (-c.shared_credits, c.serial_prefix))


def summarize(collisions: list[SerialCollision]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {
        k.value: {"pairs": 0, "credits": 0} for k in OverlapKind
    }
    for c in collisions:
        out[c.kind.value]["pairs"] += 1
        out[c.kind.value]["credits"] += c.shared_credits
    return out
