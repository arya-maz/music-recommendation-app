import json
from datetime import datetime, timezone

from music_taste.cache.profile_cache import save_cached_profile
from scripts.analyze_recommendation_pipeline import (
    analyze_cached_candidates,
    compare_recommendation_strategies,
    load_analysis_inputs,
    print_analysis,
    print_strategy_comparison,
)


def _album(album_id, artist_id, artist_name, familiarity=None):
    return {
        "id": album_id,
        "name": f"Album {album_id}",
        "artists": [{"id": artist_id, "name": artist_name}],
        **({"familiarity": familiarity} if familiarity else {}),
    }


def test_cached_analysis_reports_funnel_scores_and_ties():
    profile = {
        "artist_scores": {"artist-1": 10.0, "artist-2": 20.0},
        "saved_album_ids": ["filtered"],
    }
    cached_albums = [
        _album("a", "artist-1", "First"),
        _album("b", "artist-1", "First"),
        _album("c", "artist-2", "Second"),
        _album("filtered", "artist-2", "Second"),
    ]

    metrics = analyze_cached_candidates(profile, cached_albums)

    assert metrics["cached_candidate_count"] == 4
    assert metrics["familiarity_filtered_count"] == 1
    assert metrics["eligible_candidate_count"] == 3
    assert metrics["final_selected_count"] == 2
    assert metrics["artist_affinity_distribution"] == {10.0: 2, 20.0: 1}
    assert metrics["familiarity_distribution"] == {0: 3}
    assert metrics["unique_recommendation_score_count"] == 2
    assert metrics["largest_score_tie_count"] == 2
    assert metrics["numeric_tie_group_count"] == 1
    assert metrics["candidates_requiring_text_tiebreak"] == 2


def test_analysis_reads_cache_without_modifying_or_printing_private_values(
    tmp_path,
    capsys,
):
    profile_root = tmp_path / "users"
    candidate_path = tmp_path / "candidate_albums.json"
    profile = {"artist_scores": {"private-artist-id": 10.0}}
    albums = [_album("private-album-id", "private-artist-id", "Private Name")]
    save_cached_profile(
        "private-user-id",
        profile,
        now=datetime(2026, 8, 6, tzinfo=timezone.utc),
        cache_root=profile_root,
    )
    candidate_path.write_text(json.dumps(albums), encoding="utf-8")
    profile_path = profile_root / "private-user-id" / "profile.pkl"
    metadata_path = profile_root / "private-user-id" / "metadata.json"
    original_files = {
        profile_path: profile_path.read_bytes(),
        metadata_path: metadata_path.read_bytes(),
        candidate_path: candidate_path.read_bytes(),
    }

    loaded_profile, loaded_albums = load_analysis_inputs(
        cache_root=profile_root,
        candidate_cache_path=candidate_path,
        spotify_user_id="private-user-id",
    )
    print_analysis(analyze_cached_candidates(loaded_profile, loaded_albums))
    output = capsys.readouterr().out

    assert "Private Name" not in output
    assert "private-artist-id" not in output
    assert "private-album-id" not in output
    assert all(path.read_bytes() == contents for path, contents in original_files.items())


def test_strategy_comparison_reports_details_and_diversity_statistics(capsys):
    profile = {
        "artist_scores": {
            f"artist-{index}": index * 10 for index in range(1, 11)
        }
    }
    albums = [
        _album(
            f"album-{index}",
            f"artist-{index}",
            f"Artist {index}",
        )
        for index in range(1, 11)
    ]

    comparison = compare_recommendation_strategies(
        profile,
        albums,
        random_seed=4,
    )
    print_strategy_comparison(comparison)
    output = capsys.readouterr().out

    assert len(comparison["baseline"]) == 5
    assert len(comparison["balanced"]) == 5
    assert comparison["balanced_summary"]["unique_affinity_bands"] == 2
    assert comparison["balanced_summary"]["affinity_percentile_spread"] > 0
    assert "Current Strategy" in output
    assert "Balanced Strategy" in output
    assert "affinity:" in output
    assert "percentile:" in output
    assert "Recommendation overlap:" in output
