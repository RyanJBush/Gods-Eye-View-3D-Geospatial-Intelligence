import type { Assignment, Dataset, EventRecord, Role, Row } from "./types";
import { isSafeUsgsUrl } from "./url";

export class DatasetError extends Error {
  constructor(public readonly problems: string[]) {
    super(`Invalid dataset: ${problems.slice(0, 5).join("; ")}${problems.length > 5 ? ` (+${problems.length - 5} more)` : ""}`);
    this.name = "DatasetError";
  }
}

const JS_DATE_MAX_MS = 8_640_000_000_000_000;
const ROLES: ReadonlySet<string> = new Set(["core", "border", "noise"]);

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStrOrNull = (v: unknown): v is string | null => v === null || typeof v === "string";
const isNumOrNull = (v: unknown): v is number | null => v === null || isNum(v);
const isEpoch = (v: unknown): v is number =>
  isNum(v) && Number.isInteger(v) && Math.abs(v) <= JS_DATE_MAX_MS;

function parseEvent(raw: unknown, i: number, problems: string[]): EventRecord | null {
  const where = `events[${i}]`;
  if (!isObj(raw)) {
    problems.push(`${where} is not an object`);
    return null;
  }
  const before = problems.length;
  const { id, origin_time_ms, updated_ms, longitude_deg, latitude_deg, depth_km, magnitude } = raw;
  if (typeof id !== "string" || id === "") problems.push(`${where}.id must be a non-empty string`);
  if (!isEpoch(origin_time_ms)) problems.push(`${where}.origin_time_ms must be an integer in the JS Date range`);
  if (updated_ms !== null && !isEpoch(updated_ms)) problems.push(`${where}.updated_ms must be null or a JS Date-range integer`);
  if (!isNum(longitude_deg) || longitude_deg < -180 || longitude_deg > 180) problems.push(`${where}.longitude_deg out of range`);
  if (!isNum(latitude_deg) || latitude_deg < -90 || latitude_deg > 90) problems.push(`${where}.latitude_deg out of range`);
  if (!isNumOrNull(depth_km)) problems.push(`${where}.depth_km must be null or finite`);
  if (!isNumOrNull(magnitude)) problems.push(`${where}.magnitude must be null or finite`);
  for (const k of ["magnitude_type", "place", "status", "net", "url"] as const) {
    if (!isStrOrNull(raw[k])) problems.push(`${where}.${k} must be null or a string`);
  }
  if (problems.length > before) return null;
  return raw as unknown as EventRecord;
}

function parseAssignment(raw: unknown, i: number, problems: string[]): Assignment | null {
  const where = `assignments[${i}]`;
  if (!isObj(raw)) {
    problems.push(`${where} is not an object`);
    return null;
  }
  const before = problems.length;
  if (typeof raw.id !== "string") problems.push(`${where}.id must be a string`);
  if (!isNum(raw.cluster) || !Number.isInteger(raw.cluster) || raw.cluster < -1) problems.push(`${where}.cluster must be an integer >= -1`);
  if (typeof raw.role !== "string" || !ROLES.has(raw.role)) problems.push(`${where}.role invalid`);
  if (typeof raw.ambiguous_border !== "boolean") problems.push(`${where}.ambiguous_border must be boolean`);
  if (typeof raw.grid_cell !== "string") problems.push(`${where}.grid_cell must be a string`);
  if (typeof raw.shifted_cell !== "string") problems.push(`${where}.shifted_cell must be a string`);
  if (problems.length > before) return null;
  return raw as unknown as Assignment;
}

/** Join the source-only events artifact with the separate analysis artifact. Everything is
 * untrusted: shapes, ranges, and the join (hash and id order) are checked. */
export function parseDataset(eventsDoc: unknown, analysisDoc: unknown): Dataset {
  const problems: string[] = [];
  if (!isObj(eventsDoc) || eventsDoc.schema !== "quake-events/1") throw new DatasetError(["events artifact schema is not quake-events/1"]);
  if (!isObj(analysisDoc) || analysisDoc.schema !== "quake-analysis/1") throw new DatasetError(["analysis artifact schema is not quake-analysis/1"]);
  const prov = eventsDoc.provenance;
  if (!isObj(prov) || !isObj(prov.raw) || typeof prov.raw.sha256 !== "string") throw new DatasetError(["events provenance missing raw sha256"]);
  const kind = prov.dataset_kind;
  if (kind !== "real" && kind !== "synthetic") throw new DatasetError(["provenance.dataset_kind must be real or synthetic"]);
  if (typeof prov.source_credit !== "string") throw new DatasetError(["provenance.source_credit missing"]);
  if (analysisDoc.source_raw_sha256 !== prov.raw.sha256) {
    throw new DatasetError(["analysis was computed from a different source hash than the events artifact"]);
  }
  if (!Array.isArray(eventsDoc.events) || !Array.isArray(analysisDoc.assignments)) throw new DatasetError(["events and assignments must be arrays"]);
  if (eventsDoc.events.length !== analysisDoc.assignments.length) problems.push("events and assignments differ in length");

  const rows: Row[] = [];
  const seen = new Set<string>();
  const n = Math.min(eventsDoc.events.length, analysisDoc.assignments.length);
  for (let i = 0; i < n && problems.length < 50; i++) {
    const event = parseEvent(eventsDoc.events[i], i, problems);
    const analysis = parseAssignment(analysisDoc.assignments[i], i, problems);
    if (!event || !analysis) continue;
    if (event.id !== analysis.id) problems.push(`row ${i}: event id and assignment id differ`);
    if (seen.has(event.id)) problems.push(`duplicate id at ${i}`);
    seen.add(event.id);
    rows.push({ index: i, event, analysis, safeUrl: isSafeUsgsUrl(event.url) ? event.url : null });
  }
  if (rows.length === 0 && problems.length === 0) problems.push("no events");
  if (problems.length > 0) throw new DatasetError(problems);

  const algorithm = isObj(analysisDoc.algorithm) ? analysisDoc.algorithm : {};
  const clusters = new Set(rows.filter((r) => r.analysis.cluster >= 0).map((r) => r.analysis.cluster));
  const counts = isObj(prov.counts) ? prov.counts : {};
  const apiMeta = isObj(prov.usgs_api) ? prov.usgs_api : {};
  return {
    kind,
    sourceCredit: prov.source_credit,
    queryUrl: typeof apiMeta.query_url === "string" ? apiMeta.query_url : null,
    rawSha256: prov.raw.sha256,
    eventsSha256: typeof analysisDoc.events_sha256 === "string" ? analysisDoc.events_sha256 : "",
    params: {
      eps_km: isNum(algorithm.eps_km) ? algorithm.eps_km : NaN,
      min_samples: isNum(algorithm.min_samples) ? algorithm.min_samples : NaN,
    },
    rows,
    clusterCount: clusters.size,
    noiseCount: rows.filter((r) => r.analysis.cluster === -1).length,
    warnings: isNum(counts.warnings) ? counts.warnings : 0,
  };
}

export type { Role };
