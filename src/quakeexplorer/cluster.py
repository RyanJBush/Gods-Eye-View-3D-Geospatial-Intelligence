"""DBSCAN on the sphere (haversine), deterministic relabelling, role and ambiguity detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors

EARTH_RADIUS_KM = 6371.0088
DEFAULT_EPS_KM = 250.0
DEFAULT_MIN_SAMPLES = 4
NOISE = -1


@dataclass(frozen=True)
class Params:
    eps_km: float = DEFAULT_EPS_KM
    min_samples: int = DEFAULT_MIN_SAMPLES

    @property
    def eps_radians(self) -> float:
        return self.eps_km / EARTH_RADIUS_KM


@dataclass
class ClusterResult:
    labels: list[int]  # relabelled 0..k-1 by smallest member id, -1 noise
    roles: list[str]  # "core" | "border" | "noise"
    ambiguous: list[bool]  # non-core and within eps of core points of >= 2 components


def _coords_radians(events: Sequence[dict[str, Any]]) -> np.ndarray:
    # GeoJSON order is [lon, lat]; the haversine metric wants [lat, lon] in radians.
    return np.radians(np.array([[e["latitude_deg"], e["longitude_deg"]] for e in events], dtype=float))


def run_dbscan(events: Sequence[dict[str, Any]], params: Params = Params()) -> ClusterResult:
    """`events` must already be sorted by UTF-8 byte order of id (validate_snapshot does this).
    Depth and time are not used."""
    if not events:
        raise ValueError("no events")
    x = _coords_radians(events)
    db = DBSCAN(
        eps=params.eps_radians,
        min_samples=params.min_samples,
        metric="haversine",
        algorithm="ball_tree",
    ).fit(x)
    raw = db.labels_
    core_mask = np.zeros(len(events), dtype=bool)
    core_mask[db.core_sample_indices_] = True

    # Relabel by order of first appearance in id-sorted input == smallest member id.
    mapping: dict[int, int] = {}
    labels: list[int] = []
    for lab in raw.tolist():
        if lab == NOISE:
            labels.append(NOISE)
            continue
        if lab not in mapping:
            mapping[lab] = len(mapping)
        labels.append(mapping[lab])

    roles = [
        "core" if core_mask[i] else ("border" if labels[i] != NOISE else "noise")
        for i in range(len(events))
    ]

    nn = NearestNeighbors(
        radius=params.eps_radians, metric="haversine", algorithm="ball_tree"
    ).fit(x)
    neighbours = nn.radius_neighbors(x, return_distance=False)
    ambiguous = []
    for i, nbrs in enumerate(neighbours):
        if core_mask[i]:
            ambiguous.append(False)
            continue
        components = {int(raw[j]) for j in nbrs if core_mask[j]}
        ambiguous.append(len(components) >= 2)
    return ClusterResult(labels=labels, roles=roles, ambiguous=ambiguous)
