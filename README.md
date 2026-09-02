# Music Recommendation App

A growing Spotify-powered album recommendation platform built around thoughtful candidate discovery, explainable ranking, and evidence-driven experimentation. The repository combines a configurable recommendation engine, Spotify integration, machine-learning research, profile caching, a FastAPI backend, offline analysis tools, and automated tests to recommend albums a user is likely to enjoy but may not have fully explored.

## Background

As a long-time avid music fanatic, I've always been eager to chase new experiences through different artists, genres, styles, and eras of music. Throughout 2025, I challenged myself to check out 365 albums that I had never heard before -- some of which were newer albums releasing on a rolling basis throughout the year, while the majority were either releases that I had missed from recent years or older records that I wanted to closely familiarize myself with. This experience inspired me to build a recommendation tool that would make finding new albums to experience much easier and more straightforward.

The goal of this project is to recommend albums to a user based on their personal taste. The project originally approached this through explicit album ratings and score prediction, using my own rated albums as the foundation for a personal taste model. After evaluating the limits of exact score prediction, I began expanding the project toward a more usable Spotify-based recommendation system where a user can connect their Spotify account and receive album recommendations from their listening behavior.

## What the Project Does Today

### Recommendation engine

- Builds artist-affinity and known-album profiles from Spotify listening signals.
- Discovers candidate albums from eligible artists already represented in the profile.
- Removes known albums, duplicate Spotify album IDs, and deluxe, anniversary, expanded, remastered, live, remix, soundtrack, and similar editions.
- Estimates album familiarity from saved albums, saved tracks, top tracks, and recent listening.
- Scores the complete eligible pool using artist relevance and discovery value.
- Supports configurable final-selection strategies without duplicating scoring logic.
- Returns up to five explainable recommendations with no more than one album per artist.

### Backend

- Exposes a FastAPI REST API with health and recommendation endpoints.
- Implements Spotify authorization-code OAuth with one-time, browser-bound state.
- Uses opaque, server-side application sessions and encrypted per-user Spotify tokens.
- Provides interactive Swagger/OpenAPI documentation.
- Caches prepared Spotify profiles by user ID for 24 hours.
- Automatically rebuilds missing, expired, version-mismatched, or corrupted profiles.
- Keeps candidate discovery and recommendation generation separate from profile preparation.

### Development and research tooling

- Inspects cached profiles without modifying them.
- Measures candidate funnels, affinity and score distributions, and exact ties offline.
- Compares baseline and balanced-affinity recommendations using the same cached inputs.
- Documents candidate-discovery, artist-affinity, and recommendation-strategy investigations.
- Runs a 50-test offline suite covering auth, API, cache, pipeline, utilities, and strategies.

The rating-modeling pipelines remain in the repository as related research. They document how the project evolved from predicting personal scores toward a practical album-discovery product.

## Current Status

The project has a tested recommendation engine, CLI, API, caching layer, and research toolkit. It is actively evolving toward a user-facing, multi-user recommendation platform.

### Completed

- Original 365-album dataset and CatBoost taste-model experiment
- Model evaluation and error-reporting workflow
- Larger Album of the Year ratings pipeline
- Last.fm and Discogs metadata-enrichment experiments
- Spotify data collection and taste-profile construction
- Candidate discovery, normalization, filtering, and familiarity scoring
- Deterministic recommendation ranking and one-album-per-artist selection
- Structured recommendation objects with album artwork and Spotify links
- FastAPI backend with health, recommendation, and interactive documentation routes
- Separation of profile preparation from recommendation generation
- Versioned 24-hour filesystem cache for prepared Spotify user profiles
- Cache lifecycle logging and read-only profile inspection
- Candidate-funnel, score-distribution, and strategy-comparison tooling
- Evidence-based candidate-discovery, affinity, and tie investigations
- Configurable baseline and balanced-affinity recommendation strategies
- Reproducible runtime and development dependency files
- 50 offline automated tests across auth, API, cache, recommendation pipeline, utilities, and strategy selection

### Planned

- React frontend
- Deployment and production configuration
- Recommendation history and feedback collection

The API now resolves each request through an isolated server-side session and
per-user Spotify token. Deployment hardening and a user-facing frontend remain.

## System Architecture

```text
Spotify authorization-code OAuth
          │
          ▼
Spotify Web API / Spotipy client
          │
          ▼
User Profile Preparation
          │
          ▼
Versioned Profile Cache
          │
          ├── valid profile → load profile
          └── missing/stale profile → prepare and save profile
          │
          ▼
Candidate Album Discovery
          │
          ▼
Filtering + Familiarity Scoring
          │
          ▼
Recommendation Scoring
          │
          ▼
Configurable Selection Strategy
          │
          ▼
Structured Recommendations
          │
          ├── FastAPI JSON response → future React frontend
          └── CLI and offline analysis tools
```

Profile preparation and recommendation generation are intentionally separate. Prepared profiles are cached for 24 hours by Spotify's stable account ID; candidate discovery and ranking receive the resulting profile without knowing whether it was loaded or rebuilt. Development logs identify cache misses, hits and profile age, expiration, version mismatch, and corruption.

## Recommendation Philosophy and Strategies

The production-facing Spotify pipeline is currently rule-based and explainable rather than a black-box machine-learning recommender. Candidate generation, familiarity, scoring, and final selection are separate stages so strategy experiments can be evaluated without silently changing the baseline.

### Taste profile

The profile combines evidence from:

- ranked top artists;
- artists represented in top tracks;
- artists represented in saved albums;
- artists represented in saved tracks; and
- artists represented in recent listening.

It also tracks albums the user is likely to know using Spotify album IDs and normalized artist-and-album keys.

### Candidate discovery

By default, the candidate finder excludes the user's top 10 artists, orders the remaining eligible artists from lower to higher affinity, and searches up to 25 of them. It removes:

- known albums;
- duplicate Spotify album IDs;
- normalized matches for albums already represented in the user's profile; and
- deluxe, remastered, live, remix, soundtrack, expanded, instrumental, bonus, and similar editions.

This currently supports deeper exploration of artists already present in the user's Spotify activity. Discovery of entirely new, adjacent artists is planned.

### Familiarity and primary ranking

Each eligible album receives a familiarity score based on saved-album, top-track, saved-track, and recent-listening signals. Highly familiar albums are excluded.

The final recommendation score combines:

```text
60% normalized artist relevance
40% discovery value (100 - familiarity score)
```

Recommendation score remains the primary ranking signal. Artist relevance uses a saturating transformation so very large raw affinity scores do not dominate, while album familiarity preserves discovery value. The selector returns up to five albums, with no more than one album per primary artist.

The original `lowest_affinity` strategy remains available as the reproducible baseline. It preserves the established deterministic ranking: when score, raw affinity, and familiarity are identical, case-normalized artist name, album name, and Spotify album ID provide stable final tie-breakers.

### Balanced-affinity strategy

The current default strategy is `balanced_affinity`. It operates only on the
already-generated and filtered candidate pool and does not alter the underlying
score. It targets three recommendations from the bottom 30% of
candidate affinity percentiles and two from the 50th–90th percentiles. The
middle band represents artists with meaningful prior interest, while the top
10% is avoided when possible because those artists are likely to be heavily
represented in existing listening.

Within each band, recommendation score remains primary and familiarity remains
the next ordering field. Candidates tied exactly on both values are shuffled;
different scores are never randomized. Missing band allocations fall back to
the best remaining unique-artist candidates. This controlled randomness replaces
alphabetical tie-breaking only in the balanced path.

Strategy names, the default, percentile bounds, and allocations are defined as
named constants in `music_taste.spotify.rank_recommendations`. Callers can
select either strategy without changing scoring logic:

```python
generate_recommendations_from_profile(
    spotify_client,
    taste_profile,
    strategy="balanced_affinity",
)
```

The API and CLI use `balanced_affinity` through the shared default. Pass
`strategy="lowest_affinity"` from a Python caller to reproduce the original
baseline. For an offline side-by-side comparison using cached inputs:

```bash
python scripts/analyze_recommendation_pipeline.py \
  --compare-strategies \
  --seed 42
```

The strategy was added after analysis found a 90-album exact-score tie in the
cached pool, driven by homogeneous affinity and familiarity evidence. The
current pool still contains only affinity-10 candidates, so balanced selection
can reduce deterministic alphabetical tie bias but cannot create genuine
affinity diversity. A meaningful discovery-versus-expansion comparison requires
a candidate pool containing multiple affinity levels.

## Recommendation Research

Recommendation changes are guided by reproducible measurements rather than
arbitrary weight tuning. Completed investigations include:

- a complete candidate-discovery and filtering trace;
- recommendation-score and familiarity distributions;
- artist-affinity calculation and provenance analysis;
- exact-tie size and alphabetical tie-break analysis; and
- an offline comparison of baseline and balanced-affinity selection.

This work established that candidate generation can constrain recommendation
quality before scoring begins: the current cached pool contains 94 eligible
albums, 90 of which share the same score, while every surviving primary artist
has affinity 10. Those findings motivated making controlled tie randomization
the current strategy while preserving a configurable deterministic baseline and
the established score formula.

Detailed reports:

- [`docs/CANDIDATE_DISCOVERY_REPORT.md`](docs/CANDIDATE_DISCOVERY_REPORT.md)
- [`docs/ARTIST_AFFINITY_INVESTIGATION.md`](docs/ARTIST_AFFINITY_INVESTIGATION.md)
- [`docs/BALANCED_AFFINITY_EXPERIMENT.md`](docs/BALANCED_AFFINITY_EXPERIMENT.md)

## API

The FastAPI application currently exposes:

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/health` | Returns `{"status": "ok"}` |
| `POST` | `/api/recommendations` | Loads or prepares a profile and returns five structured album recommendations |
| `GET` | `/docs` | Opens FastAPI's interactive Swagger documentation |

A recommendation response includes:

```json
{
  "artist_name": "Example Artist",
  "album_name": "Example Album",
  "spotify_url": "https://open.spotify.com/album/...",
  "album_image_url": "https://i.scdn.co/image/...",
  "recommendation_score": 78.4,
  "reason": "strong artist-fit evidence; low album familiarity",
  "artist_affinity": 64.0,
  "familiarity_score": 20.0,
  "familiarity_label": "lightly familiar"
}
```

## Technology Stack

- Python
- FastAPI and Uvicorn
- Spotipy and the Spotify Web API
- pandas and NumPy
- scikit-learn
- CatBoost
- Last.fm API
- Discogs API
- pytest

React/Vite powers a thin, responsive frontend with Spotify sign-in,
recommendation cards, feedback controls, loading and recovery states, and a
no-auth preview mode. The application persistence layer
supports PostgreSQL in production, with SQLite retained for local development
and isolated offline tests.

## Repository Structure

```text
music-recommendation-app/
├── cache/                      # Ignored prepared Spotify user profiles
├── data/
│   ├── cache/                  # External metadata caches
│   ├── processed/              # Generated cleaned/enriched datasets
│   └── raw/                    # Personal source data and Spotify responses
├── docs/
│   ├── PROJECT_CONTEXT.md                  # Project history and decisions
│   ├── CANDIDATE_DISCOVERY_REPORT.md       # End-to-end pipeline analysis
│   ├── ARTIST_AFFINITY_INVESTIGATION.md    # Affinity provenance and tie analysis
│   └── BALANCED_AFFINITY_EXPERIMENT.md     # Experimental strategy design/results
├── models/                     # Generated model artifacts
├── scripts/
│   ├── inspect_profile.py                  # Read-only profile cache inspection
│   └── analyze_recommendation_pipeline.py  # Funnel, tie, and strategy analysis
├── src/
│   ├── api/
│   │   ├── auth.py             # Session and encrypted token persistence
│   │   └── main.py             # FastAPI application and OAuth routes
│   ├── music_taste/
│   │   ├── cache/              # Profile cache persistence and expiry
│   │   ├── spotify/            # Spotify profile and recommendation pipeline
│   │   └── ...                 # Original 365-album model workflow
│   ├── enrich_aoty_tags.py     # Metadata enrichment
│   ├── import_aoty.py          # AOTY cleaning/import
│   └── train_aoty_model.py     # AOTY Ridge evaluation
├── tests/                      # Offline API and recommendation tests
├── requirements.txt            # Runtime dependencies
└── requirements-dev.txt        # Development/test dependencies
```

Personal datasets, Spotify responses, OAuth caches, trained models, and environment variables are excluded from version control.

## Local Setup

### Prerequisites

- Python with virtual-environment support
- A Spotify developer application
- Spotify client ID, client secret, and redirect URI

### Installation

```bash
git clone <repository-url>
cd music-recommendation-app

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Create a local `.env` file with your Spotify application credentials:

```text
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/api/auth/callback
SPOTIFY_TOKEN_ENCRYPTION_KEY=replace_with_a_generated_fernet_key
DATABASE_URL=postgresql+psycopg://user:password@host:5432/music_recommendations
FRONTEND_AUTH_SUCCESS_URL=http://127.0.0.1:5173/
FRONTEND_ORIGIN=http://127.0.0.1:5173
APP_COOKIE_SECURE=false
```

Generate the encryption key once with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Register the exact `SPOTIFY_REDIRECT_URI` in the Spotify developer dashboard.
Use `127.0.0.1` consistently for the frontend, login request, and callback during
local development. Mixing `localhost` and `127.0.0.1` prevents the callback from
receiving the browser-bound OAuth state cookie and causes an invalid-state error.
For production, use an HTTPS callback URL, keep `APP_COOKIE_SECURE=true`, retain
the encryption key across deployments. Apply schema migrations with
`PYTHONPATH=src alembic upgrade head` before starting the API. For local-only
development, omit `DATABASE_URL` and set `AUTH_DATABASE_PATH=data/auth/auth.db`
to use SQLite. Do not commit `.env`, local databases, or personal listening data.
When the React app is hosted on another origin, it must send requests with
credentials enabled; `FRONTEND_ORIGIN` permits only that exact origin.

### Spotify user-data storage

Spotify tokens are encrypted in the server-side database and associated with a
durable user row keyed by the stable Spotify `account_id` returned by `/me`.
Profile version and refresh timestamps are also persisted; the prepared profile
payload remains in the existing filesystem cache. Browser cookies contain only opaque
session identifiers; their hashes are stored server-side. Spotipy refreshes an
expired access token through a per-user cache handler and persists the rotated
token without exposing it to the browser.

The browser-facing authentication lifecycle is:

```text
GET  /api/auth/login       redirect to Spotify
GET  /api/auth/callback    validate state, identify user, create session
GET  /api/auth/me          return the authenticated Spotify account identity
POST /api/auth/logout      invalidate the current session
DELETE /api/auth/account   delete local account data and all sessions
POST /api/recommendations  require a valid session
```

Account deletion requires a JSON body of `{"confirm": true}`. The user is
derived exclusively from the authenticated session. Deletion removes every
application session and encrypted Spotify token for that user, plus the entire
user-specific cache directory containing profiles, downloaded Spotify data,
and candidate results. It does not sign the user out of spotify.com or revoke
the app grant in Spotify's account settings.

All Spotify-derived recommendation data is isolated by the authenticated
Spotify account ID (never the display name):

```text
cache/
└── users/
    └── <spotify_account_id>/
        ├── metadata.json
        ├── profile.pkl
        ├── top_artists.json
        ├── top_tracks.json
        ├── saved_albums.json
        ├── saved_tracks.json
        ├── recently_played.json
        └── candidate_albums.json
```

The application creates `cache/users/<spotify_account_id>/` automatically after
authentication. Reads and refreshes are confined to that directory, so one
user's raw responses, candidates, metadata, and profile are never reused for
another user.

For compatibility, authentication falls back to Spotify's legacy `id` field if
`account_id` is absent. On the first login after this migration, existing
sessions and encrypted tokens are moved from the legacy ID to `account_id`, and
the legacy cache directory is atomically renamed. Migration refuses to overwrite
an existing destination directory. Sessions created before this identity change
are invalidated once, requiring one fresh Spotify login to establish and verify
the stable identity.

Profile freshness continues to use `last_profile_update` in `metadata.json`.
Profiles younger than 24 hours are reused. An expired or invalid profile is
rebuilt from Spotify and only that authenticated user's files are refreshed.

On the first authenticated run, files in the legacy development location
`data/raw/spotify/` are moved into the authenticated user's directory when the
corresponding destination files do not exist. Existing destination files are
never overwritten; any conflicting legacy files remain in place for manual
review. After migration or regeneration, no runtime component reads from the
legacy directory.

## Running the Project

### FastAPI backend

```bash
source .venv/bin/activate
PYTHONPATH=src python -m uvicorn api.main:app --reload
```

Then open:

- API documentation: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

The recommendation endpoint performs Spotify authentication and external API work. Use it deliberately during development.

### React frontend

In a second terminal, install the frontend packages and start Vite:

```bash
cd frontend
npm install
npm run dev
```

Then open `http://127.0.0.1:5173`. Vite proxies `/api` to the local FastAPI
server. The landing page also includes a preview mode with placeholder albums,
so the interface can be reviewed without starting Spotify OAuth. Feedback
controls are visual-only in this placeholder version and are not persisted.
The preview is also directly available at `http://127.0.0.1:5173/preview`.
The app always opens on the landing page. Authenticated users can explicitly
load recommendations, log out, or delete their account and locally stored data.

Set `VITE_API_BASE_URL` when the API is hosted at a separate origin. The API
must also set `FRONTEND_ORIGIN` to the frontend's exact origin so credentialed
session requests are permitted.

### Development utilities

#### Inspecting the profile cache

The read-only cache inspection utility reports metadata, profile type and keys,
file size, and aggregate artist, album, and saved-track counts without printing
the underlying listening data:

```bash
source .venv/bin/activate
python scripts/inspect_profile.py
```

Pass `--user-id <spotify_user_id>` to inspect one cached user directory.

#### Analyzing recommendations

For aggregate candidate-funnel, score-distribution, and tie analysis using only
the cached profile and candidate album list, run:

```bash
python scripts/analyze_recommendation_pipeline.py
```

This read-only utility prints counts and distributions without printing artist
names, album names, Spotify IDs, or raw listening-history records. Use
`--user-id <spotify_user_id>` when more than one profile is cached.

Add `--compare-strategies` to print side-by-side baseline and balanced results.
Use `--seed 42` when a repeatable comparison is useful; omit the seed to explore
different selections within exact ties.

### Spotify CLI

```bash
source .venv/bin/activate
PYTHONPATH=src python -m music_taste.spotify.run
```

The CLI prints each album's artist, title, recommendation score, artist affinity, familiarity, explanation, and Spotify URL when available.

### Tests

```bash
source .venv/bin/activate
PYTHONPATH=.:src python -m pytest -q
```

The current 50-test suite uses mocks and temporary caches; it does not need to
contact Spotify. Coverage includes OAuth/session behavior, API response behavior, profile caching and
expiration, recommendation scoring and selection, full-pool preservation,
inspection utilities, strategy allocation and fallback, and controlled tie
randomization.

## Research Pipelines

### Original 365-album model

The original CatBoost pipeline uses album metadata to predict a personal score out of 100. Error reports, tier analysis, and a reverted sample-weighting experiment document both the model's capabilities and the limits of a small, centrally distributed ratings dataset.

### Album of the Year expansion

The AOTY pipeline expands the ratings history to approximately 1,189 albums. Its current enrichment design uses Discogs for genres/styles and Last.fm for track count and runtime. The model-training script evaluates a Ridge regression pipeline against a mean baseline; it does not currently persist a reusable model.

The enrichment experiments showed that additional metadata does not automatically improve prediction quality. Noisy tags, sparse categories, and inconsistent coverage can offset the value of a larger feature set.

Detailed experiment history and architectural decisions are preserved in [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md).

## Roadmap

### Backend and product

- [x] Build Spotify taste profile and candidate-discovery pipeline
- [x] Add familiarity scoring, filtering, ranking, and explanations
- [x] Return five unique-artist recommendations through a CLI
- [x] Add a FastAPI backend and structured JSON response schema
- [x] Separate profile preparation from recommendation generation
- [x] Add offline API and orchestration tests
- [x] Cache prepared taste profiles with expiration and automatic refresh
- [x] Add candidate, affinity, score-distribution, and tie-analysis tooling
- [x] Add a balanced-affinity strategy while preserving the deterministic baseline
- [x] Expand offline coverage to API, cache, utilities, and strategy behavior
- [x] Add Spotify OAuth for arbitrary users
- [x] Build a placeholder React frontend
- [ ] Deploy the full application
- [x] Add secure multi-user token, profile, and cache isolation

### Current recommendation focus

- [ ] Diversify candidate sources beyond the lowest-affinity boundary
- [ ] Improve affinity granularity using validated evidence
- [ ] Add recommendation history and prevent repeated suggestions
- [ ] Collect explicit user feedback and reviewed recommendation sets
- [ ] Expand explanations with candidate-source and uncertainty context
- [ ] Add genre, era, novelty, and exploration controls
- [ ] Evaluate additional recommendation strategies without replacing the baseline

### Modeling research

- [ ] Run AOTY feature-group ablation experiments
- [ ] Compare additional regression models
- [ ] Improve performance analysis across score ranges
- [ ] Investigate which Last.fm, Discogs, and album-level features add useful signal

## Lessons Learned

- Recommendation quality depends as much on candidate generation as final scoring.
- Analysis tools and aggregate measurements should precede algorithm changes.
- Large recommendation ties should be traced to their evidence before weights are adjusted.
- Controlled randomness can improve variety inside exact ties without moving weaker scores ahead of stronger ones.
- Separating profile preparation, candidate discovery, scoring, and strategy selection preserves reproducibility while enabling experiments.
- A more granular number is useful only when it represents meaningful additional evidence.

## Purpose

This project explores how explicit album ratings and implicit Spotify listening behavior can support a personalized album-discovery platform. It brings together recommendation-system design, machine-learning experimentation, metadata enrichment, API development, caching, automated testing, and evidence-driven iteration in an architecture intended to keep growing.
