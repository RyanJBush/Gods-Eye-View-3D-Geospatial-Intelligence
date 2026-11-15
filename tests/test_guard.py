import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_tracked_files import REAL_ID, find_violations  # noqa: E402


def _w(root: Path, rel: str, text: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_reserved_paths_fail(tmp_path):
    for rel in ("data/raw/x.geojson", "web/public/data/events.json", "reports/local/evaluation.md", "web/dist/a.js"):
        _w(tmp_path, rel, "{}")
        assert find_violations(tmp_path, [rel]), rel


def test_geojson_only_allowed_in_fixtures(tmp_path):
    _w(tmp_path, "fixtures/synthetic_usgs.geojson", "{}")
    _w(tmp_path, "other/real.geojson", "{}")
    assert find_violations(tmp_path, ["fixtures/synthetic_usgs.geojson"]) == []
    assert find_violations(tmp_path, ["other/real.geojson"])


def test_real_looking_ids_fail_synthetic_ids_pass(tmp_path):
    # built at runtime so this file itself holds no id-shaped literal
    _w(tmp_path, "docs/a.md", f'ids: "{"us" + "1234abcd"}" and "{"nc" + "73000000"}"')
    _w(tmp_path, "docs/b.md", "fx-dense-a1 fx-ord-A user users usage us-east useful12")
    assert find_violations(tmp_path, ["docs/a.md"])
    assert find_violations(tmp_path, ["docs/b.md"]) == []


def test_pattern_matches_known_shape_without_storing_real_ids():
    assert REAL_ID.search("us" + "6000" + "abcd")
    assert not REAL_ID.search("fx-dense-a1")


def test_repo_itself_is_clean():
    import check_tracked_files as g
    root = Path(g.__file__).resolve().parent.parent
    try:
        tracked = g.git_tracked(root)
    except Exception:  # not a git checkout
        return
    assert g.find_violations(root, tracked) == []
