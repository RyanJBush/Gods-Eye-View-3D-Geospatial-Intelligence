# Implementation log

Real-data results are intentionally not recorded here (they stay in the ignored `reports/local/evaluation.md`). Nothing below is a hosted CI result.

## Session 1 (local, Claude Code desktop)

- Start: 2026-11-15T07:00:45Z. End: 2026-11-15T07:18:03Z. Wall-clock 17 min 18 s including tool latency; not a human labour measurement. Earlier audit and review sessions are untimed or timed separately (audit 2 min 20 s, Codex response 42 s), so cumulative effort cannot be computed precisely.
- Scope: contract corrections, Python pipeline, pytest suite, local real-snapshot run, Three.js viewer, Vitest, browser checks, CI file, README. Nothing committed, no remote, nothing pushed or published.

### Contract changes made (full text in contract.md)

C1 shifted latitude 0..36 with short first and last bands, +90 inclusive; C2 non-earthquake event type fails a strict snapshot; C3 non-finite JSON is a file-level parse error (also number overflow and duplicate keys); C4 ARI examples for both noise conventions; C5 determinism asserted after UTF-8 ID sort, golden label for the ambiguous border pinned to this pipeline only. Review answers applied as given, including the JS-safe timestamp range (|t| <= 8.64e15 ms).

Implementation-time choices not spelled out in the review (flag if Codex disagrees):

1. Events and analysis are separate artifacts (`events.json` source-only, `analysis.json` keyed by ID and source hash), as in the review response, so the audit draft's cluster fields on events were dropped.
2. A missing or null `properties.type` is its own reason, `event_type_missing`.
3. Non-string, non-null `place`, `magType`, `status`, `net` reject the record (`*_invalid`); a non-string `url` is treated as unsafe (null plus warning) rather than rejected.
4. Strings with lone surrogates are rejected, because canonical UTF-8 output cannot encode them.
5. `build-info.json` holds the only wall-clock metadata and is excluded from deterministic hashes.
6. The shifted grid reports its own occupancy and ARI; the primary grid remains the baseline.

### Checks actually run (2026-11-15, Windows, Python 3.13.7, Node 22.19.0)

| Check | Result |
|---|---|
| `pytest` (scikit-learn 1.7.2, pytest 8.4.2 in a fresh `.venv`) | 395 passed |
| `vitest` 5.1.0 (no jsdom) | 32 passed |
| `tsc --noEmit` and `vite build` 8.3.6 | clean; build output is one 579 kB JS chunk (Vite size warning, not addressed) |
| Real snapshot, strict validation against recorded SHA-256 | all 623 features accepted, 0 rejected; hash matched |
| Real snapshot rebuilt twice | `events.json` and `analysis.json` byte-identical across the two runs, same environment |
| Evaluation with the predeclared eps x min_samples set | written to ignored `reports/local/evaluation.md`; parameters fixed before results were seen |
| Tracked-file guard, run over every untracked non-ignored file | no violations (nothing is tracked yet because no commit exists) |
| Bundle scan of `web/dist` built from synthetic data | no real data found |
| Browser (Claude built-in browser, production preview on localhost) | globe rendered; a real click on a marker selected the matching event and table row; table click selected the same event, centred it on the globe and filled the inspector; arrow keys, Home and End moved and selected rows; noise filter worked; missing values show "Not reported"; page-hide disposed all 15 tracked GPU resources and removed the canvas, and was idempotent; all requests in the network log were same-origin; real snapshot loaded 623 rows with a link offered only for an https earthquake.usgs.gov URL |
| `?webgl=off` | table-only mode; selection and inspector still work |

### Not done or not verified

- Hosted CI has not run; `.github/workflows/ci.yml` is untested. Action versions use major tags and were not verified.
- Offline behavior: the CSP and the network log show only same-origin requests, but the machine's network was not disabled, so this is not an OS-level offline proof.
- WebGL fallback was exercised with the `?webgl=off` switch, not a browser without WebGL.
- GPU memory was not measured; the dispose check counts tracked resources only.
- No accessibility audit, screen-reader test or usability study; keyboard behavior was exercised through synthetic key events in one browser.
- Window-resize and WebGL context-loss handlers exist but were not exercised.
- No timing or memory measurements; no Windows/Linux byte comparison.
- Coastlines were cut as planned. Redistribution terms and the reference-code license remain unresolved; no code was copied from the reference repository.
- jsdom is not used. A clean `npm ci` (after deleting `node_modules`, about 07:19Z) succeeded, then build and the 32 Vitest tests passed again; this was local only, not CI.
- Checkpoints at 4 h, 8 h, 12 h were not reached; scope was not changed.

## Session 2: fixes for Codex re-review findings 1 to 3

- Start: 2026-11-15T07:45:42Z. End: 2026-11-15T07:52:01Z (time of the last check run; this log edit followed). About 6 min 19 s wall-clock including tool latency, not a human labour measurement. Nothing committed, no remote, nothing pushed or published; real data was never copied outside `data/` and `reports/local/`.
- Superseded from session 1: the documented `real --viewer-dir web/public/data` flow copied real-derived artifacts into `web/public/data`, so a normal build could place them in `web/dist`. That option and the `web/public` directory are gone.

### Changes

1. **Local real data separated from distributable builds.**
   - `web/plugins/data-separation.ts` (new): a production build emits only `data/events.json` and `data/analysis.json`, read from `web/demo-data/`, and fails unless the artifact's raw-source hash equals the SHA-256 of `fixtures/synthetic_usgs.geojson` (so a mislabelled real artifact is refused), the analysis hash fields agree, and `dataset_kind` is synthetic. The dev server serves `/data/*` from the same verified directory, and serves `/local-data/*` from `data/derived/` only in `--mode local-data`. A build in that mode throws. Vite reserves the mode name `local`, hence `local-data`.
   - `web/vite.config.ts`: `publicDir: false`, plugin wired in. `web/package.json`: `npm run local` (dev server, mode `local-data`, port 5174). `web/src/load.ts`: `?data=local` selects `./local-data/`, the default is `./data/`. `web/src/main.ts`: real-data banner "for this computer only".
   - `src/quakeexplorer/cli.py`: `real` no longer has `--viewer-dir` and writes only under `data/derived/` and `reports/local/`.
   - `scripts/verify_bundle.py` (new): positive allowlist of bundle files, byte comparison of the two data files with a fresh regeneration from the fixture, then the ID and `dataset_kind` scan labelled supplemental. CI now runs it instead of the scan alone.
   - `.gitignore`, `.github/workflows/ci.yml`, `README.md` updated to describe and enforce the actual behavior. `@types/node@22.20.5` added (dev dependency) so the plugin typechecks.
   - Tests: `web/tests/separation.test.ts` (real Vite builds and a real dev server against temp dirs) and `tests/test_bundle.py`.
2. **events.json verified against the analysis.** `web/src/integrity.ts` and `web/src/load.ts`: the loaded `events.json` bytes are hashed with Web Crypto and compared with `analysis.events_sha256` before any join; a mismatch or a missing or malformed hash is a `DatasetError` with an explicit message. Regression tests in `web/tests/integrity.test.ts` use two artifacts with the same raw-source hash and different canonical bytes, a whitespace-only re-serialisation, and a case proving the hash error wins over join errors.
3. **Back-forward cache lifecycle.** `web/src/lifecycle.ts` (new `ViewLifecycle`): `pagehide` always releases the globe, table and subscription but keeps the selection; `pageshow` with `persisted` rebuilds both and restores the selection; a non-persisted `pagehide` also drops the selection. All paths are idempotent. `web/src/main.ts` uses it, and the WebGL context-lost path calls `dropGlobe`. Tests in `web/tests/lifecycle.test.ts` use fake parts and simulated calls.

### Commands run and observed results (Windows, Python 3.13.7, Node 22.19.0)

| Command | Observed |
|---|---|
| `vitest run` | 4 files, 60 tests passed (was 32) |
| `tsc --noEmit`, `vite build` | clean |
| `pytest -q` | 408 passed (was 395) |
| `python scripts/verify_bundle.py web/dist` | bundle held `index.html`, one JS, one CSS, `data/events.json`, `data/analysis.json`; verified |
| `vite build --mode local-data` | failed with the intended message; no output directory created |
| `python -m quakeexplorer real` | strict validation and hash check passed; two builds byte-identical; no copy into `web/` |
| Tracked-file guard over all untracked, non-ignored files (59) | no violations |
| Browser, production preview (localhost:4173) | default load synthetic, 56 rows; `/local-data/events.json` returned 404 with the explanatory text; `?data=local` showed "No dataset found" with the hint and no viewer state |
| Browser, `npm run local` (localhost:5174) | `?data=local` loaded the real snapshot, 623 rows, real-data banner; `/data/events.json` served synthetic and `/local-data/events.json` real; this load passed the events-bytes hash check in a real fetch, which also confirms Python and browser hash the same bytes |
| Browser, simulated lifecycle (dispatched `pagehide`/`pageshow` events with `persisted: true`, 3 cycles) | hidden: 0 canvases, 0 table rows, 0 listeners, 0 tracked resources, selection kept; shown: 1 canvas, 56 rows, 1 listener, 15 resources, same selection and inspector; table click works after restore; non-persisted `pageshow` did not stack a second view |
| Browser, real back navigation (away to a JSON URL, then back) | navigation type `back_forward`, but a JS marker set before leaving was gone and no pagehide log survived, so the page was reloaded, not restored from the back-forward cache. The fresh load was healthy (1 mount, 1 canvas, 1 listener). **A genuine bfcache restoration was not observed.** |

### Remaining limitations

- Back-forward cache: the restore path is covered by unit tests and simulated events only. This embedded browser did not use the cache, so a genuine restoration has not been observed.
- The events-hash check detects mismatched pairs and corruption; it is integrity, not authenticity. Someone who replaces both files consistently passes it. Web Crypto needs localhost or https; elsewhere the viewer refuses with an explicit error.
- `npm run local` is a dev server with no Content-Security-Policy. It is for this computer only.
- `verify_bundle.py` regenerates the synthetic artifacts in the current environment, so demo data built under different Python or scikit-learn versions will not byte-match; regenerate `web/demo-data/` first.
- The ID and `dataset_kind` scans are supplemental by design; the guarantees are the allowlist, the fixture-hash requirement and the refused local-mode build.
- Still not observed: hosted CI, OS-level offline behavior, a genuinely WebGL-less browser (the `?webgl=off` switch only simulates it), accessibility audit, performance or memory.

## Session 3: GitHub handoff (Codex)

- 2026-11-15, 08:03:30–08:06 UTC approximately: about 2.5 minutes wall-clock to this checkpoint, including tool and CI wait time, not a human labor measurement. Earlier Claude sessions include untimed work, so cumulative actual effort remains unknown.
- Confirmed the tracked-file guard passed and local raw data, derived artifacts, and evaluation reports were ignored. Added the agreed MIT license for original code and clarified the limits of bundle checks; committed as `c775b23`.
- Created the private GitHub repository and verified its visibility before pushing. The first hosted [CI run](https://github.com/RyanJBush/project-14-earthquake-explorer/actions/runs/43692802108) passed the guard, analysis, and web jobs on `c775b23`. It used the synthetic fixture only.
- Started the local viewer on loopback. A browser loaded the real-data view with a canvas and 623 table rows; no real records were pushed. No genuine no-WebGL browser, OS-level offline test, or genuine back-forward-cache restore was observed in this session. Earlier limitations remain applicable, except hosted CI is now verified for the stated commit.
