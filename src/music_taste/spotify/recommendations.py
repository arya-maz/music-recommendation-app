from __future__ import annotations

from dataclasses import dataclass

from music_taste.spotify.build_profile import build_taste_profile
from music_taste.spotify.fetch_data import fetch_and_save_spotify_data
from music_taste.spotify.find_candidates import find_candidate_albums
from music_taste.spotify.rank_recommendations import (
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


def prepare_user_profile(spotify_client) -> dict:
    """Collect Spotify data and build the complete taste profile."""

    spotify_data = fetch_and_save_spotify_data(spotify_client)
    return build_taste_profile(spotify_data)


def generate_recommendations_from_profile(
    spotify_client,
    taste_profile: dict,
    limit: int = FINAL_RECOMMENDATION_COUNT,
) -> list[Recommendation]:
    """Generate structured recommendations from an already-prepared profile."""

    candidate_albums = find_candidate_albums(spotify_client, taste_profile)
    selected_albums = select_final_recommendations(
        candidate_albums,
        taste_profile,
        recommendation_count=limit,
    )

    return [_recommendation_from_album(album) for album in selected_albums]


def generate_recommendations(
    spotify_client,
    limit: int = FINAL_RECOMMENDATION_COUNT,
) -> list[Recommendation]:
    """Prepare a profile and generate recommendations in one convenience call."""

    taste_profile = prepare_user_profile(spotify_client)
    return generate_recommendations_from_profile(
        spotify_client,
        taste_profile,
        limit=limit,
    )
