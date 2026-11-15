/**
 * Keeps real-derived data out of anything distributable.
 *
 * - A production build emits exactly two data files, `data/events.json` and `data/analysis.json`,
 *   read from the synthetic demo directory. Their raw-source hash must equal the SHA-256 of the
 *   checked-in synthetic fixture, so a real artifact is refused even if it is mislabelled.
 * - Real-derived artifacts are served only by the dev server in `--mode local-data`, from an ignored
 *   directory, at `/local-data/*`. This plugin has no code path that writes them into a bundle,
 *   and a build in local mode is refused outright.
 */
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import type { Plugin } from "vite";

export interface SeparationOptions {
  /** Directory holding the synthetic `events.json` and `analysis.json` for the demo. */
  demoDir: string;
  /** The checked-in synthetic input whose SHA-256 every demo artifact must trace back to. */
  fixturePath: string;
  /** Ignored local directory with real-derived artifacts; served in dev `--mode local-data` only. */
  localDir: string;
}

export const DATA_FILES = ["events.json", "analysis.json"] as const;
/** Vite reserves the mode name "local", so the local real-data mode is called "local-data". */
export const LOCAL_MODE = "local-data";

const sha256 = (b: Uint8Array): string => createHash("sha256").update(b).digest("hex");

function parse(label: string, bytes: Buffer): Record<string, unknown> {
  try {
    const v: unknown = JSON.parse(bytes.toString("utf-8"));
    if (typeof v === "object" && v !== null && !Array.isArray(v)) return v as Record<string, unknown>;
  } catch {
    /* fall through */
  }
  throw new Error(`${label} is not a JSON object`);
}

const obj = (v: unknown): Record<string, unknown> =>
  typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};

/** Read and verify the synthetic demo artifacts. Throws with a specific reason on any mismatch. */
export function readSyntheticDemo(opts: Pick<SeparationOptions, "demoDir" | "fixturePath">): Record<(typeof DATA_FILES)[number], Buffer> {
  for (const name of DATA_FILES) {
    if (!existsSync(path.join(opts.demoDir, name))) {
      throw new Error(
        `Missing ${path.join(opts.demoDir, name)}. Generate synthetic demo data first: ` +
          "python -m quakeexplorer build --input fixtures/synthetic_usgs.geojson --out-dir web/demo-data --dataset-kind synthetic",
      );
    }
  }
  if (!existsSync(opts.fixturePath)) throw new Error(`Missing synthetic fixture ${opts.fixturePath}`);
  const events = readFileSync(path.join(opts.demoDir, "events.json"));
  const analysis = readFileSync(path.join(opts.demoDir, "analysis.json"));
  const e = parse("events.json", events);
  const a = parse("analysis.json", analysis);
  const prov = obj(e.provenance);
  if (prov.dataset_kind !== "synthetic") throw new Error("demo events.json is not dataset_kind=synthetic; refusing to bundle it");
  const fixtureHash = sha256(readFileSync(opts.fixturePath));
  if (obj(prov.raw).sha256 !== fixtureHash) {
    throw new Error("demo events.json does not derive from the checked-in synthetic fixture (raw hash differs); refusing to bundle it");
  }
  if (a.source_raw_sha256 !== fixtureHash) throw new Error("demo analysis.json was not computed from the synthetic fixture");
  if (a.events_sha256 !== sha256(events)) throw new Error("demo analysis.json does not match demo events.json bytes");
  return { "events.json": events, "analysis.json": analysis };
}

type Next = (err?: unknown) => void;

export function dataSeparation(opts: SeparationOptions): Plugin {
  let isLocalMode = false;

  const middleware = (serveDemo: boolean, serveLocal: boolean) => (req: IncomingMessage, res: ServerResponse, next: Next) => {
    const url = (req.url ?? "").split("?")[0] ?? "";
    const m = /^\/(data|local-data)\/(events|analysis)\.json$/.exec(url);
    if (url.startsWith("/local-data/") && !serveLocal) {
      res.statusCode = 404;
      res.setHeader("Content-Type", "text/plain; charset=utf-8");
      res.end(`local data is only served by \`npm run local\` (vite --mode ${LOCAL_MODE})`);
      return;
    }
    if (!m) return next();
    const [, area, name] = m as unknown as [string, "data" | "local-data", string];
    if (area === "data" && !serveDemo) return next(); // preview: the built bundle serves /data
    try {
      let file: string;
      if (area === "data") {
        readSyntheticDemo(opts); // same checks as the build
        file = path.join(opts.demoDir, `${name}.json`);
      } else {
        file = path.join(opts.localDir, `${name}.json`);
      }
      if (!existsSync(file)) {
        res.statusCode = 404;
        res.end(`${file} not found`);
        return;
      }
      res.setHeader("Content-Type", "application/json");
      res.setHeader("Cache-Control", "no-store");
      res.end(readFileSync(file));
    } catch (err) {
      res.statusCode = 500;
      res.end(err instanceof Error ? err.message : String(err));
    }
  };

  return {
    name: "data-separation",
    config(_config, env) {
      isLocalMode = env.mode === LOCAL_MODE;
      if (env.command === "build" && isLocalMode) {
        throw new Error(`\`--mode ${LOCAL_MODE}\` can never produce a bundle: real-derived data must not be packaged. Use \`npm run build\`.`);
      }
    },
    configureServer(server) {
      server.middlewares.use(middleware(true, isLocalMode));
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware(false, false));
    },
    generateBundle() {
      const demo = readSyntheticDemo(opts);
      for (const name of DATA_FILES) {
        this.emitFile({ type: "asset", fileName: `data/${name}`, source: demo[name] });
      }
    },
  };
}
