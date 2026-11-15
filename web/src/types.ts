export interface EventRecord {
  id: string;
  origin_time_ms: number;
  updated_ms: number | null;
  longitude_deg: number;
  latitude_deg: number;
  depth_km: number | null;
  magnitude: number | null;
  magnitude_type: string | null;
  place: string | null;
  status: string | null;
  net: string | null;
  url: string | null;
}

export type Role = "core" | "border" | "noise";

export interface Assignment {
  id: string;
  cluster: number; // -1 is DBSCAN noise
  role: Role;
  ambiguous_border: boolean;
  grid_cell: string;
  shifted_cell: string;
}

export interface Row {
  index: number; // position in the dataset (UTF-8 byte order of id)
  event: EventRecord;
  analysis: Assignment;
  /** The event URL, only if it passed the safe-link rule; otherwise null. */
  safeUrl: string | null;
}

export interface Dataset {
  kind: "real" | "synthetic";
  sourceCredit: string;
  queryUrl: string | null;
  rawSha256: string;
  eventsSha256: string;
  params: { eps_km: number; min_samples: number };
  rows: Row[];
  clusterCount: number;
  noiseCount: number;
  warnings: number;
}
