from music_taste.spotify.client import get_spotify_client
from music_taste.spotify.fetch_data import fetch_and_save_spotify_data
from music_taste.spotify.build_profile import build_taste_profile
from music_taste.spotify.find_candidates import find_candidate_albums


def main() -> None:
    spotify_data = fetch_and_save_spotify_data()
    taste_profile = build_taste_profile(spotify_data)
    sp = get_spotify_client()
    candidate_albums = find_candidate_albums(sp, taste_profile)

    print("Top Artists")
    print("-----------")

    for index, artist in enumerate(spotify_data["top_artists"][:10], start=1):
        print(f"{index}. {artist['name']}")

    print()
    print("Spotify Data Summary")
    print("--------------------")
    print(f"Top artists: {len(spotify_data['top_artists'])}")
    print(f"Top tracks: {len(spotify_data['top_tracks'])}")
    print(f"Recently played tracks: {len(spotify_data['recently_played'])}")
    print(f"Saved albums: {len(spotify_data['saved_albums'])}")
    print(f"Saved tracks: {len(spotify_data['saved_tracks'])}")

    print()
    print("Taste Profile Summary")
    print("---------------------")
    print(f"Artists scored: {len(taste_profile['artist_scores'])}")
    print(f"Known albums: {len(taste_profile['known_album_ids'])}")
    print(f"Saved albums: {len(taste_profile['saved_album_ids'])}")
    print(f"Top-track albums: {len(taste_profile['top_track_album_ids'])}")
    print(f"Recent albums: {len(taste_profile['recent_album_ids'])}")
    print(f"Saved-track albums: {len(taste_profile['saved_track_album_ids'])}")

    print()
    print("Candidate Albums")
    print("----------------")
    print(f"Candidate albums found: {len(candidate_albums)}")

    for index, album in enumerate(candidate_albums, start=1):
        artist_names = ", ".join(artist["name"] for artist in album["artists"])
        print(f"{index}. {artist_names} - {album['name']}")


if __name__ == "__main__":
    main()