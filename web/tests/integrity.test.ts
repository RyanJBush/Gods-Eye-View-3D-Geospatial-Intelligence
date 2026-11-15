import { describe, expect, it } from "vitest";
import { DatasetError } from "../src/data";
import { sha256Hex, verifyEventsBytes } from "../src/integrity";
import { dataBase, loadDataset, type FetchBytes } from "../src/load";
import { asg, docs, ev, SHA } from "./helpers";

const enc = new TextEncoder();
const bytesOf = (doc: unknown, indent?: number) => enc.encode(JSON.stringify(doc, null, indent));

describe("sha256Hex", () => {
  it("matches a known vector", async () => {
    expect(await sha256Hex(enc.encode("abc"))).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });
});

/** Two events artifacts with the SAME raw-source hash but different canonical bytes, plus an
 * analysis that was computed from the first. */
async function sameRawDifferentEvents() {
  const first = docs([ev("a", { place: "one" })], [asg("a", 0)]);
  const second = docs([ev("a", { place: "two" })], [asg("a", 0)]);
  expect(first.eventsDoc.provenance.raw.sha256).toBe(second.eventsDoc.provenance.raw.sha256);
  const eventsA = bytesOf(first.eventsDoc);
  const eventsB = bytesOf(second.eventsDoc);
  const analysis = { ...first.analysisDoc, events_sha256: await sha256Hex(eventsA) };
  return { eventsA, eventsB, analysis, first, second };
}

function serve(files: Record<string, Uint8Array>): FetchBytes {
  return async (url) => {
    const name = url.split("/").pop()!;
    const b = files[name];
    if (!b) throw new Error(`${url}: HTTP 404`);
    return b;
  };
}

describe("events.json integrity (regression: same raw hash, different canonical bytes)", () => {
  it("accepts the events bytes the analysis was computed from", async () => {
    const { eventsA, analysis } = await sameRawDifferentEvents();
    const ds = await loadDataset("./data/", serve({ "events.json": eventsA, "analysis.json": bytesOf(analysis) }));
    expect(ds.rows[0]!.event.place).toBe("one");
  });

  it("rejects events with the same raw-source hash but different bytes, with a clear error", async () => {
    const { eventsB, analysis } = await sameRawDifferentEvents();
    const run = loadDataset("./data/", serve({ "events.json": eventsB, "analysis.json": bytesOf(analysis) }));
    await expect(run).rejects.toBeInstanceOf(DatasetError);
    await expect(run).rejects.toThrow(/does not match the analysis/);
    await expect(run).rejects.toThrow(/different builds/);
  });

  it("hashes the loaded bytes, not a re-serialisation: whitespace-only differences are rejected", async () => {
    const { first, analysis } = await sameRawDifferentEvents();
    const pretty = bytesOf(first.eventsDoc, 2); // same content, different bytes
    await expect(
      loadDataset("./data/", serve({ "events.json": pretty, "analysis.json": bytesOf(analysis) })),
    ).rejects.toThrow(/does not match the analysis/);
  });

  it("verification happens before the join: a mismatch never reaches parseDataset", async () => {
    const { first, analysis } = await sameRawDifferentEvents();
    // These bytes would also fail join validation (wrong schema); the hash error must win.
    const junk = bytesOf({ ...first.eventsDoc, schema: "wrong" });
    await expect(loadDataset("./data/", serve({ "events.json": junk, "analysis.json": bytesOf(analysis) }))).rejects.toThrow(
      /does not match the analysis/,
    );
  });

  it.each([undefined, "", "xyz", "A".repeat(64), 5])("rejects a missing or malformed events_sha256 (%s)", async (bad) => {
    const { eventsA, analysis } = await sameRawDifferentEvents();
    await expect(verifyEventsBytes(eventsA, { ...analysis, events_sha256: bad })).rejects.toThrow(/no valid events_sha256/);
  });

  it("rejects non-JSON artifacts and propagates fetch failures", async () => {
    const { eventsA, analysis } = await sameRawDifferentEvents();
    await expect(loadDataset("./data/", serve({ "events.json": eventsA, "analysis.json": enc.encode("<html>") }))).rejects.toThrow(/analysis.json is not valid/);
    await expect(loadDataset("./data/", serve({ "analysis.json": bytesOf(analysis) }))).rejects.toThrow(/404/);
  });

  it("the helper source hash is shared by both artifacts", async () => {
    const { first } = await sameRawDifferentEvents();
    expect(first.analysisDoc.source_raw_sha256).toBe(SHA);
  });
});

describe("dataBase", () => {
  it("defaults to the bundled synthetic data; only ?data=local selects the local path", () => {
    expect(dataBase("")).toBe("./data/");
    expect(dataBase("?webgl=off")).toBe("./data/");
    expect(dataBase("?data=other")).toBe("./data/");
    expect(dataBase("?data=local")).toBe("./local-data/");
  });
});
