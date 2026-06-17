from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "aoty_enriched.csv"
REPORT_PATH = PROJECT_ROOT / "aoty_enriched_model_error_report.txt"
RANDOM_STATE = 42
TEST_SIZE = 0.2


CATEGORICAL_FEATURES = [
    "Artist",
    "format",
    "Genre 1",
    "Genre 2",
    "Genre 3",
]

NUMERIC_FEATURES = [
    "Year",
    "release_decade",
    "Number of tracks",
    "Runtime",
]

FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

IDENTIFIER_COLUMNS = [
    "Artist",
    "Album",
    "Year",
    "Number of tracks",
    "Runtime",
    "Genre 1",
    "Genre 2",
    "Genre 3",
    "format",
]

TARGET_COLUMN = "Score"


ERROR_TIERS = {
    "close": 5,
    "moderate": 10,
}


def make_one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def calculate_rmse(y_true: pd.Series, y_pred: pd.Series) -> float:
    mse = mean_squared_error(y_true, y_pred)
    return mse ** 0.5


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find enriched AOTY data at: {path}\n"
            "Run src/enrich_aoty_tags.py first."
        )

    return pd.read_csv(path)


def validate_data(df: pd.DataFrame) -> None:
    required_columns = set(IDENTIFIER_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN])
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    if df.empty:
        raise ValueError("The enriched AOTY dataset is empty.")


def fill_missing_numeric_column(df: pd.DataFrame, column: str) -> None:
    df[column] = pd.to_numeric(df[column], errors="coerce")

    median_value = df[column].median()

    if pd.isna(median_value):
        median_value = 0

    df[column] = df[column].fillna(median_value)


def prepare_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    model_df = df.copy()

    model_df = model_df.dropna(subset=[TARGET_COLUMN])

    for column in CATEGORICAL_FEATURES:
        model_df[column] = model_df[column].fillna("unknown").astype(str)

    for column in NUMERIC_FEATURES:
        fill_missing_numeric_column(model_df, column)

    model_df[TARGET_COLUMN] = pd.to_numeric(
        model_df[TARGET_COLUMN],
        errors="coerce",
    )

    model_df = model_df.dropna(subset=[TARGET_COLUMN])

    x = model_df[FEATURE_COLUMNS]
    y = model_df[TARGET_COLUMN]
    identifiers = model_df[IDENTIFIER_COLUMNS].copy()

    for column in ["Genre 1", "Genre 2", "Genre 3"]:
        identifiers[column] = identifiers[column].fillna("unknown").astype(str)

    identifiers["Number of tracks"] = model_df["Number of tracks"]
    identifiers["Runtime"] = model_df["Runtime"]

    return x, y, identifiers


def build_model() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                make_one_hot_encoder(),
                CATEGORICAL_FEATURES,
            ),
            (
                "numeric",
                StandardScaler(),
                NUMERIC_FEATURES,
            ),
        ]
    )

    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", Ridge(alpha=1.0)),
        ]
    )

    return model


def calculate_metrics(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": calculate_rmse(y_true, y_pred),
        "r2": r2_score(y_true, y_pred),
    }


def classify_error(error: float) -> str:
    absolute_error = abs(error)

    if absolute_error <= ERROR_TIERS["close"]:
        return "close"

    if absolute_error <= ERROR_TIERS["moderate"]:
        return "moderate"

    return "large_miss"


def build_results_df(
    identifiers_test: pd.DataFrame,
    y_test: pd.Series,
    predictions: pd.Series,
) -> pd.DataFrame:
    results_df = identifiers_test.copy()
    results_df["actual_score"] = y_test.values
    results_df["predicted_score"] = predictions.values
    results_df["error"] = results_df["predicted_score"] - results_df["actual_score"]
    results_df["absolute_error"] = results_df["error"].abs()
    results_df["error_tier"] = results_df["error"].apply(classify_error)

    return results_df.sort_values(by="absolute_error", ascending=False)


def score_range_summary(results_df: pd.DataFrame) -> pd.DataFrame:
    summary_df = results_df.copy()

    summary_df["score_range"] = pd.cut(
        summary_df["actual_score"],
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
    )

    return (
        summary_df.groupby("score_range", observed=False)
        .agg(
            count=("actual_score", "count"),
            average_actual_score=("actual_score", "mean"),
            average_predicted_score=("predicted_score", "mean"),
            average_absolute_error=("absolute_error", "mean"),
        )
        .reset_index()
    )


def format_summary(results_df: pd.DataFrame) -> pd.DataFrame:
    return (
        results_df.groupby("format")
        .agg(
            count=("actual_score", "count"),
            average_actual_score=("actual_score", "mean"),
            average_predicted_score=("predicted_score", "mean"),
            average_absolute_error=("absolute_error", "mean"),
        )
        .sort_values(by="count", ascending=False)
        .reset_index()
    )


def genre_summary(results_df: pd.DataFrame) -> pd.DataFrame:
    return (
        results_df.groupby("Genre 1")
        .agg(
            count=("actual_score", "count"),
            average_actual_score=("actual_score", "mean"),
            average_predicted_score=("predicted_score", "mean"),
            average_absolute_error=("absolute_error", "mean"),
        )
        .sort_values(by=["count", "average_absolute_error"], ascending=[False, True])
        .reset_index()
        .head(25)
    )


def year_summary(results_df: pd.DataFrame) -> pd.DataFrame:
    return (
        results_df.groupby("Year")
        .agg(
            count=("actual_score", "count"),
            average_actual_score=("actual_score", "mean"),
            average_predicted_score=("predicted_score", "mean"),
            average_absolute_error=("absolute_error", "mean"),
        )
        .sort_values(by="Year")
        .reset_index()
    )


def write_report(
    model_metrics: dict[str, float],
    dummy_metrics: dict[str, float],
    results_df: pd.DataFrame,
) -> None:
    close_count = (results_df["error_tier"] == "close").sum()
    moderate_count = (results_df["error_tier"] == "moderate").sum()
    large_miss_count = (results_df["error_tier"] == "large_miss").sum()

    with REPORT_PATH.open("w", encoding="utf-8") as report:
        report.write("AOTY ENRICHED MODEL ERROR REPORT\n")
        report.write("================================\n\n")

        report.write("Dataset\n")
        report.write("-------\n")
        report.write(f"Test rows: {len(results_df)}\n")
        report.write(f"Features used: {', '.join(FEATURE_COLUMNS)}\n")
        report.write(f"Target: {TARGET_COLUMN}\n\n")

        report.write("Model Performance\n")
        report.write("-----------------\n")
        report.write(f"Model MAE: {model_metrics['mae']:.2f}\n")
        report.write(f"Model RMSE: {model_metrics['rmse']:.2f}\n")
        report.write(f"Model R2: {model_metrics['r2']:.3f}\n\n")

        report.write("Dummy Baseline Performance\n")
        report.write("--------------------------\n")
        report.write(f"Dummy MAE: {dummy_metrics['mae']:.2f}\n")
        report.write(f"Dummy RMSE: {dummy_metrics['rmse']:.2f}\n")
        report.write(f"Dummy R2: {dummy_metrics['r2']:.3f}\n\n")

        report.write("Error Tier Counts\n")
        report.write("-----------------\n")
        report.write(f"Close predictions: {close_count}\n")
        report.write(f"Moderate predictions: {moderate_count}\n")
        report.write(f"Large misses: {large_miss_count}\n\n")

        report.write("Score Range Summary\n")
        report.write("-------------------\n")
        report.write(score_range_summary(results_df).to_string(index=False))
        report.write("\n\n")

        report.write("Format Summary\n")
        report.write("--------------\n")
        report.write(format_summary(results_df).to_string(index=False))
        report.write("\n\n")

        report.write("Primary Genre Summary\n")
        report.write("---------------------\n")
        report.write(genre_summary(results_df).to_string(index=False))
        report.write("\n\n")

        report.write("Year Summary\n")
        report.write("------------\n")
        report.write(year_summary(results_df).to_string(index=False))
        report.write("\n\n")

        report.write("Worst 25 Misses\n")
        report.write("---------------\n")
        report.write(
            results_df.head(25)[
                [
                    "Artist",
                    "Album",
                    "Year",
                    "Number of tracks",
                    "Runtime",
                    "Genre 1",
                    "Genre 2",
                    "Genre 3",
                    "actual_score",
                    "predicted_score",
                    "error",
                    "absolute_error",
                    "error_tier",
                ]
            ].to_string(index=False)
        )
        report.write("\n")


def main() -> None:
    df = load_data(DATA_PATH)
    validate_data(df)

    x, y, identifiers = prepare_data(df)

    x_train, x_test, y_train, y_test, _identifiers_train, identifiers_test = train_test_split(
        x,
        y,
        identifiers,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    model = build_model()
    model.fit(x_train, y_train)

    predictions = pd.Series(model.predict(x_test), index=y_test.index)
    model_metrics = calculate_metrics(y_test, predictions)

    dummy_model = DummyRegressor(strategy="mean")
    dummy_model.fit(x_train, y_train)
    dummy_predictions = pd.Series(dummy_model.predict(x_test), index=y_test.index)
    dummy_metrics = calculate_metrics(y_test, dummy_predictions)

    results_df = build_results_df(identifiers_test, y_test, predictions)

    write_report(model_metrics, dummy_metrics, results_df)

    print("AOTY enriched model training complete")
    print("------------------------------------")
    print(f"Model MAE: {model_metrics['mae']:.2f}")
    print(f"Dummy MAE: {dummy_metrics['mae']:.2f}")
    print(f"Report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()