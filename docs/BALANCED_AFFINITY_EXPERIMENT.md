# Experimental Balanced-Affinity Recommendation Strategy

## Status

`balanced_affinity` is an opt-in experimental final-selection strategy. The
existing `lowest_affinity` implementation remains the default and its behavior
is unchanged. No taste-profile weights, candidate retrieval rules, filters,
familiarity values, recommendation scores, or artist-uniqueness rules changed.

## Purpose

The experiment represents two intended experiences:

- **Discovery:** albums from artists near the bottom of the eligible candidate
  pool's affinity distribution.
- **Expansion:** underexplored albums from artists with clearer prior-interest
  evidence, while avoiding the most familiar affinity tail when possible.

It runs after candidate generation and filtering. It cannot introduce an artist
that the existing candidate finder did not retrieve.

## Configuration

Named constants live in
`src/music_taste/spotify/rank_recommendations.py`:

```text
DEFAULT_RECOMMENDATION_STRATEGY = "lowest_affinity"
DISCOVERY_PERCENTILE_MAX = 30.0
EXPANSION_PERCENTILE_MIN = 50.0
EXPANSION_PERCENTILE_MAX = 90.0
DISCOVERY_RECOMMENDATION_COUNT = 3
EXPANSION_RECOMMENDATION_COUNT = 2
```

Callers opt in through `generate_recommendations()` or
`generate_recommendations_from_profile()`:

```python
recommendations = generate_recommendations_from_profile(
    spotify_client,
    taste_profile,
    limit=5,
    strategy="balanced_affinity",
)
```

The FastAPI endpoint and CLI omit this argument and therefore retain the
baseline.

## Percentile calculation and bands

Percentiles are calculated from album rows in the complete eligible candidate
pool, as requested—not from the full taste profile. Affinities are assigned
tie-aware average empirical ranks on a 0–100 scale. Equal affinities always get
the same percentile; they are never split arbitrarily across bands. A pool with
one affinity value assigns 50 to every candidate.

- Discovery: percentile `<= 30`.
- Expansion: percentile `>= 50` and `<= 90`.
- Other: candidates between bands or above 90, used only as fallback when
  necessary.

The 50th–90th range targets artists with more evidence than the lowest tail.
The highest 10% is intentionally omitted from the normal allocation because
those artists are most likely to be heavily represented in the user's existing
listening. This is an experimental interpretation, not proof of album
familiarity; album familiarity remains a separate unchanged signal.

## Ranking, randomization, and selection

Each band is ordered by:

1. recommendation score descending;
2. familiarity score ascending;
3. random order only when both preceding values are exactly equal.

Randomization never moves a lower-scoring candidate above a higher-scoring one.
It replaces artist/album alphabetical ordering only inside exact numeric ties in
the experimental path. An optional `random.Random` instance makes tests and
analysis reproducible; production opt-in calls use normal process randomness.

Selection first requests three unique discovery artists and then two unique
expansion artists. If either allocation cannot be filled, a final numeric-ranked
pass over the remaining eligible pool fills the result. The selector returns
fewer than five only when fewer than five unique eligible artist names exist.
The returned five are stably re-sorted by score descending and familiarity
ascending without randomizing across bands.

## Offline comparison utility

```bash
python scripts/analyze_recommendation_pipeline.py \
  --compare-strategies \
  --seed 42
```

It prints both named recommendation lists with score, raw affinity, affinity
percentile, familiarity, and explanation, followed by:

- average affinity;
- affinity-percentile spread;
- recommendation-score spread;
- number of represented affinity bands;
- list overlap.

The seed is optional. Omitting it allows tie selections to vary between runs.

## Current cached-data comparison

Using the same 94 cached eligible albums and seed 42:

| Statistic | Baseline | Balanced |
|---|---:|---:|
| Recommendations | 5 | 5 |
| Average affinity | 10.0 | 10.0 |
| Affinity-percentile spread | 0.0 | 0.0 |
| Recommendation-score spread | 0.0 | 0.0 |
| Unique affinity bands | 1 | 1 |
| Overlap | \- | 0 of 5 |

All 94 candidate albums have affinity 10, so tie-aware percentile ranking assigns
all of them percentile 50. The discovery band has no members; expansion and
fallback fill the result. Both selected lists contain score-50, familiarity-0
albums in this seeded comparison. Balanced selection changes which exact ties
are shown but does not increase measurable affinity or score diversity.

## Advantages and disadvantages

### Baseline `lowest_affinity`

Advantages:

- unchanged, deterministic, extensively tested behavior;
- maximizes the current discovery-oriented candidate source;
- stable output is easy to reproduce and debug.

Disadvantages:

- current candidate generation already concentrates at the lowest affinity;
- very large exact ties fall through to alphabetical fields;
- it does not guarantee representation from moderately familiar artists.

### Experimental `balanced_affinity`

Advantages:

- explicit discovery/expansion allocations when the pool has affinity variety;
- score and familiarity remain quality gates;
- avoids deterministic alphabetical dominance within exact band ties;
- gracefully fills five results when a band is sparse;
- bounds, allocation, and random seed are testable and tunable.

Disadvantages:

- results can vary between calls without a seed;
- candidate-row percentiles can be influenced by artists with larger surviving
  discographies;
- percentile bands cannot repair a homogeneous upstream pool;
- randomness creates variety, not new evidence of quality;
- the current API does not expose strategy choice to clients.

## Evaluation conclusion

Synthetic tests demonstrate that a heterogeneous pool yields the intended three
discovery/two expansion allocation, maintains score-first ordering, preserves
unique artists, excludes the highest tail during normal allocation, and fills
from the remaining pool when necessary.

The current real cached pool cannot demonstrate improved affinity diversity or
recommendation quality. It demonstrates only reduced deterministic tie bias and
different tied albums. A valid quality comparison requires either a candidate
pool generated from multiple affinity bands or a future upstream candidate-
artist experiment. Therefore the balanced strategy should remain opt-in until
recommendations are reviewed on heterogeneous pools.
