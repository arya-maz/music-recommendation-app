from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "aoty_cleaned.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "aoty_enriched.csv"
REVIEW_PATH = PROJECT_ROOT / "data" / "processed" / "aoty_tags_for_review.csv"
TAG_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "lastfm_album_tags_cache.json"
METADATA_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "lastfm_album_metadata_cache.json"

LASTFM_API_ROOT = "https://ws.audioscrobbler.com/2.0/"
REQUEST_DELAY_SECONDS = 0.25
MAX_TAGS = 3

FINAL_OUTPUT_COLUMNS = [
    "Artist",
    "Album",
    "Year",
    "Number of tracks",
    "Runtime",
    "Genre 1",
    "Genre 2",
    "Genre 3",
    "Score",
]


GENRE_TAG_ALIASES = {
    "hip hop": "hip-hop",
    "hiphop": "hip-hop",
    "hip-hop": "hip-hop",
    "r&b": "rnb",
    "rhythm and blues": "rnb",
    "contemporary randb": "contemporary rnb",
    "neo soul": "neo-soul",
    "hardcore hip hop": "hardcore hip-hop",
    "abstract hip hop": "abstract hip-hop",
    "southern hip hop": "southern hip-hop",
    "east coast hip hop": "east coast hip-hop",
    "west coast hip hop": "west coast hip-hop",
    "instrumental hip hop": "instrumental hip-hop",
    "alt pop": "alt-pop",
}

IGNORED_TAGS = {
    "album",
    "albums",
    "albums i own",
    "american",
    "aoty",
    "auto-tagged",
    "best",
    "check",
    "classic",
    "comfort album",
    "favorite",
    "favorites",
    "favourite",
    "favourite albums",
    "favourites",
    "finished",
    "grammy",
    "male vocalists",
    "female vocalists",
    "female vocalist",
    "listen list",
    "lp",
    "masterpiece",
    "mid",
    "my albums",
    "owned",
    "randomvalue",
    "seen live",
    "skipless albums",
    "spotify",
    "title is declarative",
    "usa",
    "vinyl",
    "want to listen",
    "website",
    "wikipedia",
}

IGNORED_TAG_PHRASES = {
    "best of",
    "album of the year",
    "albums of",
    "favorite albums",
    "favourite albums",
    "number one",
    "out of 5",
    "out of five",
}

ACCEPTED_GENRE_TAGS = {
    "alternative metal",
    "alternative rock",
    "ambient",
    "art pop",
    "black metal",
    "boom bap",
    "cloud rap",
    "conscious hip-hop",
    "contemporary rnb",
    "death metal",
    "doom metal",
    "dream pop",
    "east coast hip-hop",
    "electronic",
    "emo",
    "experimental",
    "experimental hip-hop",
    "folk",
    "funk",
    "garage rock",
    "glitch pop",
    "grunge",
    "hard rock",
    "hardcore hip-hop",
    "hardcore punk",
    "heavy metal",
    "hip-hop",
    "indie pop",
    "indie rock",
    "industrial",
    "industrial hip-hop",
    "jazz",
    "jazz rap",
    "metal",
    "metalcore",
    "neo-soul",
    "noise rock",
    "nu metal",
    "pop",
    "pop rap",
    "post-hardcore",
    "post-punk",
    "progressive metal",
    "progressive rock",
    "psychedelic rock",
    "punk",
    "punk rock",
    "rap",
    "rnb",
    "shoegaze",
    "singer-songwriter",
    "sludge metal",
    "soul",
    "southern hip-hop",
    "synthpop",
    "trap",
    "west coast hip-hop",
}

ACCEPTED_TAG_PHRASES = {
    "ambient",
    "blues",
    "core",
    "country",
    "dance",
    "disco",
    "doom",
    "dream",
    "drone",
    "dub",
    "electro",
    "electronic",
    "emo",
    "folk",
    "funk",
    "garage",
    "gaze",
    "grind",
    "grunge",
    "hardcore",
    "hip-hop",
    "hop",
    "house",
    "industrial",
    "jazz",
    "metal",
    "noise",
    "pop",
    "post-",
    "prog",
    "progressive",
    "punk",
    "rap",
    "rnb",
    "rock",
    "shoegaze",
    "soul",
    "synth",
    "techno",
    "trap",
    "wave",
}


def get_api_key() -> str:
    api_key = os.getenv("LASTFM_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "Missing LASTFM_API_KEY environment variable.\n"
            "Run this in your terminal first:\n"
            'export LASTFM_API_KEY="your_api_key_here"'
        )

    return api_key


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_cache(cache: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2, ensure_ascii=False)


def make_cache_key(artist: str, album: str) -> str:
    return f"{artist.strip().lower()}|||{album.strip().lower()}"


def normalize_tag(tag: str) -> str:
    cleaned_tag = tag.strip().lower()
    cleaned_tag = re.sub(r"\s+", " ", cleaned_tag)
    return GENRE_TAG_ALIASES.get(cleaned_tag, cleaned_tag)


def compact_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def is_year_or_decade_tag(tag: str) -> bool:
    if re.fullmatch(r"\d{4}", tag):
        return True

    if re.fullmatch(r"\d{2}s", tag):
        return True

    if re.fullmatch(r"\d{4}s", tag):
        return True

    if re.fullmatch(r"\d+", tag):
        return True

    return False


def contains_ignored_phrase(tag: str) -> bool:
    return any(phrase in tag for phrase in IGNORED_TAG_PHRASES)


def matches_artist_or_album_name(tag: str, artist: str, album: str) -> bool:
    compact_tag = compact_text(tag)
    compact_artist = compact_text(artist)
    compact_album = compact_text(album)

    if compact_tag == compact_artist:
        return True

    if compact_tag == compact_album:
        return True

    if compact_tag and compact_tag in compact_artist and len(compact_tag) >= 5:
        return True

    if compact_tag and compact_tag in compact_album and len(compact_tag) >= 5:
        return True

    return False

def is_accepted_music_tag(tag: str) -> bool:
    if tag in ACCEPTED_GENRE_TAGS:
        return True

    compact_tag = compact_text(tag)

    for phrase in ACCEPTED_TAG_PHRASES:
        compact_phrase = compact_text(phrase)

        if compact_phrase and compact_phrase in compact_tag:
            return True

    return False


def is_useful_tag(tag: str, artist: str, album: str) -> bool:
    cleaned_tag = normalize_tag(tag)

    if not cleaned_tag:
        return False

    if len(cleaned_tag) <= 1:
        return False

    if cleaned_tag in IGNORED_TAGS:
        return False

    if is_year_or_decade_tag(cleaned_tag):
        return False

    if contains_ignored_phrase(cleaned_tag):
        return False

    if matches_artist_or_album_name(cleaned_tag, artist, album):
        return False

    if not is_accepted_music_tag(cleaned_tag):
        return False

    return True


def request_lastfm_album_tags(
    artist: str,
    album: str,
    api_key: str,
) -> list[dict[str, Any]]:
    params = {
        "method": "album.getTopTags",
        "artist": artist,
        "album": album,
        "api_key": api_key,
        "format": "json",
        "autocorrect": "1",
    }

    url = f"{LASTFM_API_ROOT}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        print(f"Last.fm tag HTTP error for {artist} - {album}: {error.code}")
        return []
    except urllib.error.URLError as error:
        print(f"Last.fm tag URL error for {artist} - {album}: {error.reason}")
        return []

    if "error" in data:
        error_code = data.get("error")
        message = data.get("message", "Unknown Last.fm error")

        print(f"Last.fm error for {artist} - {album}: {error_code} {message}")
        return []

    raw_tags = data.get("toptags", {}).get("tag", [])

    if isinstance(raw_tags, dict):
        raw_tags = [raw_tags]

    return raw_tags


def request_lastfm_album_info(
    artist: str,
    album: str,
    api_key: str,
) -> dict[str, Any]:
    params = {
        "method": "album.getInfo",
        "artist": artist,
        "album": album,
        "api_key": api_key,
        "format": "json",
        "autocorrect": "1",
    }

    url = f"{LASTFM_API_ROOT}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        print(f"Last.fm metadata HTTP error for {artist} - {album}: {error.code}")
        return {}
    except urllib.error.URLError as error:
        print(f"Last.fm metadata URL error for {artist} - {album}: {error.reason}")
        return {}

    if "error" in data:
        error_code = data.get("error")
        message = data.get("message", "Unknown Last.fm error")

        print(f"Last.fm metadata error for {artist} - {album}: {error_code} {message}")
        return {}

    return data.get("album", {})


def extract_album_metadata(album_info: dict[str, Any]) -> dict[str, Any]:
    tracks_data = album_info.get("tracks", {}).get("track", [])

    if isinstance(tracks_data, dict):
        tracks = [tracks_data]
    elif isinstance(tracks_data, list):
        tracks = tracks_data
    else:
        tracks = []

    track_count = len(tracks)
    total_seconds = 0

    for track in tracks:
        if not isinstance(track, dict):
            continue

        duration = track.get("duration")

        if isinstance(duration, int):
            total_seconds += duration
            continue

        if isinstance(duration, str) and duration.isdigit():
            total_seconds += int(duration)

    runtime_minutes = round(total_seconds / 60, 2) if total_seconds else None

    return {
        "track_count": track_count if track_count else None,
        "runtime_minutes": runtime_minutes,
        "metadata_source": "lastfm" if track_count or runtime_minutes else "missing",
    }


def extract_top_tags(
    raw_tags: list[dict[str, Any]],
    artist: str,
    album: str,
) -> list[str]:
    tags = []

    for tag_data in raw_tags:
        tag_name = tag_data.get("name", "")
        cleaned_tag = normalize_tag(tag_name)

        if is_useful_tag(cleaned_tag, artist, album) and cleaned_tag not in tags:
            tags.append(cleaned_tag)

    return tags[:MAX_TAGS]


def get_album_tags(
    artist: str,
    album: str,
    api_key: str,
    cache: dict[str, Any],
) -> list[str]:
    cache_key = make_cache_key(artist, album)

    if cache_key in cache:
        return cache[cache_key]

    raw_tags = request_lastfm_album_tags(artist, album, api_key)
    tags = extract_top_tags(raw_tags, artist, album)

    cache[cache_key] = tags
    time.sleep(REQUEST_DELAY_SECONDS)

    return tags


def get_album_metadata(
    artist: str,
    album: str,
    api_key: str,
    cache: dict[str, Any],
) -> dict[str, Any]:
    cache_key = make_cache_key(artist, album)

    if cache_key in cache:
        return cache[cache_key]

    album_info = request_lastfm_album_info(artist, album, api_key)
    metadata = extract_album_metadata(album_info)

    cache[cache_key] = metadata
    time.sleep(REQUEST_DELAY_SECONDS)

    return metadata


def add_tag_columns(
    df: pd.DataFrame,
    api_key: str,
    tag_cache: dict[str, Any],
    metadata_cache: dict[str, Any],
) -> pd.DataFrame:
    enriched_df = df.copy()

    tag_1_values = []
    tag_2_values = []
    tag_3_values = []
    tag_source_values = []
    track_count_values = []
    runtime_values = []
    metadata_source_values = []

    total_rows = len(enriched_df)

    for row_number, (_, row) in enumerate(enriched_df.iterrows(), start=1):
        artist = str(row["artist"])
        album = str(row["album"])

        print(f"[{row_number}/{total_rows}] Fetching data for {artist} - {album}")

        tags = get_album_tags(
            artist=artist,
            album=album,
            api_key=api_key,
            cache=tag_cache,
        )

        metadata = get_album_metadata(
            artist=artist,
            album=album,
            api_key=api_key,
            cache=metadata_cache,
        )

        tag_1_values.append(tags[0] if len(tags) > 0 else None)
        tag_2_values.append(tags[1] if len(tags) > 1 else None)
        tag_3_values.append(tags[2] if len(tags) > 2 else None)
        tag_source_values.append("lastfm" if tags else "missing")
        track_count_values.append(metadata.get("track_count"))
        runtime_values.append(metadata.get("runtime_minutes"))
        metadata_source_values.append(metadata.get("metadata_source", "missing"))

        if row_number % 25 == 0:
            save_cache(tag_cache, TAG_CACHE_PATH)
            save_cache(metadata_cache, METADATA_CACHE_PATH)

    enriched_df["genre_1"] = tag_1_values
    enriched_df["genre_2"] = tag_2_values
    enriched_df["genre_3"] = tag_3_values
    enriched_df["tag_source"] = tag_source_values
    enriched_df["track_count"] = track_count_values
    enriched_df["runtime_minutes"] = runtime_values
    enriched_df["metadata_source"] = metadata_source_values

    return enriched_df


def format_final_output(df: pd.DataFrame) -> pd.DataFrame:
    output_df = df.rename(
        columns={
            "artist": "Artist",
            "album": "Album",
            "release_year": "Year",
            "track_count": "Number of tracks",
            "runtime_minutes": "Runtime",
            "genre_1": "Genre 1",
            "genre_2": "Genre 2",
            "genre_3": "Genre 3",
            "score": "Score",
        }
    )

    output_df["Number of tracks"] = pd.to_numeric(
        output_df["Number of tracks"],
        errors="coerce",
    ).astype("Int64")

    remaining_columns = [
        column for column in output_df.columns if column not in FINAL_OUTPUT_COLUMNS
    ]

    return output_df[FINAL_OUTPUT_COLUMNS + remaining_columns]


def save_review_file(df: pd.DataFrame) -> None:
    review_columns = [
        "artist",
        "album",
        "release_year",
        "format",
        "score",
        "track_count",
        "runtime_minutes",
        "genre_1",
        "genre_2",
        "genre_3",
        "tag_source",
        "metadata_source",
    ]

    review_df = df[review_columns].copy()
    review_df["track_count"] = pd.to_numeric(
        review_df["track_count"],
        errors="coerce",
    ).astype("Int64")

    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    review_df.to_csv(REVIEW_PATH, index=False)


def print_summary(df: pd.DataFrame) -> None:
    total_rows = int(len(df))
    tagged_rows = int((df["tag_source"] == "lastfm").sum())
    missing_rows = int((df["tag_source"] == "missing").sum())
    tagged_percentage = (tagged_rows / total_rows) * 100 if total_rows else 0
    metadata_rows = int((df["metadata_source"] == "lastfm").sum())
    metadata_percentage = (metadata_rows / total_rows) * 100 if total_rows else 0

    print()
    print("Last.fm tag enrichment complete")
    print("-------------------------------")
    print(f"Total rows: {total_rows}")
    print(f"Tagged rows: {tagged_rows}")
    print(f"Missing rows: {missing_rows}")
    print(f"Tagged percentage: {tagged_percentage:.2f}%")
    print(f"Metadata rows: {metadata_rows}")
    print(f"Metadata percentage: {metadata_percentage:.2f}%")
    print(f"Saved enriched data to: {OUTPUT_PATH}")
    print(f"Saved review file to: {REVIEW_PATH}")
    print(f"Saved tag cache to: {TAG_CACHE_PATH}")
    print(f"Saved metadata cache to: {METADATA_CACHE_PATH}")


def main() -> None:
    api_key = get_api_key()

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Could not find cleaned AOTY data at: {INPUT_PATH}\n"
            "Run src/import_aoty.py first."
        )

    df = pd.read_csv(INPUT_PATH)
    tag_cache = load_cache(TAG_CACHE_PATH)
    metadata_cache = load_cache(METADATA_CACHE_PATH)

    enriched_df = add_tag_columns(
        df=df,
        api_key=api_key,
        tag_cache=tag_cache,
        metadata_cache=metadata_cache,
    )
    final_output_df = format_final_output(enriched_df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final_output_df.to_csv(OUTPUT_PATH, index=False)

    save_review_file(enriched_df)
    save_cache(tag_cache, TAG_CACHE_PATH)
    save_cache(metadata_cache, METADATA_CACHE_PATH)
    print_summary(enriched_df)


if __name__ == "__main__":
    main()