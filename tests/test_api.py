from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest

from api.auth import AuthStore, UserTokenCacheHandler
from api.main import app, authenticated_spotify_client, get_auth_store
from music_taste.spotify.recommendations import Recommendation


@pytest.fixture
def auth_store(tmp_path):
    return AuthStore(tmp_path / "auth.db", Fernet.generate_key().decode())


@pytest.fixture
def client(auth_store, monkeypatch):
    app.dependency_overrides[get_auth_store] = lambda: auth_store
    monkeypatch.setenv("APP_COOKIE_SECURE", "false")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recommendations_endpoint_requires_session(client):
    assert client.post("/api/recommendations").status_code == 401


def test_recommendations_endpoint_uses_existing_pipeline(client, auth_store, monkeypatch):
    spotify_client = object()
    taste_profile = {"artist_scores": {"artist-1": 80.0}}
    expected_recommendations = [
        Recommendation(
            artist_name=f"Artist {index}",
            album_name=f"Album {index}",
            spotify_url=f"https://open.spotify.test/album/{index}",
            album_image_url=f"https://images.test/album-{index}.jpg",
            recommendation_score=72.5,
            reason="strong artist-fit evidence; low album familiarity",
            artist_affinity=80.0,
            familiarity_score=15.0,
            familiarity_label="lightly familiar",
        )
        for index in range(1, 6)
    ]
    calls = {}

    def fake_get_or_prepare_user_profile(received_client, profile_metadata_store):
        calls["profile_client"] = received_client
        calls["profile_metadata_store"] = profile_metadata_store
        return taste_profile

    def fake_generate_recommendations_from_profile(received_client, profile, limit):
        calls["generate_client"] = received_client
        calls["profile"] = profile
        calls["limit"] = limit
        return expected_recommendations

    app.dependency_overrides[authenticated_spotify_client] = lambda: spotify_client
    monkeypatch.setattr(
        "api.main.get_or_prepare_user_profile",
        fake_get_or_prepare_user_profile,
    )
    monkeypatch.setattr(
        "api.main.generate_recommendations_from_profile",
        fake_generate_recommendations_from_profile,
    )

    response = client.post("/api/recommendations")

    assert response.status_code == 200
    assert calls == {
        "profile_client": spotify_client,
        "profile_metadata_store": auth_store,
        "generate_client": spotify_client,
        "profile": taste_profile,
        "limit": 5,
    }
    assert len(response.json()) == 5
    assert response.json()[0] == {
        "artist_name": "Artist 1",
        "album_name": "Album 1",
        "spotify_url": "https://open.spotify.test/album/1",
        "album_image_url": "https://images.test/album-1.jpg",
        "recommendation_score": 72.5,
        "reason": "strong artist-fit evidence; low album familiarity",
        "artist_affinity": 80.0,
        "familiarity_score": 15.0,
        "familiarity_label": "lightly familiar",
    }


def test_oauth_callback_creates_session_and_logout_invalidates_it(client, auth_store, monkeypatch):
    migrations = []

    class FakeOAuth:
        def get_authorize_url(self, state):
            return f"https://accounts.spotify.test/authorize?state={state}"

        def get_access_token(self, code, check_cache):
            assert (code, check_cache) == ("authorization-code", False)
            return {"access_token": "access", "refresh_token": "refresh", "expires_at": 9999999999}

    class FakeSpotify:
        def __init__(self, auth):
            assert auth == "access"

        def current_user(self):
            return {"id": "legacy-user-123", "account_id": "stable-account-456"}

    monkeypatch.setattr("api.main.get_spotify_oauth", lambda: FakeOAuth())
    monkeypatch.setattr("api.main.spotipy.Spotify", FakeSpotify)
    monkeypatch.setattr(
        "api.main.migrate_user_data_identity",
        lambda legacy_id, account_id: migrations.append((legacy_id, account_id)),
    )

    login = client.get("/api/auth/login", follow_redirects=False)
    state = client.cookies.get("spotify_oauth_state")
    assert login.status_code == 307
    assert state in login.headers["location"]

    callback = client.get(
        "/api/auth/callback",
        params={"state": state, "code": "authorization-code"},
        follow_redirects=False,
    )
    assert callback.status_code == 307
    assert migrations == [("legacy-user-123", "stable-account-456")]
    assert auth_store.get_token("stable-account-456")["refresh_token"] == "refresh"
    assert b"refresh" not in auth_store.database_path.read_bytes()
    assert client.get("/api/auth/me").json() == {"spotify_user_id": "stable-account-456"}

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_oauth_state_is_browser_bound_and_one_time(client, monkeypatch):
    class FakeOAuth:
        def get_authorize_url(self, state):
            return f"https://accounts.spotify.test/authorize?state={state}"

        def get_access_token(self, code, check_cache):
            return {"access_token": "access"}

    class FakeSpotify:
        def __init__(self, auth):
            pass

        def current_user(self):
            return {"id": "spotify-user-123"}

    monkeypatch.setattr("api.main.get_spotify_oauth", lambda: FakeOAuth())
    monkeypatch.setattr("api.main.spotipy.Spotify", FakeSpotify)
    client.get("/api/auth/login", follow_redirects=False)
    state = client.cookies.get("spotify_oauth_state")

    assert client.get(
        "/api/auth/callback",
        params={"state": "wrong-state", "code": "code"},
    ).status_code == 400
    client.cookies.set("spotify_oauth_state", state)
    assert client.get(
        "/api/auth/callback",
        params={"state": state, "code": "code"},
        follow_redirects=False,
    ).status_code == 307
    client.cookies.set("spotify_oauth_state", state)
    assert client.get(
        "/api/auth/callback", params={"state": state, "code": "code"}
    ).status_code == 400


def test_sessions_resolve_users_independently(auth_store):
    alice = auth_store.create_session("alice")
    bob = auth_store.create_session("bob")

    assert auth_store.get_session_user(alice) == "alice"
    assert auth_store.get_session_user(bob) == "bob"
    auth_store.delete_session(alice)
    assert auth_store.get_session_user(alice) is None
    assert auth_store.get_session_user(bob) == "bob"


def test_token_refresh_cache_updates_only_authenticated_user(auth_store):
    auth_store.save_token("alice", {"access_token": "alice-old", "refresh_token": "alice-refresh"})
    auth_store.save_token("bob", {"access_token": "bob-old", "refresh_token": "bob-refresh"})
    alice_cache = UserTokenCacheHandler(auth_store, "alice")

    alice_cache.save_token_to_cache(
        {"access_token": "alice-new", "refresh_token": "alice-refresh"}
    )

    assert alice_cache.get_cached_token()["access_token"] == "alice-new"
    assert auth_store.get_token("bob")["access_token"] == "bob-old"


def test_identity_migration_moves_sessions_and_replaces_legacy_token(auth_store):
    legacy_session = auth_store.create_session("legacy-user")
    auth_store.save_token("legacy-user", {"access_token": "legacy-token"})

    auth_store.migrate_user_identity_and_save_token(
        "stable-account",
        {"access_token": "current-token"},
        legacy_user_id="legacy-user",
    )

    assert auth_store.get_session_user(legacy_session) == "stable-account"
    assert auth_store.get_token("legacy-user") is None
    assert auth_store.get_token("stable-account") == {"access_token": "current-token"}


def test_account_deletion_removes_only_authenticated_user_data(
    client, auth_store, tmp_path, monkeypatch
):
    from music_taste.cache.profile_cache import delete_user_data

    cache_root = tmp_path / "users"
    alice_directory = cache_root / "alice"
    bob_directory = cache_root / "bob"
    alice_directory.mkdir(parents=True)
    bob_directory.mkdir(parents=True)
    (alice_directory / "saved_tracks.json").write_text('[{"id": "alice-track"}]')
    (bob_directory / "saved_tracks.json").write_text('[{"id": "bob-track"}]')

    alice_session = auth_store.create_session("alice")
    alice_other_session = auth_store.create_session("alice")
    bob_session = auth_store.create_session("bob")
    auth_store.save_token("alice", {"access_token": "alice-token"})
    auth_store.save_token("bob", {"access_token": "bob-token"})
    client.cookies.set("music_session", alice_session)
    monkeypatch.setattr(
        "api.main.delete_user_data",
        lambda user_id: delete_user_data(user_id, cache_root=cache_root),
    )

    response = client.request(
        "DELETE",
        "/api/auth/account",
        json={"confirm": True},
    )

    assert response.status_code == 204
    assert not alice_directory.exists()
    assert bob_directory.exists()
    assert auth_store.get_token("alice") is None
    assert auth_store.get_session_user(alice_session) is None
    assert auth_store.get_session_user(alice_other_session) is None
    assert auth_store.get_token("bob") == {"access_token": "bob-token"}
    assert auth_store.get_session_user(bob_session) == "bob"
    assert client.get("/api/auth/me").status_code == 401


def test_account_deletion_requires_explicit_confirmation(client, auth_store):
    session = auth_store.create_session("alice")
    auth_store.save_token("alice", {"access_token": "alice-token"})
    client.cookies.set("music_session", session)

    response = client.request("DELETE", "/api/auth/account", json={"confirm": False})

    assert response.status_code == 422
    assert auth_store.get_session_user(session) == "alice"
    assert auth_store.get_token("alice") == {"access_token": "alice-token"}
