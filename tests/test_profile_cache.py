import json
from datetime import datetime, timedelta, timezone

from music_taste.cache.profile_cache import (
    METADATA_FILENAME,
    PROFILE_FILENAME,
    PROFILE_TTL,
    PROFILE_VERSION,
    load_cached_profile,
    save_cached_profile,
)


SPOTIFY_USER_ID = "spotify-user-123"
NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
PROFILE = {
    "artist_scores": {"artist-1": 42.0},
    "known_album_ids": ["album-1"],
}


def test_cache_miss_returns_none(tmp_path, caplog):
    result = load_cached_profile(
        SPOTIFY_USER_ID,
        now=NOW,
        cache_root=tmp_path,
    )

    assert result is None
    assert "[Cache] No valid profile found for user spotify-user-123." in caplog.text
    assert "[Cache] Building new Spotify profile..." in caplog.text


def test_cache_hit_returns_saved_profile_and_metadata(tmp_path, caplog):
    save_cached_profile(
        SPOTIFY_USER_ID,
        PROFILE,
        now=NOW,
        cache_root=tmp_path,
    )

    result = load_cached_profile(
        SPOTIFY_USER_ID,
        now=NOW + timedelta(hours=23, minutes=59),
        cache_root=tmp_path,
    )
    metadata_path = tmp_path / SPOTIFY_USER_ID / METADATA_FILENAME
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert result == PROFILE
    assert metadata == {
        "spotify_user_id": SPOTIFY_USER_ID,
        "last_profile_update": NOW.isoformat(),
        "profile_version": PROFILE_VERSION,
    }
    assert "[Cache] Using cached profile for user spotify-user-123." in caplog.text
    assert "[Cache] Profile age: 23 hours 59 minutes." in caplog.text


def test_expired_cache_is_invalidated(tmp_path, caplog):
    save_cached_profile(
        SPOTIFY_USER_ID,
        PROFILE,
        now=NOW,
        cache_root=tmp_path,
    )

    result = load_cached_profile(
        SPOTIFY_USER_ID,
        now=NOW + PROFILE_TTL,
        cache_root=tmp_path,
    )

    assert result is None
    assert not (tmp_path / SPOTIFY_USER_ID).exists()
    assert "[Cache] Cached profile expired (older than 24 hours)." in caplog.text
    assert "[Cache] Rebuilding profile..." in caplog.text


def test_profile_version_mismatch_is_invalidated(tmp_path, caplog):
    save_cached_profile(
        SPOTIFY_USER_ID,
        PROFILE,
        now=NOW,
        cache_root=tmp_path,
    )
    metadata_path = tmp_path / SPOTIFY_USER_ID / METADATA_FILENAME
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["profile_version"] = PROFILE_VERSION + 1
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = load_cached_profile(
        SPOTIFY_USER_ID,
        now=NOW,
        cache_root=tmp_path,
    )

    assert result is None
    assert not (tmp_path / SPOTIFY_USER_ID).exists()
    assert "[Cache] Profile version mismatch." in caplog.text
    assert f"[Cache] Expected: {PROFILE_VERSION}" in caplog.text
    assert f"[Cache] Found: {PROFILE_VERSION + 1}" in caplog.text
    assert "[Cache] Rebuilding profile..." in caplog.text


def test_corrupted_profile_is_invalidated(tmp_path, caplog):
    save_cached_profile(
        SPOTIFY_USER_ID,
        PROFILE,
        now=NOW,
        cache_root=tmp_path,
    )
    profile_path = tmp_path / SPOTIFY_USER_ID / PROFILE_FILENAME
    profile_path.write_bytes(b"not a pickle")

    result = load_cached_profile(
        SPOTIFY_USER_ID,
        now=NOW,
        cache_root=tmp_path,
    )

    assert result is None
    assert not (tmp_path / SPOTIFY_USER_ID).exists()
    assert "[Cache] Cache is invalid or corrupted." in caplog.text
    assert "[Cache] Rebuilding profile..." in caplog.text


def test_corrupted_metadata_is_invalidated(tmp_path):
    save_cached_profile(
        SPOTIFY_USER_ID,
        PROFILE,
        now=NOW,
        cache_root=tmp_path,
    )
    metadata_path = tmp_path / SPOTIFY_USER_ID / METADATA_FILENAME
    metadata_path.write_text("not json", encoding="utf-8")

    result = load_cached_profile(
        SPOTIFY_USER_ID,
        now=NOW,
        cache_root=tmp_path,
    )

    assert result is None
    assert not (tmp_path / SPOTIFY_USER_ID).exists()
