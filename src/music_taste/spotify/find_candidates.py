import json
import re
import string
import time
from pathlib import Path

from music_taste.spotify.score_familiarity import calculate_album_familiarity


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_SPOTIFY_DIR = PROJECT_ROOT / "data" / "raw" / "spotify"
CANDIDATE_ALBUMS_CACHE_PATH = RAW_SPOTIFY_DIR / "candidate_albums.json"

VERSION_WORDS = [
    "anniversary",
    "bonus",
    "collector",
    "deluxe",
    "edition",
    "expanded",
    "explicit",
    "instrumental",
    "remaster",
    "remastered",
]

EXCLUDED_ALBUM_TITLE_TERMS = [
    "anniversary",
    "bonus",
    "collector",
    "deluxe",
    "expanded",
    "instrumental",
    "live",
    "remaster",
    "remastered",
    "remix",
    "remixed",
    "soundtrack",
]


SAVED_TRACK_ALBUM_KNOWN_THRESHOLD = 1
SPOTIFY_ARTIST_ALBUMS_MAX_LIMIT = 10


def _load_candidate_album_cache() -> list[dict] | None:
    if not CANDIDATE_ALBUMS_CACHE_PATH.exists():
        return None

    with CANDIDATE_ALBUMS_CACHE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_candidate_album_cache(albums: list[dict]) -> None:
    RAW_SPOTIFY_DIR.mkdir(parents=True, exist_ok=True)

    with CANDIDATE_ALBUMS_CACHE_PATH.open("w", encoding="utf-8") as file:
        json.dump(albums, file, indent=2)


# --- New helper functions ---
def normalize_album_name(name: str) -> str:
    normalized_name = name.lower()

    # Remove parenthetical/bracketed version text such as "(Deluxe)".
    normalized_name = re.sub(r"\([^)]*\)", "", normalized_name)
    normalized_name = re.sub(r"\[[^\]]*\]", "", normalized_name)

    for word in VERSION_WORDS:
        normalized_name = re.sub(rf"\b{word}\b", "", normalized_name)

    normalized_name = normalized_name.translate(str.maketrans("", "", string.punctuation))
    normalized_name = re.sub(r"\s+", " ", normalized_name)

    return normalized_name.strip()


def album_identity_key(album: dict) -> str:
    artists = album.get("artists", [])

    if not artists:
        primary_artist = "unknown_artist"
    else:
        primary_artist = artists[0].get("name", "unknown_artist").lower().strip()

    album_name = normalize_album_name(album.get("name", ""))

    return f"{primary_artist}::{album_name}"


def _is_unwanted_album_version(album: dict) -> bool:
    album_name = album.get("name", "").lower()

    return any(term in album_name for term in EXCLUDED_ALBUM_TITLE_TERMS)


def _saved_track_count_for_album(album_id: str | None, taste_profile: dict) -> int:
    if album_id is None:
        return 0

    saved_track_album_counts = taste_profile.get("saved_track_album_counts", {})

    return saved_track_album_counts.get(album_id, 0)


def _is_saved_track_only_album(album_id: str | None, taste_profile: dict) -> bool:
    if album_id is None:
        return False

    saved_track_album_ids = set(taste_profile.get("saved_track_album_ids", []))
    saved_album_ids = set(taste_profile.get("saved_album_ids", []))
    top_track_album_ids = set(taste_profile.get("top_track_album_ids", []))
    recent_album_ids = set(taste_profile.get("recent_album_ids", []))

    return (
        album_id in saved_track_album_ids
        and album_id not in saved_album_ids
        and album_id not in top_track_album_ids
        and album_id not in recent_album_ids
    )


def _is_known_album(album: dict, taste_profile: dict) -> bool:
    known_album_ids = set(taste_profile.get("known_album_ids", []))
    known_album_keys = set(taste_profile.get("known_album_keys", []))
    album_id = album.get("id")

    if _is_saved_track_only_album(album_id, taste_profile):
        saved_track_count = _saved_track_count_for_album(album_id, taste_profile)

        if saved_track_count < SAVED_TRACK_ALBUM_KNOWN_THRESHOLD:
            return False

    if album_id in known_album_ids:
        return True

    if known_album_keys and album_identity_key(album) in known_album_keys:
        return True

    return False


def _select_candidate_artist_ids(
    taste_profile: dict,
    limit_artists: int,
    excluded_top_artist_count: int,
    artist_selection_mode: str,
) -> list[str]:
    artist_scores = taste_profile["artist_scores"]
    top_artist_ids = taste_profile.get("top_artist_ids", [])
    excluded_artist_ids = set(top_artist_ids[:excluded_top_artist_count])

    eligible_artist_ids = [
        artist_id
        for artist_id in artist_scores
        if artist_id not in excluded_artist_ids
    ]

    if artist_selection_mode == "low_familiarity":
        sorted_artist_ids = sorted(
            eligible_artist_ids,
            key=lambda artist_id: (artist_scores[artist_id], artist_id),
        )
    elif artist_selection_mode == "adjacent":
        sorted_artist_ids = sorted(
            eligible_artist_ids,
            key=lambda artist_id: (artist_scores[artist_id], artist_id),
            reverse=True,
        )
    else:
        raise ValueError(
            "artist_selection_mode must be either 'low_familiarity' or 'adjacent'."
        )

    return sorted_artist_ids[:limit_artists]


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
    limit_artists: int = 25,
    albums_per_request: int = 10,
    max_pages_per_artist: int = 3,
    request_delay_seconds: float = 0.35,
    use_cache: bool = True,
    excluded_top_artist_count: int = 10,
    artist_selection_mode: str = "low_familiarity",
) -> list[dict]:
    if use_cache:
        cached_albums = _load_candidate_album_cache()

        if cached_albums is not None:
            return _attach_familiarity(cached_albums, taste_profile)

    candidate_artist_ids = _select_candidate_artist_ids(
        taste_profile=taste_profile,
        limit_artists=limit_artists,
        excluded_top_artist_count=excluded_top_artist_count,
        artist_selection_mode=artist_selection_mode,
    )
    request_limit = min(albums_per_request, SPOTIFY_ARTIST_ALBUMS_MAX_LIMIT)

    raw_candidate_albums = []
    seen_album_ids = set()

    for artist_id in candidate_artist_ids:
        offset = 0
        pages_fetched = 0

        while pages_fetched < max_pages_per_artist:
            response = sp.artist_albums(
                artist_id,
                album_type="album",
                country="US",
                limit=request_limit,
                offset=offset,
            )

            items = response["items"]

            if not items:
                break

            for album in items:
                album_id = album["id"]

                if album_id in seen_album_ids:
                    continue

                if _is_known_album(album, taste_profile):
                    continue

                if _is_unwanted_album_version(album):
                    continue

                seen_album_ids.add(album_id)
                raw_candidate_albums.append(album)

            pages_fetched += 1

            if not response["next"]:
                break

            offset += request_limit
            time.sleep(request_delay_seconds)

        time.sleep(request_delay_seconds)

    _save_candidate_album_cache(raw_candidate_albums)

    return _attach_familiarity(raw_candidate_albums, taste_profile)