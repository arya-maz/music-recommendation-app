import json

from music_taste.spotify.fetch_data import fetch_and_save_spotify_data
from music_taste.spotify.find_candidates import (
    CANDIDATE_ALBUMS_FILENAME,
    _load_candidate_album_cache,
    _save_candidate_album_cache,
)


class FakeSpotifyClient:
    def current_user_top_artists(self, **kwargs):
        return {"items": [{"id": "artist-user1"}]}

    def current_user_top_tracks(self, **kwargs):
        return {"items": [{"id": "track-user1"}]}

    def current_user_recently_played(self, **kwargs):
        return {"items": [{"track": {"id": "recent-user1"}}]}

    def current_user_saved_albums(self, **kwargs):
        return {"items": [{"album": {"id": "album-user1"}}], "next": None}

    def current_user_saved_tracks(self, **kwargs):
        return {"items": [{"track": {"id": "saved-user1"}}], "next": None}


def test_new_user_raw_data_directory_is_created(tmp_path):
    user_directory = tmp_path / "cache" / "users" / "user1"

    fetch_and_save_spotify_data(FakeSpotifyClient(), user_directory)

    assert user_directory.is_dir()
    assert {path.name for path in user_directory.iterdir()} == {
        "top_artists.json",
        "top_tracks.json",
        "recently_played.json",
        "saved_albums.json",
        "saved_tracks.json",
    }


def test_candidate_caches_are_isolated_between_users(tmp_path):
    user1_path = tmp_path / "users" / "user1" / CANDIDATE_ALBUMS_FILENAME
    user2_path = tmp_path / "users" / "user2" / CANDIDATE_ALBUMS_FILENAME
    _save_candidate_album_cache([{"id": "album-user1"}], user1_path)
    _save_candidate_album_cache([{"id": "album-user2"}], user2_path)

    assert _load_candidate_album_cache(user1_path) == [{"id": "album-user1"}]
    assert _load_candidate_album_cache(user2_path) == [{"id": "album-user2"}]
    assert json.loads(user1_path.read_text()) != json.loads(user2_path.read_text())
