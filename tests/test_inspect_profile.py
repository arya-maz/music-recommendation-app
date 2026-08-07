from datetime import datetime, timezone

from music_taste.cache.profile_cache import save_cached_profile
from scripts.inspect_profile import inspect_profiles


def test_inspection_utility_reports_profile_without_modifying_cache(tmp_path, capsys):
    profile = {
        "artist_scores": {"artist-1": 20.0, "artist-2": 10.0},
        "known_album_ids": ["album-1"],
        "saved_track_album_counts": {"album-1": 3, "album-2": 2},
    }
    updated_at = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    save_cached_profile("test-user", profile, now=updated_at, cache_root=tmp_path)
    profile_path = tmp_path / "test-user" / "profile.pkl"
    metadata_path = tmp_path / "test-user" / "metadata.json"
    original_profile_bytes = profile_path.read_bytes()
    original_metadata_bytes = metadata_path.read_bytes()

    result = inspect_profiles(cache_root=tmp_path)
    output = capsys.readouterr().out

    assert result == 0
    assert "Spotify User ID: test-user" in output
    assert "Profile Version: 1" in output
    assert f"Last Updated: {updated_at.isoformat()}" in output
    assert "Top-level Object Type: dict" in output
    assert "Top-level Keys: artist_scores, known_album_ids, saved_track_album_counts" in output
    assert "Artists: 2" in output
    assert "Known Album IDs: 1" in output
    assert "Saved Tracks: 5" in output
    assert profile_path.read_bytes() == original_profile_bytes
    assert metadata_path.read_bytes() == original_metadata_bytes
