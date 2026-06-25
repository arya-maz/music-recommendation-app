import json
import time
from pathlib import Path

from music_taste.spotify.score_familiarity import calculate_album_familiarity


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_SPOTIFY_DIR = PROJECT_ROOT / "data" / "raw" / "spotify"
CANDIDATE_ALBUMS_CACHE_PATH = RAW_SPOTIFY_DIR / "candidate_albums.json"


def _load_candidate_album_cache() -> list[dict] | None:
    if not CANDIDATE_ALBUMS_CACHE_PATH.exists():
        return None

    with CANDIDATE_ALBUMS_CACHE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_candidate_album_cache(albums: list[dict]) -> None:
    RAW_SPOTIFY_DIR.mkdir(parents=True, exist_ok=True)

    with CANDIDATE_ALBUMS_CACHE_PATH.open("w", encoding="utf-8") as file:
        json.dump(albums, file, indent=2)


def _attach_familiarity(albums: list[dict], taste_profile: dict) -> list[dict]:
    candidate_albums = []

    for album in albums:
        familiarity = calculate_album_familiarity(album, taste_profile)

        if familiarity["should_filter"]:
            continue

        candidate_albums.append(
            {
                **album,
                "familiarity": familiarity,
            }
        )

    return candidate_albums


def find_candidate_albums(
    sp,
    taste_profile: dict,
    limit_artists: int = 10,
    albums_per_request: int = 10,
    max_pages_per_artist: int = 1,
    request_delay_seconds: float = 0.35,
    use_cache: bool = True,
) -> list[dict]:
    if use_cache:
        cached_albums = _load_candidate_album_cache()

        if cached_albums is not None:
            return _attach_familiarity(cached_albums, taste_profile)

    artist_scores = taste_profile["artist_scores"]

    top_artist_ids = sorted(
        artist_scores,
        key=artist_scores.get,
        reverse=True,
    )[:limit_artists]

    raw_candidate_albums = []
    seen_album_ids = set()

    for artist_id in top_artist_ids:
        offset = 0
        pages_fetched = 0

        while pages_fetched < max_pages_per_artist:
            response = sp.artist_albums(
                artist_id,
                album_type="album",
                country="US",
                limit=albums_per_request,
                offset=offset,
            )

            items = response["items"]

            if not items:
                break

            for album in items:
                album_id = album["id"]

                if album_id in seen_album_ids:
                    continue

                seen_album_ids.add(album_id)
                raw_candidate_albums.append(album)

            pages_fetched += 1

            if not response["next"]:
                break

            offset += albums_per_request
            time.sleep(request_delay_seconds)

        time.sleep(request_delay_seconds)

    _save_candidate_album_cache(raw_candidate_albums)

    return _attach_familiarity(raw_candidate_albums, taste_profile)