"""Invariants measured against the real v2026-08 dataset.

Every figure here was verified against the source before being written
down, so a failure means the pipeline changed the data, not that the
expectation was optimistic.

Amounts are integer thousandths of a credit. The exact grand total of
Total Credits Issued is 2,704,143,472.766 credits; summing the same
column as floating point yields 2,704,143,472 or ...473 depending on
where rounding happens, which is precisely why the scaled integer is
the stored form.
"""

import sqlite3

EXPECTED_PROJECTS = 11_856
EXPECTED_TOTAL_ISSUED_MILLI = 2_704_143_472_766
KNOWN_REGISTRIES = {"VCS", "GOLD", "CAR", "ACR", "ART", "ISO"}
EXPECTED_KINDS = {
    "issued_vintage", "retired_year", "remaining_vintage", "issued_issue_year",
}


def scalar(db: sqlite3.Connection, sql: str):
    return db.execute(sql).fetchone()[0]


def test_project_count(db):
    assert scalar(db, "SELECT COUNT(*) FROM project") == EXPECTED_PROJECTS


def test_total_issued_is_exact(db):
    total = scalar(db, "SELECT SUM(total_issued_milli) FROM project")
    assert total == EXPECTED_TOTAL_ISSUED_MILLI


def test_registries_are_known(db):
    found = {r[0] for r in db.execute("SELECT DISTINCT registry FROM project")}
    assert found == KNOWN_REGISTRIES


def test_required_fields_never_null(db):
    for column in ("project_id", "name", "country", "registry"):
        missing = scalar(
            db, f"SELECT COUNT(*) FROM project WHERE {column} IS NULL"
        )
        assert missing == 0, f"{column} has {missing} nulls"


def test_accounting_identity_holds(db):
    """issued - retired - remaining must be zero for every project.

    Buffer pool credits are excluded from both issued and remaining since
    database version 6, so no buffer term belongs in this identity.
    """
    offenders = scalar(
        db,
        "SELECT COUNT(*) FROM project WHERE "
        "ABS(total_issued_milli - total_retired_milli "
        "    - total_remaining_milli) > 1",
    )
    assert offenders == 0


def test_vintage_block_reconciles_with_total_issued(db):
    """The per-vintage series must sum back to the project total."""
    rows = db.execute(
        """
        SELECT p.project_id,
               p.total_issued_milli AS declared,
               COALESCE(SUM(c.credits_milli), 0) AS summed
        FROM project p
        LEFT JOIN credit_year c
          ON c.project_id = p.project_id AND c.kind = 'issued_vintage'
        GROUP BY p.project_id
        HAVING ABS(declared - summed) > 1
        """
    ).fetchall()
    assert not rows, [tuple(r) for r in rows[:5]]


def test_no_fractional_credits_were_lost(db):
    """At least one project must carry a non-integer credit amount.

    If this ever passes trivially, the scaling was silently dropped.
    """
    fractional = scalar(
        db,
        "SELECT COUNT(*) FROM project WHERE total_issued_milli % 1000 != 0",
    )
    assert fractional >= 29


def test_all_four_year_blocks_present(db):
    found = {r[0] for r in db.execute("SELECT DISTINCT kind FROM credit_year")}
    assert found == EXPECTED_KINDS


def test_years_within_dataset_range(db):
    assert scalar(db, "SELECT MIN(year) FROM credit_year") >= 1996
    assert scalar(db, "SELECT MAX(year) FROM credit_year") <= 2026


def test_name_norm_is_folded(db):
    bad = scalar(
        db,
        "SELECT COUNT(*) FROM project "
        "WHERE name_norm GLOB '*[^a-z0-9 ]*' OR name_norm LIKE '% ' "
        "OR name_norm LIKE ' %'",
    )
    assert bad == 0
