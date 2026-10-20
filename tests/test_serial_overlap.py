"""Serial-level collisions, pinned against the real v2026-08 raw files."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tally.serial_overlap import (  # noqa: E402
    OverlapKind, find_collisions, summarize,
)

EXPECTED_DUPLICATE_PAIRS = 6
EXPECTED_DUPLICATE_CREDITS = 222_579
EXPECTED_REAL_PAIRS = 2
EXPECTED_REAL_CREDITS = 10_000


@pytest.fixture(scope="module")
def collisions(db):
    if not db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='credit_event'"
    ).fetchone():
        pytest.skip("raw registry files not ingested")
    if not db.execute("SELECT 1 FROM credit_event LIMIT 1").fetchone():
        pytest.skip("credit_event is empty; run scripts/run_raw_ingest.py")
    return find_collisions(db)


def test_duplicate_rows_are_separated_from_real_overlaps(collisions):
    counts = summarize(collisions)
    assert counts["duplicate_row"]["pairs"] == EXPECTED_DUPLICATE_PAIRS
    assert counts["duplicate_row"]["credits"] == EXPECTED_DUPLICATE_CREDITS


def test_real_overlaps_are_exactly_the_known_case(collisions):
    counts = summarize(collisions)
    assert counts["real_overlap"]["pairs"] == EXPECTED_REAL_PAIRS
    assert counts["real_overlap"]["credits"] == EXPECTED_REAL_CREDITS


def test_the_real_overlap_is_the_vietnamese_project(collisions):
    real = [c for c in collisions if c.kind is OverlapKind.REAL_OVERLAP]
    assert {c.project_id for c in real} == {"GS1083"}
    assert {c.registry for c in real} == {"GOLD"}


def test_duplicate_rows_really_are_identical(collisions):
    """A duplicate must match on range, date and holder, or it is not one."""
    for c in collisions:
        if c.kind is OverlapKind.DUPLICATE_ROW:
            assert c.left[0] == c.right[0]
            assert c.left[1] == c.right[1]
            assert str(c.left[3]) == str(c.right[3])
            assert str(c.left[4]) == str(c.right[4])
