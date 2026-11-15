"""Validation of an untrusted USGS GeoJSON snapshot.

Whole input is validated; every problem is reported with a stable code. Nulls are never coerced
to zero. See docs/contract.md for the codes and limits.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .canonical import id_sort_key, sha256_hex

LIMIT_COUNT = 2000
LIMIT_BYTES = 5 * 1024 * 1024
JS_DATE_MAX_MS = 8_640_000_000_000_000  # valid range of a JavaScript Date, below 2**53
SAFE_URL_HOST = "earthquake.usgs.gov"
EXPECTED_EVENT_TYPE = "earthquake"


class SnapshotError(Exception):
    """The snapshot failed validation. `errors` lists every problem found."""

    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        head = "; ".join(f"{e['scope']}:{e['code']}" for e in errors[:8])
        more = f" (+{len(errors) - 8} more)" if len(errors) > 8 else ""
        super().__init__(f"snapshot validation failed: {head}{more}")


@dataclass
class ValidationResult:
    events: list[dict[str, Any]]  # accepted, sorted by UTF-8 byte order of id
    rejected: list[dict[str, Any]]  # {"index", "id", "codes", "detail"}
    warnings: list[dict[str, Any]]
    raw_sha256: str
    raw_bytes: int
    raw_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def rejected_by_reason(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.rejected:
            for c in r["codes"]:
                out[c] = out.get(c, 0) + 1
        return dict(sorted(out.items()))


class _NonFinite(Exception):
    pass


class _DuplicateKey(Exception):
    pass


def _reject_constant(name: str) -> Any:
    raise _NonFinite(name)


def _parse_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise _NonFinite(text)
    return value


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise _DuplicateKey(key)
        out[key] = value
    return out


def parse_json_strict(raw: bytes) -> Any:
    """Parse JSON, rejecting NaN/Infinity (and overflow to infinity) and duplicate keys."""
    try:
        return json.loads(
            raw,
            parse_constant=_reject_constant,
            parse_float=_parse_float,
            object_pairs_hook=_no_duplicate_keys,
        )
    except _NonFinite as exc:
        raise SnapshotError(
            [{"scope": "file", "code": "nonfinite_json", "detail": f"non-finite number {exc}"}]
        ) from None
    except _DuplicateKey as exc:
        raise SnapshotError(
            [{"scope": "file", "code": "invalid_json", "detail": f"duplicate key {exc}"}]
        ) from None
    except (ValueError, RecursionError) as exc:  # includes JSONDecodeError, UnicodeDecodeError
        raise SnapshotError(
            [{"scope": "file", "code": "invalid_json", "detail": str(exc)[:200]}]
        ) from None


def is_safe_usgs_url(value: Any) -> bool:
    """True only for an https URL whose hostname is exactly earthquake.usgs.gov, with no
    credentials, no explicit port, and no whitespace or control characters."""
    if not isinstance(value, str) or not value:
        return False
    if any(ord(ch) <= 0x20 or ord(ch) == 0x7F for ch in value) or "\\" in value:
        return False
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "https" or port is not None:
        return False
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        return False
    return parts.hostname == SAFE_URL_HOST


def _has_lone_surrogate(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _to_epoch_ms(v: Any) -> tuple[int | None, str | None]:
    """Return (int, None) or (None, 'invalid'|'range'). Integral floats are normalised."""
    if not _is_number(v):
        return None, "invalid"
    if isinstance(v, float):
        if not math.isfinite(v) or v != math.floor(v):
            return None, "invalid"
        if abs(v) > JS_DATE_MAX_MS:
            return None, "range"
        return int(v), None
    if abs(v) > JS_DATE_MAX_MS:
        return None, "range"
    return v, None


def _opt_string(props: dict[str, Any], key: str, code: str, codes: list[str]) -> str | None:
    value = props.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or _has_lone_surrogate(value):
        codes.append(code)
        return None
    return value


def validate_feature(
    feature: Any,
) -> tuple[dict[str, Any] | None, list[str], list[str], str | None]:
    """Return (event or None, reject codes, warning codes, id if usable)."""
    codes: list[str] = []
    warnings: list[str] = []
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        return None, ["feature_shape"], warnings, None

    event_id: str | None = None
    if "id" not in feature or feature["id"] is None:
        codes.append("id_missing")
    elif not isinstance(feature["id"], str):
        codes.append("id_type")
    elif feature["id"].strip() == "":
        codes.append("id_empty")
    elif _has_lone_surrogate(feature["id"]):
        codes.append("id_invalid_unicode")
    else:
        event_id = feature["id"]

    props = feature.get("properties")
    if not isinstance(props, dict):
        codes.append("properties_missing")
        return None, codes, warnings, event_id

    event_type = props.get("type")
    if event_type is None:
        codes.append("event_type_missing")
    elif event_type != EXPECTED_EVENT_TYPE:
        codes.append("event_type_not_earthquake")

    # origin time
    time_ms: int | None = None
    if props.get("time") is None:
        codes.append("time_missing")
    else:
        time_ms, problem = _to_epoch_ms(props["time"])
        if problem == "invalid":
            codes.append("time_invalid")
        elif problem == "range":
            codes.append("time_out_of_range")

    updated_ms: int | None = None
    if props.get("updated") is not None:
        updated_ms, problem = _to_epoch_ms(props["updated"])
        if problem == "invalid":
            codes.append("updated_invalid")
        elif problem == "range":
            codes.append("updated_out_of_range")

    # geometry
    lon = lat = None
    depth: float | None = None
    geometry = feature.get("geometry")
    if geometry is None:
        codes.append("geometry_missing")
    elif not isinstance(geometry, dict) or geometry.get("type") != "Point":
        codes.append("geometry_type")
    else:
        coords = geometry.get("coordinates")
        if not isinstance(coords, list) or len(coords) not in (2, 3):
            codes.append("coordinates_shape")
        else:
            if not _is_number(coords[0]) or not _is_number(coords[1]):
                codes.append("coord_type")
            else:
                lon, lat = float(coords[0]), float(coords[1])
                if not -180.0 <= lon <= 180.0:
                    codes.append("lon_out_of_range")
                if not -90.0 <= lat <= 90.0:
                    codes.append("lat_out_of_range")
            if len(coords) == 3 and coords[2] is not None:
                if _is_number(coords[2]):
                    depth = float(coords[2])
                else:
                    codes.append("depth_invalid")

    magnitude: float | None = None
    if props.get("mag") is not None:
        if _is_number(props["mag"]):
            magnitude = float(props["mag"])
        else:
            codes.append("magnitude_invalid")

    magnitude_type = _opt_string(props, "magType", "magnitude_type_invalid", codes)
    place = _opt_string(props, "place", "place_invalid", codes)
    status = _opt_string(props, "status", "status_invalid", codes)
    net = _opt_string(props, "net", "net_invalid", codes)

    url: str | None = None
    raw_url = props.get("url")
    if raw_url is not None:
        if is_safe_usgs_url(raw_url):
            url = raw_url
        else:
            warnings.append("unsafe_url")

    if codes:
        return None, codes, warnings, event_id

    assert event_id is not None and time_ms is not None and lat is not None and lon is not None
    event = {
        "id": event_id,
        "origin_time_ms": time_ms,
        "updated_ms": updated_ms,
        "longitude_deg": lon,
        "latitude_deg": lat,
        "depth_km": depth,
        "magnitude": magnitude,
        "magnitude_type": magnitude_type,
        "place": place,
        "status": status,
        "net": net,
        "url": url,
    }
    return event, codes, warnings, event_id


def validate_snapshot(
    raw: bytes, *, strict: bool = True, expected_sha256: str | None = None
) -> ValidationResult:
    """Validate raw snapshot bytes. Strict mode raises on any rejected record (no partial
    output). Whole-file problems and duplicate IDs raise in both modes."""
    size = len(raw)
    digest = sha256_hex(raw)
    if size > LIMIT_BYTES:
        raise SnapshotError(
            [{"scope": "file", "code": "size_limit", "detail": f"{size} bytes > {LIMIT_BYTES}"}]
        )
    if expected_sha256 is not None and digest != expected_sha256.lower():
        raise SnapshotError(
            [
                {
                    "scope": "file",
                    "code": "hash_mismatch",
                    "detail": f"expected {expected_sha256.lower()} got {digest}",
                }
            ]
        )

    doc = parse_json_strict(raw)
    if (
        not isinstance(doc, dict)
        or doc.get("type") != "FeatureCollection"
        or not isinstance(doc.get("features"), list)
    ):
        raise SnapshotError([{"scope": "file", "code": "structure_invalid", "detail": "not a FeatureCollection with a features array"}])
    features: list[Any] = doc["features"]

    meta = doc.get("metadata")
    if not isinstance(meta, dict) or meta.get("status") != 200:
        raise SnapshotError([{"scope": "file", "code": "metadata_invalid", "detail": "metadata missing or status != 200"}])
    count = meta.get("count")
    if not _is_number(count) or count != len(features):
        raise SnapshotError(
            [
                {
                    "scope": "file",
                    "code": "count_mismatch",
                    "detail": f"metadata.count={count!r} features={len(features)}",
                }
            ]
        )
    if len(features) > LIMIT_COUNT:
        raise SnapshotError(
            [{"scope": "file", "code": "count_limit", "detail": f"{len(features)} > {LIMIT_COUNT}"}]
        )

    events: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: dict[str, list[int]] = {}
    for index, feature in enumerate(features):
        event, codes, warn, event_id = validate_feature(feature)
        if event_id is not None:
            seen.setdefault(event_id, []).append(index)
        for w in warn:
            warnings.append({"index": index, "id": event_id, "code": w})
        if event is None:
            rejected.append({"index": index, "id": event_id, "codes": codes})
        else:
            events.append(event)

    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    if duplicates:
        raise SnapshotError(
            [
                {"scope": "file", "code": "duplicate_id", "detail": {"id": k, "indices": v}}
                for k, v in sorted(duplicates.items(), key=lambda kv: id_sort_key(kv[0]))
            ]
        )

    if strict and rejected:
        raise SnapshotError(
            [
                {"scope": "record", "code": c, "detail": {"index": r["index"], "id": r["id"]}}
                for r in rejected
                for c in r["codes"]
            ]
        )
    if not events:
        raise SnapshotError([{"scope": "file", "code": "no_events", "detail": "zero accepted events"}])

    events.sort(key=lambda e: id_sort_key(e["id"]))
    return ValidationResult(
        events=events,
        rejected=rejected,
        warnings=warnings,
        raw_sha256=digest,
        raw_bytes=size,
        raw_count=len(features),
        metadata={
            k: meta.get(k) for k in ("generated", "url", "title", "status", "api", "count")
        },
    )
