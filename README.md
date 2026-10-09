# Liner Notes

An album discovery application that takes a user's Spotify listening data and recommends albums that lie adjacent to the familiar artists and styles.

Liner Notes is designed around a specific  problem: recommendations should feel recognizable enough to inspire interest, but not so familiar that they simply repeat albums the listener already knows. This application analyzes Spotify listening habits, selects artists from a deliberately bounded familiarity range, filters their catalogs, and returns one album from each of five distinct artists selected through the filtering process.

The repository contains the React frontend, FastAPI backend, Spotify recommendation pipeline, secure multi-user authentication, and local setup tools.

## Why I Built It

In 2025, I challenged myself to listen to 365 albums I had never heard before. Some were new releases, while many were older records or albums from recent years that I had simply missed. Honestly, it was less of a challenge and more of tasking myself to explore artists, albums, genres, styles, and trends beyond what I am already familiar with, chasing a high of discovering that one album or artist among the endless sea that I connect with on an extremely deep level.

Liner Notes turns that interest in album discovery into a Spotify-connected application based on listening behavior. It helps listeners find overlooked albums from artists adjacent to their existing tastes.

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

## Clone and Run Locally

Each installation uses its owner's **Spotify Client ID and Client Secret**, not a shared API key. No private datasets or trained models are needed for the application.

### Prerequisites

- Git
- Python **3.12**, available as `python`
- Node.js **20+** and npm; a currently supported LTS release is recommended
- A Spotify account eligible to create a development-mode app (currently the app owner needs Premium)

The setup and launcher are designed for macOS, Linux, and Windows. Offline tests and frontend lint/build checks pass on macOS; a fresh installation and full launcher startup remain unverified. Windows and Linux have not yet been verified on physical machines. Local storage uses SQLite automatically; PostgreSQL is not required.

### 1. Clone and install

```bash
git clone https://github.com/arya-maz/music-recommendation-app.git
cd music-recommendation-app
python manage.py setup
```

On Windows, `py -3.12 manage.py setup` and `py -3.12 manage.py run` are alternatives if `python` is not available.

Setup creates `.venv`, installs only the application dependencies, installs the frontend from its lockfile with `npm ci`, and creates `.env` with a randomly generated encryption key. Dependency installation requires internet access. Setup does not authenticate with Spotify or call its API.

Rerunning setup preserves an existing `.env` and encryption key. Keep that key: replacing it makes existing encrypted Spotify tokens unreadable. Application dependencies are in `requirements.txt`. The public checkout contains the application and installation instructions; personal development tools and documentation are kept locally.

### 2. Create your personal Spotify application

1. Open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create an app for your personal installation. Select **Web API** if asked which APIs you will use.
2. Set the redirect URI to exactly:

   ```text
   http://127.0.0.1:8000/api/auth/callback
   ```

3. Copy the app's **Client ID** and **Client Secret** into the corresponding placeholders in the generated `.env` file.
4. Check **Users Management** and ensure the Spotify account you will connect is authorized for that app. Any additional tester must also be allowlisted.

Use the other generated defaults as they are for this launcher. Spotify requires an explicit loopback address for local HTTP callbacks; do not substitute `localhost`.

Your `.env`, token storage, and user caches stay local and are ignored by Git. Never share your Client Secret or include your local config in screenshots or bug reports. To start from a manually created config, copy `.env.example` to `.env` and generate an encryption key using:

```bash
python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

Paste the result into `SPOTIFY_TOKEN_ENCRYPTION_KEY`.

Spotify access is governed by its current [app setup rules](https://developer.spotify.com/documentation/web-api/concepts/apps), [redirect URI requirements](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri), [quota rules](https://developer.spotify.com/documentation/web-api/concepts/quota-modes), and [Developer Policy](https://developer.spotify.com/policy). Personal credentials do not guarantee endpoint access or exempt an installation from Spotify's terms; this setup is not a way to bypass public-app access restrictions.

### 3. Start Liner Notes

```bash
python manage.py run
```

Open **http://127.0.0.1:5173**, connect Spotify, and load recommendations. Both services run in one terminal; **Ctrl+C** stops them. Starting the launcher does not initiate Spotify login; connecting and requesting recommendations do use Spotify's API.

The launcher checks configuration and port availability before starting. It binds both services to your local device, and the frontend uses its existing proxy to reach the API. The API documentation is at `http://127.0.0.1:8000/docs`; the sample preview is at `http://127.0.0.1:5173/preview`.

### Troubleshooting

| Problem | What to check |
| --- | --- |
| Setup cannot find Python or Node | Install the required versions and restart your terminal. |
| Setup fails during dependency installation | Check the installation output and internet connection, then rerun setup. Existing configuration is preserved. |
| Missing Spotify credentials | Fill in both placeholders in `.env`; Spotify uses a Client ID and Client Secret. |
| Redirect mismatch or invalid OAuth state | Register the exact callback above and use `127.0.0.1` consistently in both browser and configuration. |
| Spotify returns 403 | Check the app's allowlist and whether Spotify permits the requested endpoints for that app. |
| Spotify returns 429 | Pause requests; rate limits and development quotas still apply to your personal app. |
| Port 8000 or 5173 is occupied | Stop the existing service before starting this launcher. |
| Tokens fail after changing the encryption key | Restore the original key; if unavailable, use a fresh installation and reconnect. |

Local account deletion removes this installation's stored credentials and Spotify-derived data. To revoke Spotify's authorization grant too, remove the app through your Spotify account's Apps settings.

### Manual development and custom configurations

For backend development, activate `.venv` (`source .venv/bin/activate` on macOS/Linux, `.venv\Scripts\Activate.ps1` in Windows PowerShell), then run:

```bash
PYTHONPATH=src python -m uvicorn api.main:app --reload --host 127.0.0.1 --env-file .env
```

In PowerShell, set `$env:PYTHONPATH="src"` first and omit the `PYTHONPATH=src` prefix. Start the frontend separately:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

For PostgreSQL, set `DATABASE_URL` and apply `PYTHONPATH=src alembic upgrade head` before starting the backend. Keep the SQLite default for the standard clone-and-run path. If customizing origins, coordinate `VITE_API_BASE_URL`, `FRONTEND_ORIGIN`, the callback URI, and the frontend success URL. The launcher intentionally requires the standard local URLs; use the manual commands for custom configurations.

## Validation Status

The application passed 61 offline tests, including an isolated copy without research datasets or dependencies, and the frontend build passes. The test suite and internal development reports are maintained locally and are not included in public checkouts. A fresh-device installation and live Spotify end-to-end verification remain outstanding.

## Repository Layout

```text
music-recommendation-app/
├── manage.py                       # Setup and two-service local launcher
├── .env.example                    # Credential-free local configuration template
├── frontend/                       # React/Vite application
├── src/
│   ├── api/                        # FastAPI, OAuth, sessions, persistence
│   └── music_taste/
│       ├── cache/                  # Versioned per-user profile cache
│       └── spotify/                # Collection and recommendation pipeline
├── migrations/                     # Alembic database migrations
├── data/                           # Local account/session storage
├── cache/                          # Private per-user Spotify caches (ignored)
└── requirements.txt                # Liner Notes application dependencies
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
