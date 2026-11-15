# Earthquake Cluster Explorer

A local, descriptive and historical view of **one frozen USGS earthquake snapshot** (events with M4.5+ from 2024-01-01 to 2024-02-01, one query). A reproducible Python analysis assigns DBSCAN groups and grid cells. A 3D globe and an accessible table share one selection and show every source field, including missing ones.

[Open the public synthetic demo](https://ryanjbush.github.io/project-14-earthquake-explorer/). The public demo uses invented fixture points, not real earthquakes.

**This is not a forecast, a hazard estimate, or a validated seismological model.** DBSCAN groups are algorithmic groupings of map proximity, not ground truth. A month mixes mainshocks, aftershocks and unrelated seismicity, and catalogue completeness varies by region.

Contract and decisions: [docs/contract.md](docs/contract.md). Reviewed fixtures: [docs/fixture-table.md](docs/fixture-table.md). Work log: [docs/implementation-log.md](docs/implementation-log.md).

## Real data stays local

The real snapshot and everything derived from it live only in git-ignored local paths: `data/raw/`, `data/derived/`, `reports/local/`. Redistribution terms for this multi-contributor extract are unresolved, so it is not in any tracked file, CI artifact, log or distributable build. Confirm applicable catalogue and contributor terms before any public release. Source credit: U.S. Geological Survey, Earthquake Hazards Program / ANSS ComCat.

How that is kept true (two separate paths, enforced in code):

- **Distributable path.** `npm run build` and the demo use the synthetic fixture only. The build plugin ([web/plugins/data-separation.ts](web/plugins/data-separation.ts)) emits exactly two data files from `web/demo-data/`, and refuses them unless their raw-source hash equals the SHA-256 of the checked-in fixture, so a real artifact is rejected even if mislabelled. Nothing is copied implicitly (`publicDir` is off).
- **Local real-data path.** `npm run local` starts the Vite *dev server* in `--mode local-data`, which serves `data/derived/` at `/local-data/*` straight from disk. That mode can never run a build, and no other mode serves those URLs. Nothing real is copied into `web/`, and the `real` pipeline command writes only under `data/` and `reports/local/`.
- **Checks.** `scripts/verify_bundle.py web/dist` checks a built bundle against an allowlist of files and byte-compares its data with a fresh regeneration from the fixture. `scripts/check_tracked_files.py` fails if reserved paths or real-looking IDs are tracked. Scans for IDs and `dataset_kind: real` are supplemental; neither they nor the allowlist can prove arbitrary future code or assets contain no real data. Review changes before sharing. Focused tests: `web/tests/separation.test.ts`, `tests/test_bundle.py`.
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

On the prepared Windows installation, double-click **Launch Explorer.pyw** (or the desktop shortcut). It starts the local viewer without opening a terminal. The shortcut depends on this project folder, Python and Node remaining installed on this computer.

Place the raw response at `data/raw/usgs-2024-01_m4.5.geojson` with its hash in `data/raw/usgs-2024-01_m4.5.geojson.sha256` and acquisition notes in `data/raw/provenance.local.json`.

The original candidate came from this [USGS FDSN query](https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2024-01-01T00%3A00%3A00&endtime=2024-02-01T00%3A00%3A00&minmagnitude=4.5&eventtype=earthquake&orderby=time-asc). It was retrieved approximately 2026-11-15 06:03–06:04 UTC: 623 records, 442,192 bytes, SHA-256 `317e64198ba71405719e2ac0e177e18bb79c92b0ecc07c43a26a471ce083edfe`. Both query endpoints are inclusive. Because the catalog is revised, downloading the URL again may produce different data or bytes; an exact reproduction requires the original verified bytes, which are not distributed in this repository. To run the pipeline:

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
- Coastlines are bundled offline from Natural Earth 1:110m coastline v4.1.0, source repository commit `ca96624a56bd078437bca8184e78163e5039ad19`, file SHA-256 `851f581ff5ffb844deed8ae1a9ce22e3c4bb3d74fa342cadb5d8e39b41ae7c3c`. Natural Earth describes its data as [public domain](https://www.naturalearthdata.com/about/terms-of-use/); this separate data asset is not covered by the project's MIT code license.

## Limits and what is not claimed

Hosted CI passed for commit `c775b23` ([workflow run](https://github.com/RyanJBush/project-14-earthquake-explorer/actions/runs/43692802108)). The table fallback was also checked in headless Chrome with WebGL disabled. No OS-level offline test, genuine back-forward-cache restore, screen-reader or usability study, or performance or memory measurement exists yet. See the implementation log for what was actually run.

## License

Original project code is available under the [MIT License](LICENSE). This license does not cover the USGS snapshot or third-party dependencies; see their respective terms.
