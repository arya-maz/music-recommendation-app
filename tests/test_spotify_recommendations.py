import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from music_taste.spotify.find_candidates import (
    _load_candidate_album_cache,
    _save_candidate_album_cache,
)
from music_taste.spotify.rank_recommendations import (
    FINAL_RECOMMENDATION_COUNT,
    rank_candidates,
    select_final_recommendations,
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

            with patch(
                "music_taste.spotify.find_candidates.CANDIDATE_ALBUMS_CACHE_PATH",
                cache_path,
            ):
                _save_candidate_album_cache(candidates)
                original_cache = json.loads(cache_path.read_text(encoding="utf-8"))
                select_final_recommendations(_load_candidate_album_cache(), profile)
                final_cache = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(final_cache, original_cache)
        self.assertEqual(len(final_cache), 10)


if __name__ == "__main__":
    unittest.main()
