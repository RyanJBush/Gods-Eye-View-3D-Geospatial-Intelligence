/**
 * Lifecycle regression tests. These drive ViewLifecycle with fake parts and simulated
 * pagehide/pageshow calls. They check the logic, NOT a real browser back-forward cache.
 */
import { describe, expect, it } from "vitest";
import { ViewLifecycle, type ViewPart } from "../src/lifecycle";
import { ResourceLedger } from "../src/resources";
import { SelectionController } from "../src/selection";

interface FakePart extends ViewPart {
  calls: [string | null, boolean][];
  disposed: number;
  ledger?: ResourceLedger;
}

function rig(options: { globe?: boolean; resourcesPerGlobe?: number } = {}) {
  const controller = new SelectionController(new Set(["a", "b", "c"]));
  const tables: FakePart[] = [];
  const globes: FakePart[] = [];
  const seen: [string | null, string][] = [];
  const part = (): FakePart => {
    const p: FakePart = {
      calls: [],
      disposed: 0,
      setSelected(id, focus) {
        p.calls.push([id, focus]);
      },
      dispose() {
        p.disposed++;
        p.ledger?.disposeAll();
      },
    };
    return p;
  };
  const lifecycle = new ViewLifecycle({
    controller,
    createTable: () => {
      const t = part();
      tables.push(t);
      return t;
    },
    createGlobe: () => {
      if (options.globe === false) return null;
      const g = part();
      g.ledger = new ResourceLedger();
      for (let i = 0; i < (options.resourcesPerGlobe ?? 3); i++) g.ledger.track({ dispose() {} }, `r${i}`);
      globes.push(g);
      return g;
    },
    onSelection: (id, source) => seen.push([id, source]),
  });
  return { controller, lifecycle, tables, globes, seen };
}

const live = (globes: FakePart[]) => globes.reduce((n, g) => n + (g.ledger?.liveCount ?? 0), 0);

describe("ViewLifecycle: bfcache round trip (simulated events)", () => {
  it("pagehide(persisted) releases everything but keeps selection; pageshow(persisted) rebuilds and restores it", () => {
    const { controller, lifecycle, tables, globes, seen } = rig();
    lifecycle.mount();
    controller.select("b", "globe");
    expect(controller.listenerCount).toBe(1);
    expect(live(globes)).toBe(3);

    lifecycle.handlePageHide(true);
    expect(lifecycle.mounted).toBe(false);
    expect(tables[0]!.disposed).toBe(1);
    expect(globes[0]!.disposed).toBe(1);
    expect(live(globes)).toBe(0); // nothing parked in the cache
    expect(controller.listenerCount).toBe(0);
    expect(controller.current).toBe("b"); // selection survives

    lifecycle.handlePageShow(true);
    expect(lifecycle.mounted).toBe(true);
    expect(tables).toHaveLength(2);
    expect(globes).toHaveLength(2);
    expect(live(globes)).toBe(3); // exactly one live globe's resources again
    expect(controller.listenerCount).toBe(1);
    expect(tables[1]!.calls.at(-1)).toEqual(["b", false]);
    expect(globes[1]!.calls.at(-1)).toEqual(["b", true]);
    expect(seen.at(-1)).toEqual(["b", "restore"]);

    // selection keeps working through the new parts, shared by table and globe
    controller.select("c", "table");
    expect(tables[1]!.calls.at(-1)).toEqual(["c", false]);
    expect(globes[1]!.calls.at(-1)).toEqual(["c", true]);
    controller.select("a", "globe");
    expect(tables[1]!.calls.at(-1)).toEqual(["a", true]);
    expect(controller.current).toBe("a");
  });

  it("does not leak across many round trips and never double-disposes", () => {
    const { controller, lifecycle, tables, globes } = rig({ resourcesPerGlobe: 4 });
    lifecycle.mount();
    for (let i = 0; i < 5; i++) {
      lifecycle.handlePageHide(true);
      lifecycle.handlePageHide(true); // repeated pagehide is a no-op
      expect(live(globes)).toBe(0);
      lifecycle.handlePageShow(true);
      lifecycle.handlePageShow(true); // repeated pageshow does not stack a second view
      expect(live(globes)).toBe(4);
      expect(controller.listenerCount).toBe(1);
    }
    expect(tables).toHaveLength(6);
    expect(globes).toHaveLength(6);
    expect(tables.map((t) => t.disposed)).toEqual([1, 1, 1, 1, 1, 0]);
    expect(globes.map((g) => g.disposed)).toEqual([1, 1, 1, 1, 1, 0]);
    expect(lifecycle.mountCount).toBe(6);
  });

  it("ignores pageshow that is not a cache restore (initial load, or already mounted)", () => {
    const { lifecycle, tables } = rig();
    lifecycle.handlePageShow(false);
    expect(lifecycle.mounted).toBe(false);
    lifecycle.mount();
    lifecycle.handlePageShow(true); // no pagehide happened: must not create a second view
    expect(tables).toHaveLength(1);
  });

  it("a page that is really going away (persisted=false) also discards the selection", () => {
    const { controller, lifecycle, globes } = rig();
    lifecycle.mount();
    controller.select("a", "table");
    lifecycle.handlePageHide(false);
    expect(live(globes)).toBe(0);
    expect(controller.current).toBeNull();
    expect(controller.listenerCount).toBe(0);
  });

  it("table-only fallback (no globe) survives the round trip with selection intact", () => {
    const { controller, lifecycle, tables } = rig({ globe: false });
    lifecycle.mount();
    controller.select("b", "table");
    expect(lifecycle.hasGlobe).toBe(false);
    lifecycle.handlePageHide(true);
    lifecycle.handlePageShow(true);
    expect(lifecycle.mounted).toBe(true);
    expect(lifecycle.hasGlobe).toBe(false);
    expect(tables[1]!.calls.at(-1)).toEqual(["b", false]);
  });

  it("dropGlobe (WebGL context lost) keeps the table and is not disposed twice at pagehide", () => {
    const { controller, lifecycle, tables, globes } = rig();
    lifecycle.mount();
    lifecycle.dropGlobe();
    expect(globes[0]!.disposed).toBe(1);
    expect(lifecycle.mounted).toBe(true);
    controller.select("a", "table");
    expect(tables[0]!.calls.at(-1)).toEqual(["a", false]);
    lifecycle.handlePageHide(true);
    expect(globes[0]!.disposed).toBe(1);
    expect(tables[0]!.disposed).toBe(1);
  });
});
