# Music Recommendation App — Project Context

## Purpose of this document

This document preserves major project history, architectural decisions, experiments, current behavior, and planned work.

It is intended to help contributors and coding agents understand why the repository is structured as it is. It supplements `AGENTS.md`, which contains operational and safety instructions.

Implementation remains the source of truth. When this document conflicts with the code, inspect the implementation and report the discrepancy before changing either one.

---

## Project overview

This repository began as a personal machine-learning experiment based on album ratings and later expanded into a Spotify-connected album-discovery application.

The repository currently contains three related but distinct pipelines:

1. An original 365-album personal taste-prediction experiment.
2. A larger Album of the Year ratings and metadata-enrichment pipeline.
3. A Spotify-based unfamiliar-album discovery pipeline.

The long-term product direction is an application that recommends albums a user is likely to enjoy but has not meaningfully explored.

---

## Phase 1: Original 365-album dataset

The project began with a dataset of 365 albums listened to during a one-year album-listening challenge.

The original dataset includes album-level information such as:

* artist;
* album;
* release year;
* number of tracks;
* runtime;
* three genre fields;
* personal score.

The dataset was manually curated and relatively consistent, making it useful for prototyping feature engineering and model evaluation.

### Original modeling approach

The original model pipeline uses CatBoost and evaluates whether album metadata can predict the user's personal album score.

Early results showed that the dataset was sufficient for a prototype but too small and centrally distributed for highly reliable predictions.

Representative results included:

* baseline MAE around 7.7;
* CatBoost MAE around 7.9 on one split;
* negative R² on the held-out split;
* cross-validation MAE generally around 8–10 points.

The score distribution was concentrated around the 60–89 range, with fewer strongly disliked or highly loved albums. This made extreme predictions difficult.

### Three-tier classification experiment

Scores were also interpreted through broad preference tiers.

The original thresholds were:

* `0–39`: dislike;
* `40–69`: neutral;
* `70–100`: like.

The tier system was useful for error analysis but did not replace the regression objective.

### Sample-weighting experiment

A sample-weighting experiment was performed to increase the influence of rare high and low ratings.

The goal was to determine whether emphasizing score-distribution outliers would improve predictions at the tails.

The weighting experiment did not produce a sufficiently convincing improvement and was reverted. The final original implementation returned to unweighted training.

The experiment was retained as part of the project history rather than silently discarded.

---

## Phase 2: Album of the Year dataset expansion

The project later expanded beyond the 365 manually curated albums by exporting the user's all-time Album of the Year ratings.

The export contained approximately 1,189 records and included:

* artist;
* album;
* release year;
* release format;
* rating;
* date rated.

The larger dataset was expected to represent the user's broader historical taste more accurately and provide more examples of high and low scores.

### AOTY import decisions

`src/import_aoty.py` converts the export into a cleaned dataset.

Important decisions include:

* removing `date_rated` because it is not a stable album-level characteristic;
* normalizing names and numeric fields;
* removing incomplete or invalid rows;
* enforcing a 0–100 score range;
* deduplicating by artist, album, and release year;
* preserving the release format;
* adding dataset-source and release-decade information.

The cleaned output is written to:

```text
data/processed/aoty_cleaned.csv
```

### Metadata-enrichment experiment

The AOTY export did not contain all features used by the original 365-album model.

External metadata sources were evaluated for:

* genres and styles;
* track count;
* runtime.

Last.fm was initially used for genre tags, track count, and runtime. Coverage and tag quality were imperfect.

Discogs was later evaluated for genre and style assignment.

The current design uses:

* Discogs for genre and style values;
* Last.fm for track count and runtime.

Discogs genre and style values are merged into one flexible `Genres` field instead of being separated into rigid `Genre 1`, `Genre 2`, and `Genre 3` columns.

This was intentional because Discogs genres and styles form a variable-length set rather than a consistent three-label hierarchy.

The enriched output is:

```text
data/processed/aoty_enriched.csv
```

A review-oriented output is also produced for enrichment inspection.

### Current AOTY model

`src/train_aoty_model.py` currently evaluates a Ridge regression pipeline.

Its features include:

* artist;
* release format;
* release year;
* release decade;
* track count;
* runtime;
* multi-hot indicators derived from the comma-separated `Genres` field.

The model is compared with a mean-value baseline and evaluated using:

* MAE;
* RMSE;
* R²;
* grouped error summaries;
* worst prediction misses.

The current AOTY training script evaluates the model but does not save a reusable trained model artifact.

---

## Phase 3: Spotify album-discovery pipeline

A separate Spotify-connected pipeline was introduced to turn the project into a practical album-discovery application.

Its central goal is:

> Recommend albums that fit the user's taste but have not been meaningfully explored.

This differs from the explicit-rating model. The Spotify pipeline currently uses behavioral signals and rule-based ranking rather than predicting a numerical personal score.

### Spotify data collected

The current pipeline can collect:

* top artists;
* top tracks;
* recently played tracks;
* saved albums;
* saved tracks.

Spotify responses are stored locally under ignored raw-data paths.

### Taste-profile construction

Spotify activity is converted into artist-affinity scores.

Current affinity signals include:

* ranked top artists;
* artists represented in top tracks;
* artists represented in saved albums;
* artists represented in saved tracks;
* artists represented in recent listening.

The resulting profile includes both artist affinity and albums considered known.

### Known-album behavior

An album may be considered known when it is:

* directly saved;
* represented by a top track;
* recently played;
* represented by at least two saved tracks.

Known albums are tracked using both:

* Spotify album IDs;
* normalized artist-and-album keys.

Normalization removes punctuation, bracketed text, parenthetical text, and common edition labels such as deluxe or remastered wording.

This matching logic is important and should remain consistent across profile construction, candidate generation, and familiarity scoring.

### Candidate-generation evolution

The earliest candidate implementation primarily returned albums from heavily listened-to artists.

That was useful as a starting point, but it did not satisfy the broader discovery goal.

The desired direction changed toward artists the user has listened to very little or has not explored deeply.

The current default behavior:

* excludes the top 10 Spotify artists;
* considers remaining scored artists;
* orders eligible artists from lower to higher affinity;
* selects up to 25 artists;
* requests paginated album releases;
* removes known albums;
* removes duplicate Spotify album IDs;
* removes normalized artist-and-title matches;
* filters deluxe, remastered, live, remix, soundtrack, expanded, instrumental, bonus, and similar editions.

The pipeline currently searches through lower-affinity artists already represented somewhere in the user's Spotify activity. It does not yet provide fully independent discovery of artists absent from the profile.

### Familiarity scoring

Candidate familiarity is calculated separately.

Current signals include:

* saved album;
* top-track presence;
* saved-track presence;
* recent-play presence.

Highly familiar albums are excluded.

Remaining albums receive labels such as:

* unheard;
* lightly familiar;
* partially familiar;
* mostly familiar.

The candidate data contains familiarity details, but the current command-line output does not display all of them.

### Rate limiting

Spotify rate limiting became a major constraint during candidate pagination.

The current implementation:

* handles HTTP 429 responses;
* retries short delays;
* avoids sleeping for extremely long retry periods;
* saves partial candidate results;
* caches candidate albums to avoid unnecessary repeated API collection.

External API calls should remain cache-aware and deliberate.

### Current limitation

The current output is a filtered candidate list rather than a complete recommendation-ranking system.

It does not yet combine:

* artist affinity;
* unfamiliarity;
* candidate quality;
* genre compatibility;
* release relevance;
* other recommendation signals

into one final recommendation score.

This is the next major recommendation-engine design problem.

---

### Current recommendation-quality observation

A recent run of the Spotify pipeline produced a strong candidate set. The
albums appeared sufficiently unfamiliar while still matching the user's
preferred tastes.

The immediate problem is not candidate relevance but output volume. The
application currently returns a very long list.

The desired initial output behavior is:

- return five recommendations;
- allow no more than one album per artist;
- preserve the broader candidate pool and existing cache;
- apply the limit only during final recommendation selection or presentation.

A customizable recommendation count may be added later, but the initial
default and current requirement is five.

---

## Current repository state

The active development branch at the time Codex was introduced was:

```text
spotify-recommender
```

The repository contains working data-processing and recommendation scripts but does not yet contain:

* a production backend;
* a database schema;
* a React frontend;
* a deployed web application;
* a formal command-line interface;
* a complete automated test suite.

Some Django and related dependencies exist in `requirements.txt`, but no Django application is currently implemented.

Frontend, backend, database, authentication, and deployment choices should therefore be treated as planned architecture rather than completed functionality.

---

## Current engineering priorities

### 1. Add offline automated tests

Initial tests should target pure functions that do not make network requests.

Priority areas:

* album-title normalization;
* known-album matching;
* undesirable-edition filtering;
* candidate deduplication;
* artist-affinity ordering;
* familiarity scoring and thresholds;
* genre parsing;
* AOTY schema validation.

### 2. Improve candidate ranking

Create an explainable recommendation score that balances:

* taste fit;
* artist familiarity;
* album familiarity;
* evidence of prior interest;
* discovery value.

The system should not simply return the least familiar albums without considering whether they are likely to be relevant.

### 3. Improve output transparency

Candidate output should eventually display:

* artist;
* album;
* familiarity score;
* familiarity label;
* artist-affinity score;
* recommendation score;
* recommendation explanation.

### 4. Align documentation with implementation

The README should be corrected where it still describes:

* Last.fm as the genre source;
* candidates as coming from the strongest artists;
* familiarity details as already printed;
* candidate filtering as unfinished;
* planned application components as implemented components.

### 5. Prototype the user interface

A lightweight Python interface may be used before committing to a full frontend architecture.

A later production-oriented design may use a separate frontend, API backend, database, and Spotify OAuth flow.

---

## Important product distinctions

### Explicit taste prediction

The AOTY and 365-album pipelines use explicit personal ratings.

Their question is:

> Based on album metadata, what score might this user assign?

### Spotify album discovery

The Spotify pipeline uses behavioral and library signals.

Its question is:

> Which unfamiliar album should this user explore next?

These are related but not identical machine-learning problems.

Do not merge their assumptions, labels, evaluation methods, or objectives without an explicit design decision.

---

## Development principles

* Preserve the project history, including unsuccessful experiments.
* Prefer explainable recommendation logic before adding unnecessary model complexity.
* Treat Spotify behavior as implicit preference, not equivalent to an explicit rating.
* Keep API-backed collection separate from offline transformation and ranking.
* Keep caches reusable to reduce rate-limit exposure.
* Protect personal listening and rating data.
* Add tests before undertaking large recommendation-engine refactors.
* Update this document when major architectural decisions or experiments change the project's direction.
