import json
from pathlib import Path

def save_json(data, filename: str, user_directory: Path) -> None:
    user_directory.mkdir(parents=True, exist_ok=True)
    output_path = user_directory / filename

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


def fetch_and_save_spotify_data(sp, user_directory: Path) -> dict:
    spotify_data = {
        "top_artists": fetch_top_artists(sp),
        "top_tracks": fetch_top_tracks(sp),
        "recently_played": fetch_recently_played(sp),
        "saved_albums": fetch_saved_albums(sp),
        "saved_tracks": fetch_saved_tracks(sp),
    }

    save_json(spotify_data["top_artists"], "top_artists.json", user_directory)
    save_json(spotify_data["top_tracks"], "top_tracks.json", user_directory)
    save_json(spotify_data["recently_played"], "recently_played.json", user_directory)
    save_json(spotify_data["saved_albums"], "saved_albums.json", user_directory)
    save_json(spotify_data["saved_tracks"], "saved_tracks.json", user_directory)

    return spotify_data
