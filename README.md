# Music Recommendation App

A personal music recommendation project that began as a machine learning album-score prediction pipeline and is now expanding into a Spotify-connected album discovery app. The project uses explicit album ratings, metadata enrichment, Spotify listening behavior, and rule-based recommendation logic to identify albums a user is likely to enjoy but may not have fully explored yet.


## Background

As a long-time avid music fanatic, I've always been eager to chase new experiences through different artists, genres, styles, and eras of music. Throughout 2025, I challenged myself to check out 365 albums that I had never heard before -- some of which were newer albums releasing on a rolling basis throughout the year, while the majority were either releases that I had missed from recent years or older records that I wanted to closely familiarize myself with. This experience inspired me to build a recommendation tool that would make finding new albums to experience much easier and more straightforward.

The goal of this project is to recommend albums to a user based on their personal taste. The project originally approached this through explicit album ratings and score prediction, using my own rated albums as the foundation for a personal taste model. After evaluating the limits of exact score prediction, I began expanding the project toward a more usable Spotify-based recommendation system where a user can connect their Spotify account and receive album recommendations from their listening behavior.

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
- Whether specific tuning changes actually significantly improve the model or not

This made the project more practical because it gave me a clearer way to inspect model behavior instead of relying only on summary metrics. Since predicted scores will eventually be used to rank recommendation candidates, understanding when the model is reliable is an important part of the recommendation pipeline.

### 5. Score Tier Threshold Experiment

After reviewing the model reports, I adjusted the score thresholds used to group albums into low, mid, and high rating tiers. The original thresholds did not fully reflect the way my ratings were distributed across the dataset.

Changing the thresholds made the reports more meaningful because the model could be evaluated against score ranges that better matched my actual listening data.

### 6. Sample Weighting Experiment

I also tested sample weighting to see whether the model could better learn from albums in less common score ranges. The idea was to give certain albums more influence during training, especially ratings that were farther away from the most common score range.

After comparing the new error reports, I reverted the model back to the original unweighted baseline. The weighted version changed the model's behavior, but it did not clearly improve the predictions enough to justify keeping it.

This experiment was still useful because it showed that model tuning should be evaluated carefully. A more complex training setup is not automatically better if the resulting predictions are less stable or less useful.

### 7. AOTY Dataset Expansion

After building the original model around the 2025 listening dataset, I expanded the project by exporting my all-time Album of the Year ratings (albumoftheyear.org, aoty.org). This gave the project a much larger dataset that better represents my long-term music taste across more albums, artists, eras, and rating ranges. I did this with the objective of using the specific, detailed, and precise data collection from my smaller, 365-column dataset, with my extensive all-time data of nearly 1200 albums for a sharper prediction algorithm.

The AOTY export included:

- Artist
- Album title
- Release year
- Format
- Personal score
- Date rated

I decided to neglect the date rated column as it has virtually zero impact on this experiment, removing it from the cleaned modeling dataset. I also kept the original artist field intact instead of adding complicated multi-artist parsing, since there were only a small number of multi-artist cases and overengineering that step could create unnecessary errors. I was originally considering splitting artist names at '&' or ',' but this would have resuted in names of singular artists such as "Tyler, The Creator" to become split, causing errors.

This created a larger AOTY-based ratings dataset that could be compared against the smaller but cleaner 2025 dataset.

### 8. Last.fm Metadata Enrichment

The AOTY export was useful because it provided many more ratings, but it lacked the album-level descriptive features that made the original 2025 dataset valuable. Since AOTY does not have an API, I used Last.fm as a source for certain album attributes.

The enrichment script uses the Last.fm API to add:

- Genre 1
- Genre 2
- Genre 3
- Number of tracks
- Runtime

The genre tags required additional filtering because Last.fm tags can include non-genre labels such as years, artist names, list tags, or other user-uploaded filler, such as "2006" or "mid". To address this, I added a controlled filtering system that removes obvious junk tags while allowing specific genre names such as "hip-hop" or "alternative pop". To catch other genres that may slip through the cracks, I also implemented a list of common prefix/suffixes that appear in more niche genre names -- "gaze", "core", or "wave" to catch a genre such as "Darkwave" that may be missing from the original list.

The enriched AOTY CSV is formatted to mimic the same column order as the original 2025 dataset:

- Artist
- Album
- Year
- Number of tracks
- Runtime
- Genre 1
- Genre 2
- Genre 3
- Score

Additional tracking columns are kept after those main modeling columns so the dataset remains readable while still preserving metadata about where the enriched values came from.

The most recent enrichment pass produced strong metadata coverage, with most albums receiving track count and runtime information and a majority of albums receiving usable genre tags.

### 9. Enriched AOTY Model Experiment

After creating the enriched AOTY dataset, I trained a new model using the expanded feature set. This model used artist, format, release year, release decade, genre tags, number of tracks, and runtime to predict album scores.

The enriched model beat the dummy baseline, but it did not outperform the earlier basic AOTY model. This suggests that the additional Last.fm-derived features may introduce noise, sparse categories, or inconsistent metadata that the current model does not yet handle well.

This result is still useful because it shows that adding more features is not automatically an improvement. The next step is to run feature ablation experiments to identify which parts of the enriched dataset help prediction and which parts may hurt it.

### 10. Discogs Genre/Style Enrichment

After the Last.fm enrichment experiment, I tested Discogs as an alternative metadata source for album genre and style information. The goal was to see whether Discogs could provide cleaner or more structured genre/style labels than Last.fm's user-generated tag system.

Instead of forcing Discogs metadata into the original three-column genre format, I moved toward a more flexible single-column genre representation. Discogs genre and style values are combined into a single `Genres` field, which better preserves the range of labels attached to each album without requiring a fixed number of genre slots.

This experiment helped move the project away from overly rigid manual genre columns and toward a more flexible metadata format that can support future recommendation logic.

### 11. Spotify Recommendation Component

After evaluating the rating-prediction approach, I began adding a new Spotify-connected recommendation component on a separate development branch. The purpose of this component is to make the project more usable for real users by allowing them to connect a Spotify account instead of manually uploading or maintaining a ratings CSV.

The Spotify component currently focuses on a rule-based album discovery pipeline rather than a full machine learning recommender. Spotify listening data is used to build an implicit taste profile, identify candidate albums from artists the user already likes, and estimate whether the user is unfamiliar, lightly familiar, partially familiar, or highly familiar with each candidate album.

The current Spotify pipeline includes:

- Spotify OAuth authentication
- Fetching top artists
- Fetching top tracks
- Fetching saved albums
- Fetching saved tracks
- Fetching recently played tracks
- Saving Spotify responses locally as JSON files
- Building an artist-affinity taste profile from Spotify behavior
- Fetching candidate albums from the user's strongest artists
- Estimating album familiarity from saved/top/recent listening signals
- Filtering out albums that appear highly familiar
- Printing candidate albums with familiarity scores for inspection
- Adding local caching and safer API-call controls to reduce the risk of Spotify rate limits

This marks an important shift in the project direction. The earlier AOTY model remains useful as a research and modeling experiment, while the Spotify component is becoming the foundation for a more practical album recommendation app.

## Current Status

The project is currently transitioning from a personal rating-prediction model into a Spotify-connected album discovery app.

Completed so far:

- Created the 2025 album listening dataset
- Cleaned and structured the original dataset
- Set up the Python project workflow
- Trained an initial CatBoost taste prediction model
- Added text-based model error reports
- Evaluated prediction behavior across score tiers
- Adjusted score tier thresholds
- Tested sample weighting
- Reverted back to the original unweighted baseline model
- Exported all-time AOTY ratings into a larger CSV dataset
- Built an AOTY cleaning script
- Removed non-album-level date-rated features from the AOTY data
- Used Last.fm to enrich the AOTY dataset with genre tags, runtime, and track count metadata
- Added filtering logic to reduce noisy Last.fm tags
- Reformatted the enriched AOTY CSV to match the original 2025 dataset's column order
- Trained a model on the enriched AOTY dataset
- Compared the enriched AOTY model against the dummy baseline and earlier AOTY model
- Tested Discogs API enrichment for genre/style metadata
- Shifted from fixed three-genre columns toward a flexible combined `Genres` representation
- Created a new Spotify recommender component inside the project
- Added Spotify OAuth authentication using Spotipy
- Fetched Spotify top artists, top tracks, saved albums, saved tracks, and recently played tracks
- Saved Spotify API responses locally for repeatable development
- Built an initial Spotify taste profile from listening behavior
- Built an initial candidate-album finder based on the user's strongest artists
- Added album familiarity scoring to distinguish unheard, lightly familiar, partially familiar, mostly familiar, and highly familiar albums
- Added caching and API-call safeguards after encountering Spotify rate limits

The current finding from the rating-model side is that enriched metadata does not automatically improve score prediction, especially when genre and metadata fields are noisy or sparse. The current finding from the Spotify side is that a practical recommender can start by identifying underexplored albums from artists the user already likes, then filtering/ranking those albums by estimated familiarity.

The next step for the Spotify component is to improve candidate quality by cleaning duplicates, deluxe editions, live albums, compilations, and remasters, then ranking albums by a combination of artist affinity and album familiarity.

## Current Tech Stack

- Python
- pandas
- scikit-learn
- CatBoost
- Spotipy
- Spotify Web API
- Last.fm API
- Discogs API

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
- [x] Export all-time AOTY ratings
- [x] Clean AOTY export into a modeling dataset
- [x] Enrich AOTY data with Last.fm genre tags
- [x] Enrich AOTY data with runtime and track count metadata
- [x] Train enriched AOTY model
- [x] Experiment with Discogs API genre/style enrichment
- [x] Compare Last.fm genre tags against Discogs genre/style data
- [x] Add Spotify OAuth authentication
- [x] Fetch Spotify top artists, top tracks, saved albums, saved tracks, and recently played tracks
- [x] Save Spotify listening data locally for development
- [x] Build an initial Spotify taste profile
- [x] Build an initial candidate-album finder from top artists
- [x] Add album familiarity scoring
- [x] Add caching and API-call safeguards for Spotify requests
- [ ] Clean Spotify candidate albums by removing duplicates, deluxe editions, live albums, compilations, and remasters
- [ ] Rank Spotify candidate albums by artist affinity and familiarity score
- [ ] Add recommendation explanations
- [ ] Run feature ablation tests on AOTY feature groups
- [ ] Perform deeper exploratory data analysis
- [ ] Engineer additional taste-profile features
- [ ] Compare multiple model types
- [ ] Improve prediction consistency across score ranges
- [ ] Add adjacent-artist discovery using playlist co-occurrence, external tags, or another similarity source
- [ ] Create an interactive prototype
- [ ] Expand into a full web application

## Future Improvements

Future improvements may include:

- Cleaning Spotify candidate albums by filtering duplicate releases, deluxe editions, live albums, compilations, and remasters
- Ranking Spotify recommendations using artist affinity, familiarity score, saved-track overlap, and discovery value
- Adding readable recommendation explanations for each album
- Exploring adjacent-artist discovery using playlist co-occurrence, Last.fm tags, Discogs genres/styles, or another similarity source
- Broadening the analysis of taste by implementing new attributes such as decade, genre combinations, and artist history
- Using existing score-trend analysis to engineer stronger taste-profile and recommendation features
- Comparing CatBoost against other regression models
- Continuing to refine the expanded AOTY dataset beyond the original 365 albums
- Running ablation tests to compare basic AOTY features, genre features, metadata features, and combined features
- Investigating whether Last.fm-derived genre tags, Discogs-derived genres/styles, and album metadata improve or hurt model performance
- Creating a web interface where users can connect Spotify and receive personalized album recommendations

## Purpose

This project combines my interest in music and analytics with practical machine learning, API integration, and software development. It has progressed from a personal listening spreadsheet into a working taste-modeling pipeline with documented experiments, evaluation reports, Spotify account integration, and a clear path toward a personalized album discovery application.
