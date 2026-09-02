from __future__ import annotations

import os
import secrets
from functools import lru_cache
from typing import Literal

import spotipy
from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api.auth import AuthStore, UserTokenCacheHandler
from music_taste.cache.profile_cache import delete_user_data, migrate_user_data_identity
from music_taste.spotify.client import get_spotify_client, get_spotify_oauth
from music_taste.spotify.recommendations import (
    Recommendation,
    generate_recommendations_from_profile,
    get_or_prepare_user_profile,
)


app = FastAPI(
    title="Spotify Album Recommendation API",
    version="0.2.0",
)

if frontend_origin := os.getenv("FRONTEND_ORIGIN"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

SESSION_COOKIE = "music_session"
OAUTH_STATE_COOKIE = "spotify_oauth_state"


class AccountDeletionRequest(BaseModel):
    confirm: Literal[True]


@lru_cache
def get_auth_store() -> AuthStore:
    return AuthStore.from_environment()


def _cookie_secure() -> bool:
    return os.getenv("APP_COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}


def _set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def authenticated_user_id(
    music_session: str | None = Cookie(default=None),
    store: AuthStore = Depends(get_auth_store),
) -> str:
    user_id = store.get_session_user(music_session) if music_session else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user_id


def authenticated_spotify_client(
    user_id: str = Depends(authenticated_user_id),
    store: AuthStore = Depends(get_auth_store),
):
    if store.get_token(user_id) is None:
        raise HTTPException(status_code=401, detail="Spotify authorization missing")
    return get_spotify_client(
        cache_handler=UserTokenCacheHandler(store, user_id),
        open_browser=False,
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/auth/login")
def spotify_login(store: AuthStore = Depends(get_auth_store)) -> RedirectResponse:
    state = store.create_oauth_state()
    response = RedirectResponse(get_spotify_oauth().get_authorize_url(state=state))
    _set_cookie(response, OAUTH_STATE_COOKIE, state, max_age=600)
    return response


@app.get("/api/auth/callback")
def spotify_callback(
    state: str = Query(...),
    code: str = Query(...),
    spotify_oauth_state: str | None = Cookie(default=None),
    store: AuthStore = Depends(get_auth_store),
) -> RedirectResponse:
    if (
        not spotify_oauth_state
        or not secrets.compare_digest(state, spotify_oauth_state)
        or not store.consume_oauth_state(state)
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    token_info = get_spotify_oauth().get_access_token(code, check_cache=False)
    if not isinstance(token_info, dict) or not token_info.get("access_token"):
        raise HTTPException(status_code=502, detail="Spotify token exchange failed")
    spotify_user = spotipy.Spotify(auth=token_info["access_token"]).current_user()
    legacy_user_id = spotify_user.get("id") if isinstance(spotify_user, dict) else None
    account_id = spotify_user.get("account_id") if isinstance(spotify_user, dict) else None
    user_id = account_id or legacy_user_id
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=502, detail="Spotify user identity unavailable")

    try:
        if isinstance(legacy_user_id, str) and legacy_user_id:
            migrate_user_data_identity(legacy_user_id, user_id)
    except (FileExistsError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.migrate_user_identity_and_save_token(
        user_id,
        token_info,
        legacy_user_id=legacy_user_id,
        display_name=spotify_user.get("display_name") if isinstance(spotify_user, dict) else None,
    )
    response = RedirectResponse(os.getenv("FRONTEND_AUTH_SUCCESS_URL", "/docs"))
    _set_cookie(response, SESSION_COOKIE, store.create_session(user_id), max_age=30 * 86400)
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return response


@app.get("/api/auth/me")
def auth_me(
    user_id: str = Depends(authenticated_user_id),
    store: AuthStore = Depends(get_auth_store),
) -> dict[str, str]:
    return {
        "spotify_user_id": user_id,
        "account_name": store.get_user_display_name(user_id) or user_id,
    }


@app.post("/api/auth/logout", status_code=204)
def logout(
    response: Response,
    music_session: str | None = Cookie(default=None),
    store: AuthStore = Depends(get_auth_store),
) -> None:
    if music_session:
        store.delete_session(music_session)
    response.delete_cookie(SESSION_COOKIE, path="/")


@app.delete("/api/auth/account", status_code=204)
def delete_account(
    deletion: AccountDeletionRequest,
    response: Response,
    user_id: str = Depends(authenticated_user_id),
    store: AuthStore = Depends(get_auth_store),
) -> None:
    delete_user_data(user_id)
    store.delete_account_credentials(user_id)
    response.delete_cookie(SESSION_COOKIE, path="/")


@app.post("/api/recommendations")
def create_recommendations(
    spotify_client=Depends(authenticated_spotify_client),
    store: AuthStore = Depends(get_auth_store),
) -> list[Recommendation]:
    taste_profile = get_or_prepare_user_profile(
        spotify_client,
        profile_metadata_store=store,
    )
    return generate_recommendations_from_profile(
        spotify_client,
        taste_profile,
        limit=5,
    )
