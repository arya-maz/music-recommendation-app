from __future__ import annotations


FINAL_RECOMMENDATION_COUNT = 5
ARTIST_RELEVANCE_WEIGHT = 0.60
DISCOVERY_VALUE_WEIGHT = 0.40
ARTIST_AFFINITY_HALF_SATURATION = 50.0


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


def select_final_recommendations(
    candidate_albums: list[dict],
    taste_profile: dict,
    recommendation_count: int = FINAL_RECOMMENDATION_COUNT,
) -> list[dict]:
    """Return the strongest album for each primary artist, up to the limit."""

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
