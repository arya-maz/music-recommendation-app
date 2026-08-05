from fastapi import FastAPI

from music_taste.spotify.client import get_spotify_client
from music_taste.spotify.recommendations import (
    Recommendation,
    generate_recommendations,
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
    return generate_recommendations(spotify_client, limit=5)