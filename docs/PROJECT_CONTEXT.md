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

### Profile preparation boundary

Spotify recommendation orchestration is separated into two stages so prepared
profiles can be cached without changing recommendation logic:

* `prepare_user_profile(spotify_client)` performs Spotify data collection and
  builds the complete taste profile;
* `generate_recommendations_from_profile(spotify_client, taste_profile, limit)`
  performs candidate discovery, final ranking, and result formatting without
  fetching Spotify listening data or rebuilding the profile.

The cache is keyed by the authenticated Spotify user ID. A valid prepared
profile is reused for 24 hours. Missing, expired, corrupted, or incompatible
entries are invalidated and rebuilt automatically. The original
`generate_recommendations()` function remains as a convenience wrapper around
cached profile resolution and profile-based recommendation generation.

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

The final command-line output displays the familiarity score and label for each
selected recommendation.

### Rate limiting

Spotify rate limiting became a major constraint during candidate pagination.

The current implementation:

* handles HTTP 429 responses;
* retries short delays;
* avoids sleeping for extremely long retry periods;
* saves partial candidate results;
* caches candidate albums to avoid unnecessary repeated API collection.

External API calls should remain cache-aware and deliberate.

### Final recommendation ranking

Candidate collection, caching, and filtering still produce and retain the full
eligible pool. A separate offline stage scores every eligible candidate before
selecting the final results.

The deterministic score combines:

* 60% normalized artist relevance, using a saturating transformation of the
  existing artist-affinity value;
* 40% discovery value, calculated as `100 - familiarity score`.

The saturation prevents very large raw affinity values from dominating, while
the relevance component prevents the least familiar album from automatically
becoming the strongest recommendation. The selector follows the ranked list
and keeps the highest-ranked album for each case-insensitively normalized
primary artist until five unique artists are selected or the pool is exhausted.

Ties are resolved by raw artist affinity descending, familiarity ascending,
case-normalized artist name, case-normalized album name, and Spotify album ID.
This makes results independent of candidate input order. The name fields are
late tie-breakers, not primary ranking signals, and neither the API nor CLI
sorts the selected recommendations again.

The current score remains limited to implicit artist-affinity and coarse album-
familiarity evidence. It does not measure true expected enjoyment, album
quality, genre compatibility, lifetime play counts, or release relevance.

### Experimental balanced-affinity selection

The original `lowest_affinity` selector remains the default and retains its
deterministic behavior. The opt-in `balanced_affinity` selector is a final-stage
experiment over the same fully generated, filtered, and scored candidate pool;
it does not alter collection, filtering, familiarity, or scoring.

Candidate-album affinity values receive tie-aware empirical percentile ranks.
The experiment targets three unique artists at or below the 30th percentile and
two between the 50th and 90th percentiles. The latter range is intended to model
expansion among artists with meaningful evidence while normally excluding the
highest 10%, which is most likely to contain heavily familiar artists. Named
constants keep all bounds and allocations adjustable.

Within each band, recommendation score descends and familiarity ascends.
Randomness is used only for exact score-and-familiarity ties, and an injectable
random generator supports repeatable offline comparisons. If either band lacks
enough unique artists, the selector fills from the best remaining candidates.
The one-album-per-case-normalized-artist rule still applies.

The cached development pool currently has only one affinity value, so every
candidate receives the same tie-aware 50th percentile. In that snapshot the
discovery band is empty, the expansion/fallback path supplies all five, and the
strategy changes exact-tie variety but not affinity or score diversity. This is
a limitation of the existing candidate pool, not a percentile-calculation bug.

---

### Current recommendation-quality observation

A recent run of the Spotify pipeline produced a strong candidate set. The
albums appeared sufficiently unfamiliar while still matching the user's
preferred tastes.

The application addresses output volume in a separate final selection stage:

- return up to five ranked recommendations;
- allow no more than one album per case-insensitively normalized artist;
- preserve the broader candidate pool and existing cache;
- apply the limit only during final recommendation selection or presentation.

A customizable recommendation count may be added later, but the initial
default and current requirement is five.

---

## Phase 4: FastAPI application foundation

The repository now includes a FastAPI backend under `src/api/`. This is the
first application-facing layer over the Spotify recommendation pipeline; it is
not yet a deployed or multi-user production service.

The current application exposes:

* `GET /health`, which returns `{"status": "ok"}`;
* `POST /api/recommendations`, which returns up to five structured album
  recommendations;
* `GET /docs`, which is provided automatically by FastAPI for interactive API
  documentation.

Each recommendation contains the artist and album names, Spotify and artwork
URLs when available, recommendation score, explanation, artist affinity,
familiarity score, and familiarity label.

### Recommendation orchestration refactor

The original `generate_recommendations()` entry point remains available as a
backward-compatible convenience wrapper. The API and CLI now call the two
orchestration stages explicitly:

```text
get_spotify_client()
        │
        ▼
get_or_prepare_user_profile(client)
        │
        ├── valid cache → load profile
        └── cache miss/stale → prepare_user_profile(client) → save profile
        │
        ▼
generate_recommendations_from_profile(client, profile, limit=5)
```

This refactor did not change candidate collection, familiarity scoring,
ranking weights, deterministic tie-breaking, or unique-artist selection. Its
purpose was to create a boundary around the expensive data-collection and
profile-building stage. The local cache now resolves that boundary without
changing recommendation behavior.

Cached profiles are stored under `cache/users/<spotify_user_id>/` as
`profile.pkl` plus `metadata.json`. Metadata records the Spotify user ID, UTC
profile-update time, and profile schema version. The initial profile version is
1 and the lifetime is 24 hours. There is no refresh endpoint, database, or
multi-user session model; stale profiles refresh automatically on demand.

Cache resolution emits concise development logs for misses, hits and profile
age, expiration, schema-version mismatch, and corrupt entries. The read-only
`scripts/inspect_profile.py` utility can inspect all cached user directories or
one selected with `--user-id`. It reports metadata, top-level type and keys,
file size, and aggregate profile counts without modifying cache files or
printing the profile's detailed listening data.

### Dependency and test foundation

The prior development environment was replaced with focused runtime and
development requirement files. Django and unrelated notebook-environment
packages are no longer carried as application dependencies.

The current offline suite contains 22 tests across `tests/test_api.py`,
`tests/test_profile_cache.py`, and `tests/test_spotify_recommendations.py`.
The tests cover API health and response shape, profile preparation, cache miss
and hit behavior, expiration, version mismatch, corruption recovery,
profile-based generation, preservation of the selection limit, structured
recommendation conversion, and the orchestration boundary that prevents
profile-based generation from fetching or rebuilding Spotify data.

The suite uses mocks and can validate the recommendation endpoint without
initiating Spotify OAuth or making external requests.

---

## Current repository state

The current application-foundation work is being developed on:

```text
web-app-foundation
```

The repository currently contains:

* the original 365-album CatBoost research pipeline;
* the AOTY import, enrichment, and Ridge evaluation pipeline;
* a working Spotify taste-profile and album-recommendation pipeline;
* a command-line recommendation entry point;
* a FastAPI development backend with structured responses and Swagger docs;
* focused runtime and development dependency files;
* 15 offline automated tests.

The repository does not yet contain:

* a production backend;
* a database schema;
* a React frontend;
* a deployed web application;
* multi-user Spotify OAuth and session handling;
* a comprehensive test suite for all modeling, normalization, filtering, and
  data-pipeline behavior.

FastAPI is now the implemented backend foundation. The database, React
frontend, arbitrary-user authentication, and deployment architecture remain
planned work.

---

## Current engineering priorities

### 1. Expand offline automated tests

The existing 22-test suite protects the API, profile cache, and recommendation-
orchestration boundary. Additional pure-function coverage should target:

* album-title normalization;
* known-album matching;
* undesirable-edition filtering;
* candidate deduplication;
* artist-affinity ordering;
* familiarity scoring and thresholds;
* genre parsing;
* AOTY schema validation.

### 3. Tune and extend candidate ranking

Evaluate and tune the current artist-relevance and discovery-value weights.
Add only verified signals that improve recommendation strength without changing
or truncating the full candidate pool.

### 4. Add arbitrary-user Spotify authentication

Replace the repository owner's development credentials with a user-facing OAuth
flow, secure token handling, and user-scoped profile/cache behavior.

### 5. Build the frontend and deployment path

Build a React interface over the FastAPI contract, introduce persistent storage
when the multi-user design requires it, and deploy the frontend and backend with
credentials and personal data kept out of source control.

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
