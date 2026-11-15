import json
import sys
from pathlib import Path

from fixture_builder import collection, dump, feature, table_geojson_bytes
from quakeexplorer.cli import main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from check_tracked_files import scan_dir_for_real_data  # noqa: E402


def test_build_synthetic_strict_writes_separate_artifacts(tmp_path, capsys):
    src = tmp_path / "in.geojson"
    src.write_bytes(table_geojson_bytes())
    out = tmp_path / "out"
    assert main(["build", "--input", str(src), "--out-dir", str(out), "--dataset-kind", "synthetic"]) == 0
    events = json.loads((out / "events.json").read_text(encoding="utf-8"))
    analysis = json.loads((out / "analysis.json").read_text(encoding="utf-8"))
    assert events["provenance"]["dataset_kind"] == "synthetic"
    assert events["provenance"]["counts"]["accepted"] == 56
    assert analysis["source_raw_sha256"] == events["provenance"]["raw"]["sha256"]
    assert "build-info.json" in {p.name for p in out.iterdir()}
    # wall-clock metadata never enters the deterministic artifacts
    assert "built_utc" not in (out / "events.json").read_text(encoding="utf-8")
    assert "built_utc" not in (out / "analysis.json").read_text(encoding="utf-8")


def test_strict_failure_exit_code_and_no_partial_output(tmp_path, capsys):
    src = tmp_path / "in.geojson"
    src.write_bytes(dump(collection([feature("a", 1, 2), feature("b", 1, 2, props={"type": "explosion"})])))
    out = tmp_path / "out"
    assert main(["build", "--input", str(src), "--out-dir", str(out), "--dataset-kind", "synthetic"]) == 2
    assert not out.exists()
    assert "event_type_not_earthquake" in capsys.readouterr().err


def test_lenient_reports_rejections_in_provenance(tmp_path):
    src = tmp_path / "in.geojson"
    src.write_bytes(dump(collection([feature("a", 1, 2), feature("b", 1, 2, props={"type": "explosion"})])))
    out = tmp_path / "out"
    assert main(["build", "--input", str(src), "--out-dir", str(out), "--dataset-kind", "synthetic", "--lenient"]) == 0
    counts = json.loads((out / "events.json").read_text(encoding="utf-8"))["provenance"]["counts"]
    assert counts["accepted"] == 1 and counts["rejected"] == 1
    assert counts["rejected_by_reason"] == {"event_type_not_earthquake": 1}


def test_hash_mismatch_exit_code(tmp_path):
    src = tmp_path / "in.geojson"
    src.write_bytes(table_geojson_bytes())
    assert main(["build", "--input", str(src), "--out-dir", str(tmp_path / "o"), "--dataset-kind", "synthetic",
                 "--expected-sha256", "0" * 64]) == 2


def test_evaluate_writes_report_with_both_noise_conventions(tmp_path):
    src = tmp_path / "in.geojson"
    src.write_bytes(table_geojson_bytes())
    out = tmp_path / "out"
    main(["build", "--input", str(src), "--out-dir", str(out), "--dataset-kind", "synthetic"])
    assert main(["evaluate", "--events", str(out / "events.json"), "--out-dir", str(out)]) == 0
    ev = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))
    assert len(ev["sensitivity"]) == 9 and sum(1 for r in ev["sensitivity"] if r["is_primary"]) == 1
    assert set(ev["agreement"]["dbscan_vs_primary_grid"]) == {"noise_singleton", "noise_one_group"}
    assert ev["dbscan"]["clusters"] == 8 and ev["dbscan"]["noise"] == 16 and ev["dbscan"]["ambiguous_borders"] == 1
    assert "Not a forecast" in ev["notes"][0]
    assert (out / "evaluation.md").read_text(encoding="utf-8").startswith("# Evaluation")


def test_dist_scan_flags_real_looking_data(tmp_path):
    (tmp_path / "ok.json").write_text('{"dataset_kind": "synthetic", "id": "fx-1"}', encoding="utf-8")
    assert scan_dir_for_real_data(tmp_path) == []
    (tmp_path / "bad.json").write_text('{"dataset_kind": "real"}', encoding="utf-8")
    assert scan_dir_for_real_data(tmp_path)
