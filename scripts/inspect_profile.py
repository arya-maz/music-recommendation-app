"""Read-only inspection utility for locally cached Spotify taste profiles."""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from music_taste.cache.profile_cache import (  # noqa: E402
    METADATA_FILENAME,
    PROFILE_FILENAME,
    USER_PROFILE_CACHE_ROOT,
)


def _collection_size(profile: dict, key: str) -> int | None:
    value = profile.get(key)
    if isinstance(value, (dict, list, set, tuple)):
        return len(value)
    return None


def _print_profile_summary(user_directory: Path) -> None:
    metadata_path = user_directory / METADATA_FILENAME
    profile_path = user_directory / PROFILE_FILENAME

    print(f"\nCached profile: {user_directory.name}")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("metadata is not a JSON object")
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Metadata: invalid or unreadable ({error})")
        return

    print(f"Spotify User ID: {metadata.get('spotify_user_id', user_directory.name)}")
    print(f"Profile Version: {metadata.get('profile_version', 'unknown')}")
    print(f"Last Updated: {metadata.get('last_profile_update', 'unknown')}")

    try:
        file_size = profile_path.stat().st_size
        with profile_path.open("rb") as profile_file:
            profile = pickle.load(profile_file)
    except (EOFError, OSError, pickle.UnpicklingError) as error:
        print(f"Profile: invalid or unreadable ({error})")
        return

    print(f"Top-level Object Type: {type(profile).__name__}")
    if isinstance(profile, dict):
        print(f"Top-level Keys: {', '.join(sorted(map(str, profile.keys())))}")
    else:
        print("Top-level Keys: unavailable")
    print(f"Approximate File Size: {file_size} bytes ({file_size / 1024:.1f} KiB)")

    if not isinstance(profile, dict):
        return

    count_labels = {
        "artist_scores": "Artists",
        "known_album_ids": "Known Album IDs",
        "known_album_keys": "Known Album Keys",
        "saved_album_ids": "Saved Albums",
        "top_track_album_ids": "Top-track Albums",
        "recent_album_ids": "Recent Albums",
        "saved_track_album_ids": "Saved-track Albums",
    }
    for key, label in count_labels.items():
        count = _collection_size(profile, key)
        if count is not None:
            print(f"{label}: {count}")

    saved_track_counts = profile.get("saved_track_album_counts")
    if isinstance(saved_track_counts, dict):
        numeric_counts = [
            count for count in saved_track_counts.values()
            if isinstance(count, (int, float))
        ]
        print(f"Saved Tracks: {int(sum(numeric_counts))}")


def inspect_profiles(
    cache_root: Path = USER_PROFILE_CACHE_ROOT,
    spotify_user_id: str | None = None,
) -> int:
    """Print cache metadata and aggregate profile facts without changing files."""

    if spotify_user_id:
        user_directories = [cache_root / spotify_user_id]
    elif cache_root.exists():
        user_directories = sorted(path for path in cache_root.iterdir() if path.is_dir())
    else:
        user_directories = []

    user_directories = [path for path in user_directories if path.is_dir()]
    if not user_directories:
        print(f"No cached profiles found at: {cache_root}")
        return 1

    print(f"Profile cache: {cache_root}")
    for user_directory in user_directories:
        _print_profile_summary(user_directory)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-id",
        help="Inspect only the cache directory for this Spotify user ID.",
    )
    args = parser.parse_args()
    return inspect_profiles(spotify_user_id=args.user_id)


if __name__ == "__main__":
    raise SystemExit(main())
