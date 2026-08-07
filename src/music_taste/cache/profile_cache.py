from __future__ import annotations

import json
import logging
import os
import pickle
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
USER_PROFILE_CACHE_ROOT = PROJECT_ROOT / "cache" / "users"
PROFILE_VERSION = 1
PROFILE_TTL = timedelta(hours=24)

PROFILE_FILENAME = "profile.pkl"
METADATA_FILENAME = "metadata.json"
SPOTIFY_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _format_profile_age(age: timedelta) -> str:
    total_minutes = max(0, int(age.total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)

    if hours:
        return f"{hours} hours {minutes} minutes"

    return f"{minutes} minutes"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _user_cache_directory(
    spotify_user_id: str,
    cache_root: Path = USER_PROFILE_CACHE_ROOT,
) -> Path:
    if not SPOTIFY_USER_ID_PATTERN.fullmatch(spotify_user_id):
        raise ValueError("Spotify user ID contains unsupported characters.")

    return cache_root / spotify_user_id


def _cache_paths(
    spotify_user_id: str,
    cache_root: Path = USER_PROFILE_CACHE_ROOT,
) -> tuple[Path, Path]:
    user_directory = _user_cache_directory(spotify_user_id, cache_root)
    return (
        user_directory / PROFILE_FILENAME,
        user_directory / METADATA_FILENAME,
    )


def is_profile_expired(
    metadata: dict,
    now: datetime | None = None,
) -> bool:
    """Return whether metadata describes a stale or incompatible profile."""

    if metadata.get("profile_version") != PROFILE_VERSION:
        return True

    last_profile_update = metadata.get("last_profile_update")

    if not isinstance(last_profile_update, str):
        return True

    try:
        updated_at = datetime.fromisoformat(last_profile_update)
    except ValueError:
        return True

    if updated_at.tzinfo is None:
        return True

    current_time = now or _utc_now()
    return current_time - updated_at >= PROFILE_TTL


def invalidate_cached_profile(
    spotify_user_id: str,
    cache_root: Path = USER_PROFILE_CACHE_ROOT,
) -> None:
    """Remove a user's cached profile and metadata if they exist."""

    profile_path, metadata_path = _cache_paths(spotify_user_id, cache_root)

    profile_path.unlink(missing_ok=True)
    metadata_path.unlink(missing_ok=True)

    try:
        profile_path.parent.rmdir()
    except OSError:
        pass


def load_cached_profile(
    spotify_user_id: str,
    now: datetime | None = None,
    cache_root: Path = USER_PROFILE_CACHE_ROOT,
) -> dict | None:
    """Load a valid cached profile, invalidating stale or corrupted entries."""

    profile_path, metadata_path = _cache_paths(spotify_user_id, cache_root)

    if not profile_path.exists() or not metadata_path.exists():
        logger.info(
            "[Cache] No valid profile found for user %s.",
            spotify_user_id,
        )
        logger.info("[Cache] Building new Spotify profile...")
        invalidate_cached_profile(spotify_user_id, cache_root)
        return None

    try:
        with metadata_path.open("r", encoding="utf-8") as metadata_file:
            metadata = json.load(metadata_file)

        if not isinstance(metadata, dict):
            raise ValueError("Profile metadata must be a JSON object.")

        if metadata.get("spotify_user_id") != spotify_user_id:
            raise ValueError("Profile metadata belongs to another Spotify user.")

        cached_version = metadata.get("profile_version")
        if cached_version != PROFILE_VERSION:
            logger.info("[Cache] Profile version mismatch.")
            logger.info("[Cache] Expected: %s", PROFILE_VERSION)
            logger.info("[Cache] Found: %s", cached_version)
            logger.info("[Cache] Rebuilding profile...")
            invalidate_cached_profile(spotify_user_id, cache_root)
            return None

        last_profile_update = metadata.get("last_profile_update")
        if not isinstance(last_profile_update, str):
            raise ValueError("Profile update time is missing or invalid.")

        updated_at = datetime.fromisoformat(last_profile_update)
        if updated_at.tzinfo is None:
            raise ValueError("Profile update time must include a timezone.")

        current_time = now or _utc_now()
        profile_age = current_time - updated_at
        if profile_age >= PROFILE_TTL:
            logger.info("[Cache] Cached profile expired (older than 24 hours).")
            logger.info("[Cache] Rebuilding profile...")
            invalidate_cached_profile(spotify_user_id, cache_root)
            return None

        with profile_path.open("rb") as profile_file:
            profile = pickle.load(profile_file)

        if not isinstance(profile, dict):
            raise ValueError("Cached profile must be a dictionary.")
    except (
        AttributeError,
        EOFError,
        json.JSONDecodeError,
        OSError,
        pickle.UnpicklingError,
        TypeError,
        ValueError,
    ):
        logger.info("[Cache] Cache is invalid or corrupted.")
        logger.info("[Cache] Rebuilding profile...")
        invalidate_cached_profile(spotify_user_id, cache_root)
        return None

    logger.info("[Cache] Using cached profile for user %s.", spotify_user_id)
    logger.info("[Cache] Profile age: %s.", _format_profile_age(profile_age))
    return profile


def save_cached_profile(
    spotify_user_id: str,
    profile: dict,
    now: datetime | None = None,
    cache_root: Path = USER_PROFILE_CACHE_ROOT,
) -> None:
    """Atomically save a prepared profile and its versioned metadata."""

    if not isinstance(profile, dict):
        raise TypeError("Prepared profile must be a dictionary.")

    profile_path, metadata_path = _cache_paths(spotify_user_id, cache_root)
    profile_path.parent.mkdir(parents=True, exist_ok=True)

    current_time = now or _utc_now()
    metadata = {
        "spotify_user_id": spotify_user_id,
        "last_profile_update": current_time.isoformat(),
        "profile_version": PROFILE_VERSION,
    }

    temporary_profile_path = profile_path.with_suffix(".pkl.tmp")
    temporary_metadata_path = metadata_path.with_suffix(".json.tmp")

    try:
        with temporary_profile_path.open("wb") as profile_file:
            pickle.dump(profile, profile_file, protocol=pickle.HIGHEST_PROTOCOL)

        with temporary_metadata_path.open("w", encoding="utf-8") as metadata_file:
            json.dump(metadata, metadata_file, indent=2)

        os.replace(temporary_profile_path, profile_path)
        os.replace(temporary_metadata_path, metadata_path)
    finally:
        temporary_profile_path.unlink(missing_ok=True)
        temporary_metadata_path.unlink(missing_ok=True)
