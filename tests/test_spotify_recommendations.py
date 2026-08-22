import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from music_taste.spotify.find_candidates import (
    _load_candidate_album_cache,
    _save_candidate_album_cache,
)
from music_taste.spotify.rank_recommendations import (
    BALANCED_AFFINITY_STRATEGY,
    DEFAULT_RECOMMENDATION_STRATEGY,
    FINAL_RECOMMENDATION_COUNT,
    LOWEST_AFFINITY_STRATEGY,
    _rank_with_random_exact_ties,
    rank_candidates,
    score_candidate,
    select_final_recommendations,
)
from music_taste.spotify.recommendations import (
    Recommendation,
    generate_recommendations,
    generate_recommendations_from_profile,
    get_or_prepare_user_profile,
    prepare_user_profile,
)


def make_candidate(
    album_id: str,
    artist_id: str,
    artist_name: str,
    album_name: str,
    familiarity_score: int = 0,
) -> dict:
    if familiarity_score == 0:
        familiarity_level = "unheard"
    elif familiarity_score < 30:
        familiarity_level = "lightly familiar"
    elif familiarity_score < 60:
        familiarity_level = "partially familiar"
    else:
        familiarity_level = "mostly familiar"

    return {
        "id": album_id,
        "name": album_name,
        "artists": [{"id": artist_id, "name": artist_name}],
        "familiarity": {
            "score": familiarity_score,
            "level": familiarity_level,
            "should_filter": False,
            "reasons": [],
        },
    }


class RecommendationSelectionTests(unittest.TestCase):
    def test_explicit_baseline_strategy_matches_existing_default(self):
        candidates = [
            make_candidate(
                f"album-{index}",
                f"artist-{index}",
                f"Artist {index}",
                f"Album {index}",
            )
            for index in range(8)
        ]
        profile = {
            "artist_scores": {f"artist-{index}": index + 1 for index in range(8)}
        }

        default = select_final_recommendations(candidates, profile)
        explicit = select_final_recommendations(
            candidates,
            profile,
            strategy=DEFAULT_RECOMMENDATION_STRATEGY,
        )

        self.assertEqual(default, explicit)

    def test_balanced_strategy_allocates_discovery_and_expansion_bands(self):
        candidates = [
            make_candidate(
                f"album-{index}",
                f"artist-{index}",
                f"Artist {index}",
                f"Album {index}",
            )
            for index in range(1, 11)
        ]
        profile = {
            "artist_scores": {
                f"artist-{index}": index * 10 for index in range(1, 11)
            }
        }

        recommendations = select_final_recommendations(
            candidates,
            profile,
            strategy=BALANCED_AFFINITY_STRATEGY,
            random_generator=random.Random(7),
        )
        selected_affinities = {
            album["recommendation"]["artist_affinity"]
            for album in recommendations
        }

        self.assertEqual(selected_affinities, {10.0, 20.0, 30.0, 80.0, 90.0})
        self.assertEqual(len(recommendations), 5)

    def test_balanced_strategy_falls_back_when_one_band_is_empty(self):
        candidates = [
            make_candidate(
                f"album-{index}",
                f"artist-{index}",
                f"Artist {index}",
                f"Album {index}",
            )
            for index in range(6)
        ]
        profile = {"artist_scores": {f"artist-{index}": 10 for index in range(6)}}

        recommendations = select_final_recommendations(
            candidates,
            profile,
            strategy=BALANCED_AFFINITY_STRATEGY,
            random_generator=random.Random(3),
        )

        self.assertEqual(len(recommendations), 5)
        self.assertEqual(
            len({album["artists"][0]["name"] for album in recommendations}),
            5,
        )

    def test_balanced_strategy_randomizes_only_exact_numeric_ties(self):
        class ReverseRandom:
            @staticmethod
            def shuffle(values):
                values.reverse()

        tied_candidates = [
            make_candidate("a", "artist-a", "Alpha", "First"),
            make_candidate("b", "artist-b", "Beta", "Second"),
        ]
        profile = {"artist_scores": {"artist-a": 10, "artist-b": 10}}

        scored_candidates = [
            score_candidate(album, profile) for album in tied_candidates
        ]
        recommendations = _rank_with_random_exact_ties(
            scored_candidates,
            ReverseRandom(),
        )

        self.assertEqual([album["id"] for album in recommendations], ["b", "a"])

    def test_balanced_strategy_keeps_score_primary_and_familiarity_secondary(self):
        candidates = [
            make_candidate("strong", "artist-strong", "Strong", "Strong", 25),
            make_candidate("weak", "artist-weak", "Weak", "Weak", 0),
            make_candidate("tie-unheard", "artist-tie-a", "Tie A", "Tie A", 0),
            make_candidate("tie-familiar", "artist-tie-b", "Tie B", "Tie B", 25),
        ]
        profile = {
            "artist_scores": {
                "artist-strong": 200,
                "artist-weak": 5,
                "artist-tie-a": 20,
                "artist-tie-b": 50,
            }
        }

        recommendations = select_final_recommendations(
            candidates,
            profile,
            recommendation_count=4,
            strategy=BALANCED_AFFINITY_STRATEGY,
            random_generator=random.Random(1),
        )
        numeric_keys = [
            (
                -album["recommendation"]["score"],
                album["familiarity"]["score"],
            )
            for album in recommendations
        ]

        self.assertEqual(numeric_keys, sorted(numeric_keys))

    def test_complete_pool_is_considered_and_later_candidate_can_win(self):
        candidates = [
            make_candidate(f"album-{index}", f"artist-{index}", f"Artist {index}", f"Album {index}")
            for index in range(1, 7)
        ]
        profile = {
            "artist_scores": {
                **{f"artist-{index}": 5 for index in range(1, 7)},
                "artist-6": 200,
            }
        }

        recommendations = select_final_recommendations(candidates, profile)

        self.assertEqual(recommendations[0]["id"], "album-6")
        self.assertEqual(len(recommendations), FINAL_RECOMMENDATION_COUNT)

    def test_unfamiliarity_alone_does_not_make_candidate_strongest(self):
        candidates = [
            make_candidate("unheard", "artist-1", "Unknown Fit", "Unheard", 0),
            make_candidate("balanced", "artist-2", "Known Fit", "Underexplored", 25),
        ]
        profile = {"artist_scores": {"artist-1": 0, "artist-2": 100}}

        ranked = rank_candidates(candidates, profile)

        self.assertEqual(ranked[0]["id"], "balanced")

    def test_output_is_limited_to_five_unique_artists(self):
        candidates = [
            make_candidate(f"album-{index}", f"artist-{index}", f"Artist {index}", f"Album {index}")
            for index in range(8)
        ]
        profile = {"artist_scores": {f"artist-{index}": index + 1 for index in range(8)}}

        recommendations = select_final_recommendations(candidates, profile)

        self.assertEqual(len(recommendations), 5)
        self.assertEqual(
            len({album["artists"][0]["name"].casefold() for album in recommendations}),
            5,
        )

    def test_highest_ranked_album_is_retained_for_duplicate_artist(self):
        candidates = [
            make_candidate("familiar", "artist-1", "Artist", "Familiar Album", 60),
            make_candidate("unheard", "artist-1", "Artist", "Unheard Album", 0),
            make_candidate("other", "artist-2", "Other", "Other Album", 0),
        ]
        profile = {"artist_scores": {"artist-1": 50, "artist-2": 20}}

        recommendations = select_final_recommendations(candidates, profile)

        self.assertIn("unheard", [album["id"] for album in recommendations])
        self.assertNotIn("familiar", [album["id"] for album in recommendations])

    def test_fewer_than_five_unique_artists_returns_fewer_results(self):
        candidates = [
            make_candidate("one", "artist-1", "Artist One", "One"),
            make_candidate("two", "artist-1", "Artist One", "Two"),
            make_candidate("three", "artist-2", "Artist Two", "Three"),
        ]
        profile = {"artist_scores": {"artist-1": 20, "artist-2": 10}}

        recommendations = select_final_recommendations(candidates, profile)

        self.assertEqual(len(recommendations), 2)

    def test_artist_capitalization_is_ignored_for_uniqueness(self):
        candidates = [
            make_candidate("one", "artist-1", "The Artist", "One"),
            make_candidate("two", "artist-1", "the artist", "Two"),
        ]
        profile = {"artist_scores": {"artist-1": 20}}

        recommendations = select_final_recommendations(candidates, profile)

        self.assertEqual(len(recommendations), 1)

    def test_ranking_is_deterministic_across_input_order(self):
        candidates = [
            make_candidate("b", "artist-b", "Beta", "Second"),
            make_candidate("a", "artist-a", "Alpha", "First"),
        ]
        profile = {"artist_scores": {"artist-a": 20, "artist-b": 20}}

        forward = rank_candidates(candidates, profile)
        reverse = rank_candidates(list(reversed(candidates)), profile)

        self.assertEqual(
            [album["id"] for album in forward],
            [album["id"] for album in reverse],
        )

    def test_tie_breaking_uses_artist_then_album_then_id(self):
        candidates = [
            make_candidate("z", "artist-b", "Beta", "Album"),
            make_candidate("z", "artist-a", "Alpha", "Zulu"),
            make_candidate("b", "artist-a", "Alpha", "Album"),
            make_candidate("a", "artist-a", "Alpha", "Album"),
        ]
        profile = {"artist_scores": {"artist-a": 20, "artist-b": 20}}

        ranked = rank_candidates(candidates, profile)

        self.assertEqual([album["id"] for album in ranked], ["a", "b", "z", "z"])

    def test_candidate_cache_contents_are_not_truncated_by_selection(self):
        candidates = [
            make_candidate(f"album-{index}", f"artist-{index}", f"Artist {index}", f"Album {index}")
            for index in range(10)
        ]
        profile = {"artist_scores": {f"artist-{index}": index for index in range(10)}}

        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "candidate_albums.json"
            _save_candidate_album_cache(candidates, cache_path)
            original_cache = json.loads(cache_path.read_text(encoding="utf-8"))
            candidate_albums = _load_candidate_album_cache(cache_path)
            assert candidate_albums is not None
            select_final_recommendations(candidate_albums, profile)
            final_cache = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(final_cache, original_cache)
        self.assertEqual(len(final_cache), 10)


def test_prepare_user_profile_collects_data_and_builds_profile(monkeypatch):
    spotify_client = object()
    spotify_data = {"top_artists": [], "saved_albums": []}
    taste_profile = {"artist_scores": {}, "known_album_ids": []}
    calls = {}

    def fake_fetch(client, user_directory):
        calls["fetch_client"] = client
        calls["user_directory"] = user_directory
        return spotify_data

    def fake_build_profile(data):
        calls["profile_data"] = data
        return taste_profile

    monkeypatch.setattr(
        "music_taste.spotify.recommendations.fetch_and_save_spotify_data",
        fake_fetch,
    )
    monkeypatch.setattr(
        "music_taste.spotify.recommendations.build_taste_profile",
        fake_build_profile,
    )

    user_directory = Path("cache/users/spotify-user-123")
    result = prepare_user_profile(spotify_client, user_directory)

    assert result is taste_profile
    assert calls == {
        "fetch_client": spotify_client,
        "user_directory": user_directory,
        "profile_data": spotify_data,
    }


def test_get_or_prepare_user_profile_caches_miss_and_reuses_hit(monkeypatch, tmp_path):
    taste_profile = {"artist_scores": {"artist-1": 50}}
    prepare_calls = []

    class FakeSpotifyClient:
        def current_user(self):
            return {"id": "spotify-user-123"}

    spotify_client = FakeSpotifyClient()

    def fake_prepare(client, user_directory):
        prepare_calls.append(client)
        assert user_directory == tmp_path / "spotify-user-123"
        return taste_profile

    monkeypatch.setattr(
        "music_taste.spotify.recommendations.prepare_user_profile",
        fake_prepare,
    )

    first_result = get_or_prepare_user_profile(
        spotify_client,
        cache_root=tmp_path,
    )
    second_result = get_or_prepare_user_profile(
        spotify_client,
        cache_root=tmp_path,
    )

    assert first_result == taste_profile
    assert second_result == taste_profile
    assert prepare_calls == [spotify_client]


def test_profile_based_generation_does_not_fetch_or_rebuild_profile(monkeypatch):
    class FakeSpotifyClient:
        def current_user(self):
            return {"id": "spotify-user-123"}

    spotify_client = FakeSpotifyClient()
    taste_profile = {"artist_scores": {"artist-1": 50}}
    selected_album = {
        "id": "album-1",
        "name": "Album One",
        "artists": [{"id": "artist-1", "name": "Artist One"}],
        "external_urls": {"spotify": "https://open.spotify.test/album/1"},
        "images": [{"url": "https://images.test/album-1.jpg"}],
        "familiarity": {"score": 15, "level": "lightly familiar"},
        "recommendation": {
            "score": 64.0,
            "artist_affinity": 50.0,
            "explanation": "meaningful prior artist interest; low album familiarity",
        },
    }
    calls = {}

    def fail_if_called(*args, **kwargs):
        raise AssertionError("profile-based generation must not prepare the profile")

    def fake_find_candidates(client, profile, user_directory):
        calls["candidate_client"] = client
        calls["candidate_profile"] = profile
        calls["user_directory"] = user_directory
        return [{"id": "candidate"}]

    def fake_select(candidates, profile, recommendation_count):
        calls["selection_candidates"] = candidates
        calls["selection_profile"] = profile
        calls["selection_limit"] = recommendation_count
        return [selected_album]

    monkeypatch.setattr(
        "music_taste.spotify.recommendations.fetch_and_save_spotify_data",
        fail_if_called,
    )
    monkeypatch.setattr(
        "music_taste.spotify.recommendations.build_taste_profile",
        fail_if_called,
    )
    monkeypatch.setattr(
        "music_taste.spotify.recommendations.find_candidate_albums",
        fake_find_candidates,
    )
    monkeypatch.setattr(
        "music_taste.spotify.recommendations.select_final_recommendations",
        fake_select,
    )

    recommendations = generate_recommendations_from_profile(
        spotify_client,
        taste_profile,
        limit=3,
    )

    assert recommendations[0].album_name == "Album One"
    assert calls == {
        "candidate_client": spotify_client,
        "candidate_profile": taste_profile,
        "user_directory": Path(__file__).resolve().parents[1] / "cache" / "users" / "spotify-user-123",
        "selection_candidates": [{"id": "candidate"}],
        "selection_profile": taste_profile,
        "selection_limit": 3,
    }


def test_generate_recommendations_returns_structured_results(monkeypatch):
    class FakeSpotifyClient:
        def current_user(self):
            return {"id": "spotify-user-123"}

    spotify_client = FakeSpotifyClient()
    taste_profile = {"artist_scores": {"artist-1": 50}}
    selected_album = {
        "id": "album-1",
        "name": "Album One",
        "artists": [{"id": "artist-1", "name": "Artist One"}],
        "external_urls": {"spotify": "https://open.spotify.test/album/1"},
        "images": [{"url": "https://images.test/album-1.jpg"}],
        "familiarity": {"score": 15, "level": "lightly familiar"},
        "recommendation": {
            "score": 64.0,
            "artist_affinity": 50.0,
            "explanation": "meaningful prior artist interest; low album familiarity",
        },
    }
    calls = {}

    def fake_get_or_prepare_profile(client):
        calls["profile_client"] = client
        return taste_profile

    def fake_find_candidates(client, profile, user_directory):
        calls["candidate_client"] = client
        calls["candidate_profile"] = profile
        calls["user_directory"] = user_directory
        return [{"id": "candidate"}]

    def fake_select(candidates, profile, recommendation_count):
        calls["selection_candidates"] = candidates
        calls["selection_profile"] = profile
        calls["selection_limit"] = recommendation_count
        return [selected_album]

    monkeypatch.setattr(
        "music_taste.spotify.recommendations.get_or_prepare_user_profile",
        fake_get_or_prepare_profile,
    )
    monkeypatch.setattr(
        "music_taste.spotify.recommendations.find_candidate_albums",
        fake_find_candidates,
    )
    monkeypatch.setattr(
        "music_taste.spotify.recommendations.select_final_recommendations",
        fake_select,
    )

    recommendations = generate_recommendations(spotify_client, limit=3)

    assert recommendations == [
        Recommendation(
            artist_name="Artist One",
            album_name="Album One",
            spotify_url="https://open.spotify.test/album/1",
            album_image_url="https://images.test/album-1.jpg",
            recommendation_score=64.0,
            reason="meaningful prior artist interest; low album familiarity",
            artist_affinity=50.0,
            familiarity_score=15.0,
            familiarity_label="lightly familiar",
        )
    ]
    assert calls == {
        "profile_client": spotify_client,
        "candidate_client": spotify_client,
        "candidate_profile": taste_profile,
        "user_directory": Path(__file__).resolve().parents[1] / "cache" / "users" / "spotify-user-123",
        "selection_candidates": [{"id": "candidate"}],
        "selection_profile": taste_profile,
        "selection_limit": 3,
    }


def test_generate_recommendations_handles_missing_optional_album_media(monkeypatch):
    class FakeSpotifyClient:
        def current_user(self):
            return {"id": "spotify-user-123"}

    selected_album = {
        "name": "Album Without Media",
        "artists": [{"id": "artist-1", "name": "Artist One"}],
        "familiarity": {"score": 0, "level": "unheard"},
        "recommendation": {
            "score": 50.0,
            "artist_affinity": 10.0,
            "explanation": "some prior artist interest; no album-familiarity signals",
        },
    }

    monkeypatch.setattr(
        "music_taste.spotify.recommendations.find_candidate_albums",
        lambda client, profile, user_directory: [],
    )
    monkeypatch.setattr(
        "music_taste.spotify.recommendations.select_final_recommendations",
        lambda candidates, profile, recommendation_count: [selected_album],
    )

    recommendation = generate_recommendations_from_profile(FakeSpotifyClient(), {})[0]

    assert recommendation.spotify_url is None
    assert recommendation.album_image_url is None


def test_profile_generation_forwards_nondefault_strategy(monkeypatch):
    class FakeSpotifyClient:
        def current_user(self):
            return {"id": "spotify-user-123"}

    calls = {}
    selected_album = {
        "name": "Balanced Album",
        "artists": [{"id": "artist-1", "name": "Artist One"}],
        "familiarity": {"score": 0, "level": "unheard"},
        "recommendation": {
            "score": 50.0,
            "artist_affinity": 10.0,
            "explanation": "some prior artist interest; no album-familiarity signals",
        },
    }

    monkeypatch.setattr(
        "music_taste.spotify.recommendations.find_candidate_albums",
        lambda client, profile, user_directory: [{"id": "candidate"}],
    )

    def fake_select(candidates, profile, recommendation_count, strategy):
        calls["strategy"] = strategy
        calls["limit"] = recommendation_count
        return [selected_album]

    monkeypatch.setattr(
        "music_taste.spotify.recommendations.select_final_recommendations",
        fake_select,
    )

    recommendations = generate_recommendations_from_profile(
        FakeSpotifyClient(),
        {"artist_scores": {}},
        limit=5,
        strategy=LOWEST_AFFINITY_STRATEGY,
    )

    assert len(recommendations) == 1
    assert calls == {
        "strategy": LOWEST_AFFINITY_STRATEGY,
        "limit": 5,
    }


if __name__ == "__main__":
    unittest.main()
