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
    expected_recommendations = [
        Recommendation(
            artist_name="Artist One",
            album_name="Album One",
            spotify_url="https://open.spotify.test/album/one",
            album_image_url="https://images.test/album-one.jpg",
            recommendation_score=72.5,
            reason="strong artist-fit evidence; low album familiarity",
            artist_affinity=80.0,
            familiarity_score=15.0,
            familiarity_label="lightly familiar",
        )
    ]
    calls = {}

    def fake_get_spotify_client():
        return spotify_client

    def fake_generate_recommendations(received_client, limit):
        calls["spotify_client"] = received_client
        calls["limit"] = limit
        return expected_recommendations

    monkeypatch.setattr(
        "api.main.get_spotify_client",
        fake_get_spotify_client,
    )
    monkeypatch.setattr(
        "api.main.generate_recommendations",
        fake_generate_recommendations,
    )

    response = client.post("/api/recommendations?limit=3")

    assert response.status_code == 200
    assert calls == {"spotify_client": spotify_client, "limit": 3}
    assert response.json() == [
        {
            "artist_name": "Artist One",
            "album_name": "Album One",
            "spotify_url": "https://open.spotify.test/album/one",
            "album_image_url": "https://images.test/album-one.jpg",
            "recommendation_score": 72.5,
            "reason": "strong artist-fit evidence; low album familiarity",
            "artist_affinity": 80.0,
            "familiarity_score": 15.0,
            "familiarity_label": "lightly familiar",
        }
    ]
