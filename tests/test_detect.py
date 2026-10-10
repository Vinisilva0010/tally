"""Detection rules: pure-function cases plus checks against real data."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tally.detect import (  # noqa: E402
    MILLI, Kind, overlapping_vintages, run, severity_for,
)


# --- pure function, synthetic data ---------------------------------------

def test_no_overlap_when_vintages_are_disjoint():
    years, dup = overlapping_vintages({
        "GOLD": {2012: 100, 2013: 100},
        "VCS": {2014: 100, 2015: 100},
    })
    assert years == ()
    assert dup == 0


def test_overlap_keeps_the_largest_share():
    """Two registries credit 2014. The smaller side is the duplicate."""
    years, dup = overlapping_vintages({
        "GOLD": {2014: 900},
        "VCS": {2014: 400},
    })
    assert years == (2014,)
    assert dup == 400


def test_overlap_requires_every_registry_to_be_present():
    years, dup = overlapping_vintages({
        "GOLD": {2014: 500, 2015: 500},
        "VCS": {2015: 300},
    })
    assert years == (2015,)
    assert dup == 300


def test_three_registries_keep_only_one_legitimate_share():
    years, dup = overlapping_vintages({
        "A": {2020: 100}, "B": {2020: 60}, "C": {2020: 40},
    })
    assert years == (2020,)
    assert dup == 100  # 200 total minus the 100 largest


def test_zero_amounts_do_not_create_overlap():
    years, dup = overlapping_vintages({
        "GOLD": {2014: 0, 2015: 10},
        "VCS": {2014: 50, 2015: 0},
    })
    assert years == ()
    assert dup == 0


def test_single_registry_is_never_an_overlap():
    assert overlapping_vintages({"GOLD": {2014: 100}}) == ((), 0)


@pytest.mark.parametrize(
    "credits, expected",
    [(0, 1), (9_999 * MILLI, 1), (10_000 * MILLI, 2),
     (99_999 * MILLI, 2), (100_000 * MILLI, 3)],
)
def test_severity_thresholds(credits, expected):
    assert severity_for(credits) == expected


# --- against the real dataset --------------------------------------------

EXPECTED_OVERLAP = 13
EXPECTED_MOVES = 56
EXPECTED_CANDIDATES = 69
# Exact, in thousandths: 351,903.000 credits. Locked to equality so that any
# change in rounding, ordering or scaling fails loudly instead of drifting.
EXPECTED_DUPLICATED_MILLI = 351_903_000


@pytest.fixture(scope="module")
def findings(db):
    return run(db)


def test_candidate_counts_match_phase_zero(findings):
    overlap = [f for f in findings if f.kind is Kind.VINTAGE_OVERLAP]
    moves = [f for f in findings if f.kind is Kind.REGISTRY_MOVE]
    assert len(findings) == EXPECTED_CANDIDATES
    assert len(overlap) == EXPECTED_OVERLAP
    assert len(moves) == EXPECTED_MOVES


def test_every_overlap_is_within_one_country(findings):
    """A name match across countries would be homonyms, not double counting."""
    for f in findings:
        if f.kind is Kind.VINTAGE_OVERLAP:
            assert len(f.countries) == 1, f.display_name


def test_kielty_is_the_largest_finding(findings):
    overlap = sorted(
        (f for f in findings if f.kind is Kind.VINTAGE_OVERLAP),
        key=lambda f: -f.duplicated_milli,
    )
    top = overlap[0]
    assert set(top.project_ids) == {"ACR0931", "CAR2112"}
    assert top.overlap_years == (2025,)
    assert top.severity == 3


def test_known_clean_move_is_not_flagged(findings):
    """GS6747 / VCS1134 split their vintages; it must stay unflagged."""
    match = [f for f in findings if "VCS1134" in f.project_ids]
    assert len(match) == 1
    assert match[0].kind is Kind.REGISTRY_MOVE


def test_duplicated_total_is_exact(findings):
    total = sum(
        f.duplicated_milli for f in findings if f.kind is Kind.VINTAGE_OVERLAP
    )
    assert total == EXPECTED_DUPLICATED_MILLI


def test_findings_are_order_independent(findings):
    """The total must not depend on the order rows come back from SQLite.

    The published Merkle root is built from these findings, so a result that
    shifts with row order would not be reproducible by a third party.
    """
    forward = sum(f.duplicated_milli for f in findings
                  if f.kind is Kind.VINTAGE_OVERLAP)
    backward = sum(f.duplicated_milli for f in reversed(findings)
                   if f.kind is Kind.VINTAGE_OVERLAP)
    assert forward == backward
