# Artist Affinity Investigation

**Evidence snapshot:** 2026-08-06  
**Method:** repository trace plus aggregate-only analysis of the existing ignored
Spotify response, profile, and candidate caches. No Spotify request was made and
no recommendation behavior was changed.

## Executive conclusion

Artist affinity does **not** become 10 through normalization, rounding, scoring,
or an assignment later in the recommendation pipeline. The cached taste profile
contains 534 artists across 81 distinct affinity values, ranging from 5 to 2600
in this snapshot. The collapse happens because the default candidate selector
chooses the lowest-affinity eligible artists from a highly discrete low end:

- 3 selected artists have affinity 5;
- 22 selected artists have affinity 10;
- 283 eligible artists tie at affinity 10, so only 22 of them are selected;
- the 3 affinity-5 artists have no albums in the surviving cached pool;
- all 94 cached candidates have primary artists with affinity 10.

The raw source decomposition is exact for this snapshot:

- every one of the 283 affinity-10 artists received one saved-track contribution
  of `+10` and no other contribution;
- every selected affinity-10 artist has that same provenance;
- every primary artist represented in the cached candidate list has that same
  provenance;
- each of the three affinity-5 artists received one recent-play contribution of
  `+5` and no other contribution.

Thus “all surviving candidates are affinity 10” is primarily a consequence of
intentional lowest-affinity candidate selection interacting with coarse low-end
evidence and the observed retrieval/filter outcome. It is not an intentional
rule that forces 10, and no downstream code mutates affinity. The exact reason
the three affinity-5 artists yield no cached albums cannot be recovered because
the candidate cache stores only albums surviving retrieval-time filters.

## 1. Where affinity is calculated

Affinity is created in
`src/music_taste/spotify/build_profile.py::build_taste_profile()`.
`artist_scores` is a `defaultdict(float)` keyed by Spotify artist ID. The
function iterates five Spotify datasets and adds contributions. It returns a
plain dictionary in the taste profile:

```python
{
    "artist_scores": dict(artist_scores),
    ...
}
```

The value is read later in two places:

1. `find_candidates._select_candidate_artist_ids()` uses it to order and select
   artists for album retrieval.
2. `rank_recommendations._artist_affinity()` reads the first credited album
   artist's ID and performs `float(artist_scores.get(artist_id, 0.0))`.

No intermediate function recalculates or writes an album-specific affinity.

## 2. Exact affinity formula

For artist `a`, the implemented score is:

```text
A(a) = Σ top-artist contribution
     + Σ top-track contribution
     + Σ saved-album contribution
     + Σ saved-track contribution
     + Σ recent-play contribution
```

Exact contributions are:

| Evidence | Per-occurrence contribution to every credited artist |
|---|---:|
| Top artist at rank `r`, 1–50 | `max(1, 51-r)` = 50, 49, ..., 1 |
| Top track at rank `r`, 1–50 | `0.5 × max(1, 51-r)` = 25, 24.5, ..., 0.5 |
| Saved album | `25` |
| Saved track | `10` |
| Recently played track | `5` |

For top tracks, saved albums, saved tracks, and recent tracks, every credited
artist receives the full contribution. It is not divided among collaborators.
Repeated saved tracks and repeated recent plays add repeatedly. Duplicate artist
IDs therefore accumulate evidence rather than being deduplicated.

### Current affinity-10 provenance

The ignored raw responses contain 50 top artists, 50 top tracks, 114 saved
albums, 2,590 saved tracks, and 50 recent items. Recomputing contribution
provenance from those cached inputs showed:

```text
all 283 affinity-10 artists = {saved_track: 10.0} only
selected 22 affinity-10 artists = {saved_track: 10.0} only
19 cached primary artists = {saved_track: 10.0} only
selected 3 affinity-5 artists = {recent: 5.0} only
```

This is not an inference from the total: each component was reconstructed from
the locally cached source lists and matched to the built profile by artist ID.

## 3. Possible affinity values and granularity

Affinity is an additive, unnormalized raw score.

- It is **not continuous** in the mathematical sense.
- It is **not normalized** during profile construction.
- It is **not explicitly bucketed**, but its fixed contribution increments make
  it discrete.
- Under normal fetched inputs, every possible total is a positive multiple of
  `0.5`, because `0.5` is the smallest contribution unit.
- A built-profile artist cannot normally have zero: an ID enters the mapping only
  when a positive contribution is added. Downstream lookup can return `0.0` for
  a missing primary artist ID.
- There is no fixed global upper bound in the algorithm. Saved albums and saved
  tracks are fully paginated and repeated contributions accumulate. The actual
  upper bound depends on the user's library and returned data.

The profile's 81 observed values are:

```text
5, 10, 13, 15, 19, 20, 25, 28, 30, 30.5, 40, 50, 51, 57, 60,
70, 80, 85, 90, 92, 93, 94, 98, 100, 107.5, 110, 118, 120, 130,
139.5, 140, 145, 150, 153, 155, 160, 170, 172, 180, 185, 194,
210, 224, 230, 240, 250, 260, 266, 275, 283, 285, 290, 293.5,
305, 316, 320, 329, 334, 381, 402, 430, 432, 449, 496, 506,
571, 620, 624, 763, 795, 893, 903, 932, 1025, 1112, 1431,
1776, 1822, 2267, 2382.5, 2600
```

Some high values belong to top-10 artists later excluded from candidate
selection, so the eligible post-exclusion set does not contain every value.

Final recommendation scoring does normalize affinity with a saturating formula,
but only after candidates have survived:

```text
artist_relevance = 100 × affinity / (affinity + 50)
```

That transformation preserves equality: every affinity-10 candidate becomes
the same relevance value, `16.666...`. It does not cause the original tie.

## 4. Affinity distribution at every observable stage

### Stage A — immediately after `build_taste_profile()`

```text
Artists: 534
Distinct affinity values: 81
Minimum: 5
Maximum: 2600
```

The low end, which matters for default candidate selection, is:

| Affinity | Artist count |
|---:|---:|
| 5 | 3 |
| 10 | 283 |
| 13 | 1 |
| 15 | 2 |
| 19 | 1 |
| 20 | 68 |
| 25 | 1 |
| 28 | 1 |
| 30 | 38 |
| 30.5 | 2 |
| 40 | 24 |
| 50 | 14 |

The remaining 67 values account for the remaining artists, mostly with very
small counts per value. The full observed value list is recorded above.

### Stage B — after excluding the top 10

`_select_candidate_artist_ids()` removes `top_artist_ids[:10]` before sorting:

```text
Eligible artists: 524
Affinity-5 artists: 3
Affinity-10 artists: 283
```

None of the low-end 5 or 10 values is removed by the top-10 exclusion.

### Stage C — after candidate artists are selected

Default selection sorts by:

```text
(artist_scores[artist_id] ascending, Spotify artist ID ascending)
```

and takes the first 25:

| Affinity | Selected artist count |
|---:|---:|
| 5 | 3 |
| 10 | 22 |

This is the first severe collapse. The 25-artist limit is exhausted inside the
283-way affinity-10 boundary tie. Spotify artist ID—not additional taste
evidence—chooses which 22 affinity-10 artists proceed.

### Stage D — after album retrieval, before local filters

**Unavailable from current evidence.** The live function filters each returned
album inline and only then appends it to `raw_candidate_albums`. No unfiltered
artist-album responses or per-stage counters are persisted. Therefore the
following cannot be distinguished retrospectively:

- an affinity-5 artist returned no `album`-group US-market objects;
- its objects occurred after the three-page retrieval cap;
- every returned object was already known;
- every returned object matched an excluded edition-title term;
- a partial rate-limited collection ended before reaching it.

Any claim choosing one of these explanations would be speculation.

### Stage E — after ID, known-album, and title-edition filtering

The candidate JSON is the earliest persisted post-retrieval observation:

```text
Cached albums: 94
Distinct primary artist IDs: 19
Album-affinity distribution: 10 = 94 albums
```

Seventeen of the 19 cached primary artist IDs are also in the currently computed
25-artist selection; two are not. This is possible because the candidate cache
is global and not keyed by profile, selected artist set, timestamp, or
parameters, and because an album returned for a queried artist can have a
different first credited artist. The cache does not retain queried-source artist
provenance, so those causes cannot be separated.

All 19 cached primary artists currently have exactly the same evidence
composition: one saved-track contribution worth 10.

### Stage F — after familiarity filtering

Familiarity removes no cached album in this snapshot:

| Affinity | Surviving albums |
|---:|---:|
| 10 | 94 |

Therefore familiarity filtering does not create or deepen the affinity tie.

### Stage G — immediately before recommendation scoring

`generate_recommendations_from_profile()` passes those same 94 albums to
`select_final_recommendations()`. Immediately before `score_candidate()`:

| Affinity | Candidate count |
|---:|---:|
| 10 | 94 |

`score_candidate()` reads affinity from the profile by each album's primary
artist ID. It does not copy a cached affinity field and does not change the
profile.

## 5. Exact stage where the surviving pool becomes all 10

The selected artist set is still mixed at Stage C: three artists at 5 and 22 at
10. The first observable all-10 pool is Stage E, the list after album retrieval
and the inline duplicate-ID, known-album, and edition-title filters.

The transition therefore occurs somewhere within the combined retrieval/filter
funnel between Stages C and E. Current cache design prevents attribution to one
substep. Importantly, the transition occurs through **absence of surviving
albums from affinity-5 artists**, not because any affinity is reassigned from 5
to 10.

Classification:

| Possible explanation | Finding |
|---|---|
| Intentional design choice to force affinity 10 | **No.** No such rule exists. |
| Limitation of affinity calculation | **Contributing.** Low-evidence artists receive coarse fixed increments; 283 artists are indistinguishable at one saved track. |
| Consequence of candidate selection | **Primary cause.** Ascending selection fills 22/25 positions from the giant affinity-10 group. |
| Retrieval/filter outcome | **Necessary final step.** The only selected lower-affinity artists yield no persisted survivors. Exact subfilter unknown. |
| Unintended affinity mutation | **No.** The value is read unchanged throughout. |
| Candidate-cache side effect | **Potential provenance/currentness issue, not the cause of value 10.** The cache is global and includes two primary IDs outside the current selected set, but all independently resolve to 10. |

## 6. Would more granular affinity improve ranking?

Simply allowing more decimal places, changing float precision, or replacing the
saturation formula would not help. The 283 artists are tied because their
underlying modeled evidence is identical: exactly one saved track and no other
profile signal. The current affinity calculation is already capable of 0.5-unit
resolution and produces 81 distinct totals elsewhere in the profile.

Making affinity genuinely more granular would require adding distinctions to
that single saved-track observation—for example saved-track recency, repeated
listening evidence, the track's rank in another signal, or independently
validated album/artist context. Under the current data:

- saved-track **count per artist** would not distinguish these 283 artists;
  each has one contribution;
- normalized artist relevance would remain tied for any artists whose raw input
  remains 10;
- selecting the lowest 25 would still concentrate on the low boundary, even if
  modest new variation existed;
- large album-level ties would remain because all albums from one primary artist
  share one affinity and most have familiarity zero.

Granular evidence could improve ordering inside the 283-artist boundary, but it
would not by itself solve album ties within an artist or the narrowness created
by selecting only the lowest-affinity artists. Its benefit depends on whether
the new distinctions correlate with actual recommendation quality; granularity
alone is not quality.

## 7. Recommended next modification

No change is implemented by this investigation.

Before changing quality logic, the most useful correctness step is to persist
aggregate collection-funnel counters and queried-source artist provenance. That
would distinguish “no albums returned” from each local filter and reveal whether
the global cache reflects the current selection.

For recommendation quality, the highest-impact next experiment is **candidate-
artist source diversification across affinity bands**, evaluated against a
manually reviewed recommendation set. A stratified or hybrid selection could
retain discovery value while including artists with more than a single weak
signal. This targets the actual collapse earlier than recommendation scoring.
Only after that should the project test more granular saved-track evidence.

Rationale:

1. The full profile already contains 81 affinity values; the scorer is not
   globally starved of numeric variety.
2. Default selection intentionally discards nearly all of that variety and
   stops inside a 283-way low-end tie.
3. Every surviving artist has only one weak saved-track signal.
4. No scoring-weight change can recover evidence that candidate generation
   excluded.
5. More detailed saved-track weighting may reorder the low-evidence group but
   needs validation to show it predicts album enjoyment rather than merely
   producing different numbers.

The recommended experiment would change candidate selection and therefore must
be separately specified, tested, and reviewed; it should not be slipped into an
affinity-calculation refactor.
