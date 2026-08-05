# Music Recommendation App — Codex Instructions

## Repository purpose

This repository contains related personal music-analysis and album-discovery pipelines:

1. An original 365-album music-taste model using CatBoost.
2. An Album of the Year ratings pipeline using cleaned and externally enriched ratings.
3. A Spotify album-discovery pipeline intended to recommend unfamiliar or underexplored albums.

Keep these pipelines conceptually separate unless a task explicitly requires integrating them.

## Working conventions

* Run commands from the repository root.

* Use `python3`, never `python`.

* For modules under `src/music_taste/`, use:

  ```bash
  PYTHONPATH=src python3 -m <module>
  ```

* Inspect all relevant files before editing.

* Prefer focused changes over broad rewrites.

* Preserve existing behavior unless the requested task explicitly changes it.

* Explain significant architectural or behavioral changes.

* Do not silently change scoring thresholds, model features, weighting, filtering rules, or recommendation logic.

* Update documentation when implementation behavior changes.

## Safety, privacy, and external APIs

* Never inspect, print, expose, copy, or commit values from `.env`.
* Never commit OAuth tokens, refresh tokens, API keys, or credential caches.
* Treat personal ratings, Spotify exports, listening history, and API response caches as private data.
* Do not run Spotify, Last.fm, or Discogs API requests unless the user explicitly authorizes network-backed execution.
* Do not run the Spotify entry point merely for validation because it may initiate OAuth and API collection.
* Prefer existing cached data when testing offline behavior.
* Do not delete or overwrite raw datasets, processed datasets, caches, reports, or trained models unless explicitly instructed.
* Before changing `.gitignore` or Git tracking behavior, explain which files will be affected.

## Repository layout

* `src/`

  * AOTY import, enrichment, and model-training scripts.
* `src/music_taste/`

  * Original 365-album feature engineering, CatBoost training, summaries, and error analysis.
* `src/music_taste/spotify/`

  * Spotify authentication, collection, profile construction, candidate generation, filtering, familiarity scoring, and execution.
* `data/raw/`

  * Personal source datasets and Spotify responses.
* `data/processed/`

  * Generated cleaned and enriched datasets.
* `data/cache/`

  * External metadata caches.
* `models/`

  * Generated model artifacts.
* `catboost_info/`

  * Generated CatBoost training output.
* `README.md`

  * Project history, current behavior, and roadmap.

## Main commands

### Original 365-album pipeline

```bash
PYTHONPATH=src python3 -m music_taste.inspect_data
PYTHONPATH=src python3 -m music_taste.build_features
PYTHONPATH=src python3 -m music_taste.summarize_features
PYTHONPATH=src python3 -m music_taste.train_model
PYTHONPATH=src python3 -m music_taste.analyze_model_errors
```

### AOTY pipeline

```bash
python3 src/import_aoty.py
python3 src/enrich_aoty_tags.py
python3 src/train_aoty_model.py
```

`src/enrich_aoty_tags.py` performs external Last.fm and Discogs requests. Do not run it without explicit authorization.

### Spotify pipeline

```bash
PYTHONPATH=src python3 -m music_taste.spotify.run
```

This command may initiate Spotify OAuth and make API requests. Do not run it without explicit authorization.

## Current pipeline behavior

### AOTY pipeline

* `import_aoty.py` cleans and normalizes exported AOTY ratings.
* Discogs provides album genre and style information.
* Last.fm provides album runtime and track count.
* Discogs genres and styles are represented through one flexible `Genres` field.
* `train_aoty_model.py` currently evaluates a Ridge regression pipeline against a mean baseline.
* The AOTY model is evaluated but is not currently persisted as a reusable trained model.

### Spotify pipeline

* Spotify data is converted into artist-affinity and known-album information.
* Candidate generation excludes the top 10 artists by default.
* The default candidate mode currently prioritizes lower-affinity eligible artists.
* Known albums and undesirable album editions are filtered.
* Familiarity is calculated separately from candidate generation.
* The final candidate list is not yet ranked with a combined recommendation score.
* Avoid changing identity normalization because profile construction and candidate filtering depend on consistent album matching.

## Validation expectations

For ordinary offline changes:

1. Parse or import changed modules where safe.
2. Run relevant offline tests or scripts.
3. Do not trigger authentication or external API calls.
4. Review `git diff`.
5. Report:

   * files changed;
   * behavior changed;
   * validation performed;
   * validation not performed and why.

There is currently no established automated test suite. When adding tests, prioritize pure offline logic such as:

* album-title normalization;
* known-album matching;
* candidate deduplication;
* undesirable-edition filtering;
* familiarity thresholds;
* artist selection and affinity ordering;
* genre parsing;
* AOTY schema validation.

## Change discipline

Before editing:

1. Read the relevant implementation and callers.
2. State the intended behavior.
3. Identify files likely to change.

After editing:

1. Run appropriate offline validation.
2. Show a concise diff summary.
3. Identify remaining risks or untested paths.
4. Do not commit or push unless explicitly asked.

## Documentation

Keep `README.md` aligned with actual implementation.

In particular, verify documentation accurately describes:

* Discogs versus Last.fm enrichment responsibilities;
* current candidate artist-selection behavior;
* what recommendation details are printed;
* completed candidate filtering;
* current Ridge versus CatBoost model usage;
* which frontend, backend, and database components are planned versus implemented.
