# Project 14 — data and analysis contract (v1)

Status: implementation contract after Codex review of the synthetic fixture table (2026-11-15). Descriptive and historical only. Nothing here is a forecast, a hazard estimate, or a validated seismological model.

## 1. Changes from the reviewed fixture-table draft

| # | Change | Where it applies |
|---|---|---|
| C1 | Shifted latitude index is `floor((lat+92.5)/5)`, range **0..36** (not 0..18). Band 0 covers [-92.5, -87.5), so only [-90, -87.5) holds data (2.5 deg, short). Band 36 covers [87.5, 92.5), so only [87.5, +90] holds data (2.5 deg, short), and **+90 is inclusive** with no clamp. Shifted longitude is `floor((lon_norm+182.5)/5) mod 72`; all 72 columns are full width, with the seam at 177.5 E. | grid |
| C2 | `properties.type` must be exactly `"earthquake"`. Absent or null gives `event_type_missing`; any other value (explosion, quarry blast, ...) gives `event_type_not_earthquake`. Strict frozen-snapshot validation fails the whole snapshot; nothing is treated as an earthquake by default. | validation |
| C3 | `NaN`, `Infinity`, `-Infinity`, and numbers that overflow to infinity (e.g. `1e999`) are **invalid JSON** and fail at parse time with a file-level error (`nonfinite_json`). There is no record-level reason for them. Duplicate object keys are also a file-level parse error (`invalid_json`). Case VR12 is now file-level. | validation |
| C4 | ARI is checked on small hand-specified partitions with expected scores for both noise conventions. These verify the metric code only. | tests |
| C5 | Determinism: shuffled and reversed inputs give identical outputs after the pipeline sorts by UTF-8 byte order of ID, in the same pinned environment. The ambiguous border may belong to either component in a general implementation; its golden label is asserted only for this pinned pipeline. | tests |

## 2. Decisions taken from the review answers

- 38.7 km minimum margin to eps is sufficient for the fixture set.
- Duplicate IDs fail the whole snapshot and report every index.
- Any rejected record in a strict (frozen real snapshot) run fails with no partial output. Lenient mode exists for fixtures and reports rejections.
- A two-element `coordinates` array is accepted and depth is retained as null. An integral numeric `time` such as `1704069429096.0` is accepted and normalised to an integer. Booleans and fractional values are rejected.
- Timestamp range consumed by JavaScript: integers with `|t| <= 8_640_000_000_000_000` ms (the range of a valid JS `Date`; tighter than `Number.MAX_SAFE_INTEGER`). Outside it gives `time_out_of_range` / `updated_out_of_range`. Values are exact in a JS `number` because that bound is below 2^53.
- +2.5 deg shift on both axes with 72-column longitude wrap is accepted.
- Groups are numbered from 0 by smallest member ID in UTF-8 byte order; noise is -1.
- Unsafe `url`: accept the event, set `url` to null, count an `unsafe_url` warning. A link is offered only for a parsed `https` URL with hostname exactly `earthquake.usgs.gov`, no credentials, no explicit port, no control characters or whitespace. The viewer re-checks the same rule.

## 3. Input

USGS FDSN GeoJSON FeatureCollection. File-level checks, in order: size <= 5 MiB (`size_limit`); SHA-256 equals the recorded hash when one is supplied (`hash_mismatch`); valid JSON without non-finite numbers (`invalid_json`, `nonfinite_json`); object with `type == "FeatureCollection"` and a `features` array (`structure_invalid`); `metadata.status == 200` (`metadata_invalid`); `metadata.count` equals the number of features (`count_mismatch`); at most 2,000 features (`count_limit`; project limit, not an API guarantee); no duplicate IDs (`duplicate_id`); at least one accepted event (`no_events`).

Record-level reason codes: `feature_shape`, `id_missing`, `id_type`, `id_empty`, `id_invalid_unicode`, `properties_missing`, `event_type_missing`, `event_type_not_earthquake`, `time_missing`, `time_invalid`, `time_out_of_range`, `updated_invalid`, `updated_out_of_range`, `geometry_missing`, `geometry_type`, `coordinates_shape`, `coord_type`, `lat_out_of_range`, `lon_out_of_range`, `depth_invalid`, `magnitude_invalid`, `place_invalid`, `magnitude_type_invalid`, `status_invalid`, `net_invalid`. Warning code: `unsafe_url`.

Longitude range [-180, 180] is valid, with the source value retained. Depth may be negative. Nulls are never coerced to zero.

## 4. Artifacts

All JSON is canonical: UTF-8, sorted keys, no whitespace, `allow_nan=False`, trailing newline. Wall-clock metadata lives only in `build-info.json`, which is never part of a deterministic hash.

1. **`events.json`** (schema `quake-events/1`), source-only: `provenance` plus `events`, sorted by UTF-8 byte order of `id`. Event fields: `id`, `origin_time_ms`, `updated_ms`, `longitude_deg`, `latitude_deg`, `depth_km`, `magnitude`, `magnitude_type`, `place`, `status`, `net`, `url`. No cluster or grid fields.
2. **`analysis.json`** (schema `quake-analysis/1`), keyed by event ID, with `source_raw_sha256`, `events_sha256`, algorithm name, versions, parameters, and per-event `cluster`, `role` (core, border, noise), `ambiguous_border`, `grid_cell`, `shifted_cell`.
3. **`evaluation.json` / `evaluation.md`**, descriptive results and the sensitivity table, one per source hash.
4. **`build-info.json`**, UTC build time and command, not deterministic.

Real-data versions of all four stay local and ignored (`data/derived/`, `web/public/data/`, `reports/local/`).

## 5. Analysis

- DBSCAN: scikit-learn, `metric="haversine"`, `algorithm="ball_tree"`, inputs `[lat, lon]` in radians, `eps = eps_km / 6371.0088`, neighbourhood `<=` eps counts the point itself. Primary parameters **eps 250 km, min_samples 4**, fixed before any real result was seen.
- Input is sorted by UTF-8 byte order of ID before fitting. Relabelling: non-noise groups numbered 0, 1, ... in order of each group's smallest member ID. Relabelling fixes names only, not order-sensitive border membership.
- Ambiguous border: a non-core point within eps of core points from two or more distinct core components.
- Primary grid: 5 deg x 5 deg, half-open bins, `lat_idx = min(floor((lat+90)/5), 35)`, `lon_idx = floor((lon_norm+180)/5)`, `lon_norm = -180` when lon = +180. Computed with exact decimal arithmetic on the shortest repr of each float.
- Shifted grid: see C1.
- Agreement (descriptive only, never accuracy): ARI of DBSCAN labels against grid cells. Primary convention: each noise event is its own singleton. Secondary: all noise is one group. Coverage (share of events not noise) and noise fraction are reported with both.
- Predeclared sensitivity set: eps in {150, 250, 400} km x min_samples in {3, 4, 5}; plus the shifted grid. Declared before real results were inspected; no "best" setting is selected.

## 6. Limits and non-claims

One month of one catalogue query (minimum magnitude 4.5, event type earthquake, 2024-01-01 to 2024-02-01). A month mixes mainshocks, aftershocks and unrelated seismicity. Catalogue completeness varies by region. Cluster IDs are arbitrary names, not scientific ground truth. Grid cells have unequal physical area. No prediction, hazard, accuracy or usability claim is made.
