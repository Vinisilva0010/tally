"""Export the audit run as static JSON for the web interface.

The site has no backend. Everything it shows comes from these files, and
everything it claims can be rechecked in the browser: each finding ships
with the exact fields its leaf hash was built from, plus the Merkle proof
connecting that leaf to the published root. A reader can recompute both
without trusting the page.

Projects are exported only where a finding or a queued candidate refers
to them, along with the link to the issuing registry's own record, so a
reader can leave the site and check the claim at its source.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tally.audit import MILLI, build
from tally.merkle import proof_for

CLUSTER = "devnet"
PROGRAM_ID = "2DNtSVqoQPgrZz17C6zTEKt3WUqgVJo1vxxkYLCBM29e"


def _registry_link(row: sqlite3.Row) -> str:
    for field in ("registry_documents", "project_website"):
        value = row[field]
        if value and str(value).strip().startswith("http"):
            return str(value).strip()
    if row["registry"] == "VCS":
        digits = str(row["project_id"]).replace("VCS", "")
        if digits.isdigit():
            return f"https://registry.verra.org/verra/public/program/VCS/projects/{digits}"
    return ""


def export(
    conn: sqlite3.Connection,
    out_dir: Path,
    run_account: str,
    aggregate_sha: str,
    registry_sha: str,
    dataset_version: str,
) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    run = build(conn)
    leaves = [f.leaf() for f in run.findings]

    findings = []
    for index, finding in enumerate(run.findings):
        steps = proof_for(leaves, index)
        findings.append({
            "index": index,
            "rule": finding.rule,
            "severity": finding.severity,
            "subjects": list(finding.subjects),
            "registries": list(finding.registries),
            "country": finding.country,
            "vintages": list(finding.vintages),
            "credits": finding.credits_milli / MILLI,
            "credits_milli": finding.credits_milli,
            "note": finding.note,
            "is_finding": finding.is_finding,
            # Exactly the fields the leaf hash was computed over, in order.
            "leaf_fields": finding.leaf_fields(),
            "leaf_hash": finding.leaf().hex(),
            "proof": [
                {"sibling": s.sibling.hex(), "sibling_is_left": s.sibling_is_left}
                for s in steps
            ],
        })

    referenced: set[str] = set()
    for finding in run.findings:
        referenced.update(s for s in finding.subjects if s)

    queue = []
    from tally.link import find_candidates  # local import keeps module light
    candidates, _ = find_candidates(conn)
    for c in candidates:
        if not c.shared_vintages or c.exact_name:
            continue
        referenced.update((c.project_a, c.project_b))
        queue.append({
            "project_a": c.project_a,
            "project_b": c.project_b,
            "name_a": c.name_a,
            "name_b": c.name_b,
            "registry_a": c.registry_a,
            "registry_b": c.registry_b,
            "country": c.country,
            "vintages": list(c.shared_vintages),
            "credits": c.duplicated_milli / MILLI,
            "name_cosine": c.features.name_cosine,
            "developer_sim": c.features.developer_sim,
        })
    queue.sort(key=lambda q: -q["credits"])

    projects = {}
    if referenced:
        placeholders = ", ".join("?" for _ in referenced)
        for row in conn.execute(
            f"SELECT project_id, registry, name, country, state, type, "
            f"developer, methodology, total_issued_milli, "
            f"registry_documents, project_website "
            f"FROM project WHERE project_id IN ({placeholders})",
            tuple(sorted(referenced)),
        ):
            projects[row["project_id"]] = {
                "project_id": row["project_id"],
                "registry": row["registry"],
                "name": row["name"],
                "country": row["country"],
                "state": row["state"],
                "type": row["type"],
                "developer": row["developer"],
                "methodology": row["methodology"],
                "issued": row["total_issued_milli"] / MILLI,
                "link": _registry_link(row),
            }

    project_count = conn.execute("SELECT COUNT(*) FROM project").fetchone()[0]
    event_count = conn.execute("SELECT COUNT(*) FROM credit_event").fetchone()[0]

    manifest = {
        "dataset_version": dataset_version,
        "aggregate_sha256": aggregate_sha,
        "registry_sha256": registry_sha,
        "merkle_root": run.root.hex(),
        "cluster": CLUSTER,
        "program_id": PROGRAM_ID,
        "run_account": run_account,
        "project_count": project_count,
        "credit_event_count": event_count,
        "finding_count": len(run.findings),
        "credits_evidenced": run.credits,
        "totals": {
            rule: {
                "count": t["count"],
                "credits": t["credits_milli"] / MILLI,
            }
            for rule, t in run.totals.items()
            if rule.startswith("R")
        },
        "queue_count": len(queue),
        "linkage": run.totals.get("linkage", {}),
    }

    (out_dir / "run.json").write_text(json.dumps(manifest, indent=2))
    (out_dir / "findings.json").write_text(json.dumps(findings, indent=2))
    (out_dir / "projects.json").write_text(json.dumps(projects, indent=2))
    (out_dir / "queue.json").write_text(json.dumps(queue, indent=2))

    return {
        "findings": len(findings),
        "projects": len(projects),
        "queue": len(queue),
    }
