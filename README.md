# Music Taste Predictor

A personal machine learning project that analyzes my 2025 album listening dataset and predicts how much I may enjoy new albums based on attributes such as artist, release year, track count, runtime, genre tags, and score.

## Background

As a long-time avid music fanatic, I've always been eagerly chasing new experiences in the form of exploring new artists, genres, styles, etc. Throughout 2025, I challenged myself to check out 365 albums that I had never heard before -- some of which were newer albums releasing on a rolling basis throughout the year, while the majority were either releases that I had missed from recent years, or relics of older eras that I wanted to closely familiarize myself with.

## Project Progress

### 1. Dataset Creation

The project started with a CSV file containing albums I listened to for the first time throughout 2025. Each entry included basic album information and my personal score.

The dataset includes:

- Artist
- Album title
- Release year
- Number of tracks
- Runtime in minutes
- Average track length
- Three genre tags
- Personal score out of 100

This step turned a casual listening challenge into a usable dataset for analysis and modeling.

### 2. Data Cleaning and Project Setup

After creating the dataset, I cleaned the album data and organized the Python project structure. This created a foundation for loading the dataset, preparing features, training models, and generating repeatable outputs.

At this stage, the project moved from a spreadsheet-based idea into an actual machine learning workflow.

### 3. Baseline Model Training

Once the data was prepared, I trained an initial machine learning model to predict album scores. The current baseline model uses CatBoost because it works well with categorical features such as artist names and genre tags.

The model predicts a numeric score out of 100 for each album. Since the dataset represents my personal taste, the model is designed to learn patterns in my own ratings rather than make general claims about music quality.

### 4. Model Error Reporting

After training the baseline model, I added a text-based error reporting system. Instead of only looking at a single score such as mean absolute error, the report shows where the model performs well and where it struggles.

The error report helps identify:

- Albums with the most accurate predictions
- Albums with the largest prediction errors
- Cases where the model overpredicts or underpredicts scores
- Differences in performance across low, mid, and high score ranges
- Whether future tuning changes actually improve the model

This made the project more practical, as it gave me a clearer way to inspect model behavior instead of relying only on summary metrics.

### 5. Score Tier Threshold Experiment

After reviewing the model reports, I adjusted the score thresholds used to group albums into low, mid, and high rating tiers. The original thresholds did not fully reflect the way my ratings were distributed across the dataset.

Changing the thresholds made the reports more meaningful because the model could be evaluated against score ranges that better matched my actual listening data.

### 6. Sample Weighting Experiment

I also tested sample weighting to see whether the model could better learn from albums in less common score ranges. The idea was to give certain albums more influence during training, especially ratings that were farther away from the most common score range.

After comparing the new error reports, I reverted the model back to the original unweighted baseline. The weighted version changed the model's behavior, but it did not clearly improve the predictions enough to justify keeping it.

This experiment was still useful because it showed that model tuning should be evaluated carefully. A more complex training setup is not automatically better if the resulting predictions are less stable or less useful.

## Current Status

The project is currently in the model evaluation and experimentation stage.

Completed so far:

- Created the 2025 album listening dataset
- Cleaned and structured the dataset
- Set up the Python project workflow
- Trained an initial CatBoost regression model
- Added text-based model error reports
- Evaluated prediction behavior across score tiers
- Adjusted score tier thresholds
- Tested sample weighting
- Reverted back to the original unweighted baseline model

The current model is being treated as a stable baseline before adding more features, comparing other models, or building a recommendation system.

## Tech Stack

- Python
- pandas
- scikit-learn
- CatBoost
- FastAPI
- PostgreSQL
- React

## Roadmap

- [x] Create album listening dataset
- [x] Clean dataset
- [x] Set up Python project structure
- [x] Train baseline prediction model
- [x] Generate model error report files
- [x] Analyze prediction errors by score range
- [x] Adjust score tier thresholds
- [x] Experiment with sample weighting
- [x] Revert to stable unweighted baseline
- [ ] Perform deeper exploratory data analysis
- [ ] Engineer additional features
- [ ] Compare multiple model types
- [ ] Improve prediction consistency across score ranges
- [ ] Build a script for predicting scores of new albums
- [ ] Build a recommendation system for unlistened albums
- [ ] Create an interactive prototype
- [ ] Expand into a full web application

## Future Improvements

Future improvements may include:

- Adding decade-based and genre-combination features
- Visualizing score trends by genre, release year, runtime, and track count
- Comparing CatBoost against other regression models
- Testing more advanced recommendation logic
- Creating a web interface for entering album information and receiving a predicted score
- Expanding the dataset beyond the original 365 albums

## Purpose

This project combines my interest in music with practical machine learning and software development. It has progressed from a personal listening spreadsheet into a working prediction pipeline with documented experiments, evaluation reports, and a clear path toward a recommendation system.
