"""Feature extraction, checked against values taken from real records."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tally.features import (  # noqa: E402
    Features, agreement, hard_conflict, jaccard, normalize_org,
    place_tokens, ratio_spread,
)


def base(**over) -> Features:
    defaults = dict(
        name_cosine=0.9, name_token_set=95.0, developer_sim=80.0,
        methodology=1, type_match=1, scope_match=1, state_match=-1,
        site_overlap=0.5, markers_equal=1, shared_vintages=2,
        vintage_ratio_spread=1.2,
    )
    defaults.update(over)
    return Features(**defaults)


# --- organization normalization ------------------------------------------

def test_punctuation_and_legal_form_do_not_break_a_match():
    """The Kielty pair, a confirmed match, differs only by a comma."""
    assert normalize_org("Keyrock Environment LLC") == \
           normalize_org("Keyrock Environment,LLC")


def test_transfer_note_is_not_a_developer():
    assert normalize_org("Credits transferred from approved GHG program") == ""


def test_distinct_companies_stay_distinct():
    assert normalize_org("Qnergy International Services LLC") != \
           normalize_org("Renewable Energy Services of Ohio, LLC")


def test_empty_developer_is_empty():
    assert normalize_org(None) == ""
    assert normalize_org("") == ""


# --- three-way agreement --------------------------------------------------

def test_agreement_is_three_way():
    assert agreement("WEST VIRGINIA", "West Virginia") == 1
    assert agreement("UTAH", "OHIO") == 0
    assert agreement("UTAH", None) == -1
    assert agreement(None, None) == -1


# --- location tokens ------------------------------------------------------

def test_site_tokens_share_the_town_name():
    a = place_tokens("192 Lick Rd, Delbarton, WV")
    b = place_tokens("Delbarton")
    assert jaccard(a, b) > 0


def test_unrelated_sites_share_nothing():
    a = place_tokens("Ogden, Utah")
    b = place_tokens("Milan")
    assert jaccard(a, b) == 0.0


def test_generic_words_are_not_identity():
    assert "county" not in place_tokens("Larimer County, Colorado")


def test_missing_location_is_not_comparable():
    assert jaccard(place_tokens(None), place_tokens("Delbarton")) == -1.0


# --- hard conflicts -------------------------------------------------------

def test_conflicting_state_rejects():
    assert hard_conflict(base(state_match=0)) == "state"


def test_conflicting_type_rejects():
    assert hard_conflict(base(type_match=0)) == "type"


def test_absent_state_never_rejects():
    """Non-US projects leave the state field empty; that must not reject."""
    assert hard_conflict(base(state_match=-1)) is None


def test_matching_state_never_rejects():
    assert hard_conflict(base(state_match=1)) is None


def test_methodology_disagreement_alone_does_not_reject():
    """Registries name their own protocols; disagreement is expected."""
    assert hard_conflict(base(methodology=0)) is None


# --- vintage ratio consistency -------------------------------------------

def test_consistent_ratios_score_near_one():
    assert ratio_spread({2014: (4000, 1000), 2016: (4200, 1050)}) == 1.0


def test_inconsistent_ratios_score_high():
    """Blue Source Goodman vs Alford: 39x one year, 20x the next."""
    spread = ratio_spread({2018: (21278, 545), 2019: (26394, 1318)})
    assert spread > 1.9


def test_single_shared_year_carries_no_information():
    assert ratio_spread({2025: (147508, 147508)}) == -1.0
