import re
import string
from collections import defaultdict


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

SAVED_TRACK_ALBUM_KNOWN_THRESHOLD = 2


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


def build_taste_profile(spotify_data: dict) -> dict:
    artist_scores = defaultdict(float)

    known_album_ids = set()
    known_album_keys = set()
    saved_album_ids = set()
    top_track_album_ids = set()
    recent_album_ids = set()
    saved_track_album_ids = set()
    saved_track_album_counts = defaultdict(int)
    saved_track_album_objects = {}

    top_artist_ids = []

    # Top artists are the strongest artist-level signal.
    for rank, artist in enumerate(spotify_data["top_artists"], start=1):
        artist_id = artist["id"]
        top_artist_ids.append(artist_id)

        # Higher-ranked artists get more weight.
        artist_scores[artist_id] += max(1, 51 - rank)

    # Top tracks reveal artists and albums the user strongly returns to.
    for rank, track in enumerate(spotify_data["top_tracks"], start=1):
        album = track["album"]
        album_id = album["id"]

        known_album_ids.add(album_id)
        known_album_keys.add(album_identity_key(album))
        top_track_album_ids.add(album_id)

        track_score = max(1, 51 - rank)

        for artist in track["artists"]:
            artist_scores[artist["id"]] += track_score * 0.5

    # Saved albums are albums the user already knows and likely values.
    for item in spotify_data["saved_albums"]:
        album = item["album"]
        album_id = album["id"]

        known_album_ids.add(album_id)
        known_album_keys.add(album_identity_key(album))
        saved_album_ids.add(album_id)

        for artist in album["artists"]:
            artist_scores[artist["id"]] += 25

    # Saved tracks are strong song-level interest signals.
    for item in spotify_data["saved_tracks"]:
        track = item["track"]
        album = track["album"]
        album_id = album["id"]

        saved_track_album_counts[album_id] += 1
        saved_track_album_objects[album_id] = album
        saved_track_album_ids.add(album_id)

        for artist in track["artists"]:
            artist_scores[artist["id"]] += 10

    # Recent plays capture the user's current phase.
    for item in spotify_data["recently_played"]:
        track = item["track"]
        album = track["album"]
        album_id = album["id"]

        known_album_ids.add(album_id)
        known_album_keys.add(album_identity_key(album))
        recent_album_ids.add(album_id)

        for artist in track["artists"]:
            artist_scores[artist["id"]] += 5

    for album_id, saved_track_count in saved_track_album_counts.items():
        if saved_track_count >= SAVED_TRACK_ALBUM_KNOWN_THRESHOLD:
            known_album_ids.add(album_id)
            known_album_keys.add(album_identity_key(saved_track_album_objects[album_id]))

    return {
        "artist_scores": dict(artist_scores),
        "top_artist_ids": top_artist_ids,
        "known_album_ids": list(known_album_ids),
        "known_album_keys": list(known_album_keys),
        "saved_album_ids": list(saved_album_ids),
        "top_track_album_ids": list(top_track_album_ids),
        "recent_album_ids": list(recent_album_ids),
        "saved_track_album_ids": list(saved_track_album_ids),
        "saved_track_album_counts": dict(saved_track_album_counts),
    }