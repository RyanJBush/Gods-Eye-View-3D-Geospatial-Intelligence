import type { Assignment, EventRecord } from "../src/types";

export function ev(id: string, overrides: Partial<EventRecord> = {}): EventRecord {
  return {
    id,
    origin_time_ms: 1704067200000,
    updated_ms: null,
    longitude_deg: 10,
    latitude_deg: 20,
    depth_km: 10,
    magnitude: 4.5,
    magnitude_type: "mb",
    place: "synthetic",
    status: "reviewed",
    net: "fx",
    url: null,
    ...overrides,
  };
}

export function asg(id: string, cluster: number, overrides: Partial<Assignment> = {}): Assignment {
  return {
    id,
    cluster,
    role: cluster < 0 ? "noise" : "core",
    ambiguous_border: false,
    grid_cell: "G20_40",
    shifted_cell: "S20_40",
    ...overrides,
  };
}

export const SHA = "a".repeat(64);

export function docs(events: EventRecord[], assignments: Assignment[]) {
  return {
    eventsDoc: {
      schema: "quake-events/1",
      provenance: {
        dataset_kind: "synthetic",
        source_credit: "Synthetic fixture data. Not real earthquakes.",
        raw: { sha256: SHA, bytes: 1 },
        usgs_api: { query_url: "https://example.invalid/q" },
        counts: { warnings: 0 },
      },
      events,
    },
    analysisDoc: {
      schema: "quake-analysis/1",
      source_raw_sha256: SHA,
      events_sha256: "b".repeat(64),
      algorithm: { eps_km: 250, min_samples: 4 },
      assignments,
    },
  };
}
