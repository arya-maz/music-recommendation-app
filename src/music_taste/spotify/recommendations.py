from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from music_taste.cache.profile_cache import (
    USER_PROFILE_CACHE_ROOT,
    get_user_cache_directory,
    load_cached_profile,
    migrate_legacy_spotify_data,
    save_cached_profile,
)
from music_taste.spotify.build_profile import build_taste_profile
from music_taste.spotify.fetch_data import fetch_and_save_spotify_data
from music_taste.spotify.find_candidates import find_candidate_albums
from music_taste.spotify.rank_recommendations import (
    DEFAULT_RECOMMENDATION_STRATEGY,
    FINAL_RECOMMENDATION_COUNT,
    select_final_recommendations,
)


@dataclass(frozen=True)
class Recommendation:
    artist_name: str
    album_name: str
    spotify_url: str | None
    album_image_url: str | None
    recommendation_score: float
    reason: str
    artist_affinity: float
    familiarity_score: float
    familiarity_label: str


def _spotify_url(album: dict) -> str | None:
    external_urls = album.get("external_urls") or {}
    return external_urls.get("spotify")


def _album_image_url(album: dict) -> str | None:
    images = album.get("images") or []

    if not images:
        return None

    return images[0].get("url")


def _recommendation_from_album(album: dict) -> Recommendation:
    artist_name = ", ".join(
        artist.get("name", "unknown artist")
        for artist in album.get("artists", [])
    ) or "unknown artist"
    recommendation = album["recommendation"]
    familiarity = album.get("familiarity", {})

    return Recommendation(
        artist_name=artist_name,
        album_name=album.get("name", "unknown album"),
        spotify_url=_spotify_url(album),
        album_image_url=_album_image_url(album),
        recommendation_score=float(recommendation["score"]),
        reason=recommendation["explanation"],
        artist_affinity=float(recommendation["artist_affinity"]),
        familiarity_score=float(familiarity.get("score", 0.0)),
        familiarity_label=familiarity.get("level", "unknown"),
    )


def _authenticated_user_id(spotify_client) -> str:
    spotify_user = spotify_client.current_user()
    spotify_user_id = spotify_user.get("id") if isinstance(spotify_user, dict) else None
    if not isinstance(spotify_user_id, str) or not spotify_user_id:
        raise ValueError("Spotify current-user response is missing the user ID.")
    return spotify_user_id


def prepare_user_profile(spotify_client, user_directory: Path) -> dict:
    """Collect Spotify data and build the complete taste profile."""

    spotify_data = fetch_and_save_spotify_data(spotify_client, user_directory)
    return build_taste_profile(spotify_data)


def get_or_prepare_user_profile(
    spotify_client,
    cache_root: Path = USER_PROFILE_CACHE_ROOT,
) -> dict:
    """Load the authenticated user's profile or prepare and cache a fresh one."""

    spotify_user_id = _authenticated_user_id(spotify_client)
    if cache_root == USER_PROFILE_CACHE_ROOT:
        migrate_legacy_spotify_data(spotify_user_id, cache_root=cache_root)
    user_directory = get_user_cache_directory(spotify_user_id, cache_root, create=True)

    cached_profile = load_cached_profile(
        spotify_user_id,
        cache_root=cache_root,
    )

    if cached_profile is not None:
        return cached_profile

    taste_profile = prepare_user_profile(spotify_client, user_directory)
    save_cached_profile(
        spotify_user_id,
        taste_profile,
        cache_root=cache_root,
    )
    return taste_profile


def generate_recommendations_from_profile(
    spotify_client,
    taste_profile: dict,
    limit: int = FINAL_RECOMMENDATION_COUNT,
    strategy: str = DEFAULT_RECOMMENDATION_STRATEGY,
    cache_root: Path = USER_PROFILE_CACHE_ROOT,
) -> list[Recommendation]:
    """Generate structured recommendations from an already-prepared profile."""

    spotify_user_id = _authenticated_user_id(spotify_client)
    user_directory = get_user_cache_directory(spotify_user_id, cache_root, create=True)
    candidate_albums = find_candidate_albums(
        spotify_client,
        taste_profile,
        user_directory,
    )
    if strategy == DEFAULT_RECOMMENDATION_STRATEGY:
        selected_albums = select_final_recommendations(
            candidate_albums,
            taste_profile,
            recommendation_count=limit,
        )
    else:
        selected_albums = select_final_recommendations(
            candidate_albums,
            taste_profile,
            recommendation_count=limit,
            strategy=strategy,
        )

    return [_recommendation_from_album(album) for album in selected_albums]


def generate_recommendations(
    spotify_client,
    limit: int = FINAL_RECOMMENDATION_COUNT,
    strategy: str = DEFAULT_RECOMMENDATION_STRATEGY,
) -> list[Recommendation]:
    """Load or prepare a profile and generate recommendations in one call."""

    taste_profile = get_or_prepare_user_profile(spotify_client)
    if strategy == DEFAULT_RECOMMENDATION_STRATEGY:
        return generate_recommendations_from_profile(
            spotify_client,
            taste_profile,
            limit=limit,
        )

    return generate_recommendations_from_profile(
        spotify_client,
        taste_profile,
        limit=limit,
        strategy=strategy,
    )
