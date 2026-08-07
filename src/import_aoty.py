from pathlib import Path

import pandas as pd


RAW_DATA_PATH = Path("data/raw/aoty_export.csv")
PROCESSED_DATA_PATH = Path("data/processed/aoty_cleaned.csv")


def load_aoty_export(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Could not find AOTY export at: {path}")

    return pd.read_csv(path)


def clean_aoty_data(df: pd.DataFrame) -> pd.DataFrame:
    expected_columns = {
        "Artist",
        "Album",
        "Year",
        "Type",
        "Rating",
        "Date Rated",
    }

    missing_columns = expected_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Missing expected columns: {missing_columns}")

    cleaned_df = df.copy()

    cleaned_df = cleaned_df.rename(
        columns={
            "Artist": "artist",
            "Album": "album",
            "Year": "release_year",
            "Type": "format",
            "Rating": "score",
            "Date Rated": "date_rated",
        }
    )

    text_columns = ["artist", "album", "format"]

    for column in text_columns:
        cleaned_df[column] = cleaned_df[column].astype("string").str.strip()

    cleaned_df["release_year"] = pd.to_numeric(
        cleaned_df["release_year"],
        errors="coerce",
    )

    cleaned_df["score"] = pd.to_numeric(
        cleaned_df["score"],
        errors="coerce",
    )


    cleaned_df = cleaned_df.dropna(
        subset=[
            "artist",
            "album",
            "release_year",
            "score",
        ]
    )

    cleaned_df["release_year"] = cleaned_df["release_year"].astype(int)
    cleaned_df["score"] = cleaned_df["score"].astype(int)

    cleaned_df = cleaned_df[
        (cleaned_df["score"] >= 0)
        & (cleaned_df["score"] <= 100)
    ]

    cleaned_df = cleaned_df.drop_duplicates(
        subset=["artist", "album", "release_year"],
        keep="first",
    )

    cleaned_df["dataset_source"] = "aoty_all_time"

    cleaned_df["release_decade"] = (
        cleaned_df["release_year"] // 10 * 10
    )


    cleaned_df = cleaned_df.drop(columns=["date_rated"])

    cleaned_df = cleaned_df.sort_values(
        by=["artist", "album", "release_year"],
        ascending=[True, True, True],
    )

    return cleaned_df


def save_cleaned_data(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def print_summary(df: pd.DataFrame) -> None:
    print("AOTY cleaning complete")
    print("----------------------")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print(f"Score range: {df['score'].min()}–{df['score'].max()}")
    print(f"Average score: {df['score'].mean():.2f}")
    print(f"Release years: {df['release_year'].min()}–{df['release_year'].max()}")
    print(f"Dataset source: {df['dataset_source'].iloc[0]}")
    print()
    print("Format counts:")
    print(df["format"].value_counts())
    print()
    print("Score range counts:")
    print(pd.cut(
        df["score"],
        bins=[0, 49, 59, 69, 79, 89, 100],
        labels=[
            "0-49",
            "50-59",
            "60-69",
            "70-79",
            "80-89",
            "90-100",
        ],
        include_lowest=True,
    ).value_counts().sort_index())


def main() -> None:
    raw_df = load_aoty_export(RAW_DATA_PATH)
    cleaned_df = clean_aoty_data(raw_df)
    save_cleaned_data(cleaned_df, PROCESSED_DATA_PATH)
    print_summary(cleaned_df)


if __name__ == "__main__":
    main()