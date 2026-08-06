# Music Recommendation App

A Spotify-powered album recommendation platform backed by a personalized taste model. The project combines explicit album ratings, metadata enrichment, Spotify listening behavior, explainable ranking, and a FastAPI backend to recommend albums a user is likely to enjoy but may not have fully explored.

## Background

As a long-time avid music fanatic, I've always been eager to chase new experiences through different artists, genres, styles, and eras of music. Throughout 2025, I challenged myself to check out 365 albums that I had never heard before -- some of which were newer albums releasing on a rolling basis throughout the year, while the majority were either releases that I had missed from recent years or older records that I wanted to closely familiarize myself with. This experience inspired me to build a recommendation tool that would make finding new albums to experience much easier and more straightforward.

The goal of this project is to recommend albums to a user based on their personal taste. The project originally approached this through explicit album ratings and score prediction, using my own rated albums as the foundation for a personal taste model. After evaluating the limits of exact score prediction, I began expanding the project toward a more usable Spotify-based recommendation system where a user can connect their Spotify account and receive album recommendations from their listening behavior.

## What the Project Does Today

The current application can:

- authenticate with Spotify through Spotipy;
- collect a user's top artists, top tracks, saved albums, saved tracks, and recently played tracks;
- build an implicit taste profile from those listening signals;
- identify underexplored albums from eligible artists already represented in the profile;
- remove known albums, duplicate releases, and undesirable editions;
- estimate album familiarity from saved, top-track, and recent-listening evidence;
- rank the full eligible pool using artist relevance and discovery value;
- return up to five explainable recommendations from unique artists;
- expose recommendations as structured JSON through FastAPI; and
- print the same recommendations through a command-line entry point.

The rating-modeling pipelines remain in the repository as related research. They document how the project evolved from predicting personal scores toward a practical album-discovery product.

## Current Status

The project has a working recommendation engine, CLI, and API foundation.

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
- Reproducible runtime and development dependency files
- Offline automated tests for the API and recommendation orchestration

### Next Milestone

- Prepared user-profile caching to avoid rebuilding the same profile on every request

### Planned

- User-facing Spotify OAuth flow
- Persistent user and profile storage
- React frontend
- Deployment and production configuration

The API currently uses the repository owner's configured Spotify credentials. It is a development backend, not yet a deployed multi-user service.

## System Architecture

```text
Spotify OAuth / Web API
          │
          ▼
Spotify Data Collection
          │
          ▼
Taste Profile Preparation  ◄── future profile cache
          │
          ▼
Candidate Album Discovery
          │
          ▼
Filtering + Familiarity Scoring
          │
          ▼
Deterministic Ranking
          │
          ▼
Structured Recommendations
          │
          ├── FastAPI JSON response
          └── Command-line output
```

Profile preparation and recommendation generation are intentionally separate. The expensive Spotify collection and profile-building stage can therefore be cached later without changing candidate discovery or ranking behavior.

## Recommendation Strategy

The Spotify pipeline is currently rule-based and explainable rather than a machine-learning recommender.

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

### Familiarity and ranking

Each eligible album receives a familiarity score based on saved-album, top-track, saved-track, and recent-listening signals. Highly familiar albums are excluded.

The final recommendation score combines:

```text
60% normalized artist relevance
40% discovery value (100 - familiarity score)
```

Artist relevance uses a saturating transformation so very large raw affinity scores do not dominate the ranking. Deterministic tie-breaking makes results independent of candidate input order. The selector returns up to five albums, with no more than one album per primary artist.

## API

The FastAPI application currently exposes:

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/health` | Returns `{"status": "ok"}` |
| `POST` | `/api/recommendations` | Builds a profile and returns five structured album recommendations |
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

React and persistent database storage are planned but not yet implemented.

## Repository Structure

```text
music-recommendation-app/
├── data/
│   ├── cache/                  # External metadata caches
│   ├── processed/              # Generated cleaned/enriched datasets
│   └── raw/                    # Personal source data and Spotify responses
├── docs/
│   └── PROJECT_CONTEXT.md      # Detailed history and engineering decisions
├── models/                     # Generated model artifacts
├── notebooks/                  # Exploratory analysis
├── src/
│   ├── api/
│   │   └── main.py             # FastAPI application
│   ├── music_taste/
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
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

Do not commit `.env`, Spotify token caches, or personal listening data.

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

### Spotify CLI

```bash
source .venv/bin/activate
PYTHONPATH=src python -m music_taste.spotify.run
```

The CLI prints each album's artist, title, recommendation score, artist affinity, familiarity, explanation, and Spotify URL when available.

### Tests

```bash
source .venv/bin/activate
PYTHONPATH=src python -m pytest -q
```

The current suite uses mocks and does not need to contact Spotify.

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
- [ ] Cache prepared taste profiles with expiration and refresh behavior
- [ ] Add Spotify OAuth for arbitrary users
- [ ] Add persistent storage
- [ ] Build a React frontend
- [ ] Deploy the full application

### Recommendation quality

- [ ] Tune ranking weights against reviewed recommendation sets
- [ ] Add adjacent-artist discovery
- [ ] Evaluate additional verified recommendation signals
- [ ] Add configurable recommendation counts

### Modeling research

- [ ] Run AOTY feature-group ablation experiments
- [ ] Compare additional regression models
- [ ] Improve performance analysis across score ranges
- [ ] Investigate which Last.fm, Discogs, and album-level features add useful signal

## Purpose

This project explores how explicit album ratings and implicit Spotify listening behavior can be combined to build a personalized album-discovery platform. It brings together machine learning, recommendation systems, metadata enrichment, REST API development, testing, and an evolving full-stack architecture in one portfolio project.
