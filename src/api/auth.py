from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import (BigInteger, Column, DateTime, ForeignKey, Integer, LargeBinary,
                        MetaData, String, Table, create_engine, delete, select, update)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from spotipy.cache_handler import CacheHandler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUTH_DATABASE = PROJECT_ROOT / "data" / "auth" / "auth.db"
SESSION_TTL = timedelta(days=30)
OAUTH_STATE_TTL = timedelta(minutes=10)

metadata = MetaData()
users = Table(
    "users", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True),
    Column("spotify_user_id", String(255), nullable=False, unique=True),
    Column("display_name", String(255)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
spotify_tokens = Table(
    "spotify_tokens", metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("encrypted_token", LargeBinary, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
profiles = Table(
    "profiles", metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("profile_version", Integer, nullable=False),
    Column("last_profile_update", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
sessions = Table(
    "sessions", metadata,
    Column("session_hash", String(64), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
)
oauth_states = Table(
    "oauth_states", metadata,
    Column("state_hash", String(64), primary_key=True),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AuthStore:
    """SQL-backed users, sessions, one-time OAuth state, and encrypted tokens."""

    def __init__(self, database: Path | str, encryption_key: str, *, initialize: bool = True):
        value = str(database)
        self.database_path = None if "://" in value else Path(database)
        if self.database_path is not None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            value = f"sqlite:///{self.database_path}"
        try:
            self.cipher = Fernet(encryption_key.encode("ascii"))
        except (TypeError, ValueError) as exc:
            raise ValueError("SPOTIFY_TOKEN_ENCRYPTION_KEY must be a Fernet key.") from exc
        self.engine = create_engine(value, pool_pre_ping=True)
        if initialize:
            if self.database_path is not None:
                self._migrate_legacy_sqlite_schema()
            metadata.create_all(self.engine)
        if self.database_path is not None:
            try:
                self.database_path.chmod(0o600)
            except OSError:
                pass

    def _migrate_legacy_sqlite_schema(self) -> None:
        """Upgrade the pre-SQLAlchemy auth tables without discarding logins."""

        if self.database_path is None or not self.database_path.exists():
            return
        with sqlite3.connect(self.database_path) as connection:
            token_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(spotify_tokens)")
            }
            session_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(sessions)")
            }
            if "spotify_user_id" not in token_columns and "spotify_user_id" not in session_columns:
                return

            connection.execute("PRAGMA foreign_keys = OFF")
            if "spotify_user_id" in token_columns:
                connection.execute("ALTER TABLE spotify_tokens RENAME TO legacy_spotify_tokens")
            if "spotify_user_id" in session_columns:
                connection.execute("ALTER TABLE sessions RENAME TO legacy_sessions")

        metadata.create_all(self.engine)
        now = _now().isoformat()
        with sqlite3.connect(self.database_path) as connection:
            if "spotify_user_id" in token_columns:
                connection.execute(
                    "INSERT OR IGNORE INTO users "
                    "(spotify_user_id, created_at, updated_at) "
                    "SELECT spotify_user_id, ?, ? FROM legacy_spotify_tokens",
                    (now, now),
                )
                connection.execute(
                    "INSERT INTO spotify_tokens (user_id, encrypted_token, updated_at) "
                    "SELECT users.id, legacy.encrypted_token, ? "
                    "FROM legacy_spotify_tokens AS legacy "
                    "JOIN users ON users.spotify_user_id = legacy.spotify_user_id",
                    (now,),
                )
                connection.execute("DROP TABLE legacy_spotify_tokens")
            if "spotify_user_id" in session_columns:
                connection.execute(
                    "INSERT OR IGNORE INTO users "
                    "(spotify_user_id, created_at, updated_at) "
                    "SELECT spotify_user_id, ?, ? FROM legacy_sessions",
                    (now, now),
                )
                connection.execute(
                    "INSERT INTO sessions (session_hash, user_id, expires_at) "
                    "SELECT legacy.session_hash, users.id, legacy.expires_at "
                    "FROM legacy_sessions AS legacy "
                    "JOIN users ON users.spotify_user_id = legacy.spotify_user_id"
                )
                connection.execute("DROP TABLE legacy_sessions")

    @classmethod
    def from_environment(cls) -> AuthStore:
        encryption_key = os.getenv("SPOTIFY_TOKEN_ENCRYPTION_KEY")
        if not encryption_key:
            raise RuntimeError("SPOTIFY_TOKEN_ENCRYPTION_KEY is required.")
        database_url = os.getenv("DATABASE_URL")
        database = database_url or Path(os.getenv("AUTH_DATABASE_PATH", DEFAULT_AUTH_DATABASE))
        # Production schema changes are explicit and reviewable through Alembic.
        # Local SQLite remains zero-setup for development and isolated tests.
        return cls(database, encryption_key, initialize=database_url is None)

    def _insert(self, table: Table):
        if self.engine.dialect.name == "postgresql":
            return postgresql_insert(table)
        if self.engine.dialect.name == "sqlite":
            return sqlite_insert(table)
        raise RuntimeError(f"Unsupported database dialect: {self.engine.dialect.name}")

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    def upsert_user(self, spotify_user_id: str, display_name: str | None = None) -> int:
        now = _now()
        statement = self._insert(users).values(
            spotify_user_id=spotify_user_id, display_name=display_name,
            created_at=now, updated_at=now,
        )
        changes = {"updated_at": now}
        if display_name is not None:
            changes["display_name"] = display_name
        statement = statement.on_conflict_do_update(
            index_elements=[users.c.spotify_user_id], set_=changes
        )
        with self.engine.begin() as connection:
            connection.execute(statement)
            return int(connection.execute(
                select(users.c.id).where(users.c.spotify_user_id == spotify_user_id)
            ).scalar_one())

    def create_oauth_state(self) -> str:
        state, now = secrets.token_urlsafe(32), _now()
        with self.engine.begin() as connection:
            connection.execute(delete(oauth_states).where(oauth_states.c.expires_at <= now))
            connection.execute(oauth_states.insert().values(
                state_hash=_digest(state), expires_at=now + OAUTH_STATE_TTL
            ))
        return state

    def consume_oauth_state(self, state: str) -> bool:
        state_hash = _digest(state)
        with self.engine.begin() as connection:
            expires_at = connection.execute(select(oauth_states.c.expires_at).where(
                oauth_states.c.state_hash == state_hash
            )).scalar_one_or_none()
            connection.execute(delete(oauth_states).where(oauth_states.c.state_hash == state_hash))
        return bool(expires_at and self._as_utc(expires_at) > _now())

    def create_session(self, spotify_user_id: str) -> str:
        user_id, session_id, now = self.upsert_user(spotify_user_id), secrets.token_urlsafe(32), _now()
        with self.engine.begin() as connection:
            connection.execute(delete(sessions).where(sessions.c.expires_at <= now))
            connection.execute(sessions.insert().values(
                session_hash=_digest(session_id), user_id=user_id,
                expires_at=now + SESSION_TTL,
            ))
        return session_id

    def get_session_user(self, session_id: str) -> str | None:
        session_hash = _digest(session_id)
        with self.engine.begin() as connection:
            row = connection.execute(
                select(users.c.spotify_user_id, sessions.c.expires_at)
                .select_from(sessions.join(users))
                .where(sessions.c.session_hash == session_hash)
            ).one_or_none()
            if row and self._as_utc(row.expires_at) <= _now():
                connection.execute(delete(sessions).where(sessions.c.session_hash == session_hash))
                return None
        return row.spotify_user_id if row else None

    def delete_session(self, session_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(delete(sessions).where(sessions.c.session_hash == _digest(session_id)))

    def delete_account_credentials(self, spotify_user_id: str) -> None:
        with self.engine.begin() as connection:
            user_id = connection.execute(select(users.c.id).where(
                users.c.spotify_user_id == spotify_user_id
            )).scalar_one_or_none()
            if user_id is None:
                return
            connection.execute(delete(sessions).where(sessions.c.user_id == user_id))
            connection.execute(delete(profiles).where(profiles.c.user_id == user_id))
            connection.execute(delete(spotify_tokens).where(spotify_tokens.c.user_id == user_id))
            connection.execute(delete(users).where(users.c.id == user_id))

    def save_token(self, spotify_user_id: str, token_info: dict) -> None:
        user_id, now = self.upsert_user(spotify_user_id), _now()
        encrypted = self.cipher.encrypt(json.dumps(token_info).encode("utf-8"))
        statement = self._insert(spotify_tokens).values(
            user_id=user_id, encrypted_token=encrypted, updated_at=now
        ).on_conflict_do_update(
            index_elements=[spotify_tokens.c.user_id],
            set_={"encrypted_token": encrypted, "updated_at": now},
        )
        with self.engine.begin() as connection:
            connection.execute(statement)

    def migrate_user_identity_and_save_token(
        self, stable_account_id: str, token_info: dict, *,
        legacy_user_id: str | None = None, display_name: str | None = None,
    ) -> None:
        stable_id = self.upsert_user(stable_account_id, display_name)
        with self.engine.begin() as connection:
            legacy_id = None
            if legacy_user_id and legacy_user_id != stable_account_id:
                legacy_id = connection.execute(select(users.c.id).where(
                    users.c.spotify_user_id == legacy_user_id
                )).scalar_one_or_none()
            if legacy_id is not None:
                connection.execute(update(sessions).where(sessions.c.user_id == legacy_id).values(user_id=stable_id))
                connection.execute(delete(spotify_tokens).where(spotify_tokens.c.user_id == legacy_id))
                connection.execute(delete(profiles).where(profiles.c.user_id == legacy_id))
                connection.execute(delete(users).where(users.c.id == legacy_id))
        self.save_token(stable_account_id, token_info)

    def get_token(self, spotify_user_id: str) -> dict | None:
        with self.engine.connect() as connection:
            encrypted = connection.execute(
                select(spotify_tokens.c.encrypted_token).select_from(spotify_tokens.join(users))
                .where(users.c.spotify_user_id == spotify_user_id)
            ).scalar_one_or_none()
        if encrypted is None:
            return None
        try:
            token_info = json.loads(self.cipher.decrypt(encrypted))
        except (InvalidToken, json.JSONDecodeError):
            return None
        return token_info if isinstance(token_info, dict) else None

    def save_profile_metadata(
        self, spotify_user_id: str, profile_version: int, last_profile_update: datetime
    ) -> None:
        user_id, now = self.upsert_user(spotify_user_id), _now()
        statement = self._insert(profiles).values(
            user_id=user_id, profile_version=profile_version,
            last_profile_update=last_profile_update, updated_at=now,
        ).on_conflict_do_update(
            index_elements=[profiles.c.user_id],
            set_={"profile_version": profile_version,
                  "last_profile_update": last_profile_update, "updated_at": now},
        )
        with self.engine.begin() as connection:
            connection.execute(statement)

    def get_profile_metadata(self, spotify_user_id: str) -> dict | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(profiles.c.profile_version, profiles.c.last_profile_update)
                .select_from(profiles.join(users))
                .where(users.c.spotify_user_id == spotify_user_id)
            ).one_or_none()
        if row is None:
            return None
        return {"profile_version": row.profile_version,
                "last_profile_update": self._as_utc(row.last_profile_update)}


class UserTokenCacheHandler(CacheHandler):
    def __init__(self, store: AuthStore, spotify_user_id: str):
        self.store = store
        self.spotify_user_id = spotify_user_id

    def get_cached_token(self):
        return self.store.get_token(self.spotify_user_id)

    def save_token_to_cache(self, token_info):
        self.store.save_token(self.spotify_user_id, token_info)
