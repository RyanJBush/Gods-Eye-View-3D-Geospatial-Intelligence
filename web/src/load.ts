import { DatasetError, parseDataset } from "./data";
import { verifyEventsBytes } from "./integrity";
import type { Dataset } from "./types";

export type FetchBytes = (url: string) => Promise<Uint8Array>;

export const defaultFetchBytes: FetchBytes = async (url) => {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return new Uint8Array(await res.arrayBuffer());
};

function parseJsonBytes(label: string, bytes: Uint8Array): unknown {
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new DatasetError([`${label} is not valid UTF-8 JSON`]);
  }
}

/** Load both artifacts, verify the events bytes against the analysis hash, and only then join. */
export async function loadDataset(base: string, fetchBytes: FetchBytes = defaultFetchBytes): Promise<Dataset> {
  const [eventsBytes, analysisBytes] = await Promise.all([
    fetchBytes(`${base}events.json`),
    fetchBytes(`${base}analysis.json`),
  ]);
  const analysisDoc = parseJsonBytes("analysis.json", analysisBytes);
  await verifyEventsBytes(eventsBytes, analysisDoc);
  const eventsDoc = parseJsonBytes("events.json", eventsBytes);
  return parseDataset(eventsDoc, analysisDoc);
}

/** `?data=local` selects the ignored local real-data directory served only by `npm run local`;
 * the default is the synthetic demo data that ships in the bundle. */
export function dataBase(search: string): string {
  return new URLSearchParams(search).get("data") === "local" ? "./local-data/" : "./data/";
}
