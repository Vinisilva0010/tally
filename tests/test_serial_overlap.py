"""Serial-level collisions, pinned against the real v2026-08 raw files."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tally.serial_overlap import (  # noqa: E402
    OverlapKind, SerialCollision, find_collisions, merge_by_prefix, summarize,
)

# Pairwise detection, before merging.
EXPECTED_DUPLICATE_PAIRS = 6
EXPECTED_DUPLICATE_CREDITS = 222_579
EXPECTED_REAL_PAIRS = 2
EXPECTED_REAL_CREDITS = 10_000

# After merging, one entry per serial prefix. The two GS1083 pairs
# describe a single 10,000-credit overlap and collapse into one; the six
# export duplicates sit on six distinct prefixes and stay six.
EXPECTED_MERGED_DUPLICATES = 6
EXPECTED_MERGED_REAL = 1


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


# --- merging, on synthetic ranges -----------------------------------------

def collision(start_a, end_a, start_b, end_b, prefix="P",
              kind=OverlapKind.REAL_OVERLAP) -> SerialCollision:
    shared = min(end_a, end_b) - max(start_a, start_b) + 1
    return SerialCollision(
        kind=kind, registry="GOLD", serial_prefix=prefix,
        shared_credits=shared, project_id="GS1", vintage=2013,
        left=(start_a, end_a, "retirement", "2017-01-01", None),
        right=(start_b, end_b, "retirement", "2018-01-01", None),
    )


def test_merging_collapses_pairs_describing_one_overlap():
    """GS1083's shape: three ranges, two pairs, one 10,000 credit event."""
    pairs = [
        collision(73918, 78809, 73918, 83917),
        collision(73918, 83917, 78810, 83917),
    ]
    (merged,) = merge_by_prefix(pairs)
    assert merged.shared_credits == 10_000


def test_merging_does_not_double_count_overlapping_pairs():
    """The case pairwise addition gets wrong.

    Three ranges 1-20, 1-30 and 10-40 produce three overlapping pairs:

        1-20  with 1-30   overlaps 1-20    (20 credits)
        1-30  with 10-40  overlaps 10-30   (21 credits)
        1-20  with 10-40  overlaps 10-20   (11 credits)

    Adding the pair widths gives 52, which exceeds the 40 credits that
    exist. The union of the three spans is 1-30, so 30 credits were
    disposed of more than once.
    """
    pairs = [
        collision(1, 20, 1, 30),
        collision(1, 30, 10, 40),
        collision(1, 20, 10, 40),
    ]
    naive = sum(c.shared_credits for c in pairs)
    assert naive == 52, "the pairwise sum this test exists to reject"

    (merged,) = merge_by_prefix(pairs)
    assert merged.shared_credits == 30
    assert merged.shared_credits < naive


def test_merging_keeps_distinct_prefixes_apart():
    pairs = [
        collision(1, 10, 5, 15, prefix="A"),
        collision(1, 10, 5, 15, prefix="B"),
    ]
    assert len(merge_by_prefix(pairs)) == 2


def test_merging_keeps_kinds_apart():
    pairs = [
        collision(1, 10, 5, 15, kind=OverlapKind.REAL_OVERLAP),
        collision(1, 10, 5, 15, kind=OverlapKind.DUPLICATE_ROW),
    ]
    assert len(merge_by_prefix(pairs)) == 2


def test_disjoint_spans_under_one_prefix_are_added_not_joined():
    pairs = [
        collision(1, 10, 1, 10),
        collision(100, 110, 100, 110),
    ]
    (merged,) = merge_by_prefix(pairs)
    assert merged.shared_credits == 10 + 11


def test_merged_counts_against_the_real_dataset(collisions):
    merged = merge_by_prefix(collisions)
    counts = summarize(merged)
    assert counts["duplicate_row"]["pairs"] == EXPECTED_MERGED_DUPLICATES
    assert counts["real_overlap"]["pairs"] == EXPECTED_MERGED_REAL
    assert counts["real_overlap"]["credits"] == EXPECTED_REAL_CREDITS
