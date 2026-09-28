# Liner Notes

An album discovery application that takes a user's Spotify listening data and recommends albums that lie adjacent to the familiar artists and styles.

Liner Notes is designed around a specific  problem: recommendations should feel recognizable enough to inspire interest, but not so familiar that they simply repeat albums the listener already knows. This application analyzes Spotify listening habits, selects artists from a deliberately bounded familiarity range, filters their catalogs, and returns one album from each of five distinct artists selected through the filtering process.

The repository contains the complete React frontend, FastAPI backend, Spotify recommendation pipeline, secure multi-user authentication, offline analysis tools, automated tests, and the earlier machine-learning experiments that shaped the final product.

## Why I Built It

In 2025, I challenged myself to listen to 365 albums I had never heard before. Some were new releases, while many were older records or albums from recent years that I had simply missed. Honestly, it was less of a challenge and more of tasking myself to explore artists, albums, genres, styles, and trends beyond what I am already familiar with, chasing a high of discovering that one album or artist among the endless sea that I connect with on an extremely deep level.

Liner Notes began as a model trained on my explicit album ratings based on a profile I have on albumoftheyear.org (i.e. "AOTY") -- a site for users to rate, review, and discuss music. While it applied to my particular circumstances as an AOTY user of many years, I felt that shifting my focus to a Spotify-backed dataset rather than uploading an AOTY data export would make my application more accessible and user-friendly.

The project subsequently evolved into a Spotify-connected application based on implicit listening behavior rather than a private ratings dataset.

## Product Overview

Users can:

- Connect a Spotify account through Spotify OAuth.
- Generate five personalized album recommendations.
- Receive one recommendation per primary artist, preventing duplicates.
- Open any recommended album directly in Spotify.
- Preview the application interface without connecting Spotify.
- Log out or permanently delete locally stored credentials and Spotify-derived data.

The interface intentionally keeps the result simple: album artwork, release year, album title, artist, and a Spotify link. Recommendation calculations remain available to the backend and analysis tools without turning the product into a technical dashboard.

## How Recommendations Work

```text
Spotify listening data
        │
        ▼
Artist-affinity and known-album profile
        │
        ▼
Percentile-based artist selection
        │
        ▼
Catalog retrieval and album filtering for each artist
        │
        ▼
Familiarity and recommendation scoring for each album
        │
        ▼
One album selected from each of the catalogs
```

### 1. Taste profile

The profile combines evidence from:

- Ranked top artists
- Artists represented in top tracks
- Saved albums
- Saved tracks
- Recently played tracks

These signals produce an artist-affinity score and a set of albums the listener is likely to know. Album identity is tracked through Spotify IDs and normalized artist/title keys so alternate editions (deluxe, expanded, anniversary editions, etc.) do not bypass familiarity checks to prevent duplicate albums.

### 2. Artist selection

For profiles containing more than 20 artists, the application uses a `2 + 2 + 1` allocation:

| Affinity percentile | Artists selected | Purpose |
| --- | ---: | --- |
| 10th–50th | 2 | Stronger discovery emphasis |
| 50th–75th | 2 | Meaningful existing interest |
| 75th–90th | 1 | A more recognizable anchor |

The lowest 10% is excluded to reduce incidental connections, such as an artist encountered only through a minor feature. The highest 10% is excluded to avoid overly obvious recommendations. These boundary allocations came as a result of rigorous quality-assurance testing to ensure that the recommendations given were of the highest quality.

Profiles containing 20 or fewer artists draw up to five artists from the complete profile instead of imposing percentile bands on a small sample.

Several safeguards keep the allocation useful:

- A percentile band needs at least five eligible artists to participate directly.
- An undersized band transfers its allocation to the broader 10th–90th percentile pool.
- An artist that produces no valid album is replaced from the same band.
- If that band is exhausted, replacement falls back to the unused 10th–90th percentile pool.
- An artist is examined at most once during a roll to prevent duplicate artist rolls.

This design prevents artists from becoming guaranteed simply because they occupy a sparse band, and it avoids the catalog-size bias created by pooling albums from many artists before deciding artist representation.

### 3. Album filtering

For each selected artist, Liner Notes retrieves Spotify album metadata and removes:

- Albums already represented in the listener's profile
- Duplicate Spotify album IDs and normalized duplicates
- Highly familiar albums
- Live albums, remixes, soundtracks, and instrumental editions
- Deluxe, expanded, anniversary, bonus, remastered, and similar editions
- Releases on which the selected artist is not the primary artist

If an artist has no album left after filtering, the replacement process continues until five viable artists are found or the permitted artist pool is exhausted.

### 4. Scoring and final selection

Eligible albums are scored using:

```text
60% normalized artist relevance
40% discovery value (100 − album familiarity)
```

Artist relevance uses a saturating transformation so exceptionally large affinity scores do not dominate the result. Familiarity rewards albums with little evidence that the listener already knows them. Final selection allows no more than one album per primary artist.

The current default strategy uses controlled randomization only among candidates tied exactly on score and familiarity. A deterministic `lowest_affinity` strategy remains available for reproducible comparisons.

### 5. A duplicate-free second roll

After the first result, the application stores its displayed primary artist IDs in the authenticated user's recommendation cache. “Discover 5 more” performs a new artist draw under the same percentile rules while excluding every Roll 1 artist from individual bands, replacement queues, and the fallback pool.

Only one additional roll is currently exposed. This limit was intentionally added to prevent exceeding rate-limiting boundaries, but may be expanded in the future.

## Architecture

```text
React + Vite frontend
        │ credentialed HTTP
        ▼
FastAPI application
        ├── OAuth, sessions, and account lifecycle
        ├── recommendation orchestration
        └── OpenAPI documentation
        │
        ├────────► SQLAlchemy persistence
        │          PostgreSQL / local SQLite
        │
        └────────► Spotify Web API through Spotipy
                         │
                         ▼
                  Versioned per-user cache
```

Profile preparation and recommendation generation are separate operations. Prepared profiles are versioned and cached for 24 hours, reducing repeated Spotify collection while allowing missing, expired, incompatible, or corrupted profiles to rebuild safely.

Web requests reuse the Spotify account ID already verified during OAuth rather than making redundant current-user requests. CLI and direct Python workflows retain a one-request identity fallback when no authenticated application session exists.

## Security, Privacy, and Data Handling

- Spotify authorization uses the server-side authorization-code flow.
- OAuth state is one-time, short-lived, and bound to the browser through an HTTP-only cookie.
- Browser sessions are opaque; only session hashes are stored server-side.
- Spotify tokens are encrypted at rest with Fernet.
- Profile data and recommendation caches are isolated by stable Spotify account ID, never display name.
- Production cookies can be restricted to HTTPS with `APP_COOKIE_SECURE=true`.
- Account deletion removes local sessions, encrypted tokens, prepared profiles, downloaded Spotify data, and recommendation caches.
- Tokens, personal Spotify exports, local databases, caches, environment files, and model artifacts are excluded from version control.

Deleting an account removes application data but does not revoke the application grant from the user's Spotify account settings.

## Technology Stack

| Area | Technologies |
| --- | --- |
| Frontend | React 18, Vite, CSS |
| API | Python, FastAPI, Uvicorn |
| Spotify integration | Spotipy, Spotify Web API, OAuth 2.0 |
| Persistence | SQLAlchemy, PostgreSQL, SQLite, Alembic |
| Security | Fernet token encryption, hashed sessions and OAuth state |
| Testing | pytest, FastAPI TestClient, mocked Spotify clients |
| Research | pandas, NumPy, scikit-learn, CatBoost |

## API Overview

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health check |
| `GET` | `/api/auth/login` | Begin Spotify authorization |
| `GET` | `/api/auth/callback` | Validate OAuth state and create a session |
| `GET` | `/api/auth/me` | Return the authenticated account identity |
| `POST` | `/api/recommendations` | Generate recommendation Roll 1 or Roll 2 |
| `POST` | `/api/auth/logout` | Invalidate the active session |
| `DELETE` | `/api/auth/account` | Delete credentials, sessions, and cached user data |
| `GET` | `/docs` | Interactive OpenAPI documentation |

Recommendation requests accept `{"roll": 1}` for the initial result and `{"roll": 2}` for the single permitted reroll.

## Local Development

### Prerequisites

- Python 3.12 or another version compatible with the pinned dependencies
- Node.js and npm
- A Spotify developer application
- PostgreSQL for a production-like setup, or SQLite for local development

### 1. Install the backend

```bash
git clone <repository-url>
cd music-recommendation-app

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

### 2. Configure the environment

Create `.env` in the repository root:

```dotenv
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/api/auth/callback
SPOTIFY_TOKEN_ENCRYPTION_KEY=replace_with_a_generated_fernet_key
FRONTEND_AUTH_SUCCESS_URL=http://127.0.0.1:5173/
FRONTEND_ORIGIN=http://127.0.0.1:5173
APP_COOKIE_SECURE=false

# Choose one persistence option:
AUTH_DATABASE_PATH=data/auth/auth.db
# DATABASE_URL=postgresql+psycopg://user:password@host:5432/music_recommendations
```

Generate a Fernet key once:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Register the exact `SPOTIFY_REDIRECT_URI` in the Spotify developer dashboard. Use `127.0.0.1` consistently during local development; mixing it with `localhost` prevents the OAuth state cookie from reaching the callback.

If PostgreSQL is configured, apply migrations before starting the API:

```bash
PYTHONPATH=src alembic upgrade head
```

SQLite initializes its local schema automatically.

### 3. Start the backend

```bash
source .venv/bin/activate
PYTHONPATH=src python -m uvicorn api.main:app --reload
```

The API runs at `http://127.0.0.1:8000`; interactive documentation is available at `http://127.0.0.1:8000/docs`.

### 4. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. The no-auth preview is available at `/preview`.

If the API and frontend use different origins, set `VITE_API_BASE_URL` for the frontend and set `FRONTEND_ORIGIN` to the frontend's exact origin on the backend.

## Testing and Validation

The complete automated suite runs offline with mocked Spotify clients and temporary caches; it does not consume Spotify API quota.

```bash
source .venv/bin/activate
PYTHONPATH=.:src python -m pytest -q
```

Coverage includes:

- OAuth state, encrypted token persistence, sessions, and account deletion
- Profile caching, expiration, versioning, corruption recovery, and user isolation
- Artist-affinity percentiles, small-profile behavior, and `2 + 2 + 1` allocation
- Undersized-band fallback and invalid-catalog replacement
- Known-album, duplicate-edition, and familiarity filtering
- Recommendation scoring, tie behavior, and unique-artist selection
- Roll 2 exclusion and single-use enforcement
- API response behavior and redundant-request prevention
- Read-only inspection and recommendation-analysis utilities

Frontend validation is available through:

```bash
cd frontend
npm run lint
npm run build
```

## Development and Research

The current application is the result of several distinct iterations:

1. **Explicit rating prediction** — a CatBoost experiment trained on a personal 365-album dataset.
2. **Larger ratings pipeline** — an Album of the Year export expanded to approximately 1,189 albums and enriched through Discogs and Last.fm tags; this experiment is now archived outside the application repository.
3. **Spotify candidate discovery** — a practical recommendation pipeline based on implicit listening behavior.
4. **Catalog-bias correction** — selecting artists before albums so large discographies do not receive disproportionate influence.
5. **Affinity-band refinement** — moving from the least-familiar artists to the current 10th–90th percentile sweet spot.
6. **Production-oriented application work** — OAuth, multi-user persistence, caching, request-efficiency improvements, a REST API, and a responsive frontend.

The original 365-album modeling pipeline remains as an archive of the preliminary stage of this project, not as a dependency of the live Spotify recommendation workflow. The original AOTY import, enrichment, and model-evaluation files are retained locally but excluded from Git so application users do not need to clone unrelated datasets and experiments.

Detailed investigations are documented in:

- [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md)
- [`docs/CANDIDATE_DISCOVERY_REPORT.md`](docs/CANDIDATE_DISCOVERY_REPORT.md)
- [`docs/ARTIST_AFFINITY_INVESTIGATION.md`](docs/ARTIST_AFFINITY_INVESTIGATION.md)
- [`docs/BALANCED_AFFINITY_EXPERIMENT.md`](docs/BALANCED_AFFINITY_EXPERIMENT.md)

Read-only development utilities are also available:

```bash
python scripts/inspect_profile.py
python scripts/analyze_recommendation_pipeline.py
```

Both tools report aggregate profile and recommendation behavior without printing private artist names, album names, Spotify IDs, or listening-history records.

## Repository Layout

```text
music-recommendation-app/
├── frontend/                       # React/Vite application
├── src/
│   ├── api/                        # FastAPI, OAuth, sessions, persistence
│   └── music_taste/
│       ├── cache/                  # Versioned per-user profile cache
│       └── spotify/                # Collection and recommendation pipeline
├── scripts/                        # Read-only inspection and analysis tools
├── tests/                          # Offline automated test suite
├── migrations/                     # Alembic database migrations
├── docs/                           # Research reports and project history
├── data/                           # Local/private datasets and generated data
├── requirements.txt                # Runtime dependencies
└── requirements-dev.txt            # Development and testing dependencies
```

## Current Status and Next Steps

The core local application is complete: Spotify authentication, profile generation, recommendation selection, reroll behavior, account deletion, frontend presentation, persistence, caching, and offline testing are all implemented.

Remaining work is intentionally narrow:

- Deployment and production configuration
- App-wide Spotify request instrumentation and pacing
- Cached recommendation-set navigation and history
- Broader user testing of the current affinity bands
- Optional feedback collection for future offline evaluation

## Key Lessons

- Candidate generation can influence recommendation quality more than final score tuning.
- Selecting artists before albums prevents large catalogs from dominating the result.
- Familiarity works best as a bounded discovery target rather than a simple “least familiar is best” rule.
- Controlled randomness is useful inside exact ties but should not move weaker candidates ahead of stronger ones.
- Separating profile preparation, candidate discovery, filtering, scoring, and selection makes experimentation safer and easier to validate.
- Caching and identity reuse improve API efficiency without reducing recommendation quality.

## Project Scope

Liner Notes is a personal-scale exploration of recommendation-system design, Spotify API integration, secure authentication, data caching, API development, frontend product design, automated testing, and evidence-driven iteration. Its purpose is not to reproduce Spotify's global recommendation system, but to solve a narrower product problem well: helping a listener choose a small number of albums that feel both personally relevant and genuinely worth discovering rather than nonsensical recommendations based off of poor-quality data.
