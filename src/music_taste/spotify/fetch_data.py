import json
from pathlib import Path

from music_taste.spotify.client import get_spotify_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_SPOTIFY_DIR = PROJECT_ROOT / "data" / "raw" / "spotify"


def save_json(data, filename: str) -> None:
    RAW_SPOTIFY_DIR.mkdir(parents=True, exist_ok=True)

    output_path = RAW_SPOTIFY_DIR / filename

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def fetch_top_artists(sp, limit: int = 50, time_range: str = "medium_term"):
    return sp.current_user_top_artists(
        limit=limit,
        time_range=time_range,
    )["items"]


def fetch_top_tracks(sp, limit: int = 50, time_range: str = "medium_term"):
    return sp.current_user_top_tracks(
        limit=limit,
        time_range=time_range,
    )["items"]


def fetch_recently_played(sp, limit: int = 50):
    return sp.current_user_recently_played(limit=limit)["items"]


def fetch_saved_albums(sp, limit: int = 50):
    albums = []
    offset = 0

    while True:
        response = sp.current_user_saved_albums(
            limit=limit,
            offset=offset,
        )

        albums.extend(response["items"])

        if not response["next"]:
            break

        offset += limit

    return albums


def fetch_saved_tracks(sp, limit: int = 50):
    tracks = []
    offset = 0

    while True:
        response = sp.current_user_saved_tracks(
            limit=limit,
            offset=offset,
        )

        tracks.extend(response["items"])

        if not response["next"]:
            break

        offset += limit

    return tracks


def fetch_and_save_spotify_data() -> dict:
    sp = get_spotify_client()

    spotify_data = {
        "top_artists": fetch_top_artists(sp),
        "top_tracks": fetch_top_tracks(sp),
        "recently_played": fetch_recently_played(sp),
        "saved_albums": fetch_saved_albums(sp),
        "saved_tracks": fetch_saved_tracks(sp),
    }

    save_json(spotify_data["top_artists"], "top_artists.json")
    save_json(spotify_data["top_tracks"], "top_tracks.json")
    save_json(spotify_data["recently_played"], "recently_played.json")
    save_json(spotify_data["saved_albums"], "saved_albums.json")
    save_json(spotify_data["saved_tracks"], "saved_tracks.json")

    return spotify_data