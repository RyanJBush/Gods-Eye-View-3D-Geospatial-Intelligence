"""Build the canonical events artifact and the separate analysis artifact."""

from __future__ import annotations

import platform
from typing import Any

import numpy as np
import scipy
import sklearn

from . import ANALYSIS_SCHEMA, EVENTS_SCHEMA, __version__
from .canonical import dumps, sha256_hex
from .cluster import EARTH_RADIUS_KM, ClusterResult, Params, run_dbscan
from .grid import primary_cell, shifted_cell
from .validate import ValidationResult

USGS_CREDIT = "Source: U.S. Geological Survey, Earthquake Hazards Program / ANSS ComCat"
SYNTHETIC_CREDIT = "Synthetic fixture data. Not real earthquakes."


def environment_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
        "quakeexplorer": __version__,
    }


def build_events_artifact(
    vr: ValidationResult,
    *,
    dataset_kind: str,
    source_credit: str,
    acquisition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if dataset_kind not in ("real", "synthetic"):
        raise ValueError("dataset_kind must be 'real' or 'synthetic'")
    provenance = {
        "dataset_kind": dataset_kind,
        "source_credit": source_credit,
        "usgs_api": {
            "query_url": vr.metadata.get("url"),
            "title": vr.metadata.get("title"),
            "api_version": vr.metadata.get("api"),
            "generated_ms": vr.metadata.get("generated"),
            "metadata_count": vr.metadata.get("count"),
        },
        "acquisition": acquisition,
        "raw": {"sha256": vr.raw_sha256, "bytes": vr.raw_bytes},
        "counts": {
            "raw": vr.raw_count,
            "accepted": len(vr.events),
            "rejected": len(vr.rejected),
            "rejected_by_reason": vr.rejected_by_reason(),
            "warnings": len(vr.warnings),
            "warnings_by_code": _count_codes(vr.warnings),
        },
        "input_order": "UTF-8 byte order of event id",
        "contract": "docs/contract.md v1",
        "versions": {"quakeexplorer": __version__},
    }
    return {"schema": EVENTS_SCHEMA, "provenance": provenance, "events": vr.events}


def _count_codes(items: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        out[item["code"]] = out.get(item["code"], 0) + 1
    return dict(sorted(out.items()))


def build_analysis_artifact(
    events_doc: dict[str, Any],
    events_sha256: str,
    params: Params = Params(),
    result: ClusterResult | None = None,
) -> dict[str, Any]:
    events = events_doc["events"]
    res = result if result is not None else run_dbscan(events, params)
    assignments = []
    for e, lab, role, amb in zip(events, res.labels, res.roles, res.ambiguous):
        assignments.append(
            {
                "id": e["id"],
                "cluster": lab,
                "role": role,
                "ambiguous_border": amb,
                "grid_cell": primary_cell(e["latitude_deg"], e["longitude_deg"]),
                "shifted_cell": shifted_cell(e["latitude_deg"], e["longitude_deg"]),
            }
        )
    n_clusters = len({a["cluster"] for a in assignments if a["cluster"] != -1})
    n_noise = sum(1 for a in assignments if a["cluster"] == -1)
    return {
        "schema": ANALYSIS_SCHEMA,
        "source_raw_sha256": events_doc["provenance"]["raw"]["sha256"],
        "events_sha256": events_sha256,
        "algorithm": {
            "name": "DBSCAN",
            "implementation": "scikit-learn",
            "metric": "haversine",
            "neighbour_search": "ball_tree",
            "input_columns": "[latitude, longitude] in radians; depth and time excluded",
            "earth_radius_km": EARTH_RADIUS_KM,
            "eps_km": params.eps_km,
            "eps_radians": params.eps_radians,
            "min_samples": params.min_samples,
            "neighbourhood": "<= eps, includes the point itself",
            "input_order": "UTF-8 byte order of event id",
            "relabel": "non-noise groups numbered from 0 by smallest member id (UTF-8 byte order); noise = -1",
            "ambiguous_border": "non-core point within eps of core points from >= 2 distinct core components",
        },
        "grid": {
            "primary": "5x5 deg, half-open bins, lat idx min(floor((lat+90)/5),35), lon idx floor((lon_norm+180)/5), +180 -> -180",
            "shifted": "origin +2.5 deg both axes: lat idx floor((lat+92.5)/5) in 0..36 (short first and last bands, +90 inclusive), lon idx floor((lon_norm+182.5)/5) mod 72",
        },
        "environment": environment_versions(),
        "summary": {
            "events": len(assignments),
            "clusters": n_clusters,
            "noise": n_noise,
            "ambiguous_borders": sum(1 for a in assignments if a["ambiguous_border"]),
        },
        "assignments": assignments,
    }


def serialise(doc: dict[str, Any]) -> tuple[bytes, str]:
    data = dumps(doc)
    return data, sha256_hex(data)
