"""Assemble one audit run: rules in, findings and a Merkle root out.

This is what the on-chain attestation commits to. The root is only useful
if a third party can rebuild it exactly, so ordering is explicit here
rather than inherited from whatever order the database returned rows in.
Findings are sorted by rule, then by their identifiers -- never by credit
volume, which would make the order depend on floating point comparisons
of amounts that may tie.

Each finding carries its own evidence in the leaf. A verifier does not
have to trust a summary: the leaf names the projects, the vintages and
the quantity, so recomputing it from the public files either reproduces
the committed hash or does not.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from tally.detect import Kind as VintageKind
from tally.detect import run as run_vintage_rules
from tally.link import find_candidates
from tally.merkle import encode_leaf, leaf_hash, root_of
from tally.serial_overlap import OverlapKind, find_collisions, merge_by_prefix

MILLI = 1000

RULE_VINTAGE_OVERLAP = "R1"
RULE_REGISTRY_MOVE = "R2"
RULE_SERIAL_OVERLAP = "R3"
RULE_EXPORT_DUPLICATE = "R4"

RULE_ORDER = {
    RULE_VINTAGE_OVERLAP: 0,
    RULE_REGISTRY_MOVE: 1,
    RULE_SERIAL_OVERLAP: 2,
    RULE_EXPORT_DUPLICATE: 3,
}

# Two rules evidence double counting; two describe the data around it.
# They are never ranked together. Sorting everything by volume alone put
# three export duplicates above almost every real finding, which reads as
# though a spreadsheet artefact were the market's largest problem.
FINDING_RULES = frozenset({RULE_VINTAGE_OVERLAP, RULE_SERIAL_OVERLAP})
CONTEXT_RULES = frozenset({RULE_REGISTRY_MOVE, RULE_EXPORT_DUPLICATE})


def is_finding(rule: str) -> bool:
    """True when the rule asserts double counting rather than context."""
    return rule in FINDING_RULES


@dataclass(frozen=True)
class AuditFinding:
    rule: str
    severity: int
    subjects: tuple[str, ...]
    registries: tuple[str, ...]
    country: str
    vintages: tuple[int, ...]
    credits_milli: int
    note: str = ""

    def leaf_fields(self) -> list[str | int]:
        """Fixed order. Changing it changes every root ever published."""
        return [
            self.rule,
            self.severity,
            "|".join(self.subjects),
            "|".join(self.registries),
            self.country,
            "|".join(str(v) for v in self.vintages),
            self.credits_milli,
            self.note,
        ]

    def leaf(self) -> bytes:
        return leaf_hash(encode_leaf(self.leaf_fields()))

    @property
    def is_finding(self) -> bool:
        return is_finding(self.rule)

    @property
    def sort_key(self) -> tuple:
        """Deterministic leaf order. Never by amount: ties would be
        resolved differently on different machines, and the root must be
        reproducible exactly."""
        return (RULE_ORDER[self.rule], self.subjects, self.vintages)


@dataclass(frozen=True)
class AuditRun:
    findings: tuple[AuditFinding, ...]
    root: bytes
    totals: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def credits(self) -> float:
        """Credits evidenced as double counted. Context rules excluded."""
        return sum(
            f.credits_milli for f in self.findings if f.is_finding
        ) / MILLI

    @property
    def confirmed(self) -> tuple["AuditFinding", ...]:
        return tuple(f for f in self.findings if f.is_finding)

    @property
    def context(self) -> tuple["AuditFinding", ...]:
        return tuple(f for f in self.findings if not f.is_finding)


def _severity(credits_milli: int) -> int:
    if credits_milli >= 100_000 * MILLI:
        return 3
    if credits_milli >= 10_000 * MILLI:
        return 2
    return 1


def collect(conn: sqlite3.Connection) -> list[AuditFinding]:
    out: list[AuditFinding] = []

    for finding in run_vintage_rules(conn):
        if finding.kind is VintageKind.VINTAGE_OVERLAP:
            out.append(
                AuditFinding(
                    rule=RULE_VINTAGE_OVERLAP,
                    severity=finding.severity,
                    subjects=tuple(sorted(finding.project_ids)),
                    registries=tuple(finding.registries),
                    country=finding.countries[0] if finding.countries else "",
                    vintages=finding.overlap_years,
                    credits_milli=finding.duplicated_milli,
                    note=finding.display_name,
                )
            )
        else:
            out.append(
                AuditFinding(
                    rule=RULE_REGISTRY_MOVE,
                    severity=0,
                    subjects=tuple(sorted(finding.project_ids)),
                    registries=tuple(finding.registries),
                    country=finding.countries[0] if finding.countries else "",
                    vintages=(),
                    credits_milli=0,
                    note=finding.display_name,
                )
            )

    for collision in merge_by_prefix(find_collisions(conn)):
        rule = (
            RULE_SERIAL_OVERLAP
            if collision.kind is OverlapKind.REAL_OVERLAP
            else RULE_EXPORT_DUPLICATE
        )
        credits_milli = collision.shared_credits * MILLI
        out.append(
            AuditFinding(
                rule=rule,
                severity=(
                    _severity(credits_milli)
                    if rule == RULE_SERIAL_OVERLAP else 0
                ),
                subjects=(collision.project_id or "", collision.serial_prefix),
                registries=(collision.registry,),
                country="",
                vintages=(collision.vintage,) if collision.vintage else (),
                credits_milli=credits_milli,
                note=f"{collision.left[0]}-{collision.left[1]} vs "
                     f"{collision.right[0]}-{collision.right[1]}",
            )
        )

    return out


def build(conn: sqlite3.Connection) -> AuditRun:
    findings = tuple(sorted(collect(conn), key=lambda f: f.sort_key))
    leaves = [f.leaf() for f in findings]

    totals: dict[str, dict[str, int]] = {}
    for f in findings:
        bucket = totals.setdefault(f.rule, {"count": 0, "credits_milli": 0})
        bucket["count"] += 1
        bucket["credits_milli"] += f.credits_milli

    # Candidates awaiting human review are counted but never committed as
    # findings: an unreviewed match is a question, not a result.
    candidates, stats = find_candidates(conn)
    pending = [
        c for c in candidates if c.shared_vintages and not c.exact_name
    ]
    totals["review_queue"] = {
        "count": len(pending),
        "credits_milli": sum(c.duplicated_milli for c in pending),
    }
    totals["linkage"] = {k: v for k, v in stats.items() if isinstance(v, int)}

    return AuditRun(findings=findings, root=root_of(leaves), totals=totals)
