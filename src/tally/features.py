"""Pairwise evidence used to decide whether two records are one project.

Name similarity alone cannot separate "Weber County Landfill" from "Erie
County Landfill": the shared words are the words of the sector, not of the
project. The dataset carries six further fields per project, and measuring
them against pairs already judged by hand shows where the signal actually
sits.

What that measurement found:

  Conflicts are decisive. Across every false pair examined, either the US
  state differed (Utah vs Ohio, Wisconsin vs Missouri) or the project type
  differed (wind vs solar). Across every true pair, type agreed 13 of 13,
  and state either agreed or was absent -- non-US projects leave it empty.
  So a populated field that disagrees rejects the pair outright, while an
  empty field never rejects: absence is not evidence.

  Exact equality is the wrong test for free text. The Kielty pair, which is
  a confirmed match, writes its developer as "Keyrock Environment LLC" on
  one side and "Keyrock Environment,LLC" on the other. Compared literally
  the field looks useless; compared the way names are compared, it is
  strong. Legal suffixes are stripped for the same reason.

  Some fields carry placeholders rather than values. A developer recorded
  as "Credits transferred from approved GHG program" is a transfer note,
  not a company, and is treated as missing.

Methodology is deliberately weak evidence. Registries name their own
protocols ("CAR U.S. Landfill Protocol" vs "ACR Landfill Gas Destruction"),
so the same physical project can carry different protocol names honestly.
It contributes when it agrees and never rejects when it does not.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

from rapidfuzz import fuzz

# Corporate forms carry no identity; two registries pick different ones.
LEGAL_SUFFIXES = frozenset({
    "llc", "ltd", "limited", "inc", "incorporated", "co", "company",
    "corp", "corporation", "pvt", "private", "plc", "gmbh", "sa", "srl",
    "bv", "nv", "ag", "as", "ab", "oy", "pte", "llp", "lp", "pp",
    "jsc", "cv", "sas", "spa", "sl", "aps", "kft", "doo", "sdn", "bhd",
})

# Values that occupy the developer field without naming a developer.
DEVELOPER_PLACEHOLDERS = (
    "credits transferred",
    "approved ghg program",
    "not applicable",
    "unknown",
    "n/a",
)

# Words too common in project names to carry identity on their own.
GENERIC_SITE_WORDS = frozenset({
    "county", "project", "city", "state", "district", "province",
    "region", "area", "site", "plant", "facility", "farm", "landfill",
})

STOPWORDS = frozenset({"the", "of", "in", "at", "and", "for", "by", "a", "an"})


def fold(text: object) -> str:
    """Lowercase, strip accents, reduce to letters digits and spaces."""
    if text is None:
        return ""
    folded = unicodedata.normalize("NFKD", str(text))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


def normalize_org(text: object) -> str:
    """Fold an organization name and drop its legal form."""
    folded = fold(text)
    if not folded:
        return ""
    if any(p in folded for p in DEVELOPER_PLACEHOLDERS):
        return ""
    kept = [t for t in folded.split() if t not in LEGAL_SUFFIXES]
    return " ".join(kept)


def place_tokens(text: object) -> frozenset[str]:
    """Identifying words from a free-text location."""
    folded = fold(text)
    if not folded:
        return frozenset()
    return frozenset(
        t for t in folded.split()
        if len(t) > 2 and t not in GENERIC_SITE_WORDS and t not in STOPWORDS
    )


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return -1.0
    return len(a & b) / len(a | b)


def agreement(a: object, b: object) -> int:
    """1 agree, 0 disagree, -1 not comparable (either side empty).

    The three-way result matters: disagreement and absence must never be
    collapsed, because one rejects a pair and the other cannot.
    """
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return -1
    return 1 if fa == fb else 0


@dataclass(frozen=True)
class Features:
    name_cosine: float      # char 3-gram TF-IDF, supplied by the caller
    name_token_set: float   # 0..100
    developer_sim: float    # 0..100, or -1 when either side is empty
    methodology: int        # 1 / 0 / -1
    type_match: int         # 1 / 0 / -1
    scope_match: int        # 1 / 0 / -1
    state_match: int        # 1 / 0 / -1
    site_overlap: float     # jaccard, or -1
    markers_equal: int      # 1 / 0
    shared_vintages: int    # count of years credited by both
    vintage_ratio_spread: float  # consistency of the per-year ratios, or -1

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def hard_conflict(f: Features) -> str | None:
    """Reasons to reject a pair no matter how alike the names are.

    Each of these was observed separating a known false pair, and none of
    them fires on a known true pair.
    """
    if f.type_match == 0:
        return "type"
    if f.state_match == 0:
        return "state"
    if f.markers_equal == 0:
        return "marker"
    return None


def ratio_spread(shared: dict[int, tuple[int, int]]) -> float:
    """How consistent the two sides' volumes are across shared vintages.

    One physical project metered twice should keep a roughly constant
    relationship between the two registries' figures year on year. Two
    unrelated projects that happen to share a year have no reason to.
    Returns max/min of the yearly ratios; 1.0 is perfect consistency.
    A single shared year carries no information, so it returns -1.
    """
    if len(shared) < 2:
        return -1.0
    ratios = []
    for left, right in shared.values():
        if left <= 0 or right <= 0:
            return -1.0
        ratios.append(left / right)
    return round(max(ratios) / min(ratios), 4)


# --- corpus-derived vocabulary -------------------------------------------
#
# A project name carries two kinds of word. "Fajina Geothermal Based Space
# Heating System" and "Luohe Geothermal Based Space Heating System" are two
# plants in two Chinese cities; everything after the first word is the
# description of the technology, shared by nineteen other projects.
# Character-level similarity scores that pair at 0.81 because forty of the
# forty-six characters agree.
#
# Measuring document frequency over the 6,058 issuing projects separates
# the two kinds cleanly, with no overlap to arbitrate:
#
#   fajina 1 · luohe 1 · kielty 2 · heqing 2 · yangjiayao 4   (identity)
#   geothermal 19 · heating 12 · mine 106 · methane 190       (description)
#   wind 736 · power 878 · project 2,714                      (description)
#
# The cutoff is therefore derived from the corpus rather than chosen: a
# token appearing in under 1% of projects identifies, one above describes.
# Writing the list by hand would be arbitrary and would not survive a new
# dataset version.

GENERIC_DF_THRESHOLD = 0.01


def build_vocabulary(names: list[str]) -> frozenset[str]:
    """Tokens too frequent in this corpus to identify a single project."""
    if not names:
        return frozenset()
    counts: dict[str, int] = {}
    for name in names:
        for token in set(name.split()):
            counts[token] = counts.get(token, 0) + 1
    limit = GENERIC_DF_THRESHOLD * len(names)
    return frozenset(t for t, c in counts.items() if c > limit)


# Place names sit between the two kinds of word. Within India, "gujarat"
# appears in 66 projects and "karnataka" in 89 -- frequent enough to be
# filtered as vocabulary, yet they are exactly what separates two
# otherwise identically worded wind projects. Frequency alone cannot tell
# them apart from sector words, but exclusivity can: a place name occurs
# in one country and nowhere else, while "wind" and "project" occur
# everywhere. Such a token is treated as an identity marker, so two names
# carrying different ones are rejected rather than compared.

# Frequency cannot find these. A first attempt admitted a token as a place
# name only inside a frequency window, and that window failed at both ends:
# "gujarat" (6.8% of Indian projects) and "karnataka" (9.1%) sat above it,
# while "lalpur", "adavikanda" and "larimer" sat below it. Worse, a term
# above the window also escaped the generic-vocabulary filter, whose own
# cutoff is 1%, so the two mechanisms left a gap between them and a pair of
# wind projects in two different Indian states compared as identical.
#
# Exclusivity does find them, and needs no window to calibrate. "Gujarat"
# occurs only in India, "mordogan" only in Türkiye, "larimer" only in the
# United States. "Wind", "power" and "project" occur in scores of
# countries. A token confined to a single country names a place in that
# country at any frequency, so it is treated as an identity marker: two
# names carrying different ones are different projects.

MIN_PLACE_LENGTH = 4


def build_place_names(
    names_by_country: dict[str, list[str]],
) -> frozenset[str]:
    """Tokens occurring in exactly one country, at any frequency."""
    seen: dict[str, set[str]] = {}
    for country, names in names_by_country.items():
        for name in names:
            for token in set(name.split()):
                seen.setdefault(token, set()).add(country)

    return frozenset(
        token for token, countries in seen.items()
        if len(countries) == 1
        and len(token) >= MIN_PLACE_LENGTH
        and not token.isdigit()
    )


def distinctive(name_norm: str, generic: frozenset[str]) -> frozenset[str]:
    """What remains of a name once the sector vocabulary is removed.

    Pure digits are excluded here because they are handled separately as
    identity markers; a bare "2" is not a name.
    """
    return frozenset(
        token for token in name_norm.split()
        if token not in generic and not token.isdigit() and len(token) > 2
    )
