import { describe, expect, it, vi } from "vitest";
import { DatasetError, parseDataset } from "../src/data";
import { latLonToXYZ } from "../src/geo";
import { ResourceLedger } from "../src/resources";
import { clusterStyle, describeRow, filterRows, formatUtc, NOT_REPORTED, PALETTE, SHAPES, sortRows } from "../src/rows";
import { SelectionController } from "../src/selection";
import { isSafeUsgsUrl } from "../src/url";
import { asg, docs, ev, SHA } from "./helpers";

const SAFE = "https://earthquake.usgs.gov/earthquakes/eventpage/fx1";

describe("isSafeUsgsUrl", () => {
  it("accepts only https on exactly earthquake.usgs.gov", () => {
    expect(isSafeUsgsUrl(SAFE)).toBe(true);
  });
  it.each([
    "http://earthquake.usgs.gov/x",
    "https://earthquake.usgs.gov.evil.example/x",
    "javascript:alert(1)",
    "https://earthquake.usgs.gov@evil.example/",
    "https://user:pw@earthquake.usgs.gov/x",
    "https://earthquake.usgs.gov:8443/x",
    "https://earthquake.usgs.gov./x",
    "https://earthquake.usgs.gov/a b",
    "https://earthquake.usgs.gov\\@evil.example/",
    "//earthquake.usgs.gov/x",
    "",
    "not a url",
  ])("rejects %s", (u) => expect(isSafeUsgsUrl(u)).toBe(false));
  it("rejects non-strings", () => {
    for (const v of [null, undefined, 5, {}, []]) expect(isSafeUsgsUrl(v)).toBe(false);
  });
});

describe("parseDataset", () => {
  const good = () => docs([ev("a"), ev("b", { magnitude: null, url: SAFE })], [asg("a", 0), asg("b", -1)]);

  it("joins events with analysis and keeps nulls as null", () => {
    const { eventsDoc, analysisDoc } = good();
    const ds = parseDataset(eventsDoc, analysisDoc);
    expect(ds.rows.map((r) => r.event.id)).toEqual(["a", "b"]);
    expect(ds.rows[1]!.event.magnitude).toBeNull();
    expect(ds.rows[1]!.safeUrl).toBe(SAFE);
    expect(ds.clusterCount).toBe(1);
    expect(ds.noiseCount).toBe(1);
    expect(ds.kind).toBe("synthetic");
    expect(ds.params).toEqual({ eps_km: 250, min_samples: 4 });
  });

  it("suppresses an unsafe link without rejecting the event", () => {
    const { eventsDoc, analysisDoc } = docs([ev("a", { url: "http://evil.example/x" })], [asg("a", 0)]);
    const ds = parseDataset(eventsDoc, analysisDoc);
    expect(ds.rows[0]!.safeUrl).toBeNull();
  });

  it("rejects analysis from a different source hash", () => {
    const { eventsDoc, analysisDoc } = good();
    (analysisDoc as { source_raw_sha256: string }).source_raw_sha256 = "c".repeat(64);
    expect(() => parseDataset(eventsDoc, analysisDoc)).toThrow(DatasetError);
  });

  it("rejects wrong schemas, length mismatch, id mismatch, duplicates, bad values", () => {
    let d = good();
    (d.eventsDoc as { schema: string }).schema = "other";
    expect(() => parseDataset(d.eventsDoc, d.analysisDoc)).toThrow(DatasetError);

    d = good();
    d.analysisDoc.assignments.pop();
    expect(() => parseDataset(d.eventsDoc, d.analysisDoc)).toThrow(/differ in length/);

    d = docs([ev("a"), ev("b")], [asg("a", 0), asg("zzz", 0)]);
    expect(() => parseDataset(d.eventsDoc, d.analysisDoc)).toThrow(/ids? differ|differ/);

    d = docs([ev("a"), ev("a")], [asg("a", 0), asg("a", 0)]);
    expect(() => parseDataset(d.eventsDoc, d.analysisDoc)).toThrow(/duplicate/);

    for (const bad of [
      { latitude_deg: 91 },
      { longitude_deg: -181 },
      { origin_time_ms: 1.5 },
      { origin_time_ms: 8_640_000_000_000_001 },
      { magnitude: "4.5" as unknown as number },
      { place: 5 as unknown as string },
    ]) {
      d = docs([ev("a", bad)], [asg("a", 0)]);
      expect(() => parseDataset(d.eventsDoc, d.analysisDoc)).toThrow(DatasetError);
    }
    d = docs([ev("a")], [asg("a", -2)]);
    expect(() => parseDataset(d.eventsDoc, d.analysisDoc)).toThrow(DatasetError);
    d = docs([], []);
    expect(() => parseDataset(d.eventsDoc, d.analysisDoc)).toThrow(/no events/);
  });

  it("source hash constant is what the helper uses", () => {
    expect(good().eventsDoc.provenance.raw.sha256).toBe(SHA);
  });
});

describe("SelectionController", () => {
  const make = () => new SelectionController(new Set(["a", "b", "c"]));

  it("selects by id, notifies once per change, and reports the source", () => {
    const c = make();
    const fn = vi.fn();
    c.subscribe(fn);
    expect(c.select("a", "table")).toBe(true);
    expect(c.select("a", "globe")).toBe(false); // same event: no echo
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith("a", "table");
    expect(c.current).toBe("a");
  });

  it("table and globe selecting the same event leave one shared state", () => {
    const c = make();
    c.select("b", "globe");
    c.select("c", "table");
    expect(c.current).toBe("c");
    c.select("b", "globe");
    expect(c.current).toBe("b");
  });

  it("ignores unknown ids, supports clearing, unsubscribing, and listener failures", () => {
    const c = make();
    const seen: (string | null)[] = [];
    const off = c.subscribe((id) => seen.push(id));
    c.subscribe(() => {
      throw new Error("boom");
    });
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(c.select("nope", "t")).toBe(false);
    expect(c.current).toBeNull();
    c.select("a", "t");
    c.select(null, "t");
    expect(seen).toEqual(["a", null]); // the throwing listener did not block the other
    expect(err).toHaveBeenCalled();
    off();
    c.select("b", "t");
    expect(seen).toEqual(["a", null]);
    err.mockRestore();
  });

  it("dispose clears listeners and state", () => {
    const c = make();
    c.subscribe(() => {});
    c.select("a", "t");
    c.dispose();
    expect(c.listenerCount).toBe(0);
    expect(c.current).toBeNull();
  });
});

describe("rows", () => {
  const rows = parseDataset(
    ...(Object.values(
      docs(
        [
          ev("a", { magnitude: 5, depth_km: null, origin_time_ms: 300 }),
          ev("b", { magnitude: null, depth_km: 5, origin_time_ms: 100 }),
          ev("c", { magnitude: 4.6, depth_km: 20, origin_time_ms: 200 }),
          ev("d", { magnitude: 5, depth_km: 1, origin_time_ms: 400, url: SAFE }),
        ],
        [asg("a", 1), asg("b", -1), asg("c", 0), asg("d", 1)],
      ),
    ) as [unknown, unknown]),
  ).rows;

  it("sorts with missing values last in both directions, ties by dataset order", () => {
    expect(sortRows(rows, "magnitude", "asc").map((r) => r.event.id)).toEqual(["c", "a", "d", "b"]);
    expect(sortRows(rows, "magnitude", "desc").map((r) => r.event.id)).toEqual(["a", "d", "c", "b"]);
    expect(sortRows(rows, "depth", "asc").map((r) => r.event.id)).toEqual(["d", "b", "c", "a"]);
    expect(sortRows(rows, "time", "desc").map((r) => r.event.id)).toEqual(["d", "a", "c", "b"]);
    expect(sortRows(rows, "id", "asc").map((r) => r.event.id)).toEqual(["a", "b", "c", "d"]);
    expect(sortRows(rows, "group", "asc").map((r) => r.event.id)).toEqual(["b", "c", "a", "d"]);
  });

  it("filters by group and noise", () => {
    expect(filterRows(rows, "noise").map((r) => r.event.id)).toEqual(["b"]);
    expect(filterRows(rows, 1).map((r) => r.event.id)).toEqual(["a", "d"]);
    expect(filterRows(rows, "all")).toHaveLength(4);
  });

  it("shows missing values explicitly and only links safe urls", () => {
    const f = Object.fromEntries(describeRow(rows[1]!).map((x) => [x.label, x]));
    expect(f["Magnitude"]!.value).toBe(NOT_REPORTED);
    expect(f["Event page"]!.value).toBe(NOT_REPORTED);
    expect(f["Event page"]!.href).toBeUndefined();
    const g = Object.fromEntries(describeRow(rows[3]!).map((x) => [x.label, x]));
    expect(g["Event page"]!.href).toBe(SAFE);
    expect(g["Depth"]!.value).toBe("1 km");
    expect(describeRow(rows[0]!).find((x) => x.label === "Depth")!.value).toBe(NOT_REPORTED);
  });

  it("describes unsafe urls without making them links", () => {
    const { eventsDoc, analysisDoc } = docs([ev("a", { url: "javascript:alert(1)" })], [asg("a", 0)]);
    const row = parseDataset(eventsDoc, analysisDoc).rows[0]!;
    const url = describeRow(row).find((x) => x.label === "Event page")!;
    expect(url.href).toBeUndefined();
    expect(url.value).toMatch(/suppressed/);
  });

  it("formats time in UTC and survives the extreme range", () => {
    expect(formatUtc(1704069429096)).toBe("2024-01-01T00:37:09.096Z");
    expect(formatUtc(null)).toBe(NOT_REPORTED);
    expect(() => formatUtc(8_640_000_000_000_000)).not.toThrow();
  });

  it("uses distinct color+shape pairs for 21 groups and a separate noise style", () => {
    const seen = new Set<string>();
    for (let c = 0; c < PALETTE.length * SHAPES.length; c++) {
      const s = clusterStyle(c);
      seen.add(`${s.color}|${s.shape}`);
    }
    expect(seen.size).toBe(21);
    expect(clusterStyle(-1).shape).toBe("noise");
  });
});

describe("latLonToXYZ", () => {
  it("places poles, equator and the dateline on the unit sphere", () => {
    expect(latLonToXYZ(90, 0)[1]).toBeCloseTo(1, 12);
    expect(latLonToXYZ(-90, 33)[1]).toBeCloseTo(-1, 12);
    const [x, y, z] = latLonToXYZ(0, 0);
    expect([x, y, z]).toEqual([0, 0, 1]);
    const a = latLonToXYZ(12, 180);
    const b = latLonToXYZ(12, -180);
    for (let i = 0; i < 3; i++) expect(a[i]).toBeCloseTo(b[i]!, 12);
    const r = latLonToXYZ(33, -77, 2.5);
    expect(Math.hypot(...r)).toBeCloseTo(2.5, 12);
  });
});

describe("ResourceLedger", () => {
  const disposable = () => ({ dispose: vi.fn() });

  it("disposes each tracked resource once; shared resources are tracked once; idempotent", () => {
    const l = new ResourceLedger();
    const geo = disposable();
    const mat = disposable();
    l.track(geo, "geo");
    l.track(mat, "mat");
    l.track(geo, "geo again"); // shared geometry used by two meshes
    expect(l.liveCount).toBe(2);
    l.disposeAll();
    l.disposeAll();
    expect(geo.dispose).toHaveBeenCalledTimes(1);
    expect(mat.dispose).toHaveBeenCalledTimes(1);
    expect(l.liveCount).toBe(0);
    expect(l.disposedTotal).toBe(2);
  });

  it("keeps disposing after a failure and reports it", () => {
    const l = new ResourceLedger();
    const bad = { dispose: vi.fn(() => { throw new Error("x"); }) };
    const ok = disposable();
    l.track(bad, "bad");
    l.track(ok, "ok");
    expect(() => l.disposeAll()).toThrow(AggregateError);
    expect(ok.dispose).toHaveBeenCalledTimes(1);
    expect(l.liveCount).toBe(0);
  });
});
