# Music Recommendation App

A personal machine learning music recommendation project that builds a user taste profile from album ratings and uses predicted scores to vet and rank candidate albums before recommending them.


## Background

As a long-time avid music fanatic, I've always been eager to chase new experiences through different artists, genres, styles, and eras of music. Throughout 2025, I challenged myself to check out 365 albums that I had never heard before -- some of which were newer albums releasing on a rolling basis throughout the year, while the majority were either releases that I had missed from recent years or older records that I wanted to closely familiarize myself with.

The goal of this project is to recommend albums to a user based on their personal taste. At this stage, I am building the taste-modeling foundation for that larger recommendation system. Score prediction is being used as a practical way to estimate how much a user may enjoy an album, which can later help determine which candidate albums should be recommended, filtered out, or ranked higher.

## Project Progress

### 1. Dataset Creation

The project started with a CSV file containing albums I listened to for the first time throughout 2025. Each entry included basic album information as well as my personal score.

The dataset includes:

- Artist
- Album title
- Release year
- Number of tracks
- Runtime in minutes
- Three genre tags
- Personal score out of 100

This step turned a casual listening challenge into a usable dataset for taste analysis, score prediction, and future album recommendation.

### 2. Data Cleaning and Project Setup

After creating the dataset, I cleaned the album data and organized the Python project structure. This created a foundation for loading the dataset, preparing features, training models, and generating repeatable outputs.

At this stage, the project moved from a spreadsheet-based idea into an actual machine learning workflow.

### 3. Baseline Taste Model Training

Once the data was prepared, I trained an initial machine learning model to predict album scores. The current baseline model uses CatBoost because it works well with categorical features such as artist names and genre tags.

The model predicts a numeric score out of 100 for each album. Since the dataset represents my personal taste, the model is designed to learn patterns in my own ratings rather than make general claims about music quality. These predicted scores are not the final product by themselves; they are intended to act as a recommendation signal that can help vet and rank albums the user has not listened to yet.

### 4. Model Error Reporting

After training the baseline model, I added a text-based error reporting system. Instead of only looking at a single score such as mean absolute error, the report shows where the model performs well and where it struggles.

The error report helps identify:

- Albums with the most accurate predictions
- Albums with the largest prediction errors
- Cases where the model overpredicts or underpredicts scores
- Differences in performance across low, mid, and high score ranges
- Whether future tuning changes actually improve the model

This made the project more practical because it gave me a clearer way to inspect model behavior instead of relying only on summary metrics. Since predicted scores will eventually be used to rank recommendation candidates, understanding when the model is reliable is an important part of the recommendation pipeline.

### 5. Score Tier Threshold Experiment

After reviewing the model reports, I adjusted the score thresholds used to group albums into low, mid, and high rating tiers. The original thresholds did not fully reflect the way my ratings were distributed across the dataset.

Changing the thresholds made the reports more meaningful because the model could be evaluated against score ranges that better matched my actual listening data.

### 6. Sample Weighting Experiment

I also tested sample weighting to see whether the model could better learn from albums in less common score ranges. The idea was to give certain albums more influence during training, especially ratings that were farther away from the most common score range.

After comparing the new error reports, I reverted the model back to the original unweighted baseline. The weighted version changed the model's behavior, but it did not clearly improve the predictions enough to justify keeping it.

This experiment was still useful because it showed that model tuning should be evaluated carefully. A more complex training setup is not automatically better if the resulting predictions are less stable or less useful.

## Current Status

The project is currently in the taste-model evaluation and recommendation-planning stage.

Completed so far:

- Created the 2025 album listening dataset
- Cleaned and structured the dataset
- Set up the Python project workflow
- Trained an initial CatBoost taste prediction model
- Added text-based model error reports
- Evaluated prediction behavior across score tiers
- Adjusted score tier thresholds
- Tested sample weighting
- Reverted back to the original unweighted baseline model

The current model is being treated as a stable baseline before adding more features, comparing other models, and building the recommendation layer that will use predicted scores to rank unseen albums.

## Current Tech Stack

- Python
- pandas
- scikit-learn
- CatBoost

## Planned App Stack

- FastAPI
- PostgreSQL
- React

## Roadmap

- [x] Create album listening dataset
- [x] Clean dataset
- [x] Set up Python project structure
- [x] Train baseline taste prediction model
- [x] Generate model error report files
- [x] Analyze prediction errors by score range
- [x] Adjust score tier thresholds
- [x] Experiment with sample weighting
- [x] Revert to stable unweighted baseline
- [ ] Perform deeper exploratory data analysis
- [ ] Engineer additional taste-profile features
- [ ] Compare multiple model types
- [ ] Improve prediction consistency across score ranges
- [ ] Build a candidate album dataset
- [ ] Build a script for ranking unseen albums as recommendation candidates
- [ ] Build a recommendation system for unlistened albums
- [ ] Create an interactive prototype
- [ ] Expand into a full web application

## Future Improvements

Future improvements may include:

- Adding more thorough analysis of taste (decade, genre combinations, etc.)
- Visualizing score trends by genre, release year, runtime, and track count
- Comparing CatBoost against other regression models
- Testing more advanced recommendation logic
- Creating a web interface where users can upload data and receive personalized album recommendations
- Expanding the dataset beyond the original 365 albums

## Purpose

This project combines my interest in music and analytics with practical machine learning and software development. It has progressed from a personal listening spreadsheet into a working taste-modeling pipeline with documented experiments, evaluation reports, and a clear path toward a personalized album recommendation system.
