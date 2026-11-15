"""Command line: build, evaluate, real. Real-data outputs go only to ignored local paths."""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .artifacts import (
    SYNTHETIC_CREDIT,
    USGS_CREDIT,
    build_analysis_artifact,
    build_events_artifact,
    environment_versions,
    serialise,
)
from .canonical import dumps, sha256_hex
from .cluster import DEFAULT_EPS_KM, DEFAULT_MIN_SAMPLES, Params
from .evaluate import evaluate, render_markdown
from .validate import SnapshotError, validate_snapshot

REAL_RAW = Path("data/raw/usgs-2024-01_m4.5.geojson")
REAL_PROVENANCE = Path("data/raw/provenance.local.json")


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _print_error(exc: SnapshotError) -> None:
    print("VALIDATION FAILED", file=sys.stderr)
    for err in exc.errors:
        print(f"  [{err['scope']}] {err['code']}: {err.get('detail')}", file=sys.stderr)


def build_to_dir(
    input_path: Path,
    out_dir: Path,
    *,
    dataset_kind: str,
    source_credit: str,
    strict: bool,
    expected_sha256: str | None,
    acquisition: dict[str, Any] | None,
    params: Params,
    write_build_info: bool = True,
) -> dict[str, str]:
    raw = input_path.read_bytes()
    vr = validate_snapshot(raw, strict=strict, expected_sha256=expected_sha256)
    events_doc = build_events_artifact(
        vr, dataset_kind=dataset_kind, source_credit=source_credit, acquisition=acquisition
    )
    events_bytes, events_sha = serialise(events_doc)
    analysis_doc = build_analysis_artifact(events_doc, events_sha, params)
    analysis_bytes, analysis_sha = serialise(analysis_doc)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "events.json").write_bytes(events_bytes)
    (out_dir / "analysis.json").write_bytes(analysis_bytes)
    if write_build_info:
        info = {
            "built_utc": _utc_now(),
            "input": str(input_path),
            "strict": strict,
            "params": {"eps_km": params.eps_km, "min_samples": params.min_samples},
            "environment": environment_versions(),
            "note": "wall-clock metadata; excluded from deterministic hashes",
        }
        (out_dir / "build-info.json").write_bytes(dumps(info))
    return {"events_sha256": events_sha, "analysis_sha256": analysis_sha, "raw_sha256": vr.raw_sha256}


def _read_expected_hash(path: Path) -> str | None:
    side = path.with_name(path.name + ".sha256")
    if side.exists():
        return side.read_text(encoding="ascii").split()[0].lower()
    return None


def _load_acquisition(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _cmd_build(args: argparse.Namespace) -> int:
    credit = args.source_credit or (USGS_CREDIT if args.dataset_kind == "real" else SYNTHETIC_CREDIT)
    try:
        hashes = build_to_dir(
            Path(args.input),
            Path(args.out_dir),
            dataset_kind=args.dataset_kind,
            source_credit=credit,
            strict=not args.lenient,
            expected_sha256=args.expected_sha256,
            acquisition=_load_acquisition(Path(args.provenance) if args.provenance else None),
            params=Params(args.eps_km, args.min_samples),
        )
    except SnapshotError as exc:
        _print_error(exc)
        return 2
    print(json.dumps(hashes, indent=2))
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    doc = json.loads(Path(args.events).read_text(encoding="utf-8"))
    ev = evaluate(doc["events"], doc["provenance"]["raw"]["sha256"])
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation.json").write_bytes(dumps(ev))
    (out / "evaluation.md").write_text(render_markdown(ev), encoding="utf-8")
    print(f"wrote {out / 'evaluation.json'} and {out / 'evaluation.md'}")
    return 0


def _cmd_real(args: argparse.Namespace) -> int:
    """Regenerate everything for the local real snapshot, twice, and compare bytes."""
    raw_path = Path(args.input)
    expected = _read_expected_hash(raw_path)
    if expected is None:
        print(f"missing sidecar hash {raw_path}.sha256", file=sys.stderr)
        return 2
    prov = Path(args.provenance)
    acquisition = _load_acquisition(prov if prov.exists() else None)
    derived = Path("data/derived")
    runs = [derived / "run-a", derived / "run-b"]
    results = []
    try:
        for run in runs:
            if run.exists():
                shutil.rmtree(run)
            results.append(
                build_to_dir(
                    raw_path,
                    run,
                    dataset_kind="real",
                    source_credit=USGS_CREDIT,
                    strict=True,
                    expected_sha256=expected,
                    acquisition=acquisition,
                    params=Params(DEFAULT_EPS_KM, DEFAULT_MIN_SAMPLES),
                )
            )
    except SnapshotError as exc:
        _print_error(exc)
        return 2
    same_files = all(
        (runs[0] / name).read_bytes() == (runs[1] / name).read_bytes()
        for name in ("events.json", "analysis.json")
    )
    print(json.dumps({"results": results, "byte_identical_across_two_runs": same_files}, indent=2))
    if not same_files:
        print("NOT REPRODUCIBLE", file=sys.stderr)
        return 3
    for name in ("events.json", "analysis.json", "build-info.json"):
        shutil.copyfile(runs[0] / name, derived / name)
    doc = json.loads((derived / "events.json").read_text(encoding="utf-8"))
    ev = evaluate(doc["events"], doc["provenance"]["raw"]["sha256"])
    (derived / "evaluation.json").write_bytes(dumps(ev))
    report_dir = Path("reports/local")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "evaluation.md").write_text(render_markdown(ev), encoding="utf-8")
    # Nothing is copied anywhere else. The viewer reads data/derived directly through
    # `npm run local` (dev server only); real-derived files never go into web/ or any bundle.
    print("real-data artifacts written under data/derived and reports/local (all git-ignored)")
    print("view locally: cd web && npm run local, then open /?data=local")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="quakeexplorer")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="validate input and write events.json + analysis.json")
    b.add_argument("--input", required=True)
    b.add_argument("--out-dir", required=True)
    b.add_argument("--dataset-kind", choices=("real", "synthetic"), required=True)
    b.add_argument("--source-credit")
    b.add_argument("--lenient", action="store_true", help="report rejected records instead of failing (fixtures only)")
    b.add_argument("--expected-sha256")
    b.add_argument("--provenance", help="JSON file with acquisition notes")
    b.add_argument("--eps-km", type=float, default=DEFAULT_EPS_KM)
    b.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    b.set_defaults(func=_cmd_build)

    e = sub.add_parser("evaluate", help="descriptive evaluation and sensitivity grid")
    e.add_argument("--events", required=True)
    e.add_argument("--out-dir", required=True)
    e.set_defaults(func=_cmd_evaluate)

    r = sub.add_parser("real", help="local real snapshot: build twice, compare, evaluate (ignored paths)")
    r.add_argument("--input", default=str(REAL_RAW))
    r.add_argument("--provenance", default=str(REAL_PROVENANCE))
    r.set_defaults(func=_cmd_real)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
