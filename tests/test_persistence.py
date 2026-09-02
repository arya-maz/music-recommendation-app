from datetime import datetime, timezone
import hashlib
import json
import sqlite3

from cryptography.fernet import Fernet

from api.auth import AuthStore


def test_user_token_and_profile_metadata_share_a_persistent_user(tmp_path):
    database_path = tmp_path / "auth.db"
    encryption_key = Fernet.generate_key().decode()
    updated_at = datetime(2026, 9, 2, 15, 30, tzinfo=timezone.utc)

    store = AuthStore(database_path, encryption_key)
    store.upsert_user("spotify-account", "Listener")
    store.save_token("spotify-account", {"access_token": "secret"})
    store.save_profile_metadata("spotify-account", 1, updated_at)
    store.engine.dispose()

    reopened = AuthStore(database_path, encryption_key)

    assert reopened.get_token("spotify-account") == {"access_token": "secret"}
    assert reopened.get_profile_metadata("spotify-account") == {
        "profile_version": 1,
        "last_profile_update": updated_at,
    }
    assert b"secret" not in database_path.read_bytes()


def test_account_deletion_removes_profile_metadata(tmp_path):
    store = AuthStore(tmp_path / "auth.db", Fernet.generate_key().decode())
    store.save_profile_metadata("spotify-account", 1, datetime.now(timezone.utc))

    store.delete_account_credentials("spotify-account")

    assert store.get_profile_metadata("spotify-account") is None


def test_existing_sqlite_auth_database_is_upgraded_without_losing_login(tmp_path):
    database_path = tmp_path / "auth.db"
    encryption_key = Fernet.generate_key()
    cipher = Fernet(encryption_key)
    session_id = "existing-session"
    encrypted_token = cipher.encrypt(json.dumps({"access_token": "existing"}).encode())
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE spotify_tokens (
                spotify_user_id TEXT PRIMARY KEY,
                encrypted_token BLOB NOT NULL
            );
            CREATE TABLE sessions (
                session_hash TEXT PRIMARY KEY,
                spotify_user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO spotify_tokens VALUES (?, ?)",
            ("spotify-account", encrypted_token),
        )
        connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?)",
            (
                hashlib.sha256(session_id.encode()).hexdigest(),
                "spotify-account",
                "2099-09-02T15:30:00+00:00",
            ),
        )

    store = AuthStore(database_path, encryption_key.decode())

    assert store.get_token("spotify-account") == {"access_token": "existing"}
    assert store.get_session_user(session_id) == "spotify-account"
