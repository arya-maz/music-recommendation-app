import logging

from music_taste.spotify.client import get_spotify_client
from music_taste.spotify.recommendations import (
    FINAL_RECOMMENDATION_COUNT,
    Recommendation,
    generate_recommendations_from_profile,
    get_or_prepare_user_profile,
)


def print_recommendations(recommendations: list[Recommendation]) -> None:
    print(f"Final {FINAL_RECOMMENDATION_COUNT} Album Recommendations")
    print("-----------------------------")

    for index, recommendation in enumerate(recommendations, start=1):
        print(
            f"{index}. {recommendation.artist_name} - "
            f"{recommendation.album_name}"
        )
        print(f"   Recommendation score: {recommendation.recommendation_score:.2f}")
        print(f"   Artist affinity: {recommendation.artist_affinity:.2f}")
        print(
            "   Familiarity: "
            f"{recommendation.familiarity_score:g} "
            f"({recommendation.familiarity_label})"
        )
        print(f"   Why: {recommendation.reason}")
        if recommendation.spotify_url:
            print(f"   Spotify: {recommendation.spotify_url}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    spotify_client = get_spotify_client()
    taste_profile = get_or_prepare_user_profile(spotify_client)
    recommendations = generate_recommendations_from_profile(
        spotify_client,
        taste_profile,
    )
    print_recommendations(recommendations)


if __name__ == "__main__":
    main()
