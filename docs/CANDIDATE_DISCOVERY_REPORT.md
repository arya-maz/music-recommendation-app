# Candidate Discovery and Recommendation Pipeline Report

**Evidence snapshot:** 2026-08-06  
**Scope:** current repository implementation, offline aggregate analysis of the
existing profile and candidate caches, and current official Spotify Web API
documentation. No live Spotify request was made for this report.

## Evidence labels used in this report

- **Implemented:** behavior directly visible in this repository.
- **Spotify-documented:** behavior stated in current official Spotify developer
  documentation.
- **Observed locally:** aggregate behavior measured from ignored local caches;
  it describes this snapshot, not a universal guarantee.
- **Inference:** a conclusion supported by code or aggregate evidence but not an
  API contract.
- **Unknown:** not established by the repository or official documentation.

## 1. Executive summary

The system does not ask Spotify to recommend albums. It builds its own candidate
set from artists already present in one user's Spotify activity. Profile
preparation requests the current user's top 50 artists and top 50 tracks for
Spotify's `medium_term` window, the latest 50 recently played items, and every
page of saved albums and saved tracks. Repository-defined weights turn those
signals into an `artist_scores` mapping and several sets of known/familiar album
IDs and normalized artist-title keys.

By default, candidate discovery excludes the first 10 IDs from Spotify's ranked
top-artist response, sorts every other profiled artist by repository affinity
ascending and Spotify artist ID ascending, and searches the first 25. For each,
it calls `GET /artists/{id}/albums` through Spotipy's `artist_albums`, asking for
US-market releases in the `album` group. It requests at most three pages of 10,
so the hard retrieval ceiling is 30 returned objects per selected artist and
750 across 25 artists. Spotify supplies the catalog objects and their page
order; the repository neither requests nor documents an album sort order.

During live collection, the repository removes duplicate Spotify album IDs,
albums already known by ID or normalized primary-artist/title identity, and
titles containing excluded edition terms. The surviving list—not the original
unfiltered responses—is stored in one global
`data/raw/spotify/candidate_albums.json`. On later runs, that JSON list is loaded
immediately, bypassing artist selection and album retrieval, then familiarity is
recalculated against the current profile. The candidate cache has no user key,
age, profile version, or market metadata.

Familiarity is an additive album-ID heuristic: top-track album `+35`, any saved
track `+25`, and recent album `+15`; a saved album is `100`. Scores at least 85
are removed. Every remaining candidate is scored:

```text
artist_relevance = 100 × affinity / (affinity + 50), or 0 if affinity <= 0
discovery_value = max(0, 100 - familiarity)
recommendation_score = 0.60 × artist_relevance + 0.40 × discovery_value
```

Candidates sort by recommendation score descending, raw affinity descending,
familiarity ascending, case-folded artist name, case-folded album name, then
Spotify album ID. Selection walks that ranking, keeping only the first album for
each case-insensitively normalized primary-artist name, and stops at five.
FastAPI converts the dataclasses to JSON without changing list order.

The repository controls signal weighting, filtering, scoring, sorting, and
selection. Spotify controls the contents and availability of returned catalog
objects, calculated top-item affinity, and the live order of artist-album pages;
Spotify does not disclose the internal calculation behind top-item affinity in
the referenced documentation. The consumer application's complete listening
history, internal recommendation/editorial logic, and a guarantee for artist-
album result ordering are not available here.

## 2. Complete end-to-end call graph

```text
POST /api/recommendations
  -> api.main.create_recommendations()
     -> music_taste.spotify.client.get_spotify_client()
        -> load_dotenv()
        -> SpotifyOAuth(scopes=user-top-read user-library-read
          user-read-recently-played)
        -> spotipy.Spotify(...)
     -> recommendations.get_or_prepare_user_profile(spotify_client)
        -> spotify_client.current_user()                    [GET /me]
        -> profile_cache.load_cached_profile(user ID)
           -> validate profile.pkl + metadata.json presence
           -> validate Spotify user ID, PROFILE_VERSION=1, age < 24 hours
           -> valid: unpickle and return dict
           -> invalid: delete cache entry and return None
        -> on miss/stale/invalid:
           -> recommendations.prepare_user_profile(client)
              -> fetch_data.fetch_and_save_spotify_data(client)
                 -> fetch_top_artists(limit=50, medium_term)
                 -> fetch_top_tracks(limit=50, medium_term)
                 -> fetch_recently_played(limit=50)
                 -> fetch_saved_albums(limit=50, offset pages until next=null)
                 -> fetch_saved_tracks(limit=50, offset pages until next=null)
                 -> write five ignored raw Spotify JSON files
              -> build_profile.build_taste_profile(spotify_data)
           -> profile_cache.save_cached_profile(user ID, profile)
     -> recommendations.generate_recommendations_from_profile(
          spotify_client, taste_profile, limit=5)
        -> find_candidates.find_candidate_albums(client, profile)
           -> candidate cache exists:
              -> _load_candidate_album_cache()
              -> _attach_familiarity(cached albums, profile)
           -> otherwise:
              -> _select_candidate_artist_ids(...)
              -> for each of up to 25 artists:
                 -> _fetch_artist_album_page(...)           [GET /artists/{id}/albums]
                 -> up to 3 pages × 10, album group, US market
                 -> reject duplicate ID
                 -> _is_known_album(...)
                 -> _is_unwanted_album_version(...)
                 -> append in Spotify response order
              -> _save_candidate_album_cache(filtered list)
              -> _attach_familiarity(...)
                 -> score_familiarity.calculate_album_familiarity(...)
                 -> reject should_filter=true
        -> rank_recommendations.select_final_recommendations(...)
           -> rank_candidates(full eligible list, profile)
              -> score_candidate(...) for every candidate
              -> sorted(..., key=_ranking_key)
           -> scan ranked list
           -> keep first album per case-folded primary-artist name
           -> stop at 5 unique artists or exhaustion
        -> recommendations._recommendation_from_album(...) for each selected album
        -> list[Recommendation]
     -> FastAPI/Pydantic serialization
     -> JSON array in the same order
```

`generate_recommendations(client, limit=5)` is a convenience wrapper around
`get_or_prepare_user_profile()` and `generate_recommendations_from_profile()`.
The CLI calls the two stages explicitly and prints the returned order.

## 3. User profile construction

### Spotify sources and request bounds

| Repository function | Spotipy method / Web endpoint | Parameters in code | Pagination in code |
|---|---|---|---|
| `fetch_top_artists()` | `current_user_top_artists` / `GET /me/top/artists` | 50, `medium_term` | None; one maximum-size page |
| `fetch_top_tracks()` | `current_user_top_tracks` / `GET /me/top/tracks` | 50, `medium_term` | None; one maximum-size page |
| `fetch_recently_played()` | `current_user_recently_played` / `GET /me/player/recently-played` | 50 | None; only one page |
| `fetch_saved_albums()` | `current_user_saved_albums` / `GET /me/albums` | 50 per page | Offset increments by 50 until `next` is false |
| `fetch_saved_tracks()` | `current_user_saved_tracks` / `GET /me/tracks` | 50 per page | Offset increments by 50 until `next` is false |

Spotify documents `medium_term` as approximately the last six months and says
top items are based on calculated affinity. It also offers `short_term` and
`long_term`, but this code requests neither. The endpoint limit is 50, so the
code receives at most 50 top artists and 50 top tracks even if more affinity
data exists. [Official top-items reference](https://developer.spotify.com/documentation/web-api/reference/get-users-top-artists-and-tracks)

Recently played supports cursors and a maximum page size of 50, but the code
does not follow a cursor. It therefore uses only the most recent returned page,
not all available recent history. [Official recently-played reference](https://developer.spotify.com/documentation/web-api/reference/get-recently-played)

Saved albums and tracks are exhaustively paginated as exposed by those endpoints
at request time. This is complete for the user's current saved library, not a
history of saves, removals, streams, or unsaved listening.
[Saved-albums reference](https://developer.spotify.com/documentation/web-api/reference/get-users-saved-albums) ·
[saved-tracks reference](https://developer.spotify.com/documentation/web-api/reference/get-users-saved-tracks)

### Exact artist-affinity contributions

`build_taste_profile()` accumulates floats by Spotify artist ID:

| Signal | Artist contribution | Album-memory effect |
|---|---:|---|
| Top artist rank `r`, 1–50 | `max(1, 51-r)` = 50 down to 1 | Adds artist ID to ordered `top_artist_ids` |
| Top track rank `r`, 1–50 | `0.5 × max(1, 51-r)` to **each credited track artist** = 25 down to 0.5 | Album ID/key is known; ID enters `top_track_album_ids` |
| Saved album | `+25` to **each credited album artist** | Album ID/key known; ID enters `saved_album_ids` |
| Saved track | `+10` to **each credited track artist**, per saved track | Counts saved tracks per album; enters `saved_track_album_ids` |
| Recent play | `+5` to **each credited track artist**, per returned play | Album ID/key known; ID enters `recent_album_ids` |

Repeated artists accumulate all contributions. Repeated recent plays each add
five. Multiple saved tracks from one album each add ten to every credited track
artist. Collaborators therefore receive the same per-item increment as the
primary artist; contributions are not divided among artists.

Album IDs and normalized identities are sets during construction, so repeated
evidence does not duplicate membership. Saved-track counts do preserve how many
saved tracks were encountered per album. An album with at least two saved tracks
is added to `known_album_ids` and `known_album_keys`; exactly one saved track is
not marked known at profile-build time.

Normalization lowercases the primary artist name, removes any parenthetical or
bracketed text from the album title, removes selected version words and all
punctuation, collapses whitespace, and combines `artist::album`. This can merge
editions, but it relies on the first credited artist's name and does not use an
external release-group identifier.

### Profile fields and downstream use

| Field | Candidate discovery/filtering | Familiarity | Final ranking |
|---|---|---|---|
| `artist_scores` | Selects and orders artist IDs | No | Raw affinity and normalized relevance |
| `top_artist_ids` | First 10 excluded by default | No | No |
| `known_album_ids` | Known-album exclusion | No direct use | No |
| `known_album_keys` | Normalized known-edition exclusion | No direct use | No |
| `saved_album_ids` | Helps classify saved-track-only albums | +100 | Via familiarity |
| `top_track_album_ids` | Helps classify saved-track-only albums | +35 | Via familiarity |
| `recent_album_ids` | Helps classify saved-track-only albums | +15 | Via familiarity |
| `saved_track_album_ids` | Helps classify saved-track-only albums | +25 | Via familiarity |
| `saved_track_album_counts` | Known-album edge case | Count itself is not weighted | No |

The first 10 top artists are excluded only from candidate retrieval. Their
scores still exist, and their albums can appear if an album returned for another
selected artist credits one of them as primary or collaborator; the final score
uses the returned album's first artist ID.

Most fields in Spotify's full response objects are fetched and saved but unused
by profile construction. Examples include timestamps (`added_at`, `played_at`),
play context, track duration, explicit flag, popularity, release date, markets,
genres, follower counts, images, and external URLs. Candidate response images
and external Spotify URLs are used later for output; release date, total tracks,
market list, and other catalog metadata are not ranking inputs.

## 4. Candidate artist discovery

- **Eligible universe:** every key accumulated in `artist_scores`, except IDs in
  `top_artist_ids[:10]`. This includes top-track collaborators, saved-album
  artists, saved-track artists, and recent-track artists—not just Spotify's top
  artist list.
- **Default maximum searched:** 25 (`limit_artists=25`). Not all eligible artists
  are searched when more than 25 remain.
- **Affinity threshold:** none. Any accumulated positive artist score is
  eligible; custom or malformed profiles could also contain zero/negative
  values.
- **Default ordering (`low_familiarity`):** `(artist_score ascending,
  Spotify artist ID ascending)`, followed by slicing to 25. The ID is an opaque
  deterministic tie-breaker, not an alphabetical artist-name comparison.
- **Alternate implemented mode (`adjacent`):** the same tuple in reverse, so
  both affinity and ID descend. No current API or CLI caller selects it.
- **Insertion order:** the initial dictionary order determines the unsorted
  intermediate list but not the returned default selection because an explicit
  sort follows.
- **Not used:** related artists, Spotify Recommendations, search, playlists,
  playlist co-occurrence, Last.fm, Discogs, MusicBrainz, genres, eras, or external
  ratings.

This is underexplored-discography discovery among already-observed artists, not
new-artist discovery. The phrase `low_familiarity` refers to low **artist
affinity** at this stage; album familiarity is calculated later.

## 5. Candidate album retrieval

`_fetch_artist_album_page()` calls Spotipy `artist_albums()` corresponding to
`GET /artists/{id}/albums` with:

```text
include_groups/album_type = album
market/country = US
limit = min(albums_per_request, 10) = 10 by default
offset = 0, 10, 20
```

Spotify documents `album`, `single`, `appears_on`, and `compilation` include
groups, a current maximum page size of 10, market filtering, and offset paging.
[Official artist-albums reference](https://developer.spotify.com/documentation/web-api/reference/get-an-artists-albums)

Consequences:

- Singles, EPs represented by Spotify in the `single` group, appearances, and
  compilations are excluded by the request rather than a local filter.
- Live albums, remasters, deluxe versions, soundtracks, and similarly titled
  releases can initially be returned when Spotify classifies them as `album`;
  local title filtering then removes many of them.
- At most 30 items per artist are examined. A discography with more than three
  pages is truncated even when `next` remains non-null.
- Retrieval stops earlier when a page is empty, `next` is false, or rate-limit
  handling returns `None`.
- On HTTP 429, the code retries at most three times when `Retry-After <= 60`,
  sleeping `Retry-After + 1`. For a longer wait or exhausted retries, it saves
  and uses the partial candidate list. Other Spotify errors propagate.

The endpoint documentation exposes pagination but states no sort parameter or
ordering guarantee. **Unknown:** whether live pages are consistently ordered by
release date, popularity, Spotify catalog ingestion, or another internal rule.
The code preserves item/page/artist iteration order until final ranking. A
repeat using the same JSON cache is deterministic, but that does not prove a
Spotify ordering contract.

### Candidate cache semantics

The candidate cache contains simplified album objects **after** ID, known-album,
and title-edition filters but **before** familiarity and recommendation scoring.
It preserves the JSON list order and full returned object fields. On a cache
hit, `find_candidate_albums()` does not select artists or call Spotify at all.

Important limitation: this is one global file, not keyed by Spotify user ID,
profile version, selected artist IDs, collection parameters, market, or age.
Thus a candidate pool built for one profile can be reused with another profile.
The user-profile cache is separately keyed and expires after 24 hours; candidate
cache behavior is not coupled to it.

## 6. Candidate filtering funnel

### Live collection order

| Order | File / function | Rule | Effect | Order preserved? |
|---:|---|---|---|---|
| 1 | `find_candidates.find_candidate_albums()` | Artist albums request uses only group `album`, US market, max 3×10 | Spotify omits other groups/market-ineligible or later-page items before local code sees them | Returned order retained |
| 2 | same, `seen_album_ids` | Reject an ID already appended | Excludes duplicate Spotify IDs across pages/artists | Yes |
| 3 | `_is_known_album()` | Reject ID in `known_album_ids` or normalized key in `known_album_keys` | Excludes known album/edition | Yes |
| 4 | `_is_unwanted_album_version()` | Case-insensitive substring match against 12 terms | Excludes titled edition variants | Yes |
| 5 | `_save_candidate_album_cache()` | Persist survivors | No filtering | Yes |
| 6 | `_attach_familiarity()` | Reject familiarity `>=85` | Excludes highly familiar candidates | Yes |

Excluded title substrings are: `anniversary`, `bonus`, `collector`, `deluxe`,
`expanded`, `instrumental`, `live`, `remaster`, `remastered`, `remix`, `remixed`,
and `soundtrack`. Substring matching can reject an original title containing one
of those character sequences; it does not inspect Spotify edition metadata.

Clarifications:

- There is **no candidate-to-candidate normalized-release deduplication**. Two
  different Spotify IDs with normalized-equivalent artist/title values can both
  survive unless that identity is already in the user's known keys. The README's
  broad phrase “duplicate releases” should therefore be read as ID deduplication
  plus known-edition matching, not release-group deduplication.
- Saved albums, top-track albums, recent albums, and albums with at least two
  saved tracks normally enter `known_album_ids` during profile construction and
  are removed by step 3. One saved-track-only album remains eligible and later
  receives familiarity 25.
- Missing album ID is not gracefully filtered during live collection:
  `album["id"]` raises `KeyError`. Missing `items` similarly raises. Missing
  artists can flow through some helpers and later receive affinity zero.
- Compilations/singles/EPs/appearances are request-level omissions, not local
  title filters. “Live” is only a title substring filter.

### Measurable local funnel

The existing candidate JSON begins after filters 1–4, so raw retrieval and
per-filter historical counts cannot be reconstructed from it. No claim is made
for those unavailable counts. Aggregate, read-only analysis produced:

| Observable stage | Count |
|---|---:|
| Cached post-ID/known/title-filter candidates | 94 |
| Unique non-empty Spotify album IDs | 94 |
| Removed by current-profile familiarity threshold | 0 |
| Final familiarity-eligible pool | 94 |
| Selected final recommendations | 5 |

These are **observed local snapshot values**, not expected production sizes.
The analyzer cannot recover “raw albums retrieved,” separate ID/known/title
filter losses, pages fetched, or timing because the cache does not store those
events.

## 7. Familiarity scoring

`calculate_album_familiarity()` matches only exact Spotify album IDs. It does not
normalize editions. Edition normalization affects the earlier known-album
filter, not familiarity scoring.

| Signal | Score behavior | Reason text |
|---|---:|---|
| Missing album ID | 0, label `unknown`, not filtered | `missing album ID` |
| Saved album | Sets score to 100; other signals skipped | saved album reason |
| Top-track album | +35 | contains at least one top track |
| Any saved-track album | +25 | contains at least one saved track |
| Recent album | +15 | appeared in recent listening |
| No signal | 0 | no saved, top, or recent tracks found |

Saved-track count is bucketed to presence: one saved track and ten saved tracks
both add 25. One top track and several top tracks both add 35. Repeated recent
plays do not increase album familiarity beyond 15. The score is additive except
that a saved album directly sets 100 and skips other additions, then clamped at
100.

Labels and filtering are:

| Score condition | Label | Filtered? |
|---|---|---|
| Missing ID | `unknown` | No |
| 0 | `unheard` | No |
| 1–29 | `lightly familiar` | No |
| 30–59 | `partially familiar` | No |
| 60–84 | `mostly familiar` | No |
| 85–100 | `highly familiar` | Yes |

With valid current signals, realistic values are `0, 15, 25, 35, 40, 50, 60,
75, 100`. The `85` threshold is not itself generated by these weights; saved
albums produce 100, while all three non-library signals sum to 75. Thus nine
values are possible, eight remain eligible, and missing IDs also produce numeric
zero with a different label.

Familiarity has two downstream effects: candidates at least 85 are removed, and
remaining values reduce discovery value continuously by the numeric amount.
The final sort also prefers lower familiarity after recommendation score and raw
affinity are tied.

## 8. Recommendation scoring formula

Constants in `rank_recommendations.py`:

```text
ARTIST_RELEVANCE_WEIGHT = 0.60
DISCOVERY_VALUE_WEIGHT = 0.40
ARTIST_AFFINITY_HALF_SATURATION = 50.0
```

For the first credited album artist:

```text
A = float(profile.artist_scores.get(primary_artist_id, 0))
R = 0                                      if A <= 0
R = 100 × A / (A + 50)                    otherwise
F = float(album.familiarity.score or 0)
D = max(0, 100 - F)
S = 0.60R + 0.40D
```

There is no popularity, release-date, genre, quality, album-length, or candidate
position input. The score is not rounded for sorting or JSON conversion. CLI
display formats it to two decimals, but that formatting does not alter ranking.
Familiarity is bucketed upstream; affinity can be an integer or half-integer
sum under normal inputs. `D` is lower-clamped but not upper-clamped; valid
familiarity is nonnegative. For valid nonnegative inputs, theoretical `S` lies
in `[0, 100)`, approaching but not reaching 100 because relevance asymptotically
approaches 100. Eligible normal candidates have `F <= 75`.

Worked examples:

1. **High affinity + unheard:** `A=100`, `F=0`. `R=66.6667`, `D=100`,
   `S=.6×66.6667 + .4×100 = 80.0`.
2. **Medium affinity + lightly familiar:** `A=50`, `F=25`. `R=50`,
   `D=75`, `S=.6×50 + .4×75 = 60.0`.
3. **Low affinity + partially familiar:** `A=10`, `F=35`. `R=16.6667`,
   `D=65`, `S=.6×16.6667 + .4×65 = 36.0`.

There is no fixed universal count of distinct recommendation scores because the
affinity sum has many possible values. For any one artist, however, albums can
occupy at most the eight normal eligible familiarity levels. Candidate
generation often returns many albums per artist, giving them identical affinity;
when most are unheard, large exact ties are expected.

Explanation text is also bucketed: normalized relevance at least 60 is “strong
artist-fit evidence,” at least 30 is “meaningful prior artist interest,” else
“some prior artist interest.” Familiarity zero says no album-familiarity signals,
up to 25 says low familiarity, and higher eligible values say some familiarity.

## 9. Tie analysis

The read-only `scripts/analyze_recommendation_pipeline.py` reproduced these
aggregate metrics from the current ignored caches:

| Metric | Observed value |
|---|---:|
| Eligible candidates | 94 |
| Distinct artist-affinity values | 1 |
| Affinity distribution | 10.0: 94 |
| Distinct familiarity values | 2 |
| Familiarity distribution | 0: 90; 25: 4 |
| Distinct exact recommendation scores | 2 |
| Recommendation-score distribution | 50.0: 90; 40.0: 4 |
| Largest exact-score tie | 90 (95.7%) |
| Numeric tie groups `(score, affinity, familiarity)` | 2 |
| Candidates in groups requiring text/ID tie-breaking | 94 (100%) |
| Largest numeric tie group | 90 |

The score of 50 follows directly from `A=10`, `F=0`: relevance is 16.6667,
giving 10 relevance points plus 40 discovery points. At `F=25`, discovery
contributes 30 instead of 40, yielding 40.

The dominant cause is not rounding: the scores are mathematically identical
before display formatting. In this snapshot all albums inherit the same primary-
artist affinity and only two coarse familiarity states exist. Candidate
generation is homogeneous because it selects low-affinity known artists and can
return many albums from each, while familiarity collapses all absence-of-evidence
cases to zero. Under the current inputs, candidates inside each numeric tie are
genuinely indistinguishable to the scoring model even though unmodeled qualities
may differ.

“How often alphabetical tie-breaking determines ordering” has two meanings:

- Among the current eligible pool, 100% belong to a group whose numeric fields
  tie with another candidate, so artist/album/ID fields are needed to fully order
  every group.
- Artist name is decisive only when score, affinity, and familiarity all tie and
  the normalized artist names differ. Album name is consulted only when those
  fields plus artist name tie; ID is last. The aggregate-only utility deliberately
  does not print names or reconstruct pairwise private ordering, so it does not
  report how many comparisons stop at each textual field.

## 10. Final sorting and selection

`_ranking_key()` sorts lexicographically:

1. `-recommendation_score`: descending score.
2. `-artist_affinity`: descending raw affinity.
3. `familiarity_score`: ascending familiarity.
4. normalized primary-artist name: ascending Unicode case-folded text.
5. normalized album name: ascending Unicode case-folded text.
6. normalized Spotify album ID: ascending.

The text/ID fields make results independent of candidate input order. Given the
observed tie collapse, they materially determine current within-group order,
but they never outrank different numeric scores.

`select_final_recommendations()` scans this ranked list. It case-folds the
primary artist **name**, not artist ID, to enforce uniqueness. Therefore two
different Spotify artists with identical normalized names collide, while the
same artist under meaningfully different names could evade the rule. For each
identity, the first—and thus highest-ranked—album is retained. Scanning continues
until five unique names are selected or candidates end. Ranked order is
preserved.

`_recommendation_from_album()` joins all credited artist names for display but
selection and scoring used only the first artist. It copies score, reason,
affinity, familiarity, first image URL, and Spotify URL into a frozen dataclass.
FastAPI serializes the returned list in place. The CLI enumerates it in place.
Neither layer sorts it.

## 11. Spotify-controlled and unknown behavior

### Current-user profile (`GET /me`)

The application asks only through Spotipy `current_user()` and uses `id` as its
profile-cache key. Spotify's current documentation now describes `account_id`
as immutable and preferred for account linking, while `id` should not be used
for that purpose. The repository follows its original requirement to use ID;
this is a future identity-migration consideration, not changed here.
[Official current-user reference](https://developer.spotify.com/documentation/web-api/reference/get-current-users-profile)

### Top artists/tracks (`GET /me/top/{type}`)

Spotify documents that these are based on calculated affinity and defines the
approximate time windows. **Hidden:** the affinity algorithm, play weighting,
skip/background-listening treatment, editorial adjustments, and exact update
cadence. The API returns ranks, not numeric affinity. This repository invents
its own rank-to-points transformation.

The single 50-item `medium_term` page omits artists/tracks outside Spotify's top
50 for approximately six months. It is not a complete lifetime history.

### Recently played (`GET /me/player/recently-played`)

Spotify documents a cursor-paged response and maximum page size 50. The code
requests only one page, so older recent plays are intentionally omitted by the
implementation. Podcast episodes are not supported by this endpoint. Local
files may appear as track objects, but unavailable, deleted, private, or
restricted items may be absent or represented differently; the repository has
no reconciliation logic.

### Saved albums/tracks (`GET /me/albums`, `GET /me/tracks`)

The code paginates the exposed current library. These endpoints do not provide
complete stream history or removed-library history. Market/account country can
affect availability. The code does not use `added_at`, so saving recency has no
effect.

### Artist albums (`GET /artists/{id}/albums`)

The application requests album-group releases for US market. Spotify documents
group filtering, market filtering, offset, and page size, but the reference
does not state a ranking/order guarantee. Therefore popularity, recency,
availability, ingestion, personalization, or editorial influence on order must
be treated as **unknown**, not assumed. The endpoint returns catalog data rather
than claiming to be personalized.

US-market restriction can omit regional releases. Spotify documents restriction
reasons including market, product, and explicit settings on catalog objects.
The consumer Spotify app may display data or recommendations not exposed in
these Web API responses; this repository cannot infer its internal logic.

### Recommendations, related artists, and development mode

This repository does not call Spotify's related-artist or recommendation
endpoints. Spotify announced that new Web API use cases and development-mode
apps lost access to Related Artists, Recommendations, Audio Features, Audio
Analysis, and several editorial endpoints in November 2024, while existing
extended-mode integrations were excepted.
[Official November 2024 announcement](https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api)

Current quota documentation says development mode is intended for construction
or single-account use, has an allowlist/user cap, requires Premium, and has
separate quota limits; the exact bucket limits may change. Spotify also applies
a rolling 30-second API rate limit and returns 429 responses.
[Official quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes) ·
[official rate limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits)

Spotify's 2026 documentation changed over time, including postponed endpoint-
access changes for existing integrations and July quota updates. Whether this
specific app can access a given endpoint depends on its creation date, mode,
owner status, and Spotify's current dashboard configuration—facts not stored in
the repository and not inspected here.

## 12. Effect on the project goal

Goal: recommend albums the user is likely to enjoy but has not meaningfully
explored.

| Dimension | Current strength | Current limitation |
|---|---|---|
| Familiar-artist discovery | Directly searches discographies of observed artists | Default searches the lowest-affinity 25 and excludes top 10, which may weaken fit |
| Unfamiliar-artist discovery | None | No related artists, co-occurrence, external candidate sources, or collaborative data |
| Full-album hearing | Saved album and track evidence are explainable | No lifetime play counts, completion, or album-session detection |
| Background vs genuine preference | Top-item rank may partially reflect repeat behavior | Repository cannot see skips, intent, context quality, or listening concentration |
| One track vs whole album | Saved-track evidence is represented | Presence is bucketed; one track makes the whole album 25-familiar, while many tracks do not increase it |
| Long-term history | Entire current saved library is fetched | Top data is only medium-term top 50; recent is only latest 50; removed/unsaved history is absent |
| Adjacent artists | Alternate high-affinity ordering exists | Still only searches already-profiled artists; mode is not currently used by API |
| Popularity bias | Popularity is not an explicit score | Spotify top-item calculation and catalog availability may embody unknown exposure effects |
| Alphabetical bias | Text never overrides numeric quality | Massive exact numeric ties make alphabetical fields frequently decisive within ties |
| Freshness | Profile automatically refreshes after 24 hours | Global candidate cache has no expiration, profile binding, or release refresh |
| Rate limiting | Profile cache, candidate cache, delays, and 429 retry reduce calls | Cold profile fetch exhaustively pages libraries; candidate cold run can make up to 75 album calls |
| Multi-user scale | Profile cache directories are user-keyed | OAuth is owner-oriented and candidate cache is shared globally, risking cross-user mismatch/privacy concerns |
| Genre/era diversity | One album per artist | No genre, era, geography, or catalog-distribution objective |
| Explainability | Formula and evidence labels are simple and auditable | Explanations are broad buckets and omit why the candidate source/artist was chosen |

## 13. Optimization opportunities

These are analyses, not implemented changes.

| Improvement | Expected recommendation-quality impact | API-call impact | Complexity | Current data available? | Priority |
|---|---|---:|---|---|---|
| Add aggregate score/tie monitoring | Indirect but high diagnostic value | None | Low | Yes | **P0—done as read-only utility** |
| Increase score granularity with verified existing signals | High; reduces 95.7% tie | None | Medium | Partly (rank, saved-track counts) | **P1** |
| User feedback buttons | Very high over time | None initially | Medium | No feedback yet | **P1** |
| Recommendation history / prevent repeats | High usability and exploration value | None | Medium | No persistence yet | **P1** |
| Make candidate cache profile/user/parameter-aware | High correctness/freshness | May increase correct cache misses | Medium | Yes | **P1** |
| Incremental profile refresh | Medium quality, high efficiency | Reduces calls | High | Timestamps partly available but discarded | **P1** |
| Candidate source diversification | Very high for unfamiliar artists | Medium–high | High | No | **P1/P2** |
| Artist diversity beyond one-per-artist | Medium | None | Low–medium | Yes | **P2** |
| Novelty/exploration control | High personalization | None | Medium | Yes, coarse familiarity | **P2** |
| Genre/decade controls | Medium–high diversity | None if metadata cached | Medium | Release date present; genres absent in Spotify profile | **P2** |
| Optional AOTY/CSV import | High for explicit preference grounding | None | Medium–high | Existing separate pipeline | **P2** |
| Last.fm tags | Medium; adjacent genre/style evidence | External calls | Medium | Existing enrichment experience, not Spotify candidates | **P2** |
| Discogs genres/styles | Medium; better catalog taxonomy | External calls, cacheable | Medium–high | Existing enrichment experience | **P2** |
| MusicBrainz identifiers/metadata | Medium; edition/release-group dedupe | External calls, cacheable | High | No | **P2** |
| Playlist co-occurrence | Potentially high adjacent discovery | High and access-dependent | High | No playlist collection | **P2/P3** |
| Shared artist-discography cache across users | Little direct quality; high scale efficiency | Strong reduction | Medium | Candidate objects exist | **P2**, after safe cache design |
| Album popularity signal or penalty | Ambiguous: relevance vs anti-popularity tradeoff | None if field present/reliable; current field may be deprecated/absent | Low–medium | Not reliably used | **P3 experiment** |
| Release recency | Medium freshness | None; release date present | Low | Yes | **P3 experiment** |
| Change deterministic tie-break behavior | Medium perceived variety, not stronger evidence | None | Low | Yes | **P3 after evaluation** |
| Seeded random selection within exact ties | Medium variety; reproducible per seed | None | Low | Yes | **P3 experiment** |
| Weighted random sampling among top candidates | Medium diversity, lower determinism | None | Medium | Yes | **P3 experiment** |
| Collaborative data from multiple users | Potentially very high | Indirect | Very high/privacy-sensitive | No | **P4** |

Random tie handling should follow, not substitute for, better evidence. With 90
albums tied, randomization would diversify presentation but would not make the
choice more knowledgeable.

## 14. Recommended near-term plan

### Immediate, before OAuth/frontend

1. Preserve the new aggregate analyzer as a baseline and record reviewed
   recommendation sets without raw private data in version control.
2. Add tests and documented measurements for every candidate filter, including
   a collection-stage stats object so future runs can report raw/ID/known/title
   funnel counts without printing data.
3. Correct candidate-cache identity design: bind entries to source artist,
   market, parameters, and freshness; keep per-user eligibility separate from
   reusable discography data.
4. Evaluate higher-granularity existing signals—saved-track count, source-signal
   composition, and artist evidence—against manually judged recommendation
   quality before changing weights.
5. Add recommendation-history storage design and explicit release-group/edition
   tests before broad source diversification.

### During Spotify OAuth

1. Use authorization-code PKCE or an appropriate server-side flow; never expose
   client secrets to the browser.
2. Associate token storage, profile cache, recommendation history, and logs with
   a stable user identity. Review Spotify's new `account_id` guidance and plan a
   migration from current `id` keys if appropriate.
3. Encrypt/protect refresh tokens, isolate cache directories, validate ownership,
   and support revocation/deletion.
4. Prevent concurrent requests from rebuilding the same profile or corrupting
   cache files; define per-user refresh locks.
5. Surface clear quota/re-authentication errors without leaking token details.

### During React frontend

1. Add like/dislike/not-interested/already-know controls and optional reasons.
2. Add novelty and exploration controls plus genre/decade filters that clearly
   describe their effect.
3. Show evidence-based explanations and familiarity uncertainty rather than
   presenting “unheard” as known fact.
4. Record impressions separately from clicks and feedback to prevent repeats and
   enable evaluation.
5. Provide manual refresh status without causing uncontrolled API refreshes.

### After deployment

1. Measure acceptance, already-known false negatives, repeats, diversity, and
   tie rates across consenting users.
2. A/B test deterministic versus seeded tie handling only after defining quality
   metrics.
3. Evaluate external/collaborative candidate sources against privacy, API cost,
   and incremental quality.
4. Tune weights on held-out feedback rather than the repository owner's account.
5. Monitor Spotify API/development-mode changes, quota failures, cache staleness,
   and regional availability.

## 15. Risk assessment

| Risk | Likelihood | Impact | Current mitigation | Recommended mitigation |
|---|---|---|---|---|
| Excessive API calls | Medium cold / low warm | High | 24h profile cache, global candidate cache, delays, 429 retry | Incremental refresh, request coalescing, scoped discography cache, quota telemetry |
| Stale profile | Medium | Medium | 24h TTL/versioning | Conditional/incremental refresh and visible update time |
| Stale/global candidate cache | High | High | Reuse avoids calls only | Bind cache to parameters/source artists/market; separate shared catalog from user eligibility |
| Incomplete listening data | High | High | Multiple Spotify signals | State uncertainty; add feedback/imports; do not equate no evidence with unheard |
| False unfamiliarity | High | High | Saved/top/recent/normalized-known checks | History/feedback, edition identifiers, optional explicit ratings/import |
| False familiarity | Medium | Medium | Explainable low weights | Use saved-track counts and album-level session evidence if available |
| Candidate-pool narrowness | High | High | Up to 25 known artists | Diversify sources and expose exploration control |
| Score collapse into large ties | High (95.7% observed) | High | Deterministic tie-break | Add validated granular signals; monitor tie metrics |
| Alphabetical deterministic bias | High within observed ties | Medium | Names only follow numeric fields | Improve signals; then evaluate seeded tie policy |
| Unsafe pickle loading | Medium locally; high if path writable by attacker | High | Cache path ignored/local, user-ID validation | Use non-executable schema format or signed/trusted cache; strict permissions |
| Cache privacy | Medium | High | Ignored paths; aggregate-only utilities | Encryption/permissions, retention/deletion policy, minimize raw storage |
| Token privacy | Medium | Critical | `.env` ignored; no token logging | Secure server-side token store, encryption, rotation, least scopes |
| User-data separation | High in future multi-user mode | Critical | Profile cache keyed by user ID | User-scoped auth/storage; eliminate global candidate eligibility cache |
| Regional availability mismatch | Medium | Medium | Candidate request uses US market | Use authenticated user's effective market and record it in cache key |
| Recommendation repetition | High | Medium | None | Impression/history store and repeat suppression |
| Overfitting to owner account | High | High | Rule-based explainability/tests | Multi-user evaluation and held-out feedback before tuning |
| Missing/invalid Spotify objects | Low–medium | Medium | Some `.get()` fallbacks | Validate schemas, skip malformed records with aggregate diagnostics |
| Rate-limit partial pools | Medium | Medium | Partial cache saved and reused | Mark cache incomplete; preserve retry metadata; retry later |

## Reproducing the offline aggregate analysis

```bash
source .venv/bin/activate
python scripts/analyze_recommendation_pipeline.py
```

If multiple profile directories exist:

```bash
python scripts/analyze_recommendation_pipeline.py --user-id <spotify_user_id>
```

The utility reads `cache/users/<id>/profile.pkl` and
`data/raw/spotify/candidate_albums.json`, prints aggregates only, and does not
call cache invalidation, write files, or contact Spotify. Because pickle can
execute code during deserialization, it must only be run against cache files
created and controlled by this application.

## Repository evidence inspected

- `AGENTS.md`, `README.md`, `docs/PROJECT_CONTEXT.md`
- every source file under `src/music_taste/spotify/`
- every source file under `src/music_taste/cache/`
- every source file under `src/api/`
- all files under `tests/`
- requirements and pytest configuration
- repository structure and Git status
- aggregate structure of the existing ignored profile and candidate caches

Related AOTY and original-model modules were inspected for repository context;
they do not participate in the Spotify call graph described above.
