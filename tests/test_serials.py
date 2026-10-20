"""Serial range parsing, one case per registry format.

The examples are real rows from the v2026-08 raw registry files. Each
registry writes ranges differently and two of the formats are easy to
misread, so every format is pinned here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tally.serials import SerialRange, overlap, parse  # noqa: E402


def test_acr_to_range():
    (r,) = parse("ACR-US-114-2015-646-777955 to 778357", "ACR")
    assert (r.start, r.end, r.count) == (777955, 778357, 403)
    assert r.prefix == "ACR-US-114-2015-646"


def test_acr_multiple_ranges_in_one_cell():
    """A single issuance row may carry several ranges, semicolon separated."""
    ranges = parse(
        "ACR-US-590-2022-1949-1 to 9711;ACR-US-590-2022-1950-1 to 28336", "ACR"
    )
    assert len(ranges) == 2
    assert sum(r.count for r in ranges) == 9711 + 28336


def test_car_long_prefix():
    (r,) = parse("CAR-1-US-1480-46-1156-FL-2026-10272-852724 to 860723", "CAR")
    assert (r.start, r.end, r.count) == (852724, 860723, 8000)


def test_car_single_credit_range():
    (r,) = parse("CAR-1-US-1480-46-1156-FL-2026-10272-915425 to 915425", "CAR")
    assert r.count == 1


def test_gold_trailing_pair_without_the_word_to():
    (r,) = parse("GS1-1-XZ-GS12303-17-2022-30775-1077-1127", "GOLD")
    assert (r.start, r.end, r.count) == (1077, 1127, 51)


def test_verra_range_comes_first_not_last():
    """Verra puts start and end in positions two and three.

    Reading the trailing numbers here would capture the vintage dates and
    a flag, producing a range of nonsense that still looks plausible.
    """
    (r,) = parse(
        "18453-896309560-896329558-VCS-VCU-1507-VER-IN-1-1904-01092024-31122024-0",
        "VCS",
    )
    assert (r.start, r.end) == (896309560, 896329558)
    assert r.count == 19999


def test_verra_does_not_fall_back_to_the_trailing_pair():
    assert parse("not-a-serial-at-all", "VCS") == []


def test_blank_values_parse_to_nothing():
    for value in (None, "", "   ", "nan"):
        assert parse(value, "ACR") == []


def test_overlap_counts_shared_credits():
    a = SerialRange("", "ACR-US-114-2015-646", 100, 200)
    b = SerialRange("", "ACR-US-114-2015-646", 150, 250)
    assert overlap(a, b) == 51


def test_overlap_requires_the_same_prefix():
    """Identical numbers under different prefixes are different credits."""
    a = SerialRange("", "ACR-US-114-2015-646", 100, 200)
    b = SerialRange("", "CAR-1-US-1480-46-1156", 100, 200)
    assert overlap(a, b) == 0


def test_disjoint_ranges_do_not_overlap():
    a = SerialRange("", "P", 1, 10)
    b = SerialRange("", "P", 11, 20)
    assert overlap(a, b) == 0
