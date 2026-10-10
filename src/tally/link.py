"""Candidate matching for projects registered under more than one registry.

Scoring by name alone put "Weber County Landfill" (Utah) next to four other
county landfills in four other states, and paired a Gujarat wind farm with
a solar project. The words those names share are the words of the sector.

So a pair is now assembled as evidence rather than a similarity score. Two
names that look alike open the question; the remaining fields answer it.
The decisive part is negative: a field that is populated on both sides and
disagrees rejects the pair outright, because that is what separated every
false pair examined by hand. A field that is empty rejects nothing, because
absence is not evidence -- most non-US projects record no state at all.

Candidate generation still blocks by country and requires two different
registries. Country blocking is not only an optimization: it is what stops
an Indian wind farm matching a Chinese one, and every confirmed case of
double counting found so far sits inside a single country.

The output of this module is a candidate list with a feature vector per
pair, not a verdict. A vintage overlap is still required before a candidate
becomes a finding, and a finding published as such is reviewed by hand.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from tally.features import (
    Features, agreement, build_place_names, build_vocabulary, distinctive,
    hard_conflict, jaccard, normalize_org, place_tokens, ratio_spread,
)

# Gate for opening the question at all; the fields decide from here.
# All thirteen confirmed pairs score 1.00 on cosine, so 0.80 keeps every
# one of them with room to spare while discarding the 0.45-0.80 band where
# the generic-name pairs sit.
MIN_COSINE = 0.80
MIN_TOKEN_SET = 70.0

# Two names must share at least this much of their distinctive vocabulary.
# "fajina" and "luohe" share none; "kielty" and "kielty" share all.
MIN_DISTINCTIVE_OVERLAP = 0.34

MIN_BLOCK_FOR_TFIDF = 5
MIN_NAME_LENGTH = 9

DIRECTIONS = frozenset({
    "north", "south", "east", "west",
    "northeast", "northwest", "southeast", "southwest",
    "upper", "lower",
})

ROMAN = frozenset({"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"})

HAS_DIGIT = re.compile(r"\d")


def discriminators(
    name_norm: str, places: frozenset[str] = frozenset()
) -> frozenset[str]:
    """Tokens that say which project of a family this is.

    Any token with a digit, any roman numeral, any direction, and any
    country-exclusive place name. Without the first three, "Oaktown Fuel 1"
    and "Oaktown Fuel 2" score 0.98 and "Phase I" matches "Phase II" at 100
    on word-set comparison. Without the last, a Gujarat wind project
    matches a Karnataka one, since everything else in both names is the
    standard wording of the sector.
    """
    return frozenset(
        token for token in name_norm.split()
        if HAS_DIGIT.search(token) or token in ROMAN or token in DIRECTIONS
        or token in places
    )


@dataclass(frozen=True)
class Candidate:
    project_a: str
    project_b: str
    name_a: str
    name_b: str
    registry_a: str
    registry_b: str
    country: str
    exact_name: bool
    features: Features
    shared_vintages: tuple[int, ...]
    duplicated_milli: int


def load_issuing_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Projects that issued credits. A listing alone cannot double count."""
    return conn.execute(
        """
        SELECT project_id, registry, name, name_norm, country, state, type,
               scope, methodology, developer, owner, site_location,
               total_issued_milli
        FROM project
        WHERE total_issued_milli > 0 AND LENGTH(name_norm) >= ?
        ORDER BY country, project_id
        """,
        (MIN_NAME_LENGTH,),
    ).fetchall()


def load_vintages(conn: sqlite3.Connection) -> dict[str, dict[int, int]]:
    """Issued-by-vintage series for every project, in one query."""
    series: dict[str, dict[int, int]] = {}
    for row in conn.execute(
        "SELECT project_id, year, credits_milli FROM credit_year "
        "WHERE kind = 'issued_vintage' AND credits_milli > 0"
    ):
        series.setdefault(row["project_id"], {})[row["year"]] = row["credits_milli"]
    return series


def build_features(
    left: sqlite3.Row,
    right: sqlite3.Row,
    cosine: float,
    token_set: float,
    shared: dict[int, tuple[int, int]],
    places: frozenset[str] = frozenset(),
) -> Features:
    dev_a, dev_b = normalize_org(left["developer"]), normalize_org(right["developer"])
    developer_sim = (
        float(fuzz.token_set_ratio(dev_a, dev_b)) if dev_a and dev_b else -1.0
    )
    return Features(
        name_cosine=round(cosine, 4),
        name_token_set=token_set,
        developer_sim=developer_sim,
        methodology=agreement(left["methodology"], right["methodology"]),
        type_match=agreement(left["type"], right["type"]),
        scope_match=agreement(left["scope"], right["scope"]),
        state_match=agreement(left["state"], right["state"]),
        site_overlap=jaccard(
            place_tokens(left["site_location"]),
            place_tokens(right["site_location"]),
        ),
        markers_equal=int(
            discriminators(left["name_norm"], places)
            == discriminators(right["name_norm"], places)
        ),
        shared_vintages=len(shared),
        vintage_ratio_spread=ratio_spread(shared),
    )


def _block(
    rows: list[sqlite3.Row],
    vintages: dict[str, dict[int, int]],
    stats: dict[str, int],
    places: frozenset[str] = frozenset(),
) -> list[Candidate]:
    if len(rows) < 2:
        return []

    names = [r["name_norm"] for r in rows]
    generic = build_vocabulary(names)
    distinct = [distinctive(n, generic) for n in names]
    if len(rows) >= MIN_BLOCK_FOR_TFIDF:
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 3))
        similarity = cosine_similarity(vectorizer.fit_transform(names))
    else:
        similarity = None

    out: list[Candidate] = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if rows[i]["registry"] == rows[j]["registry"]:
                continue
            stats["compared"] += 1

            cosine = float(similarity[i][j]) if similarity is not None else 0.0
            if similarity is not None and cosine < MIN_COSINE:
                continue
            token_set = float(fuzz.token_set_ratio(names[i], names[j]))
            if token_set < MIN_TOKEN_SET:
                continue
            if similarity is None:
                cosine = token_set / 100.0

            stats["name_gate_passed"] += 1

            # Both sides keep distinctive words, and they must meet.
            da, db = distinct[i], distinct[j]
            if da and db:
                overlap = len(da & db) / len(da | db)
                if overlap < MIN_DISTINCTIVE_OVERLAP:
                    stats["rejected_distinctive"] += 1
                    continue

            va = vintages.get(rows[i]["project_id"], {})
            vb = vintages.get(rows[j]["project_id"], {})
            shared = {y: (va[y], vb[y]) for y in sorted(set(va) & set(vb))}

            features = build_features(
                rows[i], rows[j], cosine, token_set, shared, places
            )

            reason = hard_conflict(features)
            if reason:
                stats[f"rejected_{reason}"] += 1
                continue

            duplicated = sum(
                left + right - max(left, right) for left, right in shared.values()
            )
            out.append(
                Candidate(
                    project_a=rows[i]["project_id"],
                    project_b=rows[j]["project_id"],
                    name_a=rows[i]["name"],
                    name_b=rows[j]["name"],
                    registry_a=rows[i]["registry"],
                    registry_b=rows[j]["registry"],
                    country=rows[i]["country"],
                    exact_name=names[i] == names[j],
                    features=features,
                    shared_vintages=tuple(shared),
                    duplicated_milli=duplicated,
                )
            )
            stats["accepted"] += 1
    return out


def find_candidates(
    conn: sqlite3.Connection,
) -> tuple[list[Candidate], dict[str, int]]:
    rows = load_issuing_projects(conn)
    vintages = load_vintages(conn)

    blocks: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        blocks.setdefault(row["country"], []).append(row)

    stats = {
        "projects": len(rows), "countries": len(blocks), "compared": 0,
        "name_gate_passed": 0, "accepted": 0,
        "rejected_type": 0, "rejected_state": 0, "rejected_marker": 0,
        "rejected_distinctive": 0,
    }

    places = build_place_names(
        {c: [r["name_norm"] for r in rs] for c, rs in blocks.items()}
    )
    stats["place_names"] = len(places)

    candidates: list[Candidate] = []
    for block in blocks.values():
        candidates.extend(_block(block, vintages, stats, places))

    candidates.sort(key=lambda c: (-c.duplicated_milli, c.project_a, c.project_b))
    return candidates, stats
