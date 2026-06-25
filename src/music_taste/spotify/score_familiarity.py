

from __future__ import annotations


HIGH_FAMILIARITY_THRESHOLD = 85


def _as_set(values) -> set[str]:
    """Safely convert a taste-profile list into a set of Spotify IDs."""

    if not values:
        return set()

    return set(values)


def _get_album_id(album: dict) -> str | None:
    """Return the Spotify album ID from an album object."""

    return album.get("id")


def calculate_album_familiarity(album: dict, taste_profile: dict) -> dict:
    """
    Estimate how familiar the user is with an album based on Spotify signals.

    Spotify does not expose full lifetime album play counts through the public API,
    so this score is an approximation based on saved albums, saved-track albums,
    top-track albums, and recently played albums.

    Score guide:
        0   = no evidence the user knows the album
        15  = recently played at least one track from the album
        25  = saved at least one track from the album
        35  = has a top track from the album
        85+ = familiar enough to filter out
        100 = saved album
    """

    album_id = _get_album_id(album)

    if album_id is None:
        return {
            "score": 0,
            "level": "unknown",
            "should_filter": False,
            "reasons": ["missing album ID"],
        }

    saved_album_ids = _as_set(taste_profile.get("saved_album_ids"))
    top_track_album_ids = _as_set(taste_profile.get("top_track_album_ids"))
    recent_album_ids = _as_set(taste_profile.get("recent_album_ids"))
    saved_track_album_ids = _as_set(taste_profile.get("saved_track_album_ids"))

    score = 0
    reasons = []

    if album_id in saved_album_ids:
        score = 100
        reasons.append("album is saved in user's Spotify library")
    else:
        if album_id in top_track_album_ids:
            score += 35
            reasons.append("album contains at least one top track")

        if album_id in saved_track_album_ids:
            score += 25
            reasons.append("album contains at least one saved track")

        if album_id in recent_album_ids:
            score += 15
            reasons.append("album appeared in recent listening")

    score = min(score, 100)

    if score == 0:
        level = "unheard"
        reasons.append("no saved, top, or recent tracks found for this album")
    elif score < 30:
        level = "lightly familiar"
    elif score < 60:
        level = "partially familiar"
    elif score < HIGH_FAMILIARITY_THRESHOLD:
        level = "mostly familiar"
    else:
        level = "highly familiar"

    return {
        "score": score,
        "level": level,
        "should_filter": score >= HIGH_FAMILIARITY_THRESHOLD,
        "reasons": reasons,
    }


def format_familiarity_reason(familiarity: dict) -> str:
    """Create a readable explanation for terminal output or recommendation cards."""

    reasons = familiarity.get("reasons", [])

    if not reasons:
        return "no familiarity details available"

    return "; ".join(reasons)