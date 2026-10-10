"""Cross-registry detection rules.

The core question: when the same physical project is registered with more
than one registry, did both registries issue credits for the same vintage
year -- the year the emission reduction actually happened?

If they did, the same tonne was very likely counted twice. If they did not,
the project simply moved from one registry to another, which is legitimate
and common. Telling those two apart is the whole point; a tool that flags
every cross-listed project is noise.

All amounts are integer thousandths of a credit ("milli"), as stored.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from enum import Enum

MILLI = 1000

# Short normalized names collide across unrelated projects ("wind farm").
MIN_NAME_LENGTH = 9

SEVERITY_HIGH_MILLI = 100_000 * MILLI
SEVERITY_MEDIUM_MILLI = 10_000 * MILLI


class Kind(str, Enum):
    VINTAGE_OVERLAP = "R1"   # same vintage credited by two registries
    REGISTRY_MOVE = "R2"     # cross-listed, no vintage overlap


@dataclass(frozen=True)
class Candidate:
    """One normalized project name present in two or more registries."""

    name_norm: str
    display_name: str
    project_ids: tuple[str, ...]
    registries: tuple[str, ...]
    countries: tuple[str, ...]
    types: tuple[str, ...]
    # registry -> {vintage year: credits_milli}
    vintages: dict[str, dict[int, int]] = field(default_factory=dict)

    @property
    def single_country(self) -> bool:
        return len(self.countries) == 1


@dataclass(frozen=True)
class Finding:
    kind: Kind
    severity: int
    name_norm: str
    display_name: str
    project_ids: tuple[str, ...]
    registries: tuple[str, ...]
    countries: tuple[str, ...]
    types: tuple[str, ...]
    overlap_years: tuple[int, ...]
    duplicated_milli: int
    issued_by_registry_milli: dict[str, int]

    @property
    def duplicated_credits(self) -> float:
        return self.duplicated_milli / MILLI


def overlapping_vintages(
    vintages: dict[str, dict[int, int]],
) -> tuple[tuple[int, ...], int]:
    """Years credited by EVERY registry, and how much is duplicated.

    A year counts as overlapping only when all registries involved issued a
    positive amount for it. The duplicated figure for such a year is the
    total issued minus the largest single registry's share: if the reduction
    is real, one registry's credits are legitimate and the rest are not.

    Returns (years, duplicated_milli). Pure function -- no database.
    """
    if len(vintages) < 2:
        return (), 0

    per_registry = list(vintages.values())
    shared = set(
        year for year, amount in per_registry[0].items() if amount > 0
    )
    for series in per_registry[1:]:
        shared &= {year for year, amount in series.items() if amount > 0}

    if not shared:
        return (), 0

    duplicated = 0
    for year in shared:
        amounts = [series.get(year, 0) for series in per_registry]
        duplicated += sum(amounts) - max(amounts)

    return tuple(sorted(shared)), duplicated


def severity_for(duplicated_milli: int) -> int:
    if duplicated_milli >= SEVERITY_HIGH_MILLI:
        return 3
    if duplicated_milli >= SEVERITY_MEDIUM_MILLI:
        return 2
    return 1


def load_candidates(conn: sqlite3.Connection) -> list[Candidate]:
    """Projects whose normalized name appears in 2+ registries, each issuing."""
    rows = conn.execute(
        """
        WITH issuing AS (
            SELECT project_id, registry, name, name_norm, country, type
            FROM project
            WHERE total_issued_milli > 0
              AND LENGTH(name_norm) >= ?
        ),
        multi AS (
            SELECT name_norm
            FROM issuing
            GROUP BY name_norm
            HAVING COUNT(DISTINCT registry) >= 2
        )
        SELECT i.name_norm, i.project_id, i.registry, i.name, i.country, i.type
        FROM issuing i
        JOIN multi m ON m.name_norm = i.name_norm
        ORDER BY i.name_norm, i.registry, i.project_id
        """,
        (MIN_NAME_LENGTH,),
    ).fetchall()

    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(row["name_norm"], []).append(row)

    candidates: list[Candidate] = []
    for name_norm, members in grouped.items():
        ids = tuple(r["project_id"] for r in members)
        placeholders = ", ".join("?" for _ in ids)
        series = conn.execute(
            f"""
            SELECT project_id, year, credits_milli
            FROM credit_year
            WHERE kind = 'issued_vintage'
              AND credits_milli > 0
              AND project_id IN ({placeholders})
            """,
            ids,
        ).fetchall()

        registry_of = {r["project_id"]: r["registry"] for r in members}
        vintages: dict[str, dict[int, int]] = {}
        for row in series:
            bucket = vintages.setdefault(registry_of[row["project_id"]], {})
            bucket[row["year"]] = bucket.get(row["year"], 0) + row["credits_milli"]

        if len(vintages) < 2:
            continue

        candidates.append(
            Candidate(
                name_norm=name_norm,
                display_name=members[0]["name"],
                project_ids=ids,
                registries=tuple(sorted(vintages)),
                countries=tuple(sorted({r["country"] for r in members})),
                types=tuple(sorted({r["type"] or "" for r in members})),
                vintages=vintages,
            )
        )
    return candidates


def evaluate(candidate: Candidate) -> Finding:
    years, duplicated = overlapping_vintages(candidate.vintages)
    kind = Kind.VINTAGE_OVERLAP if years else Kind.REGISTRY_MOVE
    return Finding(
        kind=kind,
        severity=severity_for(duplicated) if years else 0,
        name_norm=candidate.name_norm,
        display_name=candidate.display_name,
        project_ids=candidate.project_ids,
        registries=candidate.registries,
        countries=candidate.countries,
        types=candidate.types,
        overlap_years=years,
        duplicated_milli=duplicated,
        issued_by_registry_milli={
            reg: sum(series.values()) for reg, series in candidate.vintages.items()
        },
    )


def run(conn: sqlite3.Connection) -> list[Finding]:
    return [evaluate(c) for c in load_candidates(conn)]
