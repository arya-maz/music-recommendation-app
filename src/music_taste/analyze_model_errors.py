from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd


PREDICTIONS_PATH = Path("data/processed/model_predictions.csv")
REPORT_OUTPUT_PATH = Path("model_error_report.txt")

SCORE_TIER_ORDER = [
    "love",
    "like",
    "moderately_like",
    "neutral",
    "dislike",
]

LIKE_LABEL_ORDER = [
    "like",
    "neutral",
    "dislike",
]



def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def summarize_overall_error(df: pd.DataFrame) -> None:
    print_section("Overall Error Summary")

    print(f"Rows analyzed: {len(df)}")
    print(f"Mean actual score: {df['SCORE'].mean():.2f}")
    print(f"Mean predicted score: {df['PREDICTED_SCORE'].mean():.2f}")
    print(f"Mean error: {df['ERROR'].mean():.2f}")
    print(f"Mean absolute error: {df['ABS_ERROR'].mean():.2f}")
    print(f"Median absolute error: {df['ABS_ERROR'].median():.2f}")
    print(f"Max absolute error: {df['ABS_ERROR'].max():.2f}")


def summarize_error_by_score_tier(df: pd.DataFrame) -> None:
    print_section("Error by Score Tier")

    summary = (
        df.groupby("SCORE_TIER")
        .agg(
            count=("SCORE", "count"),
            avg_actual_score=("SCORE", "mean"),
            avg_predicted_score=("PREDICTED_SCORE", "mean"),
            avg_error=("ERROR", "mean"),
            avg_abs_error=("ABS_ERROR", "mean"),
            median_abs_error=("ABS_ERROR", "median"),
        )
        .reindex(SCORE_TIER_ORDER)
        .round(2)
    )

    print(summary)


def summarize_error_by_like_label(df: pd.DataFrame) -> None:
    print_section("Error by Three-Label Category")

    summary = (
        df.groupby("LIKE_LABEL")
        .agg(
            count=("SCORE", "count"),
            avg_actual_score=("SCORE", "mean"),
            avg_predicted_score=("PREDICTED_SCORE", "mean"),
            avg_error=("ERROR", "mean"),
            avg_abs_error=("ABS_ERROR", "mean"),
            median_abs_error=("ABS_ERROR", "median"),
        )
        .reindex(LIKE_LABEL_ORDER)
        .round(2)
    )

    print(summary)


def summarize_prediction_compression(df: pd.DataFrame) -> None:
    print_section("Prediction Range Compression")

    print("Actual score range:")
    print(df["SCORE"].describe().round(2))

    print("\nPredicted score range:")
    print(df["PREDICTED_SCORE"].describe().round(2))

    print(
        "\nIf the predicted score range is much narrower than the actual score "
        "range, the model is probably compressing predictions toward the middle."
    )


def summarize_biggest_misses(df: pd.DataFrame) -> None:
    print_section("Largest Absolute Errors")

    columns = [
        "ARTIST",
        "ALBUM",
        "SCORE",
        "PREDICTED_SCORE",
        "ERROR",
        "ABS_ERROR",
        "SCORE_TIER",
        "PREDICTED_SCORE_TIER",
        "GENRE_1",
        "GENRE_2",
        "GENRE_3",
    ]

    print(df.sort_values("ABS_ERROR", ascending=False)[columns].head(20).to_string(index=False))


def summarize_overpredictions(df: pd.DataFrame) -> None:
    print_section("Most Overpredicted Albums")

    columns = [
        "ARTIST",
        "ALBUM",
        "SCORE",
        "PREDICTED_SCORE",
        "ERROR",
        "ABS_ERROR",
        "SCORE_TIER",
        "PREDICTED_SCORE_TIER",
        "GENRE_1",
        "GENRE_2",
        "GENRE_3",
    ]

    overpredicted = df[df["ERROR"] > 0].sort_values("ERROR", ascending=False)

    print(overpredicted[columns].head(20).to_string(index=False))


def summarize_underpredictions(df: pd.DataFrame) -> None:
    print_section("Most Underpredicted Albums")

    columns = [
        "ARTIST",
        "ALBUM",
        "SCORE",
        "PREDICTED_SCORE",
        "ERROR",
        "ABS_ERROR",
        "SCORE_TIER",
        "PREDICTED_SCORE_TIER",
        "GENRE_1",
        "GENRE_2",
        "GENRE_3",
    ]

    underpredicted = df[df["ERROR"] < 0].sort_values("ERROR")

    print(underpredicted[columns].head(20).to_string(index=False))


def summarize_error_by_primary_genre(df: pd.DataFrame) -> None:
    print_section("Error by Primary Genre")

    summary = (
        df.groupby("GENRE_1")
        .agg(
            count=("SCORE", "count"),
            avg_actual_score=("SCORE", "mean"),
            avg_predicted_score=("PREDICTED_SCORE", "mean"),
            avg_error=("ERROR", "mean"),
            avg_abs_error=("ABS_ERROR", "mean"),
        )
        .query("count >= 3")
        .sort_values("avg_abs_error", ascending=False)
        .round(2)
    )

    print(summary.head(25))


def summarize_error_by_all_genres(df: pd.DataFrame) -> None:
    print_section("Error by All Genre Tags")

    genre_df = df.melt(
        id_vars=["SCORE", "PREDICTED_SCORE", "ERROR", "ABS_ERROR"],
        value_vars=["GENRE_1", "GENRE_2", "GENRE_3"],
        var_name="GENRE_POSITION",
        value_name="GENRE",
    )

    summary = (
        genre_df.groupby("GENRE")
        .agg(
            count=("SCORE", "count"),
            avg_actual_score=("SCORE", "mean"),
            avg_predicted_score=("PREDICTED_SCORE", "mean"),
            avg_error=("ERROR", "mean"),
            avg_abs_error=("ABS_ERROR", "mean"),
        )
        .query("count >= 5")
        .sort_values("avg_abs_error", ascending=False)
        .round(2)
    )

    print(summary.head(30))


def summarize_tier_confusion(df: pd.DataFrame) -> None:
    print_section("Actual vs Predicted Score Tier")
    print("Rows = actual score tier")
    print("Columns = predicted score tier")

    confusion = pd.crosstab(
        df["SCORE_TIER"],
        df["PREDICTED_SCORE_TIER"],
    )

    confusion = confusion.reindex(
        index=SCORE_TIER_ORDER,
        columns=SCORE_TIER_ORDER,
        fill_value=0,
    )

    print(confusion)


def summarize_like_label_confusion(df: pd.DataFrame) -> None:
    print_section("Actual vs Predicted Three-Label Category")
    print("Rows = actual three-label category")
    print("Columns = predicted three-label category")

    confusion = pd.crosstab(
        df["LIKE_LABEL"],
        df["PREDICTED_LIKE_LABEL"],
    )

    confusion = confusion.reindex(
        index=LIKE_LABEL_ORDER,
        columns=LIKE_LABEL_ORDER,
        fill_value=0,
    )

    print(confusion)


def summarize_low_score_problem(df: pd.DataFrame) -> None:
    print_section("Low-Score Album Analysis")

    low_score_df = df[df["SCORE"] <= 39]

    if low_score_df.empty:
        print("No albums with SCORE <= 39 found.")
        return

    print(f"Low-score albums: {len(low_score_df)}")
    print(f"Average actual score: {low_score_df['SCORE'].mean():.2f}")
    print(f"Average predicted score: {low_score_df['PREDICTED_SCORE'].mean():.2f}")
    print(f"Average error: {low_score_df['ERROR'].mean():.2f}")
    print(f"Average absolute error: {low_score_df['ABS_ERROR'].mean():.2f}")

    print("\nLow-score albums sorted by largest overprediction:")
    print(
        low_score_df.sort_values("ERROR", ascending=False)[
            [
                "ARTIST",
                "ALBUM",
                "SCORE",
                "PREDICTED_SCORE",
                "ERROR",
                "ABS_ERROR",
                "GENRE_1",
                "GENRE_2",
                "GENRE_3",
            ]
        ]
        .head(25)
        .to_string(index=False)
    )


def run_error_report(df: pd.DataFrame) -> None:
    summarize_overall_error(df)
    summarize_error_by_score_tier(df)
    summarize_error_by_like_label(df)
    summarize_prediction_compression(df)
    summarize_biggest_misses(df)
    summarize_overpredictions(df)
    summarize_underpredictions(df)
    summarize_error_by_primary_genre(df)
    summarize_error_by_all_genres(df)
    summarize_tier_confusion(df)
    summarize_like_label_confusion(df)
    summarize_low_score_problem(df)


def main() -> None:
    if not PREDICTIONS_PATH.exists():
        raise FileNotFoundError(
            f"Could not find predictions file at {PREDICTIONS_PATH}. "
            "Run train_model.py first."
        )

    df = pd.read_csv(PREDICTIONS_PATH)


    report_buffer = StringIO()

    with redirect_stdout(report_buffer):
        run_error_report(df)

    report_text = report_buffer.getvalue()
    save_message = (
        "\n"
        + "=" * 80
        + f"\nSaved model error report to: {REPORT_OUTPUT_PATH}\n"
        + "=" * 80
        + "\n"
    )

    REPORT_OUTPUT_PATH.write_text(report_text + save_message, encoding="utf-8")

    print(report_text, end="")
    print(save_message, end="")


if __name__ == "__main__":
    main()