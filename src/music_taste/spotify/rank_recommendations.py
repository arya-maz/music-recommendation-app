from __future__ import annotations

import random
from itertools import groupby


FINAL_RECOMMENDATION_COUNT = 5
ARTIST_RELEVANCE_WEIGHT = 0.60
DISCOVERY_VALUE_WEIGHT = 0.40
ARTIST_AFFINITY_HALF_SATURATION = 50.0

LOWEST_AFFINITY_STRATEGY = "lowest_affinity"
BALANCED_AFFINITY_STRATEGY = "balanced_affinity"
DEFAULT_RECOMMENDATION_STRATEGY = BALANCED_AFFINITY_STRATEGY

DISCOVERY_PERCENTILE_MAX = 30.0
EXPANSION_PERCENTILE_MIN = 50.0
EXPANSION_PERCENTILE_MAX = 90.0
DISCOVERY_RECOMMENDATION_COUNT = 3
EXPANSION_RECOMMENDATION_COUNT = 2


def _primary_artist(album: dict) -> dict:
    artists = album.get("artists") or []

    if not artists:
        return {}

    return artists[0]


def _normalized_text(value: object) -> str:
    return str(value or "").strip().casefold()


def _artist_affinity(album: dict, taste_profile: dict) -> float:
    artist_id = _primary_artist(album).get("id")
    artist_scores = taste_profile.get("artist_scores", {})

    return float(artist_scores.get(artist_id, 0.0))


def _normalized_artist_relevance(artist_affinity: float) -> float:
    if artist_affinity <= 0:
        return 0.0

    return 100.0 * artist_affinity / (
        artist_affinity + ARTIST_AFFINITY_HALF_SATURATION
    )


def _recommendation_explanation(
    artist_relevance: float,
    familiarity_score: float,
) -> str:
    if artist_relevance >= 60:
        fit_description = "strong artist-fit evidence"
    elif artist_relevance >= 30:
        fit_description = "meaningful prior artist interest"
    else:
        fit_description = "some prior artist interest"

    if familiarity_score == 0:
        discovery_description = "no album-familiarity signals"
    elif familiarity_score <= 25:
        discovery_description = "low album familiarity"
    else:
        discovery_description = "some album familiarity"

    return f"{fit_description}; {discovery_description}"


def score_candidate(album: dict, taste_profile: dict) -> dict:
    """Attach an explainable relevance/discovery score to one eligible album."""

    familiarity = album.get("familiarity", {})
    familiarity_score = float(familiarity.get("score", 0.0))
    artist_affinity = _artist_affinity(album, taste_profile)
    artist_relevance = _normalized_artist_relevance(artist_affinity)
    discovery_value = max(0.0, 100.0 - familiarity_score)
    recommendation_score = (
        ARTIST_RELEVANCE_WEIGHT * artist_relevance
        + DISCOVERY_VALUE_WEIGHT * discovery_value
    )

    return {
        **album,
        "recommendation": {
            "score": recommendation_score,
            "artist_affinity": artist_affinity,
            "artist_relevance": artist_relevance,
            "discovery_value": discovery_value,
            "explanation": _recommendation_explanation(
                artist_relevance,
                familiarity_score,
            ),
        },
    }


def _ranking_key(album: dict) -> tuple:
    recommendation = album["recommendation"]
    familiarity = album.get("familiarity", {})
    artist_name = _primary_artist(album).get("name", "")

    # Text and ID fields make ties independent of candidate input order.
    return (
        -recommendation["score"],
        -recommendation["artist_affinity"],
        float(familiarity.get("score", 0.0)),
        _normalized_text(artist_name),
        _normalized_text(album.get("name")),
        _normalized_text(album.get("id")),
    )


def rank_candidates(candidate_albums: list[dict], taste_profile: dict) -> list[dict]:
    """Score and deterministically rank the complete eligible candidate pool."""

    scored_candidates = [
        score_candidate(album, taste_profile) for album in candidate_albums
    ]
    return sorted(scored_candidates, key=_ranking_key)


def _attach_affinity_percentiles(scored_candidates: list[dict]) -> list[dict]:
    """Attach a tie-aware percentile calculated across candidate album rows."""

    if not scored_candidates:
        return []

    affinities = [
        float(album["recommendation"]["artist_affinity"])
        for album in scored_candidates
    ]
    sorted_affinities = sorted(affinities)
    candidate_count = len(sorted_affinities)

    if candidate_count == 1 or len(set(sorted_affinities)) == 1:
        percentiles = {affinity: 50.0 for affinity in set(sorted_affinities)}
    else:
        percentiles = {}
        for affinity in set(sorted_affinities):
            lower_count = sum(value < affinity for value in sorted_affinities)
            equal_count = sum(value == affinity for value in sorted_affinities)
            average_zero_based_rank = lower_count + (equal_count - 1) / 2
            percentiles[affinity] = (
                100.0 * average_zero_based_rank / (candidate_count - 1)
            )

    return [
        {
            **album,
            "recommendation": {
                **album["recommendation"],
                "affinity_percentile": percentiles[
                    float(album["recommendation"]["artist_affinity"])
                ],
            },
        }
        for album in scored_candidates
    ]


def _balanced_numeric_key(album: dict) -> tuple[float, float]:
    return (
        -float(album["recommendation"]["score"]),
        float(album.get("familiarity", {}).get("score", 0.0)),
    )


def _rank_with_random_exact_ties(
    scored_candidates: list[dict],
    random_generator=None,
) -> list[dict]:
    """Rank numerically, randomizing only candidates tied on score/familiarity."""

    generator = random_generator or random
    ordered_candidates = sorted(scored_candidates, key=_balanced_numeric_key)
    randomized_candidates = []

    for _, tied_group in groupby(ordered_candidates, key=_balanced_numeric_key):
        group = list(tied_group)
        generator.shuffle(group)
        randomized_candidates.extend(group)

    return randomized_candidates


def _select_unique_artists(
    ranked_candidates: list[dict],
    selected_recommendations: list[dict],
    selected_artists: set[str],
    target_count: int,
) -> None:
    for album in ranked_candidates:
        if len(selected_recommendations) >= target_count:
            break

        artist_name = _primary_artist(album).get("name", "unknown artist")
        artist_key = _normalized_text(artist_name)

        if artist_key in selected_artists:
            continue

        selected_artists.add(artist_key)
        selected_recommendations.append(album)


def select_balanced_affinity_recommendations(
    candidate_albums: list[dict],
    taste_profile: dict,
    recommendation_count: int = FINAL_RECOMMENDATION_COUNT,
    random_generator=None,
) -> list[dict]:
    """Select discovery and expansion recommendations from percentile bands."""

    scored_candidates = [
        score_candidate(album, taste_profile) for album in candidate_albums
    ]
    candidates_with_percentiles = _attach_affinity_percentiles(scored_candidates)
    discovery_candidates = [
        album
        for album in candidates_with_percentiles
        if album["recommendation"]["affinity_percentile"]
        <= DISCOVERY_PERCENTILE_MAX
    ]
    expansion_candidates = [
        album
        for album in candidates_with_percentiles
        if EXPANSION_PERCENTILE_MIN
        <= album["recommendation"]["affinity_percentile"]
        <= EXPANSION_PERCENTILE_MAX
    ]

    selected_recommendations = []
    selected_artists = set()
    discovery_target = min(
        DISCOVERY_RECOMMENDATION_COUNT,
        recommendation_count,
    )
    _select_unique_artists(
        _rank_with_random_exact_ties(discovery_candidates, random_generator),
        selected_recommendations,
        selected_artists,
        discovery_target,
    )

    expansion_target = min(
        discovery_target + EXPANSION_RECOMMENDATION_COUNT,
        recommendation_count,
    )
    _select_unique_artists(
        _rank_with_random_exact_ties(expansion_candidates, random_generator),
        selected_recommendations,
        selected_artists,
        expansion_target,
    )

    # If either band cannot fill its allocation, use the best remaining eligible
    # candidates from any percentile so a sufficiently diverse pool still fills.
    _select_unique_artists(
        _rank_with_random_exact_ties(
            candidates_with_percentiles,
            random_generator,
        ),
        selected_recommendations,
        selected_artists,
        recommendation_count,
    )

    # Re-establish global numeric quality order without re-randomizing candidates
    # across affinity bands. Python's stable sort preserves each band's tie order.
    return sorted(selected_recommendations, key=_balanced_numeric_key)


def select_final_recommendations(
    candidate_albums: list[dict],
    taste_profile: dict,
    recommendation_count: int = FINAL_RECOMMENDATION_COUNT,
    strategy: str = DEFAULT_RECOMMENDATION_STRATEGY,
    random_generator=None,
) -> list[dict]:
    """Return the strongest album for each primary artist, up to the limit."""

    if strategy == BALANCED_AFFINITY_STRATEGY:
        return select_balanced_affinity_recommendations(
            candidate_albums,
            taste_profile,
            recommendation_count=recommendation_count,
            random_generator=random_generator,
        )

    if strategy != LOWEST_AFFINITY_STRATEGY:
        raise ValueError(
            "strategy must be either 'lowest_affinity' or 'balanced_affinity'."
        )

    ranked_candidates = rank_candidates(candidate_albums, taste_profile)
    selected_recommendations = []
    selected_artists = set()

    for album in ranked_candidates:
        artist_name = _primary_artist(album).get("name", "unknown artist")
        artist_key = _normalized_text(artist_name)

        if artist_key in selected_artists:
            continue

        selected_artists.add(artist_key)
        selected_recommendations.append(album)

        if len(selected_recommendations) >= recommendation_count:
            break

    return selected_recommendations
