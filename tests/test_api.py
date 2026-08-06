from fastapi.testclient import TestClient

from api.main import app
from music_taste.spotify.recommendations import Recommendation


client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recommendations_endpoint_uses_existing_pipeline(monkeypatch):
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

    def fake_get_spotify_client():
        return spotify_client

    def fake_prepare_user_profile(received_client):
        calls["prepare_client"] = received_client
        return taste_profile

    def fake_generate_recommendations_from_profile(received_client, profile, limit):
        calls["generate_client"] = received_client
        calls["profile"] = profile
        calls["limit"] = limit
        return expected_recommendations

    monkeypatch.setattr(
        "api.main.get_spotify_client",
        fake_get_spotify_client,
    )
    monkeypatch.setattr(
        "api.main.prepare_user_profile",
        fake_prepare_user_profile,
    )
    monkeypatch.setattr(
        "api.main.generate_recommendations_from_profile",
        fake_generate_recommendations_from_profile,
    )

    response = client.post("/api/recommendations")

    assert response.status_code == 200
    assert calls == {
        "prepare_client": spotify_client,
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
