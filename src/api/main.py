from fastapi import FastAPI

from music_taste.spotify.client import get_spotify_client
from music_taste.spotify.recommendations import (
    Recommendation,
    generate_recommendations_from_profile,
    prepare_user_profile,
)


app = FastAPI(
    title="Spotify Album Recommendation API",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/recommendations")
def create_recommendations() -> list[Recommendation]:
    spotify_client = get_spotify_client()
    taste_profile = prepare_user_profile(spotify_client)
    return generate_recommendations_from_profile(
        spotify_client,
        taste_profile,
        limit=5,
    )
