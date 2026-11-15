"""Verify that a built viewer bundle is distributable: synthetic data only.

The real check is structural and positive:
  1. every file in the bundle is on an allowlist (index.html, assets/*.js|css, and exactly
     data/events.json + data/analysis.json), so there is no path a local-data file could take in;
  2. data/events.json and data/analysis.json are byte-identical to what the pipeline regenerates
     from the checked-in synthetic fixture, so they cannot be real-derived.
A scan for real-looking IDs and for dataset_kind "real" runs as well, but it is SUPPLEMENTAL: a
scan can only find what it knows to look for and is not proof that a bundle holds no real data.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_tracked_files import scan_dir_for_real_data  # noqa: E402
from quakeexplorer.artifacts import SYNTHETIC_CREDIT  # noqa: E402
from quakeexplorer.cli import build_to_dir  # noqa: E402
from quakeexplorer.cluster import Params  # noqa: E402

DATA_FILES = ("data/events.json", "data/analysis.json")
ASSET_SUFFIXES = {".js", ".css"}


def verify_bundle(dist: Path, fixture: Path) -> list[str]:
    problems: list[str] = []
    if not dist.is_dir():
        return [f"bundle directory does not exist: {dist}"]
    files = sorted(p.relative_to(dist).as_posix() for p in dist.rglob("*") if p.is_file())

    # 1. allowlist
    for rel in files:
        if rel == "index.html" or rel in DATA_FILES:
            continue
        if rel.startswith("assets/") and Path(rel).suffix.lower() in ASSET_SUFFIXES:
            continue
        problems.append(f"unexpected file in bundle (not on the allowlist): {rel}")

    # 2. data files equal a fresh synthetic build, byte for byte
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        build_to_dir(
            fixture,
            out,
            dataset_kind="synthetic",
            source_credit=SYNTHETIC_CREDIT,
            strict=True,
            expected_sha256=None,
            acquisition=None,
            params=Params(),
            write_build_info=False,
        )
        for rel in DATA_FILES:
            name = Path(rel).name
            target = dist / rel
            if not target.is_file():
                problems.append(f"bundle is missing {rel}")
            elif target.read_bytes() != (out / name).read_bytes():
                problems.append(f"{rel} differs from the artifact regenerated from the synthetic fixture")

    # supplemental, not proof
    problems += [f"(supplemental scan) {p}" for p in scan_dir_for_real_data(dist)]
    return problems


def main(argv: list[str]) -> int:
    dist = Path(argv[0]) if argv else ROOT / "web" / "dist"
    fixture = ROOT / "fixtures" / "synthetic_usgs.geojson"
    problems = verify_bundle(dist, fixture)
    for p in problems:
        print(f"BUNDLE FAIL: {p}", file=sys.stderr)
    if problems:
        return 1
    print(f"bundle ok: {dist} holds only the allowlisted files and synthetic demo data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
