import json

import pytest

from fixture_builder import collection, dump, feature, table_geojson_bytes
from quakeexplorer.validate import (
    JS_DATE_MAX_MS,
    SnapshotError,
    is_safe_usgs_url,
    validate_snapshot,
)


def one(feat, **kw):
    return validate_snapshot(dump(collection([feat])), strict=False, **kw)


def codes_for(feat):
    vr = one_expect_reject(feat)
    return vr["codes"]


def one_expect_reject(feat):
    # a second valid feature keeps no_events from masking the record-level result
    good = feature("fx-good", 1.0, 1.0, k=99)
    vr = validate_snapshot(dump(collection([feat, good])), strict=False)
    assert len(vr.rejected) == 1 and len(vr.events) == 1
    return vr.rejected[0]


def file_codes(raw, **kw):
    with pytest.raises(SnapshotError) as ei:
        validate_snapshot(raw, **kw)
    return [e["code"] for e in ei.value.errors]


# ---- accepted, nulls preserved -------------------------------------------------------------

def test_fixture_table_accepted_strict():
    vr = validate_snapshot(table_geojson_bytes(), strict=True)
    assert len(vr.events) == 56 and not vr.rejected


def test_va1_null_magnitude_not_zero():
    e = one(feature("a", 1, 2, mag=None)).events[0]
    assert e["magnitude"] is None


def test_va2_negative_depth_kept():
    assert one(feature("a", 1, 2, depth=-1.2)).events[0]["depth_km"] == -1.2


def test_va3_two_element_coordinates_depth_null():
    e = one(feature("a", 1, 2, coords=[2, 1])).events[0]
    assert e["depth_km"] is None and e["longitude_deg"] == 2.0


def test_va3b_null_depth_element():
    assert one(feature("a", 1, 2, depth=None)).events[0]["depth_km"] is None


@pytest.mark.parametrize("key,field", [("place", "place"), ("magType", "magnitude_type"),
                                       ("updated", "updated_ms"), ("status", "status"), ("net", "net"),
                                       ("url", "url")])
def test_va_nullable_fields(key, field):
    e = one(feature("a", 1, 2, props={key: None})).events[0]
    assert e[field] is None


@pytest.mark.parametrize("url", [
    "http://earthquake.usgs.gov/earthquakes/eventpage/x",
    "https://earthquake.usgs.gov.evil.example/x",
    "javascript:alert(1)",
    "https://earthquake.usgs.gov@evil.example/",
    "https://user:pw@earthquake.usgs.gov/x",
    "https://earthquake.usgs.gov:8443/x",
    "https://earthquake.usgs.gov./x",
    "https://earthquake.usgs.gov/a b",
    "https://earthquake.usgs.gov\\@evil.example/",
    "",
    "//earthquake.usgs.gov/x",
])
def test_va9_unsafe_url_event_kept_link_dropped_warning_counted(url):
    vr = one(feature("a", 1, 2, props={"url": url}))
    assert vr.events[0]["url"] is None
    assert [w["code"] for w in vr.warnings] == ["unsafe_url"]


def test_safe_url_kept():
    u = "https://earthquake.usgs.gov/earthquakes/eventpage/fx1"
    assert is_safe_usgs_url(u)
    assert one(feature("a", 1, 2, props={"url": u})).events[0]["url"] == u


def test_va9b_non_string_url_is_unsafe_not_fatal():
    vr = one(feature("a", 1, 2, props={"url": 5}))
    assert vr.events[0]["url"] is None and vr.warnings[0]["code"] == "unsafe_url"


def test_va10_markup_id_accepted_verbatim():
    ident = 'fx-"<img src=x onerror=alert(1)>&amp;'
    assert one(feature(ident, 1, 2)).events[0]["id"] == ident


def test_va11_negative_time_ok():
    assert one(feature("a", 1, 2, time=-1000)).events[0]["origin_time_ms"] == -1000


def test_va12_integral_float_time_normalised_to_int():
    raw = dump(collection([feature("a", 1, 2, time=1704069429096.0)]))
    assert b"1704069429096.0" in raw
    e = validate_snapshot(raw).events[0]
    assert e["origin_time_ms"] == 1704069429096 and isinstance(e["origin_time_ms"], int)


def test_va13_extra_properties_not_copied():
    e = one(feature("a", 1, 2, props={"sig": 340, "felt": None})).events[0]
    assert set(e) == {"id", "origin_time_ms", "updated_ms", "longitude_deg", "latitude_deg",
                      "depth_km", "magnitude", "magnitude_type", "place", "status", "net", "url"}


@pytest.mark.parametrize("lat,lon", [(90, 180), (-90, -180), (90.0, 0), (0, 180.0)])
def test_extreme_valid_coordinates_retained(lat, lon):
    e = one(feature("a", lat, lon)).events[0]
    assert (e["latitude_deg"], e["longitude_deg"]) == (float(lat), float(lon))


def test_time_range_edge_accepted():
    assert one(feature("a", 1, 2, time=JS_DATE_MAX_MS)).events[0]["origin_time_ms"] == JS_DATE_MAX_MS


# ---- rejected at record level --------------------------------------------------------------

def _no_id():
    f = feature("x", 1, 2)
    del f["id"]
    return f


def _del_prop(name):
    f = feature("x", 1, 2)
    del f["properties"][name]
    return f


@pytest.mark.parametrize("feat,code", [
    (_no_id(), "id_missing"),
    (feature("", 1, 2), "id_empty"),
    (feature("  ", 1, 2), "id_empty"),
    (feature(123, 1, 2), "id_type"),
    (feature(True, 1, 2), "id_type"),
    (feature("x", 1, 2, props={"time": None}), "time_missing"),
    (_del_prop("time"), "time_missing"),
    (feature("x", 1, 2, time="1704069429096"), "time_invalid"),
    (feature("x", 1, 2, time=True), "time_invalid"),
    (feature("x", 1, 2, time=1704069429096.5), "time_invalid"),
    (feature("x", 1, 2, time=JS_DATE_MAX_MS + 1), "time_out_of_range"),
    (feature("x", 1, 2, time=10**30), "time_out_of_range"),
    (feature("x", 1, 2, props={"updated": 1.5}), "updated_invalid"),
    (feature("x", 1, 2, props={"updated": JS_DATE_MAX_MS + 1}), "updated_out_of_range"),
    (feature("x", 90.0001, 2), "lat_out_of_range"),
    (feature("x", -90.0001, 2), "lat_out_of_range"),
    (feature("x", 1, 180.0001), "lon_out_of_range"),
    (feature("x", 1, -180.0001), "lon_out_of_range"),
    (feature("x", None, 2), "coord_type"),
    (feature("x", 1, "2"), "coord_type"),
    (feature("x", True, 2), "coord_type"),
    (feature("x", 1, 2, depth="10"), "depth_invalid"),
    (feature("x", 1, 2, mag="4.5"), "magnitude_invalid"),
    (feature("x", 1, 2, mag=True), "magnitude_invalid"),
    (feature("x", 1, 2, props={"place": 5}), "place_invalid"),
    (feature("x", 1, 2, props={"magType": 5}), "magnitude_type_invalid"),
    (feature("x", 1, 2, props={"status": []}), "status_invalid"),
    (feature("x", 1, 2, props={"net": {}}), "net_invalid"),
    (feature("x", 1, 2, props={"type": "explosion"}), "event_type_not_earthquake"),
    (feature("x", 1, 2, props={"type": "quarry blast"}), "event_type_not_earthquake"),
    (feature("x", 1, 2, props={"type": "Earthquake"}), "event_type_not_earthquake"),
    (feature("x", 1, 2, props={"type": None}), "event_type_missing"),
    (_del_prop("type"), "event_type_missing"),
    (feature("x", 1, 2, coords=[1, 2, 3, 4]), "coordinates_shape"),
    (feature("x", 1, 2, coords=[1]), "coordinates_shape"),
    (feature("x", 1, 2, coords="1,2"), "coordinates_shape"),
])
def test_record_rejections(feat, code):
    assert code in codes_for(feat)


def test_geometry_cases():
    f = feature("x", 1, 2)
    f["geometry"] = None
    assert "geometry_missing" in codes_for(f)
    f = feature("x", 1, 2)
    del f["geometry"]
    assert "geometry_missing" in codes_for(f)
    f = feature("x", 1, 2)
    f["geometry"]["type"] = "LineString"
    assert "geometry_type" in codes_for(f)


def test_feature_and_properties_shape():
    assert "feature_shape" in codes_for(5)
    assert "feature_shape" in codes_for({"type": "Point"})
    f = feature("x", 1, 2)
    f["properties"] = None
    assert "properties_missing" in codes_for(f)


def test_lone_surrogate_id_rejected_record_level():
    good = dump(collection([feature("fx-bad", 1, 1, k=1), feature("fx-ok", 2, 2, k=2)]))
    raw = good.replace(b'"fx-bad"', b'"fx-\\ud800"')
    vr = validate_snapshot(raw, strict=False)
    assert vr.rejected[0]["codes"] == ["id_invalid_unicode"]


def test_strict_mode_fails_whole_snapshot_without_partial_output():
    raw = dump(collection([feature("a", 1, 2), feature("b", 1, 2, props={"type": "explosion"})]))
    with pytest.raises(SnapshotError) as ei:
        validate_snapshot(raw, strict=True)
    assert [e["code"] for e in ei.value.errors] == ["event_type_not_earthquake"]
    assert ei.value.errors[0]["scope"] == "record"
    # lenient mode reports it and keeps the rest
    vr = validate_snapshot(raw, strict=False)
    assert [e["id"] for e in vr.events] == ["a"] and vr.rejected_by_reason() == {"event_type_not_earthquake": 1}


def test_multiple_reasons_reported():
    r = one_expect_reject(feature("x", 95, 200, mag="z"))
    assert set(r["codes"]) == {"lat_out_of_range", "lon_out_of_range", "magnitude_invalid"}


# ---- whole-snapshot failures ---------------------------------------------------------------

@pytest.mark.parametrize("strict", [True, False])
def test_vf1_duplicate_ids_fail_and_report_both_locations(strict):
    raw = dump(collection([feature("dup", 1, 2), feature("ok", 3, 4), feature("dup", 5, 6)]))
    with pytest.raises(SnapshotError) as ei:
        validate_snapshot(raw, strict=strict)
    err = ei.value.errors[0]
    assert err["code"] == "duplicate_id" and err["detail"] == {"id": "dup", "indices": [0, 2]}


def test_duplicates_detected_even_if_one_record_otherwise_rejected():
    raw = dump(collection([feature("dup", 1, 2), feature("dup", 99, 2)]))
    assert file_codes(raw, strict=False) == ["duplicate_id"]


def test_vf2_count_mismatch():
    assert file_codes(dump(collection([feature("a", 1, 2)], count=2))) == ["count_mismatch"]


def test_vf3_metadata():
    assert file_codes(dump(collection([feature("a", 1, 2)], status=500))) == ["metadata_invalid"]
    doc = collection([feature("a", 1, 2)])
    del doc["metadata"]
    assert file_codes(dump(doc)) == ["metadata_invalid"]


@pytest.mark.parametrize("raw", [b"{not json", b"", b"[]", b'{"type":"FeatureCollection"}',
                                 b'{"type":"FeatureCollection","features":{}}',
                                 b'{"type":"Feature","features":[]}', b"\xff\xfe\x00"])
def test_vf4_structure_or_json(raw):
    assert file_codes(raw)[0] in ("invalid_json", "structure_invalid")


def test_vf5_count_limit():
    feats = [feature(f"e{i}", 1, 2) for i in range(2001)]
    assert file_codes(dump(collection(feats))) == ["count_limit"]
    ok = [feature(f"e{i:04d}", 1, 2) for i in range(2000)]
    assert len(validate_snapshot(dump(collection(ok))).events) == 2000


def test_vf6_size_limit():
    assert file_codes(b" " * (5 * 1024 * 1024 + 1)) == ["size_limit"]


def test_vf7_hash_mismatch_and_match():
    raw = table_geojson_bytes()
    assert file_codes(raw, expected_sha256="0" * 64) == ["hash_mismatch"]
    import hashlib
    h = hashlib.sha256(raw).hexdigest()
    assert validate_snapshot(raw, expected_sha256=h.upper()).raw_sha256 == h


def test_vf8_no_events():
    assert file_codes(dump(collection([])), strict=False) == ["no_events"]
    assert file_codes(dump(collection([feature("x", 99, 2)])), strict=False) == ["no_events"]


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_nonfinite_json_is_file_level_parse_error(literal):
    raw = dump(collection([feature("a", 1, 2)])).replace(b'"mag": 4.5', b'"mag": ' + literal.encode())
    assert literal.encode() in raw
    with pytest.raises(SnapshotError) as ei:
        validate_snapshot(raw, strict=False)
    assert [(e["scope"], e["code"]) for e in ei.value.errors] == [("file", "nonfinite_json")]


def test_nonfinite_in_coordinates_is_file_level_too():
    doc ='{"type":"FeatureCollection","metadata":{"status":200,"count":1},"features":[{"type":"Feature","id":"a","properties":{"time":1,"type":"earthquake"},"geometry":{"type":"Point","coordinates":[NaN,1,2]}}]}'
    assert file_codes(doc.encode()) == ["nonfinite_json"]


def test_duplicate_object_keys_are_invalid_json():
    doc = b'{"type":"FeatureCollection","type":"FeatureCollection","features":[]}'
    assert file_codes(doc) == ["invalid_json"]


def test_output_events_sorted_in_utf8_byte_order():
    vr = validate_snapshot(table_geojson_bytes())
    ids = [e["id"] for e in vr.events]
    assert ids == sorted(ids, key=lambda s: s.encode("utf-8"))
    tail = [i for i in ids if i.startswith("fx-ord-")]
    assert tail == ["fx-ord-A", "fx-ord-a", "fx-ord-é", "fx-ord-～", "fx-ord-\U0001f30b"]
    assert tail != sorted(tail, key=lambda s: s.encode("utf-16-be"))  # UTF-16 order would differ
