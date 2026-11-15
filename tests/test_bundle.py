import json
import shutil
import sys
from pathlib import Path

import pytest

from fixture_builder import collection, dump, feature, table_geojson_bytes
from quakeexplorer.cli import build_to_dir, main
from quakeexplorer.cluster import Params

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from verify_bundle import verify_bundle  # noqa: E402

FIXTURE = ROOT / "fixtures" / "synthetic_usgs.geojson"


def _synthetic_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "assets" / "app.css").write_text("body{}", encoding="utf-8")
    build_to_dir(FIXTURE, dist / "data", dataset_kind="synthetic", source_credit="Synthetic fixture data. Not real earthquakes.",
                 strict=True, expected_sha256=None, acquisition=None, params=Params(), write_build_info=False)
    return dist


def test_good_synthetic_bundle_passes(tmp_path):
    assert verify_bundle(_synthetic_dist(tmp_path), FIXTURE) == []


def test_extra_local_data_directory_is_rejected_by_allowlist(tmp_path):
    dist = _synthetic_dist(tmp_path)
    (dist / "local-data").mkdir()
    (dist / "local-data" / "events.json").write_text("{}", encoding="utf-8")
    problems = verify_bundle(dist, FIXTURE)
    assert any("local-data/events.json" in p and "allowlist" in p for p in problems)


@pytest.mark.parametrize("name", ["assets/extra.json", "assets/app.js.map", "data/build-info.json", "notes.txt", "data/other.json"])
def test_any_non_allowlisted_file_fails(tmp_path, name):
    dist = _synthetic_dist(tmp_path)
    (dist / name).write_text("{}", encoding="utf-8")
    assert any(name in p for p in verify_bundle(dist, FIXTURE))


def test_real_style_data_in_place_of_the_demo_data_fails_structurally(tmp_path):
    """A mislabelled or differently-built artifact with no recognisable ID is still refused,
    because the data must equal a regeneration from the fixture, not merely pass a scan."""
    dist = _synthetic_dist(tmp_path)
    other = tmp_path / "other.geojson"
    other.write_bytes(dump(collection([feature("zz-opaque-1", 10, 10), feature("zz-opaque-2", 10.1, 10.1, k=2)])))
    build_to_dir(other, dist / "data", dataset_kind="synthetic", source_credit="Synthetic fixture data. Not real earthquakes.",
                 strict=True, expected_sha256=None, acquisition=None, params=Params(), write_build_info=False)
    problems = verify_bundle(dist, FIXTURE)
    assert any("differs from the artifact regenerated" in p for p in problems)
    assert not any("supplemental" in p for p in problems)  # the scan alone would NOT have caught it


def test_tampered_analysis_or_missing_file_fails(tmp_path):
    dist = _synthetic_dist(tmp_path)
    (dist / "data" / "analysis.json").write_bytes(b"{}\n")
    assert any("analysis.json differs" in p for p in verify_bundle(dist, FIXTURE))
    (dist / "data" / "events.json").unlink()
    assert any("missing data/events.json" in p for p in verify_bundle(dist, FIXTURE))


def test_supplemental_scan_is_labelled_and_still_runs(tmp_path):
    dist = _synthetic_dist(tmp_path)
    (dist / "assets" / "app.js").write_text('"dataset_kind":"real"', encoding="utf-8")
    assert any(p.startswith("(supplemental scan)") for p in verify_bundle(dist, FIXTURE))


def test_missing_bundle_directory(tmp_path):
    assert verify_bundle(tmp_path / "nope", FIXTURE)


def test_real_command_has_no_viewer_copy_option(capsys):
    with pytest.raises(SystemExit) as ei:
        main(["real", "--viewer-dir", "web/public/data"])
    assert ei.value.code == 2
    assert "--viewer-dir" in capsys.readouterr().err


def test_real_command_writes_only_ignored_locations(tmp_path, monkeypatch, capsys):
    """Run `real` in a scratch cwd (with the synthetic fixture standing in for the snapshot)."""
    monkeypatch.chdir(tmp_path)
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "usgs-2024-01_m4.5.geojson").write_bytes(table_geojson_bytes())
    import hashlib
    (raw / "usgs-2024-01_m4.5.geojson.sha256").write_text(hashlib.sha256(table_geojson_bytes()).hexdigest() + "  x\n", encoding="ascii")
    assert main(["real"]) == 0
    created = {p.relative_to(tmp_path).parts[:2] for p in tmp_path.rglob("*") if p.is_file()}
    top_dirs = {parts[0] for parts in created}
    assert top_dirs == {"data", "reports"}  # nothing under web/ or anywhere distributable
    assert {parts[1] for parts in created if parts[0] == "data"} <= {"raw", "derived"}
    assert not (tmp_path / "web").exists()
    out = capsys.readouterr().out
    assert "npm run local" in out and json.loads(out[: out.index("real-data artifacts")])["byte_identical_across_two_runs"] is True
