"""Aggregate-only, read-only analysis of cached recommendation inputs."""

from __future__ import annotations

import argparse
import json
import pickle
import random
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from music_taste.cache.profile_cache import (  # noqa: E402
    PROFILE_FILENAME,
    SPOTIFY_USER_ID_PATTERN,
    USER_PROFILE_CACHE_ROOT,
)
from music_taste.spotify.find_candidates import (  # noqa: E402
    CANDIDATE_ALBUMS_FILENAME,
)
from music_taste.spotify.rank_recommendations import (  # noqa: E402
    BALANCED_AFFINITY_STRATEGY,
    DISCOVERY_PERCENTILE_MAX,
    EXPANSION_PERCENTILE_MAX,
    EXPANSION_PERCENTILE_MIN,
    LOWEST_AFFINITY_STRATEGY,
    _attach_affinity_percentiles,
    score_candidate,
    select_final_recommendations,
)
from music_taste.spotify.score_familiarity import (  # noqa: E402
    calculate_album_familiarity,
)


def _distribution(values: list[float]) -> dict[float, int]:
    return dict(sorted(Counter(values).items()))


def analyze_cached_candidates(profile: dict, cached_albums: list[dict]) -> dict:
    """Return aggregate funnel, score, and tie metrics for cached albums."""

    eligible_albums = []
    for album in cached_albums:
        familiarity = calculate_album_familiarity(album, profile)
        if not familiarity["should_filter"]:
            eligible_albums.append({**album, "familiarity": familiarity})

    scored_albums = [score_candidate(album, profile) for album in eligible_albums]
    affinities = [
        album["recommendation"]["artist_affinity"] for album in scored_albums
    ]
    familiarity_scores = [
        album["familiarity"]["score"] for album in scored_albums
    ]
    recommendation_scores = [
        album["recommendation"]["score"] for album in scored_albums
    ]
    numeric_ranking_groups = Counter(
        (
            album["recommendation"]["score"],
            album["recommendation"]["artist_affinity"],
            album["familiarity"]["score"],
        )
        for album in scored_albums
    )
    score_distribution = Counter(recommendation_scores)
    tied_numeric_group_sizes = [
        size for size in numeric_ranking_groups.values() if size > 1
    ]
    eligible_count = len(eligible_albums)
    largest_score_tie = max(score_distribution.values(), default=0)
    text_tie_candidates = sum(tied_numeric_group_sizes)

    return {
        "cached_candidate_count": len(cached_albums),
        "unique_spotify_album_ids": len(
            {album.get("id") for album in cached_albums if album.get("id")}
        ),
        "familiarity_filtered_count": len(cached_albums) - eligible_count,
        "eligible_candidate_count": eligible_count,
        "final_selected_count": len(
            select_final_recommendations(eligible_albums, profile)
        ),
        "artist_affinity_distribution": _distribution(affinities),
        "familiarity_distribution": _distribution(familiarity_scores),
        "recommendation_score_distribution": _distribution(
            recommendation_scores
        ),
        "unique_recommendation_score_count": len(score_distribution),
        "largest_score_tie_count": largest_score_tie,
        "largest_score_tie_percentage": (
            100.0 * largest_score_tie / eligible_count if eligible_count else 0.0
        ),
        "numeric_tie_group_count": len(tied_numeric_group_sizes),
        "candidates_requiring_text_tiebreak": text_tie_candidates,
        "text_tiebreak_candidate_percentage": (
            100.0 * text_tie_candidates / eligible_count if eligible_count else 0.0
        ),
        "largest_numeric_tie_group": max(tied_numeric_group_sizes, default=0),
    }


def _eligible_scored_candidates(
    profile: dict,
    cached_albums: list[dict],
) -> list[dict]:
    eligible_albums = []
    for album in cached_albums:
        familiarity = calculate_album_familiarity(album, profile)
        if not familiarity["should_filter"]:
            eligible_albums.append({**album, "familiarity": familiarity})

    return _attach_affinity_percentiles(
        [score_candidate(album, profile) for album in eligible_albums]
    )


def _affinity_band(percentile: float) -> str:
    if percentile <= DISCOVERY_PERCENTILE_MAX:
        return "discovery"
    if EXPANSION_PERCENTILE_MIN <= percentile <= EXPANSION_PERCENTILE_MAX:
        return "expansion"
    return "other"


def _strategy_summary(recommendations: list[dict]) -> dict:
    affinities = [
        float(album["recommendation"]["artist_affinity"])
        for album in recommendations
    ]
    percentiles = [
        float(album["recommendation"]["affinity_percentile"])
        for album in recommendations
    ]
    scores = [
        float(album["recommendation"]["score"])
        for album in recommendations
    ]

    return {
        "average_affinity": sum(affinities) / len(affinities) if affinities else 0.0,
        "affinity_percentile_spread": (
            max(percentiles) - min(percentiles) if percentiles else 0.0
        ),
        "recommendation_score_spread": (
            max(scores) - min(scores) if scores else 0.0
        ),
        "unique_affinity_bands": len(
            {_affinity_band(percentile) for percentile in percentiles}
        ),
    }


def compare_recommendation_strategies(
    profile: dict,
    cached_albums: list[dict],
    random_seed: int | None = None,
) -> dict:
    """Compare baseline and balanced selection using the same eligible pool."""

    scored_candidates = _eligible_scored_candidates(profile, cached_albums)
    affinity_percentile_by_value = {
        album["recommendation"]["artist_affinity"]:
        album["recommendation"]["affinity_percentile"]
        for album in scored_candidates
    }
    # Selection scores candidates internally, so remove the analysis-only score
    # fields and retain the already attached familiarity input.
    eligible_candidates = [
        {
            key: value
            for key, value in album.items()
            if key != "recommendation"
        }
        for album in scored_candidates
    ]
    baseline = select_final_recommendations(
        eligible_candidates,
        profile,
        strategy=LOWEST_AFFINITY_STRATEGY,
    )
    balanced = select_final_recommendations(
        eligible_candidates,
        profile,
        strategy=BALANCED_AFFINITY_STRATEGY,
        random_generator=random.Random(random_seed),
    )

    def attach_percentile(albums):
        return [
            {
                **album,
                "recommendation": {
                    **album["recommendation"],
                    "affinity_percentile": affinity_percentile_by_value[
                        album["recommendation"]["artist_affinity"]
                    ],
                },
            }
            for album in albums
        ]

    baseline = attach_percentile(baseline)
    balanced = attach_percentile(balanced)
    baseline_ids = {album.get("id") for album in baseline}
    balanced_ids = {album.get("id") for album in balanced}

    return {
        "baseline": baseline,
        "balanced": balanced,
        "baseline_summary": _strategy_summary(baseline),
        "balanced_summary": _strategy_summary(balanced),
        "overlap_count": len(baseline_ids & balanced_ids),
    }


def _select_user_directory(cache_root: Path, spotify_user_id: str | None) -> Path:
    if spotify_user_id:
        if not SPOTIFY_USER_ID_PATTERN.fullmatch(spotify_user_id):
            raise ValueError("Spotify user ID contains unsupported characters.")
        candidates = [cache_root / spotify_user_id]
    else:
        candidates = sorted(
            path
            for path in cache_root.iterdir()
            if path.is_dir() and (path / PROFILE_FILENAME).is_file()
        ) if cache_root.exists() else []

    candidates = [path for path in candidates if (path / PROFILE_FILENAME).is_file()]
    if not candidates:
        raise FileNotFoundError("No cached profile was found.")
    if len(candidates) > 1:
        raise ValueError("Multiple cached profiles found; pass --user-id.")
    return candidates[0]


def load_analysis_inputs(
    cache_root: Path = USER_PROFILE_CACHE_ROOT,
    spotify_user_id: str | None = None,
) -> tuple[dict, list[dict]]:
    """Read one user's profile and candidate cache without modifying either."""

    user_directory = _select_user_directory(cache_root, spotify_user_id)
    candidate_cache_path = user_directory / CANDIDATE_ALBUMS_FILENAME
    with (user_directory / PROFILE_FILENAME).open("rb") as profile_file:
        profile = pickle.load(profile_file)
    with candidate_cache_path.open("r", encoding="utf-8") as candidate_file:
        cached_albums = json.load(candidate_file)

    if not isinstance(profile, dict):
        raise ValueError("Cached profile must be a dictionary.")
    if not isinstance(cached_albums, list):
        raise ValueError("Candidate cache must be a JSON list.")
    return profile, cached_albums


def _print_distribution(label: str, distribution: dict[float, int]) -> None:
    rendered = ", ".join(
        f"{value:g}: {count}" for value, count in distribution.items()
    )
    print(f"{label}: {rendered or 'none'}")


def print_analysis(metrics: dict) -> None:
    """Print aggregate metrics without artist names, album names, or IDs."""

    print("Cached Recommendation Pipeline Analysis")
    print(f"Cached candidates: {metrics['cached_candidate_count']}")
    print(f"Unique Spotify album IDs: {metrics['unique_spotify_album_ids']}")
    print(f"Filtered by familiarity: {metrics['familiarity_filtered_count']}")
    print(f"Eligible candidates: {metrics['eligible_candidate_count']}")
    print(f"Final selected: {metrics['final_selected_count']}")
    _print_distribution(
        "Artist affinity distribution",
        metrics["artist_affinity_distribution"],
    )
    _print_distribution(
        "Familiarity distribution",
        metrics["familiarity_distribution"],
    )
    _print_distribution(
        "Recommendation score distribution",
        metrics["recommendation_score_distribution"],
    )
    print(
        "Largest exact-score tie: "
        f"{metrics['largest_score_tie_count']} "
        f"({metrics['largest_score_tie_percentage']:.1f}%)"
    )
    print(f"Numeric tie groups: {metrics['numeric_tie_group_count']}")
    print(
        "Candidates requiring text/ID tie-breaks: "
        f"{metrics['candidates_requiring_text_tiebreak']} "
        f"({metrics['text_tiebreak_candidate_percentage']:.1f}%)"
    )
    print(f"Largest numeric tie group: {metrics['largest_numeric_tie_group']}")


def _print_recommendation_list(label: str, recommendations: list[dict]) -> None:
    print(f"\n{label}")
    for index, album in enumerate(recommendations, start=1):
        recommendation = album["recommendation"]
        familiarity = album.get("familiarity", {})
        artists = album.get("artists") or []
        artist_name = artists[0].get("name", "unknown artist") if artists else "unknown artist"
        print(f"{index}. {artist_name} — {album.get('name', 'unknown album')}")
        print(
            "   Score: "
            f"{recommendation['score']:.2f}; "
            f"affinity: {recommendation['artist_affinity']:g}; "
            f"percentile: {recommendation['affinity_percentile']:.1f}; "
            f"familiarity: {familiarity.get('score', 0):g} "
            f"({familiarity.get('level', 'unknown')})"
        )
        print(f"   Why: {recommendation['explanation']}")


def print_strategy_comparison(comparison: dict) -> None:
    """Print recommendation details and aggregate diversity statistics."""

    _print_recommendation_list("Current Strategy", comparison["baseline"])
    print("\n----------------------------")
    _print_recommendation_list("Balanced Strategy", comparison["balanced"])

    print("\nSummary")
    for label, summary_key in (
        ("Current", "baseline_summary"),
        ("Balanced", "balanced_summary"),
    ):
        summary = comparison[summary_key]
        print(
            f"{label}: average affinity {summary['average_affinity']:.2f}; "
            "affinity percentile spread "
            f"{summary['affinity_percentile_spread']:.1f}; "
            f"score spread {summary['recommendation_score_spread']:.2f}; "
            f"unique affinity bands {summary['unique_affinity_bands']}"
        )
    print(f"Recommendation overlap: {comparison['overlap_count']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", help="Analyze one cached Spotify user profile.")
    parser.add_argument(
        "--compare-strategies",
        action="store_true",
        help="Print named recommendation lists for baseline and balanced selection.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional repeatable random seed for balanced exact-tie selection.",
    )
    args = parser.parse_args()

    try:
        profile, cached_albums = load_analysis_inputs(
            spotify_user_id=args.user_id,
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError, pickle.UnpicklingError, ValueError) as error:
        print(f"Unable to analyze cached data: {error}", file=sys.stderr)
        return 1

    print_analysis(analyze_cached_candidates(profile, cached_albums))
    if args.compare_strategies:
        print_strategy_comparison(
            compare_recommendation_strategies(
                profile,
                cached_albums,
                random_seed=args.seed,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
