import pandas as pd


REFERENCE_YEAR = 2025 # To reflect the year of the album data

# Thresholds that I set personally based on what feels appropriate
LONG_TRACKLIST_THRESHOLD = 15
SHORT_TRACK_DENSITY_THRESHOLD = 3.0
MODERN_ALBUM_YEAR = 2015

# If I want to switch to a relatively dynamic definition of "modern"
# from datetime import date
# MODERN_ALBUM_YEAR = date.today().year - 10


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Album decade
    df["ALBUM_AGE"] = REFERENCE_YEAR - df["YEAR"]
    df["DECADE"] = (df["YEAR"] // 10) * 10

    # Whether album has a long tracklist (15 or more tracks)
    df["LONG_TRACKLIST"] = (
        df["TRACKS"] >= LONG_TRACKLIST_THRESHOLD
    ).astype(int)

    # Whether album has a short tracklist (7 or fewer tracks)
    df["FEW_TRACKS"] = (df["TRACKS"] <= 7).astype(int)

    # Album is short or long based on runtime
    df["SHORT_ALBUM"] = (df["RUNTIME_MIN"] <= 30).astype(int)
    df["LONG_ALBUM"] = (df["RUNTIME_MIN"] >= 60).astype(int)

    # Album has many yet short tracks (15+ tracks at <3min average)
    df["SHORT_TRACK_DENSE"] = (
        (df["TRACKS"] >= LONG_TRACKLIST_THRESHOLD)
        & (df["AVG_TRACK_LENGTH"] < SHORT_TRACK_DENSITY_THRESHOLD)
    ).astype(int)

    df["MODERN_ALBUM"] = (df["YEAR"] >= MODERN_ALBUM_YEAR).astype(int)

    df["SCORE_TIER"] = df["SCORE"].apply(score_to_tier)
    df["SCORE_TIER_NUM"] = df["SCORE"].apply(score_to_tier_num)

    df["LIKE_LABEL"] = df["SCORE"].apply(score_to_three_category_label)

    return df

# Apply text labels to the score to create categorical features
def score_to_tier(score: int | float) -> str:
    if score <= 39:
        return "dislike"
    elif score <= 54:
        return "neutral"
    elif score <= 69:
        return "moderately_like"
    elif score <= 79:
        return "like"
    else:
        return "love"

# Apply numerical labels to the score to create categorical features
def score_to_tier_num(score: int | float) -> int:
    if score <= 39:
        return 0
    elif score <= 54:
        return 1
    elif score <= 69:
        return 2
    elif score <= 79:
        return 3
    else:
        return 4

# A simpler 3-label set to use for a smaller set of training data
def score_to_three_category_label(score: int | float) -> str:
    if score <= 39:
        return "dislike"
    elif score <= 69:
        return "neutral"
    else:
        return "like"