import "./style.css";
import { DatasetError } from "./data";
import { createGlobe } from "./globe";
import { renderInspector } from "./inspector";
import { dataBase, loadDataset } from "./load";
import { ViewLifecycle, type ViewPart } from "./lifecycle";
import { clusterStyle, groupLabel, SHAPE_SYMBOL } from "./rows";
import { SelectionController } from "./selection";
import { createTable } from "./table";
import type { Dataset } from "./types";

function $(id: string): HTMLElement {
  const node = document.getElementById(id);
  if (!node) throw new Error(`missing #${id}`);
  return node;
}

function showFatal(message: string, detail?: string): void {
  const box = $("fatal");
  box.hidden = false;
  box.replaceChildren();
  const h = document.createElement("strong");
  h.textContent = message;
  box.appendChild(h);
  if (detail) {
    const p = document.createElement("p");
    p.textContent = detail;
    box.appendChild(p);
  }
}

function renderSummary(ds: Dataset): void {
  const banner = $("kind-banner");
  banner.hidden = false;
  banner.textContent =
    ds.kind === "synthetic"
      ? "Synthetic fixture data. These are invented points, not real earthquakes."
      : "Local real-data view (USGS-derived). For this computer only: do not share, publish or bundle it.";
  $("credit").textContent = ds.sourceCredit;
  $("counts").textContent = `${ds.rows.length} events, ${ds.clusterCount} algorithmic groups, ${ds.noiseCount} noise points (DBSCAN, eps ${ds.params.eps_km} km, min_samples ${ds.params.min_samples}).`;
  $("query").textContent = ds.queryUrl ?? "not recorded";
  $("hash").textContent = ds.rawSha256;

  const legend = $("legend-list");
  legend.replaceChildren();
  const counts = new Map<number, number>();
  for (const r of ds.rows) counts.set(r.analysis.cluster, (counts.get(r.analysis.cluster) ?? 0) + 1);
  for (const cluster of [...counts.keys()].sort((a, b) => a - b)) {
    const li = document.createElement("li");
    const style = clusterStyle(cluster);
    const sym = document.createElement("span");
    sym.textContent = SHAPE_SYMBOL[style.shape];
    sym.className = "group-symbol";
    sym.style.color = style.color;
    sym.setAttribute("aria-hidden", "true");
    li.append(sym, document.createTextNode(` ${groupLabel(cluster)}: ${counts.get(cluster)} events`));
    legend.appendChild(li);
  }
}

async function start(): Promise<void> {
  const params = new URLSearchParams(location.search);
  const forceNoWebGL = params.get("webgl") === "off";
  const base = dataBase(location.search);
  let ds: Dataset;
  try {
    ds = await loadDataset(base);
  } catch (err) {
    if (err instanceof DatasetError) {
      showFatal("The dataset failed validation.", err.problems.slice(0, 8).join("\n"));
    } else {
      const hint =
        base === "./local-data/"
          ? "Local real-data viewing works only from `npm run local` after the pipeline has written data/derived."
          : "Generate the synthetic demo data first (see README), then reload.";
      showFatal("No dataset found.", `${err instanceof Error ? err.message : String(err)}. ${hint}`);
    }
    return;
  }
  renderSummary(ds);

  const controller = new SelectionController(new Set(ds.rows.map((r) => r.event.id)));
  const rowById = new Map(ds.rows.map((r) => [r.event.id, r] as const));
  const status = $("sr-status");
  const globeHost = $("globe");
  const fallback = $("globe-fallback");

  // `lifecycle` is assigned below; the globe's context-lost callback runs later, never during setup.
  let lifecycle!: ViewLifecycle;

  function makeGlobe(): ViewPart | null {
    const result = createGlobe(globeHost, ds.rows, controller, {
      forceNoWebGL,
      onContextLost: () => {
        lifecycle.dropGlobe();
        globeHost.hidden = true;
        fallback.hidden = false;
        fallback.textContent =
          "The 3D globe is unavailable (the browser lost the WebGL context). The table and inspector still work and show the same events.";
      },
    });
    if (result.ok) {
      globeHost.hidden = false;
      fallback.hidden = true;
      return result.handle;
    }
    globeHost.hidden = true;
    fallback.hidden = false;
    fallback.textContent = `The 3D globe is unavailable (${result.reason}). The table and inspector still work and show the same events.`;
    return null;
  }

  lifecycle = new ViewLifecycle({
    controller,
    createTable: () => createTable($("table-host"), ds.rows, controller),
    createGlobe: makeGlobe,
    onSelection: (id, source) => {
      const row = id === null ? null : (rowById.get(id) ?? null);
      renderInspector($("inspector"), row);
      if (source !== "restore") {
        status.textContent = row ? `Selected ${row.event.id}, ${groupLabel(row.analysis.cluster)}.` : "Selection cleared.";
      }
    },
  });
  lifecycle.mount();

  // Release GPU resources whenever the page is hidden for good or parked in the back-forward
  // cache; rebuild the view if the browser later restores it from that cache.
  window.addEventListener("pagehide", (e) => lifecycle.handlePageHide(e.persisted));
  window.addEventListener("pageshow", (e) => lifecycle.handlePageShow(e.persisted));

  // Read-only state for browser checks.
  (window as unknown as { __quake?: unknown }).__quake = {
    selected: () => controller.current,
    mode: () => (lifecycle.mounted ? (lifecycle.hasGlobe ? "globe" : "table-only") : "unmounted"),
    rows: ds.rows.length,
    kind: ds.kind,
    mountCount: () => lifecycle.mountCount,
    listeners: () => controller.listenerCount,
    canvases: () => document.querySelectorAll("canvas").length,
    tableRows: () => document.querySelectorAll("#table-host tbody tr").length,
    screenPosition: (id: string) => {
      const g = lifecycle.currentGlobe as (ViewPart & { screenPosition?: (id: string) => { x: number; y: number } | null }) | null;
      return g?.screenPosition?.(id) ?? null;
    },
    liveResources: () => {
      const g = lifecycle.currentGlobe as (ViewPart & { ledger?: { liveCount: number } }) | null;
      return g?.ledger?.liveCount ?? 0;
    },
  };
}

void start();
