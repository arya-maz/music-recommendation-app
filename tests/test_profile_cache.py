import json
from datetime import datetime, timedelta, timezone

import pytest

from music_taste.cache.profile_cache import (
    METADATA_FILENAME,
    PROFILE_FILENAME,
    PROFILE_TTL,
    PROFILE_VERSION,
    load_cached_profile,
    migrate_legacy_spotify_data,
    migrate_user_data_identity,
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


def test_expiration_does_not_modify_another_user_cache(tmp_path):
    other_user_id = "spotify-user-456"
    save_cached_profile(SPOTIFY_USER_ID, PROFILE, now=NOW, cache_root=tmp_path)
    save_cached_profile(other_user_id, PROFILE, now=NOW, cache_root=tmp_path)
    other_profile = tmp_path / other_user_id / PROFILE_FILENAME
    other_metadata = tmp_path / other_user_id / METADATA_FILENAME
    original_other_files = (other_profile.read_bytes(), other_metadata.read_bytes())

    assert load_cached_profile(
        SPOTIFY_USER_ID,
        now=NOW + PROFILE_TTL,
        cache_root=tmp_path,
    ) is None

    assert (other_profile.read_bytes(), other_metadata.read_bytes()) == original_other_files


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


def test_legacy_data_is_moved_once_without_overwriting_user_data(tmp_path):
    cache_root = tmp_path / "cache" / "users"
    legacy_root = tmp_path / "data" / "raw" / "spotify"
    legacy_root.mkdir(parents=True)
    (legacy_root / "top_artists.json").write_text('[{"id": "legacy"}]')
    user_directory = cache_root / SPOTIFY_USER_ID
    user_directory.mkdir(parents=True)
    (user_directory / "saved_tracks.json").write_text('[{"id": "current"}]')
    (legacy_root / "saved_tracks.json").write_text('[{"id": "legacy"}]')

    migrated = migrate_legacy_spotify_data(
        SPOTIFY_USER_ID,
        cache_root=cache_root,
        legacy_root=legacy_root,
    )

    assert migrated == [user_directory / "top_artists.json"]
    assert not (legacy_root / "top_artists.json").exists()
    assert (user_directory / "top_artists.json").read_text() == '[{"id": "legacy"}]'
    assert (user_directory / "saved_tracks.json").read_text() == '[{"id": "current"}]'
    assert (legacy_root / "saved_tracks.json").exists()


def test_legacy_user_cache_is_migrated_to_stable_account_id(tmp_path):
    stable_account_id = "stable-account-456"
    save_cached_profile(SPOTIFY_USER_ID, PROFILE, now=NOW, cache_root=tmp_path)
    legacy_directory = tmp_path / SPOTIFY_USER_ID
    (legacy_directory / "saved_tracks.json").write_text('[{"id": "track-1"}]')

    migrated = migrate_user_data_identity(
        SPOTIFY_USER_ID,
        stable_account_id,
        cache_root=tmp_path,
    )

    assert migrated is True
    assert not legacy_directory.exists()
    assert (tmp_path / stable_account_id / "saved_tracks.json").exists()
    assert load_cached_profile(stable_account_id, now=NOW, cache_root=tmp_path) == PROFILE


def test_identity_migration_refuses_to_overwrite_stable_user_cache(tmp_path):
    legacy_directory = tmp_path / SPOTIFY_USER_ID
    stable_directory = tmp_path / "stable-account-456"
    legacy_directory.mkdir()
    stable_directory.mkdir()
    (legacy_directory / "profile.pkl").write_bytes(b"legacy")
    (stable_directory / "profile.pkl").write_bytes(b"stable")

    with pytest.raises(FileExistsError):
        migrate_user_data_identity(
            SPOTIFY_USER_ID,
            "stable-account-456",
            cache_root=tmp_path,
        )

    assert (legacy_directory / "profile.pkl").read_bytes() == b"legacy"
    assert (stable_directory / "profile.pkl").read_bytes() == b"stable"
