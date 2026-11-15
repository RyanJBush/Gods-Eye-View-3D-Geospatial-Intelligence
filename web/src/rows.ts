import type { Row } from "./types";

export type SortKey = "id" | "time" | "magnitude" | "depth" | "group";
export type SortDir = "asc" | "desc";
export type GroupFilter = "all" | "noise" | number;

export const NOT_REPORTED = "Not reported";

export function groupLabel(cluster: number): string {
  return cluster < 0 ? "Noise (no group)" : `Group ${cluster}`;
}

export function roleLabel(role: string, ambiguous: boolean): string {
  const base = role === "core" ? "Core point" : role === "border" ? "Border point" : "Noise";
  return ambiguous ? `${base}, ambiguous (within reach of two or more groups)` : base;
}

function value(row: Row, key: SortKey): number | null {
  switch (key) {
    case "id":
      return row.index; // dataset order is UTF-8 byte order of id
    case "time":
      return row.event.origin_time_ms;
    case "magnitude":
      return row.event.magnitude;
    case "depth":
      return row.event.depth_km;
    case "group":
      return row.analysis.cluster;
  }
}

/** Stable sort; missing values always sort last, in either direction. Ties keep dataset order. */
export function sortRows(rows: readonly Row[], key: SortKey, dir: SortDir): Row[] {
  const sign = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = value(a, key);
    const vb = value(b, key);
    if (va === null && vb === null) return a.index - b.index;
    if (va === null) return 1;
    if (vb === null) return -1;
    if (va !== vb) return va < vb ? -sign : sign;
    return a.index - b.index;
  });
}

export function filterRows(rows: readonly Row[], filter: GroupFilter): Row[] {
  if (filter === "all") return [...rows];
  if (filter === "noise") return rows.filter((r) => r.analysis.cluster === -1);
  return rows.filter((r) => r.analysis.cluster === filter);
}

export function formatUtc(ms: number | null): string {
  if (ms === null) return NOT_REPORTED;
  try {
    return new Date(ms).toISOString();
  } catch {
    return `${ms} ms (outside displayable range)`;
  }
}

function num(v: number | null, unit = ""): string {
  return v === null ? NOT_REPORTED : `${v}${unit}`;
}

function text(v: string | null): string {
  return v === null || v === "" ? NOT_REPORTED : v;
}

export interface Field {
  label: string;
  value: string;
  /** Present only for a link that passed the safe-URL rule. */
  href?: string;
}

/** Every source field plus the algorithmic fields, as plain strings (rendered with textContent). */
export function describeRow(row: Row): Field[] {
  const e = row.event;
  const a = row.analysis;
  const link: Field =
    row.safeUrl !== null
      ? { label: "Event page", value: row.safeUrl, href: row.safeUrl }
      : { label: "Event page", value: e.url === null ? NOT_REPORTED : "Link suppressed (not an https earthquake.usgs.gov URL)" };
  return [
    { label: "Event ID", value: e.id },
    { label: "Origin time (UTC)", value: formatUtc(e.origin_time_ms) },
    { label: "Last updated (UTC)", value: formatUtc(e.updated_ms) },
    { label: "Latitude", value: `${e.latitude_deg}°` },
    { label: "Longitude", value: `${e.longitude_deg}°` },
    { label: "Depth", value: num(e.depth_km, " km") },
    { label: "Magnitude", value: num(e.magnitude) },
    { label: "Magnitude type", value: text(e.magnitude_type) },
    { label: "Place", value: text(e.place) },
    { label: "Review status", value: text(e.status) },
    { label: "Network", value: text(e.net) },
    link,
    { label: "Algorithmic group", value: groupLabel(a.cluster) },
    { label: "DBSCAN role", value: roleLabel(a.role, a.ambiguous_border) },
    { label: "Grid cell (5° x 5°)", value: a.grid_cell },
    { label: "Shifted grid cell", value: a.shifted_cell },
  ];
}

/** Cluster -> color and shape indices so groups are distinguishable without color alone. */
export const PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442"] as const;
export const SHAPES = ["circle", "diamond", "square"] as const;
export const SHAPE_SYMBOL: Record<(typeof SHAPES)[number] | "noise", string> = {
  circle: "●",
  diamond: "◆",
  square: "■",
  noise: "▲",
};
export const NOISE_COLOR = "#8a8f98";

export function clusterStyle(cluster: number): { color: string; shape: (typeof SHAPES)[number] | "noise" } {
  if (cluster < 0) return { color: NOISE_COLOR, shape: "noise" };
  return { color: PALETTE[cluster % PALETTE.length]!, shape: SHAPES[cluster % SHAPES.length]! };
}
