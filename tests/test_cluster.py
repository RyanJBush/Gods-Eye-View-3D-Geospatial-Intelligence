import random

import pytest

from fixture_builder import collection, dump, feature, table_features, table_geojson_bytes
from fixture_table import AMBIG, GROUP_COUNT, NOISE_IDS, TABLE
from quakeexplorer.artifacts import build_analysis_artifact, build_events_artifact, serialise
from quakeexplorer.cluster import Params, run_dbscan
from quakeexplorer.validate import validate_snapshot

# Label of the ambiguous border as produced by the PINNED pipeline (scikit-learn 1.7.2, ids sorted
# by UTF-8 byte order). Golden for this environment only; other implementations may differ.
PINNED_Z_GROUP = 0


@pytest.fixture(scope="module")
def run():
    vr = validate_snapshot(table_geojson_bytes())
    res = run_dbscan(vr.events)
    ids = [e["id"] for e in vr.events]
    return vr, res, dict(zip(ids, res.labels)), dict(zip(ids, res.roles)), dict(zip(ids, res.ambiguous))


def test_groups_and_noise_match_table(run):
    _, res, lab, role, amb = run
    for rid, _, _, _, r, group, _, _ in TABLE:
        if group == AMBIG:
            assert lab[rid] in (0, 1) and lab[rid] != -1
        else:
            assert lab[rid] == group, rid
        assert role[rid] == ("border" if r == "ambiguous" else r), rid


def test_noise_set_is_exactly_the_sixteen(run):
    _, _, lab, _, _ = run
    assert sorted(i for i, v in lab.items() if v == -1) == NOISE_IDS and len(NOISE_IDS) == 16


def test_group_numbers_are_exactly_0_to_7(run):
    _, _, lab, _, _ = run
    assert sorted({v for v in lab.values() if v != -1}) == list(range(GROUP_COUNT))
    assert sum(1 for v in lab.values() if v != -1) == 40


def test_co_membership(run):
    _, _, lab, _, _ = run
    members = {}
    for rid, *_rest in TABLE:
        members.setdefault(lab[rid], []).append(rid)
    assert len(members[2]) == 6 and len(members[3]) == 5 and len(members[7]) == 4


def test_ambiguous_border_exactly_one_and_pinned_label(run):
    _, _, lab, _, amb = run
    assert [i for i, v in amb.items() if v] == ["fx-amb-z"]
    assert lab["fx-amb-z"] == PINNED_Z_GROUP  # pinned pipeline only
    # the two core components are never merged
    assert lab["fx-amb-l1"] != lab["fx-amb-r1"]


def test_chain_margin_probes(run):
    _, _, lab, role, _ = run
    assert lab["fx-chain-y"] == 2 and role["fx-chain-y"] == "border"   # 200 km, inside eps
    assert lab["fx-chain-x"] == -1                                       # 300 km, outside eps


def test_dateline_one_group_but_grid_splits(run):
    from quakeexplorer.grid import primary_cell, shifted_cell
    vr, _, lab, _, _ = run
    d = [e for e in vr.events if e["id"].startswith("fx-dateline-")]
    assert len({lab[e["id"]] for e in d}) == 1 and lab[d[0]["id"]] == 3
    assert len({primary_cell(e["latitude_deg"], e["longitude_deg"]) for e in d}) == 2
    assert len({shifted_cell(e["latitude_deg"], e["longitude_deg"]) for e in d}) == 1


def test_poles_and_min_samples_boundary(run):
    _, _, lab, role, _ = run
    assert {lab[f"fx-npole-{i}"] for i in range(1, 6)} == {6}
    assert {lab[f"fx-spole-{i}"] for i in range(1, 5)} == {7}      # exactly min_samples
    assert all(lab[f"fx-small-{i}"] == -1 for i in range(1, 4))     # one below min_samples


def test_relabel_by_smallest_member_id(run):
    vr, _, lab, _, _ = run
    first = {}
    for e in vr.events:  # sorted by UTF-8 byte order
        v = lab[e["id"]]
        if v != -1:
            first.setdefault(v, e["id"])
    smallest = [first[k] for k in sorted(first)]
    assert smallest == sorted(smallest, key=lambda s: s.encode("utf-8"))
    assert smallest == ["fx-amb-l1", "fx-amb-r1", "fx-chain-1", "fx-dateline-1", "fx-dense-a1",
                        "fx-dense-b1", "fx-npole-1", "fx-spole-1"]


def _artifact_bytes(raw: bytes) -> tuple[bytes, bytes]:
    vr = validate_snapshot(raw)
    ev = build_events_artifact(vr, dataset_kind="synthetic", source_credit="x")
    eb, esha = serialise(ev)
    ab, _ = serialise(build_analysis_artifact(ev, esha))
    return eb, ab


def _shuffled_raw(seed=None, reverse=False) -> bytes:
    feats = table_features()
    if reverse:
        feats.reverse()
    else:
        random.Random(seed).shuffle(feats)
    return dump(collection(feats))


@pytest.mark.parametrize("variant", [{"seed": 1}, {"seed": 2}, {"seed": 99}, {"reverse": True}])
def test_shuffled_and_reversed_inputs_give_identical_bytes(variant):
    # Raw bytes differ, but after sorting by UTF-8 id the pipeline output is identical.
    base = _artifact_bytes(table_geojson_bytes())
    other_raw = _shuffled_raw(**variant)
    assert other_raw != table_geojson_bytes()
    eb, ab = _artifact_bytes(other_raw)
    # raw hash is in provenance, so compare event lists and assignments, not whole files
    import json
    assert json.loads(eb)["events"] == json.loads(base[0])["events"]
    assert json.loads(ab)["assignments"] == json.loads(base[1])["assignments"]


def test_repeated_runs_byte_identical():
    assert _artifact_bytes(table_geojson_bytes()) == _artifact_bytes(table_geojson_bytes())


def test_depth_and_time_do_not_affect_assignments():
    base = run_dbscan(validate_snapshot(table_geojson_bytes()).events).labels
    feats = table_features()
    rng = random.Random(7)
    times = [f["properties"]["time"] for f in feats]
    rng.shuffle(times)
    for f, t in zip(feats, times):
        f["properties"]["time"] = t
        f["geometry"]["coordinates"][2] = rng.uniform(-5, 700)
    changed = validate_snapshot(dump(collection(feats))).events
    assert run_dbscan(changed).labels == base


def test_events_artifact_is_source_only_and_analysis_is_keyed(run):
    vr, *_ = run
    ev = build_events_artifact(vr, dataset_kind="synthetic", source_credit="x")
    assert all("cluster" not in e and "grid_cell" not in e for e in ev["events"])
    eb, esha = serialise(ev)
    an = build_analysis_artifact(ev, esha)
    assert an["source_raw_sha256"] == vr.raw_sha256 and an["events_sha256"] == esha
    assert [a["id"] for a in an["assignments"]] == [e["id"] for e in ev["events"]]
    assert an["algorithm"]["eps_km"] == 250.0 and an["algorithm"]["min_samples"] == 4
    assert b"NaN" not in eb and eb.endswith(b"\n")


def test_other_parameters_run():
    events = validate_snapshot(table_geojson_bytes()).events
    for eps in (150.0, 250.0, 400.0):
        for ms in (3, 4, 5):
            res = run_dbscan(events, Params(eps, ms))
            assert len(res.labels) == 56
    # at eps 150 km the 100 km-spaced chain has too few neighbours per point for min_samples 4
    chain = run_dbscan(events, Params(150.0, 4))
    ids = [e["id"] for e in events]
    assert all(chain.labels[ids.index(f"fx-chain-{i}")] == -1 for i in range(1, 6))


def test_checked_in_synthetic_fixture_matches_generator():
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_usgs.geojson"
    assert path.read_bytes() == table_geojson_bytes()
