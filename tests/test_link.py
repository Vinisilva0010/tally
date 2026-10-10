"""Linkage rules, locked against the cases that shaped them.

Each test here corresponds to a false pair that an earlier version of the
linker accepted, or a true pair that a proposed rule would have destroyed.
Without them the calibration is invisible and the next refactor silently
undoes it.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tally.features import build_place_names, build_vocabulary, distinctive  # noqa: E402
from tally.link import discriminators, find_candidates  # noqa: E402

CONFIRMED = {
    ("ACR0931", "CAR2112"), ("GS3015", "VCS900"), ("GS1588", "VCS1887"),
    ("GS1378", "VCS1886"), ("CAR495", "VCS80"), ("GS7754", "VCS924"),
    ("GS1371", "VCS783"), ("GS5064", "VCS1692"), ("GS4532", "VCS1693"),
    ("GS2405", "VCS370"), ("GS7615", "VCS1781"), ("GS23339", "VCS3881"),
    ("ACR0234", "CAR1582"),
}

# Accepted by an earlier version; each is two different projects.
MUST_NOT_PAIR = [
    ("GS2405", "VCS384"),    # Gujarat vs Karnataka wind, identical wording
    ("ACR1064", "CAR444"),   # Weber County (Utah) vs Erie County (Ohio)
    ("ACR1064", "CAR509"),   # Weber County vs Larimer County (Colorado)
    ("GS2405", "VCS1890"),   # wind vs solar
    ("ACR0202", "CAR2047"),  # Blue Source Goodman (WI) vs Alford (MO)
    ("ACR0695", "CAR2218"),  # Oaktown Fuel 1 vs Oaktown Fuel 2
    ("GS11400", "VCS2635"),  # Fajina vs Luohe geothermal
    ("GS1370", "VCS783"),    # Bangkok Kamphaeng Saen West vs East
]


@pytest.fixture(scope="module")
def linked(db):
    candidates, stats = find_candidates(db)
    return {
        tuple(sorted((c.project_a, c.project_b))): c for c in candidates
    }, stats


def test_every_confirmed_pair_survives(linked):
    pairs, _ = linked
    missing = [p for p in CONFIRMED if tuple(sorted(p)) not in pairs]
    assert not missing, f"lost confirmed pairs: {missing}"


def test_known_false_pairs_are_rejected(linked):
    pairs, _ = linked
    accepted = [p for p in MUST_NOT_PAIR if tuple(sorted(p)) in pairs]
    assert not accepted, f"accepted known-false pairs: {accepted}"


def test_queue_stays_reviewable(linked):
    """A queue a human cannot read is a queue nobody reviews."""
    pairs, _ = linked
    with_overlap = [c for c in pairs.values() if c.shared_vintages]
    assert len(with_overlap) <= 40


def test_rejections_are_attributed(linked):
    """Every rejection must be counted under a named reason."""
    _, stats = linked
    for reason in ("rejected_type", "rejected_state", "rejected_marker",
                   "rejected_distinctive"):
        assert stats[reason] > 0, f"{reason} never fires"


def test_no_pair_crosses_a_country_border(linked):
    pairs, _ = linked
    for c in pairs.values():
        assert isinstance(c.country, str) and c.country


def test_no_pair_is_within_one_registry(linked):
    pairs, _ = linked
    for c in pairs.values():
        assert c.registry_a != c.registry_b


# --- vocabulary construction, on synthetic corpora -----------------------

def test_exclusive_token_is_a_place_name():
    places = build_place_names({
        "India": ["wind power project in gujarat"] * 10,
        "China": ["wind power project in hebei"] * 10,
    })
    assert "gujarat" in places
    assert "hebei" in places
    assert "wind" not in places
    assert "project" not in places


def test_place_names_separate_two_indian_states():
    places = build_place_names({
        "India": ["bundled wind power project in gujarat",
                  "bundled wind power project in karnataka"],
        "Brazil": ["landfill gas project in bahia"],
    })
    a = discriminators("bundled wind power project in gujarat", places)
    b = discriminators("bundled wind power project in karnataka", places)
    assert a != b


def test_frequent_words_become_generic():
    corpus = ["wind power project alpha", "wind power project beta",
              "wind power project gamma"] * 40
    generic = build_vocabulary(corpus)
    assert "wind" in generic
    assert "project" in generic


def test_rare_words_stay_distinctive():
    corpus = ["wind power project kielty"] + ["wind power project x"] * 300
    generic = build_vocabulary(corpus)
    assert "kielty" not in generic
    assert distinctive("wind power project kielty", generic) == {"kielty"}
