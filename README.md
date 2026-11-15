# Earthquake Cluster Explorer

A local, descriptive and historical view of **one frozen USGS earthquake snapshot** (events with M4.5+ from 2024-01-01 to 2024-02-01, one query). A reproducible Python analysis assigns DBSCAN groups and grid cells. A 3D globe and an accessible table share one selection and show every source field, including missing ones.

**This is not a forecast, a hazard estimate, or a validated seismological model.** DBSCAN groups are algorithmic groupings of map proximity, not ground truth. A month mixes mainshocks, aftershocks and unrelated seismicity, and catalogue completeness varies by region.

Contract and decisions: [docs/contract.md](docs/contract.md). Reviewed fixtures: [docs/fixture-table.md](docs/fixture-table.md). Work log: [docs/implementation-log.md](docs/implementation-log.md).

## Real data stays local

The real snapshot and everything derived from it live only in git-ignored local paths: `data/raw/`, `data/derived/`, `reports/local/`. Redistribution terms for this multi-contributor extract are unresolved, so it is not in any tracked file, CI artifact, log or distributable build. Confirm applicable catalogue and contributor terms before any public release. Source credit: U.S. Geological Survey, Earthquake Hazards Program / ANSS ComCat.

How that is kept true (two separate paths, enforced in code):

- **Distributable path.** `npm run build` and the demo use the synthetic fixture only. The build plugin ([web/plugins/data-separation.ts](web/plugins/data-separation.ts)) emits exactly two data files from `web/demo-data/`, and refuses them unless their raw-source hash equals the SHA-256 of the checked-in fixture, so a real artifact is rejected even if mislabelled. Nothing is copied implicitly (`publicDir` is off).
- **Local real-data path.** `npm run local` starts the Vite *dev server* in `--mode local-data`, which serves `data/derived/` at `/local-data/*` straight from disk. That mode can never run a build, and no other mode serves those URLs. Nothing real is copied into `web/`, and the `real` pipeline command writes only under `data/` and `reports/local/`.
- **Checks.** `scripts/verify_bundle.py web/dist` checks a built bundle against an allowlist of files and byte-compares its data with a fresh regeneration from the fixture. `scripts/check_tracked_files.py` fails if reserved paths or real-looking IDs are tracked. Scans for IDs and `dataset_kind: real` run too, but they are **supplemental**: a scan only finds what it knows to look for and is not proof. The structural checks are the guarantee. Focused tests: `web/tests/separation.test.ts`, `tests/test_bundle.py`.
- A real-data view carries a banner: for this computer only, do not share, publish or bundle it. Do not screenshot or share the local viewer.

## Setup (Python 3.13, Node 22.12+)

```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock
```

Set `PYTHONPATH=src` (PowerShell: `$env:PYTHONPATH='src'`) for the commands below.

## Tests

```bash
.venv/Scripts/python -m pytest -q
cd web && npm ci && npm test
```

`requirements.lock` is the full tested set; `requirements.in` lists the direct pins (scikit-learn 1.7.2, pytest 8.4.2).

## Run on synthetic fixtures (no real data)

```bash
python -m quakeexplorer build --input fixtures/synthetic_usgs.geojson --out-dir web/demo-data --dataset-kind synthetic
cd web && npm run build && npm run preview
python ../scripts/verify_bundle.py dist
```

Then open http://127.0.0.1:4173. The page shows a "Synthetic fixture data" banner. `web/demo-data/` is generated and git-ignored.

## Run on the local real snapshot

Place the raw response at `data/raw/usgs-2024-01_m4.5.geojson` with its hash in `data/raw/usgs-2024-01_m4.5.geojson.sha256` and acquisition notes in `data/raw/provenance.local.json`. Then:

```bash
python -m quakeexplorer real
cd web && npm run local
```

Then open http://127.0.0.1:5174/?data=local. `real` validates in strict mode (any rejected record fails with no partial output), checks the recorded SHA-256, builds twice and compares bytes, and writes `data/derived/` and `reports/local/evaluation.md`. It never re-fetches and copies nothing into `web/`. The viewer additionally refuses to join `events.json` to an analysis unless the SHA-256 of the loaded `events.json` bytes equals the `events_sha256` recorded in `analysis.json`. `?data=local` against a built bundle (`npm run preview`) finds nothing, by design.

## Layout

| Path | Purpose |
|---|---|
| `src/quakeexplorer/` | validation, grid, DBSCAN, metrics, artifacts, evaluation, CLI |
| `tests/` | pytest suite built from the reviewed fixture table (the independent oracle) |
| `fixtures/synthetic_usgs.geojson` | invented, USGS-shaped input; regenerate with `scripts/make_fixtures.py` |
| `web/` | Vite + TypeScript + Three.js viewer, no backend, no map tiles, no API key |

## Viewer notes

- One selection controller is shared by the globe, table and inspector. Table rows are real buttons: Tab to the list, then arrow keys, Home and End move and select; the table works with no WebGL.
- Marker shape and color both encode the group, and the table and legend carry text labels. Size encodes magnitude only.
- Text is inserted with `textContent`. A link is offered only for an https URL on exactly `earthquake.usgs.gov` with no credentials or port.
- Production builds carry a Content-Security-Policy that allows only same-origin requests.
- On `pagehide` the globe and table are disposed. If the browser restores the page from the back-forward cache (`pageshow` with `persisted`), they are rebuilt and the selection is restored. A page that is really going away also drops the selection.
- `?webgl=off` forces the no-WebGL fallback for testing. It simulates the failure; it is not a real WebGL-less browser.

## Limits and what is not claimed

No hosted CI result, no OS-level offline test, no real WebGL-unavailable browser test, no screen-reader or usability study, and no performance or memory measurement exist yet. See the implementation log for what was actually run.
