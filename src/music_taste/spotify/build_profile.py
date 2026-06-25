from collections import defaultdict


def build_taste_profile(spotify_data: dict) -> dict:
    artist_scores = defaultdict(float)

    known_album_ids = set()
    saved_album_ids = set()
    top_track_album_ids = set()
    recent_album_ids = set()
    saved_track_album_ids = set()

    top_artist_ids = []

    # Top artists are the strongest artist-level signal.
    for rank, artist in enumerate(spotify_data["top_artists"], start=1):
        artist_id = artist["id"]
        top_artist_ids.append(artist_id)

        # Higher-ranked artists get more weight.
        artist_scores[artist_id] += max(1, 51 - rank)

    # Top tracks reveal artists and albums the user strongly returns to.
    for rank, track in enumerate(spotify_data["top_tracks"], start=1):
        album = track["album"]
        album_id = album["id"]

        known_album_ids.add(album_id)
        top_track_album_ids.add(album_id)

        track_score = max(1, 51 - rank)

        for artist in track["artists"]:
            artist_scores[artist["id"]] += track_score * 0.5

    # Saved albums are albums the user already knows and likely values.
    for item in spotify_data["saved_albums"]:
        album = item["album"]
        album_id = album["id"]

        known_album_ids.add(album_id)
        saved_album_ids.add(album_id)

        for artist in album["artists"]:
            artist_scores[artist["id"]] += 25

    # Saved tracks are strong song-level interest signals.
    for item in spotify_data["saved_tracks"]:
        track = item["track"]
        album = track["album"]
        album_id = album["id"]

        known_album_ids.add(album_id)
        saved_track_album_ids.add(album_id)

        for artist in track["artists"]:
            artist_scores[artist["id"]] += 10

    # Recent plays capture the user's current phase.
    for item in spotify_data["recently_played"]:
        track = item["track"]
        album = track["album"]
        album_id = album["id"]

        known_album_ids.add(album_id)
        recent_album_ids.add(album_id)

        for artist in track["artists"]:
            artist_scores[artist["id"]] += 5

    return {
        "artist_scores": dict(artist_scores),
        "top_artist_ids": top_artist_ids,
        "known_album_ids": list(known_album_ids),
        "saved_album_ids": list(saved_album_ids),
        "top_track_album_ids": list(top_track_album_ids),
        "recent_album_ids": list(recent_album_ids),
        "saved_track_album_ids": list(saved_track_album_ids),
    }