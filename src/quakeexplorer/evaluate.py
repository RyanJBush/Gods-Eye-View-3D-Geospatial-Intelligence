"""Descriptive evaluation: summary statistics, grid contrast, and the predeclared sensitivity set.

Nothing here measures accuracy. DBSCAN groups and grid cells are two different, arbitrary
partitions; agreement is a descriptive contrast only.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any, Sequence

from .cluster import DEFAULT_EPS_KM, DEFAULT_MIN_SAMPLES, Params, run_dbscan
from .grid import primary_cell, shifted_cell
from .metrics import ari_both_conventions, coverage, partition_ari_both

SENSITIVITY_EPS_KM = (150.0, 250.0, 400.0)
SENSITIVITY_MIN_SAMPLES = (3, 4, 5)


def _dist(sizes: Sequence[int]) -> dict[str, Any]:
    if not sizes:
        return {"count": 0, "min": None, "median": None, "max": None, "sizes_desc": []}
    ordered = sorted(sizes, reverse=True)
    return {
        "count": len(ordered),
        "min": ordered[-1],
        "median": statistics.median(ordered),
        "max": ordered[0],
        "sizes_desc": ordered,
    }


def _cell_labels(cells: Sequence[str]) -> list[str]:
    return list(cells)


def _cluster_summary(labels: Sequence[int], ambiguous: Sequence[bool]) -> dict[str, Any]:
    n = len(labels)
    sizes = Counter(lab for lab in labels if lab != -1)
    noise = n - sum(sizes.values())
    largest = max(sizes.values()) if sizes else 0
    return {
        "clusters": len(sizes),
        "cluster_sizes": _dist(list(sizes.values())),
        "largest_cluster_share": largest / n,
        "noise": noise,
        "noise_fraction": noise / n,
        "coverage": coverage(labels),
        "ambiguous_borders": sum(1 for a in ambiguous if a),
    }


def _grid_summary(cells: Sequence[str]) -> dict[str, Any]:
    n = len(cells)
    occ = Counter(cells)
    return {
        "occupied_cells": len(occ),
        "occupancy": _dist(list(occ.values())),
        "largest_cell_share": max(occ.values()) / n,
    }


def evaluate(events: Sequence[dict[str, Any]], source_raw_sha256: str) -> dict[str, Any]:
    n = len(events)
    primary_cells = [primary_cell(e["latitude_deg"], e["longitude_deg"]) for e in events]
    shifted_cells = [shifted_cell(e["latitude_deg"], e["longitude_deg"]) for e in events]
    base_params = Params(DEFAULT_EPS_KM, DEFAULT_MIN_SAMPLES)
    base = run_dbscan(events, base_params)

    sensitivity = []
    for eps in SENSITIVITY_EPS_KM:
        for ms in SENSITIVITY_MIN_SAMPLES:
            p = Params(eps, ms)
            res = base if p == base_params else run_dbscan(events, p)
            row = {
                "eps_km": eps,
                "min_samples": ms,
                "is_primary": p == base_params,
                "source_raw_sha256": source_raw_sha256,
                **_cluster_summary(res.labels, res.ambiguous),
                "ari_vs_primary_grid": ari_both_conventions(res.labels, primary_cells),
                "ari_vs_shifted_grid": ari_both_conventions(res.labels, shifted_cells),
                "ari_vs_primary_dbscan": partition_ari_both(res.labels, base.labels),
            }
            sensitivity.append(row)

    return {
        "schema": "quake-evaluation/1",
        "source_raw_sha256": source_raw_sha256,
        "events": n,
        "primary_params": {"eps_km": DEFAULT_EPS_KM, "min_samples": DEFAULT_MIN_SAMPLES},
        "dbscan": _cluster_summary(base.labels, base.ambiguous),
        "grid_primary": _grid_summary(primary_cells),
        "grid_shifted": _grid_summary(shifted_cells),
        "agreement": {
            "dbscan_vs_primary_grid": ari_both_conventions(base.labels, primary_cells),
            "dbscan_vs_shifted_grid": ari_both_conventions(base.labels, shifted_cells),
            "primary_grid_vs_shifted_grid": _grid_vs_grid(primary_cells, shifted_cells),
            "dbscan_coverage": coverage(base.labels),
        },
        "sensitivity": sensitivity,
        "notes": [
            "Descriptive and historical. Not a forecast or hazard estimate.",
            "ARI measures agreement between two arbitrary partitions, not accuracy.",
            "Primary noise convention: each noise event is its own singleton; secondary: all noise one group. The singleton treatment is a convention, not a noise label.",
            "One month of one catalogue query aggregates unrelated seismicity and aftershocks; catalogue completeness varies by region.",
            "Parameters were fixed before results were inspected; no setting is selected as best.",
        ],
    }


def _grid_vs_grid(a: Sequence[str], b: Sequence[str]) -> float:
    from .metrics import adjusted_rand_index

    return adjusted_rand_index(list(a), list(b))


def _fmt(x: float) -> str:
    return f"{x:.3f}"


def render_markdown(ev: dict[str, Any]) -> str:
    d = ev["dbscan"]
    gp, gs = ev["grid_primary"], ev["grid_shifted"]
    ag = ev["agreement"]
    lines = [
        "# Evaluation (descriptive; local only)",
        "",
        f"Source SHA-256: `{ev['source_raw_sha256']}`  ",
        f"Events: {ev['events']}. Primary DBSCAN: eps {ev['primary_params']['eps_km']:g} km, min_samples {ev['primary_params']['min_samples']}.",
        "",
        "## Primary DBSCAN",
        f"- Clusters: {d['clusters']}; noise: {d['noise']} ({_fmt(d['noise_fraction'])}); coverage {_fmt(d['coverage'])}",
        f"- Cluster sizes: min {d['cluster_sizes']['min']}, median {d['cluster_sizes']['median']}, max {d['cluster_sizes']['max']}; largest cluster share {_fmt(d['largest_cluster_share'])}",
        f"- Ambiguous border points: {d['ambiguous_borders']}",
        "",
        "## Grids",
        f"- Primary 5 deg grid: {gp['occupied_cells']} occupied cells; occupancy min {gp['occupancy']['min']}, median {gp['occupancy']['median']}, max {gp['occupancy']['max']}; largest cell share {_fmt(gp['largest_cell_share'])}",
        f"- Shifted grid: {gs['occupied_cells']} occupied cells; occupancy min {gs['occupancy']['min']}, median {gs['occupancy']['median']}, max {gs['occupancy']['max']}; largest cell share {_fmt(gs['largest_cell_share'])}",
        "",
        "## Agreement (descriptive contrast, not accuracy)",
        "| Pair | ARI, noise as singletons | ARI, noise as one group |",
        "|---|---|---|",
        f"| DBSCAN vs primary grid | {_fmt(ag['dbscan_vs_primary_grid']['noise_singleton'])} | {_fmt(ag['dbscan_vs_primary_grid']['noise_one_group'])} |",
        f"| DBSCAN vs shifted grid | {_fmt(ag['dbscan_vs_shifted_grid']['noise_singleton'])} | {_fmt(ag['dbscan_vs_shifted_grid']['noise_one_group'])} |",
        f"| Primary grid vs shifted grid | {_fmt(ag['primary_grid_vs_shifted_grid'])} | same (no noise) |",
        "",
        "## Sensitivity (predeclared; no setting is chosen as best)",
        "| eps km | min_samples | clusters | noise frac | largest share | ambiguous | ARI vs grid (single / one) | ARI vs shifted (single / one) | ARI vs primary DBSCAN (single / one) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in ev["sensitivity"]:
        mark = " (primary)" if r["is_primary"] else ""
        lines.append(
            f"| {r['eps_km']:g}{mark} | {r['min_samples']} | {r['clusters']} | {_fmt(r['noise_fraction'])} | {_fmt(r['largest_cluster_share'])} | {r['ambiguous_borders']} | "
            f"{_fmt(r['ari_vs_primary_grid']['noise_singleton'])} / {_fmt(r['ari_vs_primary_grid']['noise_one_group'])} | "
            f"{_fmt(r['ari_vs_shifted_grid']['noise_singleton'])} / {_fmt(r['ari_vs_shifted_grid']['noise_one_group'])} | "
            f"{_fmt(r['ari_vs_primary_dbscan']['noise_singleton'])} / {_fmt(r['ari_vs_primary_dbscan']['noise_one_group'])} |"
        )
    lines += ["", "## Notes", *[f"- {n}" for n in ev["notes"]], ""]
    return "\n".join(lines)
