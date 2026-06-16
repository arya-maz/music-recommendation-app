from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, train_test_split

from music_taste.features import score_to_three_category_label, score_to_tier


DATA_PATH = Path("data/processed/albums_2025_features.csv")
MODEL_OUTPUT_PATH = Path("models/catboost_score_model.cbm")
PREDICTIONS_OUTPUT_PATH = Path("data/processed/model_predictions.csv")

USE_SAMPLE_WEIGHTS = False

DISLIKE_WEIGHT = 2.0
LOW_NEUTRAL_WEIGHT = 1.25
MIDDLE_SCORE_WEIGHT = 1.0
LOVE_WEIGHT = 1.5


FEATURE_COLUMNS = [
    "ARTIST",
    "YEAR",
    "TRACKS",
    "RUNTIME_MIN",
    "AVG_TRACK_LENGTH",
    "GENRE_1",
    "GENRE_2",
    "GENRE_3",
    "ALBUM_AGE",
    "DECADE",
    "LONG_TRACKLIST",
    "FEW_TRACKS",
    "SHORT_ALBUM",
    "LONG_ALBUM",
    "SHORT_TRACK_DENSE",
    "MODERN_ALBUM",
]

CATEGORICAL_COLUMNS = [
    "ARTIST",
    "GENRE_1",
    "GENRE_2",
    "GENRE_3",
]

PREDICTION_OUTPUT_COLUMNS = [
    "ARTIST",
    "ALBUM",
    "YEAR",
    "TRACKS",
    "RUNTIME_MIN",
    "AVG_TRACK_LENGTH",
    "GENRE_1",
    "GENRE_2",
    "GENRE_3",
    "SCORE",
    "SCORE_TIER",
    "LIKE_LABEL",
]


def create_model() -> CatBoostRegressor:
    return CatBoostRegressor(
        iterations=500,
        learning_rate=0.03,
        depth=4,
        loss_function="RMSE",
        random_seed=42,
        verbose=False,
    )


def score_to_sample_weight(score: int | float) -> float:
    if score <= 39:
        return DISLIKE_WEIGHT
    elif score <= 59:
        return LOW_NEUTRAL_WEIGHT
    elif score >= 80:
        return LOVE_WEIGHT
    else:
        return MIDDLE_SCORE_WEIGHT


def evaluate_single_split(
    X: pd.DataFrame,
    y: pd.Series,
    sample_weights: pd.Series | None,
) -> None:
    if sample_weights is not None:
        X_train, X_test, y_train, y_test, weights_train, _ = train_test_split(
            X,
            y,
            sample_weights,
            test_size=0.2,
            random_state=42,
        )
        baseline_value = np.average(y_train, weights=weights_train)
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
        )
        weights_train = None
        baseline_value = y_train.mean()

    baseline_prediction = np.full(shape=len(y_test), fill_value=baseline_value)
    baseline_mae = mean_absolute_error(y_test, baseline_prediction)

    model = create_model()
    model.fit(
        X_train,
        y_train,
        cat_features=CATEGORICAL_COLUMNS,
        sample_weight=weights_train,
    )

    predictions = model.predict(X_test)

    model_mae = mean_absolute_error(y_test, predictions)
    model_r2 = r2_score(y_test, predictions)

    print("Single Train/Test Split")
    print("-" * 80)
    print(f"Training rows: {len(X_train)}")
    print(f"Testing rows: {len(X_test)}")
    print(f"Mean baseline MAE: {baseline_mae:.2f} points")
    print(f"CatBoost MAE: {model_mae:.2f} points")
    print(f"CatBoost R² Score: {model_r2:.3f}")


def build_fold_prediction_rows(
    df: pd.DataFrame,
    test_index: np.ndarray,
    predictions: np.ndarray,
    fold_number: int,
) -> pd.DataFrame:
    fold_results = df.iloc[test_index][PREDICTION_OUTPUT_COLUMNS].copy()

    fold_results["FOLD"] = fold_number
    fold_results["PREDICTED_SCORE"] = np.round(predictions, 2)
    fold_results["PREDICTED_SCORE_TIER"] = fold_results[
        "PREDICTED_SCORE"
    ].apply(score_to_tier)
    fold_results["PREDICTED_LIKE_LABEL"] = fold_results["PREDICTED_SCORE"].apply(
        score_to_three_category_label
    )
    fold_results["ERROR"] = np.round(
        fold_results["PREDICTED_SCORE"] - fold_results["SCORE"], 2
    )
    fold_results["ABS_ERROR"] = fold_results["ERROR"].abs()

    return fold_results


def evaluate_cross_validation(
    df: pd.DataFrame,
    X: pd.DataFrame,
    y: pd.Series,
    sample_weights: pd.Series | None,
) -> pd.DataFrame:
    kf = KFold(n_splits=5, shuffle=True, random_state=42)

    baseline_mae_scores = []
    model_mae_scores = []
    model_r2_scores = []
    prediction_rows = []

    for fold_number, (train_index, test_index) in enumerate(kf.split(X), start=1):
        X_train = X.iloc[train_index]
        X_test = X.iloc[test_index]
        y_train = y.iloc[train_index]
        y_test = y.iloc[test_index]

        if sample_weights is not None:
            weights_train = sample_weights.iloc[train_index]
            baseline_value = np.average(y_train, weights=weights_train)
        else:
            weights_train = None
            baseline_value = y_train.mean()

        baseline_prediction = np.full(shape=len(y_test), fill_value=baseline_value)
        baseline_mae = mean_absolute_error(y_test, baseline_prediction)
        baseline_mae_scores.append(baseline_mae)

        model = create_model()
        model.fit(
            X_train,
            y_train,
            cat_features=CATEGORICAL_COLUMNS,
            sample_weight=weights_train,
        )

        predictions = model.predict(X_test)

        model_mae = mean_absolute_error(y_test, predictions)
        model_r2 = r2_score(y_test, predictions)

        model_mae_scores.append(model_mae)
        model_r2_scores.append(model_r2)

        fold_results = build_fold_prediction_rows(
            df=df,
            test_index=test_index,
            predictions=predictions,
            fold_number=fold_number,
        )
        prediction_rows.append(fold_results)

        print(
            f"Fold {fold_number}: "
            f"Baseline MAE = {baseline_mae:.2f}, "
            f"CatBoost MAE = {model_mae:.2f}, "
            f"R² = {model_r2:.3f}"
        )

    print("\n5-Fold Cross-Validation Summary")
    print("-" * 80)
    print(
        f"Mean baseline MAE: "
        f"{np.mean(baseline_mae_scores):.2f} "
        f"± {np.std(baseline_mae_scores):.2f} points"
    )
    print(
        f"CatBoost MAE: "
        f"{np.mean(model_mae_scores):.2f} "
        f"± {np.std(model_mae_scores):.2f} points"
    )
    print(
        f"CatBoost R² Score: "
        f"{np.mean(model_r2_scores):.3f} "
        f"± {np.std(model_r2_scores):.3f}"
    )

    return pd.concat(prediction_rows, ignore_index=True)


def save_model_predictions(predictions_df: pd.DataFrame) -> None:
    predictions_df = predictions_df.sort_values("ABS_ERROR", ascending=False)
    PREDICTIONS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    predictions_df.to_csv(PREDICTIONS_OUTPUT_PATH, index=False)

    print("\nModel Predictions")
    print("-" * 80)
    print(f"Saved out-of-fold predictions to: {PREDICTIONS_OUTPUT_PATH}")
    print("\nLargest prediction misses:")
    print(
        predictions_df[
            [
                "ARTIST",
                "ALBUM",
                "SCORE",
                "PREDICTED_SCORE",
                "ERROR",
                "ABS_ERROR",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )


def train_final_model(
    X: pd.DataFrame,
    y: pd.Series,
    sample_weights: pd.Series | None,
) -> None:
    model = create_model()
    model.fit(
        X,
        y,
        cat_features=CATEGORICAL_COLUMNS,
        sample_weight=sample_weights,
    )

    MODEL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(MODEL_OUTPUT_PATH)

    print("\nFinal Model")
    print("-" * 80)
    print(f"Trained final model on all {len(X)} rows.")
    print(f"Saved model to: {MODEL_OUTPUT_PATH}")


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Could not find processed data at {DATA_PATH}. "
            "Run build_features.py first."
        )

    df = pd.read_csv(DATA_PATH)

    X = df[FEATURE_COLUMNS]
    y = df["SCORE"]

    if USE_SAMPLE_WEIGHTS:
        sample_weights = y.apply(score_to_sample_weight)
    else:
        sample_weights = None

    print("Model Evaluation")
    print("=" * 80)
    print(f"Total rows: {len(df)}")
    print(f"Input features: {len(FEATURE_COLUMNS)}")
    print(f"Sample weighting enabled: {USE_SAMPLE_WEIGHTS}")

    if sample_weights is not None:
        print("Sample weight distribution:")
        print(sample_weights.value_counts().sort_index())

    print()

    evaluate_single_split(X, y, sample_weights)

    print("\n5-Fold Cross-Validation")
    print("-" * 80)
    predictions_df = evaluate_cross_validation(df, X, y, sample_weights)
    save_model_predictions(predictions_df)

    train_final_model(X, y, sample_weights)


if __name__ == "__main__":
    main()