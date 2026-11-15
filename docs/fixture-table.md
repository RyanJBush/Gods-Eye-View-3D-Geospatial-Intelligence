# Project 14 — synthetic fixture table (DRAFT for Codex review)

Status: reviewed by Codex and implemented as test fixtures. **Where this draft differs from [contract.md](contract.md), the contract wins**: shifted latitude indices run 0..36 (not 0..18; first and last bands are 2.5 degrees wide, +90 inclusive); non-finite JSON (VR12) is a file-level parse error; a non-earthquake event type is a validation case that fails a strict snapshot; duplicate IDs, strict mode, two-element coordinates, integral-float times, unsafe-URL handling and the +2.5 degree shift were all answered as proposed. The original text below is kept for the record. Fixtures are synthetic; labels encode construction intent only. No label applies to any real USGS record. All coordinates are invented.

## 1. Fixed conventions (from the audit and the Codex review)

- DBSCAN: haversine on [lat, lon] radians; eps = 250 km / 6371.0088 km; neighbourhood is `<=` eps and counts the point itself; min_samples = 4. Depth and time are excluded.
- Input sorted by event ID in UTF-8 byte order before fitting. Non-noise groups are relabelled 0, 1, 2, ... by each group's smallest member ID (UTF-8 byte order). Noise is -1.
- Primary grid: 5 deg x 5 deg, half-open [lower, upper). `lat_idx = min(floor((lat+90)/5), 35)`, so +90 falls in the top bin. `lon_idx = floor((lon_norm+180)/5)`, with `lon_norm = -180` when lon = +180, else lon. Cell ID `Gnn_mm` (nn = lat_idx, mm = lon_idx, zero-padded).
- Shifted grid (sensitivity; offset proposed here): origin shifted +2.5 deg on both axes. `lat_idx_s = floor((lat+92.5)/5)` (draft said range 0..18; corrected to 0..36 in contract C1). `lon_idx_s = floor((lon_norm+182.5)/5) mod 72`, so its seam is at 177.5 E. Cell ID `Snn_mm`.
- Margins: every in-eps pair is <= 211.3 km; every pair near the threshold on the far side is >= 300.2 km. Smallest margin to eps is 38.7 km. No fixture asserts behaviour at exactly 250 km.

## 2. Table A: geometry fixtures (56 events, in UTF-8 byte order of ID)

| ID | lat | lon | Set | Role under DBSCAN | Expected group | Grid | Shifted |
|---|---|---|---|---|---|---|---|
| fx-amb-l1 | 40.70 | 120.20 | AMB | core | 0 | G26_60 | S26_60 |
| fx-amb-l2 | 39.70 | 120.20 | AMB | core | 0 | G25_60 | S26_60 |
| fx-amb-l3 | 38.80 | 120.20 | AMB | core | 0 | G25_60 | S26_60 |
| fx-amb-l4 | 37.80 | 120.20 | AMB | border (L only) | 0 | G25_60 | S26_60 |
| fx-amb-r1 | 44.30 | 120.20 | AMB | core | 1 | G26_60 | S27_60 |
| fx-amb-r2 | 45.30 | 120.20 | AMB | core | 1 | G27_60 | S27_60 |
| fx-amb-r3 | 46.20 | 120.20 | AMB | core | 1 | G27_60 | S27_60 |
| fx-amb-r4 | 47.20 | 120.20 | AMB | border (R only) | 1 | G27_60 | S27_60 |
| fx-amb-z | 42.50 | 120.20 | AMB | AMBIGUOUS border | 0 or 1, never -1 | G26_60 | S27_60 |
| fx-chain-1 | 0.50 | 50.20 | CHAIN | core | 2 | G18_46 | S18_46 |
| fx-chain-2 | 1.40 | 50.20 | CHAIN | core | 2 | G18_46 | S18_46 |
| fx-chain-3 | 2.30 | 50.20 | CHAIN | core | 2 | G18_46 | S18_46 |
| fx-chain-4 | 3.20 | 50.20 | CHAIN | core | 2 | G18_46 | S19_46 |
| fx-chain-5 | 4.10 | 50.20 | CHAIN | border | 2 | G18_46 | S19_46 |
| fx-chain-x | 6.80 | 50.20 | CHAIN | noise (300 km past chain-5) | -1 | G19_46 | S19_46 |
| fx-chain-y | -1.30 | 50.20 | CHAIN | border (200 km from core chain-1) | 2 | G17_46 | S18_46 |
| fx-dateline-1 | -15.20 | 179.60 | DATELINE | core | 3 | G14_71 | S15_00 |
| fx-dateline-2 | -15.40 | 179.90 | DATELINE | core | 3 | G14_71 | S15_00 |
| fx-dateline-3 | -15.30 | -179.80 | DATELINE | core | 3 | G14_00 | S15_00 |
| fx-dateline-4 | -15.10 | -179.50 | DATELINE | core | 3 | G14_00 | S15_00 |
| fx-dateline-5 | -15.25 | 180.00 | DATELINE | core (source lon +180 retained) | 3 | G14_00 | S15_00 |
| fx-dense-a1 | 12.00 | 22.00 | DENSE-A | core | 4 | G20_40 | S20_40 |
| fx-dense-a2 | 12.20 | 22.10 | DENSE-A | core | 4 | G20_40 | S20_40 |
| fx-dense-a3 | 12.10 | 22.30 | DENSE-A | core | 4 | G20_40 | S20_40 |
| fx-dense-a4 | 12.05 | 22.20 | DENSE-A | core | 4 | G20_40 | S20_40 |
| fx-dense-a5 | 12.30 | 21.90 | DENSE-A | core | 4 | G20_40 | S20_40 |
| fx-dense-a6 | 12.40 | 22.40 | DENSE-A | core | 4 | G20_40 | S20_40 |
| fx-dense-b1 | -33.40 | -69.60 | DENSE-B | core | 5 | G11_22 | S11_22 |
| fx-dense-b2 | -33.20 | -69.40 | DENSE-B | core | 5 | G11_22 | S11_22 |
| fx-dense-b3 | -33.30 | -69.20 | DENSE-B | core | 5 | G11_22 | S11_22 |
| fx-dense-b4 | -33.10 | -69.50 | DENSE-B | core | 5 | G11_22 | S11_22 |
| fx-dense-b5 | -33.45 | -69.30 | DENSE-B | core | 5 | G11_22 | S11_22 |
| fx-edge-1 | 0.00 | 0.00 | EDGE | noise | -1 | G18_36 | S18_36 |
| fx-edge-2 | 10.00 | -110.00 | EDGE | noise | -1 | G20_14 | S20_14 |
| fx-edge-3 | 14.9999 | -65.0001 | EDGE | noise (pair with edge-4, ~15 m apart) | -1 | G20_22 | S21_23 |
| fx-edge-4 | 15.00 | -65.00 | EDGE | noise (pair with edge-3) | -1 | G21_23 | S21_23 |
| fx-edge-5 | -50.00 | -180.00 | EDGE | noise | -1 | G08_00 | S08_00 |
| fx-iso-1 | 45.50 | 100.50 | ISO | noise | -1 | G27_56 | S27_56 |
| fx-iso-2 | -60.20 | 10.30 | ISO | noise | -1 | G05_38 | S06_38 |
| fx-npole-1 | 89.50 | 0.00 | NPOLE | core | 6 | G35_36 | S36_36 |
| fx-npole-2 | 89.50 | 90.00 | NPOLE | core | 6 | G35_54 | S36_54 |
| fx-npole-3 | 89.50 | 180.00 | NPOLE | core (source lon +180 retained) | 6 | G35_00 | S36_00 |
| fx-npole-4 | 89.50 | -90.00 | NPOLE | core | 6 | G35_18 | S36_18 |
| fx-npole-5 | 90.00 | 0.00 | NPOLE | core (exact pole, top lat bin) | 6 | G35_36 | S36_36 |
| fx-ord-A | -25.50 | 140.50 | ORDER | noise | -1 | G12_64 | S13_64 |
| fx-ord-a | 35.50 | -80.50 | ORDER | noise | -1 | G25_19 | S25_20 |
| fx-ord-é (U+00E9) | -5.50 | -100.50 | ORDER | noise | -1 | G16_15 | S17_16 |
| fx-ord-～ (U+FF5E) | 65.50 | 20.50 | ORDER | noise | -1 | G31_40 | S31_40 |
| fx-ord-🌋 (U+1F30B) | -40.50 | 70.50 | ORDER | noise | -1 | G09_50 | S10_50 |
| fx-small-1 | -45.50 | -30.50 | SMALL | noise (3 points < min_samples) | -1 | G08_29 | S09_30 |
| fx-small-2 | -45.60 | -30.40 | SMALL | noise | -1 | G08_29 | S09_30 |
| fx-small-3 | -45.40 | -30.60 | SMALL | noise | -1 | G08_29 | S09_30 |
| fx-spole-1 | -89.50 | 30.00 | SPOLE | core (group of exactly 4) | 7 | G00_42 | S00_42 |
| fx-spole-2 | -89.50 | 120.00 | SPOLE | core | 7 | G00_60 | S00_60 |
| fx-spole-3 | -89.50 | -150.00 | SPOLE | core | 7 | G00_06 | S00_06 |
| fx-spole-4 | -90.00 | 0.00 | SPOLE | core (exact pole, bottom lat bin) | 7 | G00_36 | S00_36 |

Totals: 56 events; 40 in 8 groups (0-7); 16 noise; 1 ambiguous border (fx-amb-z).
Group sizes: 0 = 4 (+z?), 1 = 4 (+z?), 2 = 6, 3 = 5, 4 = 6, 5 = 5, 6 = 5, 7 = 4. Group 0 and 1 sizes are 5 and 4, or 4 and 5, depending on z.
Group numbering by smallest member ID: amb-l1 (0) < amb-r1 (1) < chain-1 (2) < dateline-1 (3) < dense-a1 (4) < dense-b1 (5) < npole-1 (6) < spole-1 (7). This holds whichever group z joins, because l1 and r1 sort before z.

Non-ID fields for fixture records (proposed): `time` = 1704067200000 + 3600000 x k (k = 1-based row in byte order), `depth_km` = 10.0, `mag` = 4.5, `place` = "synthetic", `updated` = null. Clustering must not depend on them.

## 3. Table B: what each set tests

| Set | Events | Purpose | Key expectation |
|---|---|---|---|
| DENSE-A | 6 | Well-separated dense group inside one grid cell | One group (4); grid cell G20_40 for all 6 |
| DENSE-B | 5 | Second dense group, southern hemisphere | One group (5); G11_22 for all 5; not merged with A |
| CHAIN | 7 | Density reachability and eps margin | chain-1..4 core, chain-5 border; y (200 km, inside) joins as border; x (300 km, outside) is noise |
| AMB | 9 | Two core components plus a border within eps of both | l1-l3 form group 0, r1-r3 form group 1 (never merged); l4, r4 are unambiguous borders; z is non-core and within eps of l1 and r1 only, so ambiguous |
| DATELINE | 5 | Spherical neighbourhood versus grid seam | One DBSCAN group; primary grid splits {1,2} in G14_71 from {3,4,5} in G14_00; shifted grid puts all five in S15_00; source lon +180 kept, grid uses -180 |
| NPOLE | 5 | Longitudes far apart but physically close; exact +90 | One group; lat 89.5 events at lons 0/90/180/-90 are within ~111 km across the pole; npole-5 (+90) lands in top lat bin (35) |
| SPOLE | 4 | Group of exactly min_samples; exact -90 | One group of 4, all core; spole-4 in bottom lat bin (0) |
| SMALL | 3 | Dense but below min_samples | All noise |
| ISO | 2 | Isolated points | Noise |
| EDGE | 5 | Grid boundaries, inclusive lower bound | edge-1 (0,0) G18_36; edge-2 (10,-110) G20_14; edge-4 (15,-65) G21_23 vs edge-3 (14.9999,-65.0001) G20_22; edge-5 (-50,-180) G08_00 |
| ORDER | 5 | UTF-8 byte order versus UTF-16 and locale order | Byte order: A, a, é, ～, 🌋. UTF-16 order would put 🌋 before ～ and is wrong |

Planar Euclidean distance on raw lon/lat would split DATELINE and NPOLE. That is a known failure mode these sets exist to catch, not a claim about any other implementation.

## 4. Table C: validation fixtures (hand-built USGS-shaped; each is its own tiny GeoJSON input)

Accepted, with nulls preserved (never coerced to zero):

| Case | Input | Expected |
|---|---|---|
| VA1 | `mag` null | Accepted; magnitude null; UI says not reported |
| VA2 | depth -1.2 (negative) | Accepted; -1.2 retained |
| VA3 | coordinates have 2 values (no depth) | Accepted; depth null (proposed; see Q4) |
| VA4 | `place` null | Accepted; place null |
| VA5 | `magType` null | Accepted; magnitude_type null |
| VA6 | `updated` null | Accepted; updated_ms null |
| VA7 | `status` null and `net` null | Accepted; both null |
| VA8 | `url` null | Accepted; no link shown |
| VA9 | `url` is `http://earthquake.usgs.gov/...`, or host `earthquake.usgs.gov.evil.example`, or `javascript:alert(1)`, or `https://earthquake.usgs.gov@evil.example/` | Event accepted; link not offered; unsafe_url warning counted (proposed; see Q8) |
| VA10 | `id` = `fx-"<img src=x onerror=alert(1)>&amp;` | Accepted; shown as literal text; never parsed as HTML and never spliced into a URL |
| VA11 | `time` = -1000 (before 1970) | Accepted; integer retained |
| VA12 | `time` = 1704069429096.0 (integral float) | Accepted; canonical integer (proposed; see Q4) |
| VA13 | extra unknown properties | Accepted; ignored, not copied |

Rejected at record level (counted with reason code; no silent repair):

| Case | Input | Reason code |
|---|---|---|
| VR1 | `id` absent | id_missing |
| VR2 | `id` empty or whitespace-only | id_empty |
| VR3 | `id` not a string (e.g. 123) | id_type |
| VR4 | `time` null or absent | time_missing |
| VR5 | `time` is a string, boolean, or 1704069429096.5 | time_invalid |
| VR6 | `geometry` null or absent | geometry_missing |
| VR7 | `geometry.type` not "Point" | geometry_type |
| VR8 | `coordinates` not an array, or length not 2 or 3 | coordinates_shape |
| VR9 | lat 90.0001 or -90.0001 | lat_out_of_range |
| VR10 | lon 180.0001 or -180.0001 | lon_out_of_range |
| VR11 | lat or lon is null, string, or boolean | coord_type |
| VR12 | JSON literal `NaN`, `Infinity` or `-Infinity` in coordinates or `mag` | nonfinite_number (see Q5) |
| VR13 | `mag` non-null but not a finite number (e.g. "4.5", true) | magnitude_invalid |
| VR14 | depth non-null but not a finite number | depth_invalid |
| VR15 | `updated` non-null but not an integral number | updated_invalid |
| VR16 | feature is not an object, or `type` is not "Feature" | feature_shape |
| VR17 | `properties` absent or not an object | properties_missing |

Whole-snapshot failures (no partial output):

| Case | Input | Reason code |
|---|---|---|
| VF1 | Two features with the same `id` | duplicate_id (report both; see Q2) |
| VF2 | `metadata.count` differs from number of features | count_mismatch |
| VF3 | `metadata` missing or `status` not 200 | metadata_invalid |
| VF4 | Invalid JSON, top level not FeatureCollection, or `features` not an array | structure_invalid |
| VF5 | More than 2,000 features (project limit, not an API guarantee) | count_limit |
| VF6 | Raw file larger than 5 MiB (project limit) | size_limit |
| VF7 | Raw SHA-256 differs from the recorded hash (frozen-snapshot mode) | hash_mismatch |
| VF8 | Zero accepted events | no_events |

## 5. Assertion policy

1. Group co-membership: all events of each expected group (0-7), except fx-amb-z, are mutual co-members; events in different groups are not.
2. Noise set is exactly these 16 IDs: fx-chain-x, fx-edge-1..5, fx-iso-1..2, fx-ord-A, fx-ord-a, fx-ord-é, fx-ord-～, fx-ord-🌋, fx-small-1..3.
3. fx-amb-z: label is 0 or 1, never -1; ambiguous-border count is exactly 1. The exact label is not asserted across implementations. A golden file may record it for the pinned environment only.
4. Relabelling: group IDs are exactly 0-7 as listed, not sklearn's raw labels.
5. Grid cells (primary and shifted) are asserted exactly against an independent oracle that uses integer or decimal arithmetic, not the same float formula as the implementation.
6. DATELINE: all five share one DBSCAN group, occupy two primary cells, and share one shifted cell. No equivalence between cells and groups is claimed.
7. Order independence: shuffled and reversed input give byte-identical output in the same pinned environment.
8. Depth and time invariance: permuting `time` and `depth_km` among events leaves assignments unchanged.
9. Agreement metrics (ARI) are not asserted on fixtures. Fixture labels test implementation behaviour only, not clustering validity.

## 6. Open questions for Codex

1. Are the 38.7 km minimum margin and the "inside 200 km / outside 300 km" probes sufficient, or should any pair sit closer to eps?
2. Duplicate IDs: hard failure of the whole snapshot (proposed), or reject later records and continue?
3. On the real frozen snapshot, should any rejected record fail the build (strict mode, proposed), with lenient mode only for fixtures?
4. Accept coordinates of length 2 (depth null), and accept integral-valued float `time` (canonicalised to integer)? Both are proposed accepts.
5. Non-standard JSON constants (`NaN`, `Infinity`): record reject (as in VR12) or whole-file parse failure?
6. Is +2.5 deg on both axes the right shifted-grid offset, and is the 72-column wrap with seam at 177.5 E acceptable?
7. Group numbering starts at 0 in ascending order of smallest byte-order member ID. Confirm.
8. Unsafe `url`: accept the event, drop the link, count a warning (proposed), or reject the record?

## 7. How this was checked

A throwaway script outside the repo computed pairwise haversine distances, neighbour counts including self, core status, and grid cells (float formula cross-checked against decimal arithmetic). It found no in-eps pairs between different sets and confirmed the core, border and noise roles above. Expected DBSCAN labels were derived by hand from those counts. No DBSCAN implementation, scikit-learn, or test suite was run.
