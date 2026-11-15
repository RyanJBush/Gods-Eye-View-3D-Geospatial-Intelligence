"""Build hand-made USGS-shaped GeoJSON for tests and the checked-in synthetic demo input."""

from __future__ import annotations

import json
from typing import Any

from fixture_table import TABLE

QUERY_URL = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2024-01-01T00%3A00%3A00"
    "&endtime=2024-02-01T00%3A00%3A00&minmagnitude=4.5&eventtype=earthquake&orderby=time-asc"
)
BASE_TIME_MS = 1704067200000


def feature(
    event_id: Any,
    lat: Any,
    lon: Any,
    *,
    k: int = 1,
    depth: Any = 10.0,
    mag: Any = 4.5,
    time: Any = None,
    props: dict[str, Any] | None = None,
    coords: list[Any] | None = None,
) -> dict[str, Any]:
    properties = {
        "mag": mag,
        "place": "synthetic",
        "time": BASE_TIME_MS + 3600000 * k if time is None else time,
        "updated": None,
        "url": None,
        "status": "reviewed",
        "net": "fx",
        "magType": "mb",
        "type": "earthquake",
    }
    if props:
        properties.update(props)
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": "Point", "coordinates": coords if coords is not None else [lon, lat, depth]},
        "id": event_id,
    }


def collection(features: list[Any], *, count: Any = "auto", status: int = 200) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated": 1794722633000,
            "url": QUERY_URL,
            "title": "Synthetic fixture (not real earthquake data)",
            "status": status,
            "api": "2.8.4",
            "count": len(features) if count == "auto" else count,
        },
        "features": features,
    }


def dump(doc: Any) -> bytes:
    return json.dumps(doc, ensure_ascii=False, indent=1, allow_nan=False).encode("utf-8") + b"\n"


def table_features(rows=TABLE) -> list[dict[str, Any]]:
    # k is the 1-based row in UTF-8 byte order of id, as specified in the fixture table.
    ordered = sorted(rows, key=lambda r: r[0].encode("utf-8"))
    return [feature(r[0], r[1], r[2], k=i + 1) for i, r in enumerate(ordered)]


def table_geojson_bytes() -> bytes:
    return dump(collection(table_features()))
