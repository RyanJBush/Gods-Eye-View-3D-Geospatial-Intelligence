/**
 * Separation of local real data from distributable builds. These run real Vite builds and a real
 * dev server against temporary directories. Marker strings stand in for "real" data; scanning
 * for them is a supplemental check, while the structural checks (exact file allowlist, refused
 * builds, no code path that serves local data from a bundle) are the actual guarantee.
 */
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import http from "node:http";
import type { AddressInfo } from "node:net";
import os from "node:os";
import path from "node:path";
import { build, createServer } from "vite";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { dataSeparation, LOCAL_MODE, readSyntheticDemo, type SeparationOptions } from "../plugins/data-separation";

const sha = (b: Uint8Array | string) => createHash("sha256").update(b).digest("hex");
const MARKER = "REAL-LOOKING-MARKER-8f3a1c";

let tmp: string;
let opts: SeparationOptions;
let appRoot: string;

function writeJson(file: string, doc: unknown): Buffer {
  const bytes = Buffer.from(JSON.stringify(doc) + "\n");
  writeFileSync(file, bytes);
  return bytes;
}

function writeDemo(dir: string, fixtureBytes: Buffer, over: { kind?: string; rawHash?: string; analysisEventsHash?: string } = {}) {
  mkdirSync(dir, { recursive: true });
  const raw = over.rawHash ?? sha(fixtureBytes);
  const events = writeJson(path.join(dir, "events.json"), {
    schema: "quake-events/1",
    provenance: { dataset_kind: over.kind ?? "synthetic", raw: { sha256: raw } },
    events: [],
  });
  writeJson(path.join(dir, "analysis.json"), {
    schema: "quake-analysis/1",
    source_raw_sha256: raw,
    events_sha256: over.analysisEventsHash ?? sha(events),
    assignments: [],
  });
}

function listFiles(dir: string, base = dir): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((d) =>
    d.isDirectory() ? listFiles(path.join(dir, d.name), base) : [path.relative(base, path.join(dir, d.name)).replaceAll("\\", "/")],
  );
}

async function buildApp(outDir: string, mode = "production", pluginOpts: SeparationOptions = opts) {
  await build({
    root: appRoot,
    configFile: false,
    mode,
    logLevel: "silent",
    publicDir: false,
    plugins: [dataSeparation(pluginOpts)],
    build: { outDir, emptyOutDir: true },
  });
}

beforeAll(() => {
  tmp = mkdtempSync(path.join(os.tmpdir(), "quake-sep-"));
  appRoot = path.join(tmp, "app");
  mkdirSync(appRoot);
  writeFileSync(path.join(appRoot, "index.html"), '<!doctype html><html><head></head><body><script type="module" src="./main.js"></script></body></html>');
  writeFileSync(path.join(appRoot, "main.js"), "document.title = 'x';\n");
  const fixture = path.join(tmp, "synthetic_usgs.geojson");
  writeFileSync(fixture, "synthetic fixture bytes");
  const demoDir = path.join(tmp, "demo-data");
  writeDemo(demoDir, readFileSync(fixture));
  const localDir = path.join(tmp, "local-derived");
  mkdirSync(localDir);
  writeJson(path.join(localDir, "events.json"), { schema: "quake-events/1", provenance: { dataset_kind: "real", raw: { sha256: "r".repeat(64) } }, marker: MARKER, events: [] });
  writeJson(path.join(localDir, "analysis.json"), { schema: "quake-analysis/1", marker: MARKER, assignments: [] });
  opts = { demoDir, fixturePath: fixture, localDir };
});

afterAll(() => rmSync(tmp, { recursive: true, force: true }));

describe("production build", () => {
  it("emits only the synthetic demo data plus the app files, even with real-looking local data present", async () => {
    const out = path.join(tmp, "out-ok");
    await buildApp(out);
    const files = listFiles(out);
    expect(files.filter((f) => !f.startsWith("assets/")).sort()).toEqual(["data/analysis.json", "data/events.json", "index.html"]);
    expect(files.some((f) => f.includes("local"))).toBe(false);
    for (const f of files) expect(readFileSync(path.join(out, f), "utf-8")).not.toContain(MARKER); // supplemental
    expect(readFileSync(path.join(out, "data/events.json")).equals(readFileSync(path.join(opts.demoDir, "events.json")))).toBe(true);
  });

  it("refuses a real-labelled demo directory", async () => {
    const demoDir = path.join(tmp, "demo-real-kind");
    writeDemo(demoDir, readFileSync(opts.fixturePath), { kind: "real" });
    await expect(buildApp(path.join(tmp, "o1"), "production", { ...opts, demoDir })).rejects.toThrow(/not dataset_kind=synthetic/);
  });

  it("refuses a mislabelled artifact: label says synthetic but it does not derive from the fixture", async () => {
    const demoDir = path.join(tmp, "demo-wrong-hash");
    writeDemo(demoDir, readFileSync(opts.fixturePath), { rawHash: "9".repeat(64) });
    await expect(buildApp(path.join(tmp, "o2"), "production", { ...opts, demoDir })).rejects.toThrow(/does not derive from the checked-in synthetic fixture/);
  });

  it("refuses demo artifacts whose analysis does not match the events bytes", async () => {
    const demoDir = path.join(tmp, "demo-mismatch");
    writeDemo(demoDir, readFileSync(opts.fixturePath), { analysisEventsHash: "0".repeat(64) });
    await expect(buildApp(path.join(tmp, "o3"), "production", { ...opts, demoDir })).rejects.toThrow(/does not match demo events.json bytes/);
  });

  it("explains how to generate demo data when it is missing", () => {
    expect(() => readSyntheticDemo({ demoDir: path.join(tmp, "nope"), fixturePath: opts.fixturePath })).toThrow(/Generate synthetic demo data first/);
  });

  it("can never build in local mode, so local real data cannot be packaged", async () => {
    await expect(buildApp(path.join(tmp, "o4"), LOCAL_MODE)).rejects.toThrow(/can never produce a bundle/);
  });
});

describe("dev server", () => {
  async function get(mode: string, url: string) {
    const server = await createServer({
      root: appRoot,
      configFile: false,
      mode,
      logLevel: "silent",
      publicDir: false,
      plugins: [dataSeparation(opts)],
      server: { middlewareMode: true },
      appType: "custom",
    });
    const http_ = http.createServer(server.middlewares);
    await new Promise<void>((r) => http_.listen(0, "127.0.0.1", r));
    try {
      const res = await fetch(`http://127.0.0.1:${(http_.address() as AddressInfo).port}${url}`);
      return { status: res.status, text: await res.text() };
    } finally {
      await new Promise((r) => http_.close(r));
      await server.close();
    }
  }

  it("serves local real-derived data only in the local-data mode, from the ignored local directory", async () => {
    const r = await get(LOCAL_MODE, "/local-data/events.json");
    expect(r.status).toBe(200);
    expect(r.text).toContain(MARKER);
  });

  it("does not serve local data in any other mode", async () => {
    for (const mode of ["development", "production"]) {
      const r = await get(mode, "/local-data/events.json");
      expect(r.status).toBe(404);
      expect(r.text).not.toContain(MARKER);
    }
  });

  it("serves the verified synthetic demo at /data in every mode", async () => {
    for (const mode of ["development", LOCAL_MODE]) {
      const r = await get(mode, "/data/events.json");
      expect(r.status).toBe(200);
      expect(r.text).not.toContain(MARKER);
    }
  });
});
