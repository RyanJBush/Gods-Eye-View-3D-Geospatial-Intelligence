import { filterRows, groupLabel, type GroupFilter, NOT_REPORTED, SHAPE_SYMBOL, clusterStyle, sortRows, type SortDir, type SortKey, formatUtc } from "./rows";
import type { SelectionController } from "./selection";
import type { Row } from "./types";

export interface TableView {
  setSelected(id: string | null, scrollIntoView: boolean): void;
  dispose(): void;
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "id", label: "Event ID" },
  { key: "time", label: "Origin time (UTC)" },
  { key: "magnitude", label: "Magnitude" },
  { key: "depth", label: "Depth (km)" },
  { key: "group", label: "Algorithmic group" },
];

function el<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string, cls?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text; // never innerHTML: ids and places are untrusted
  if (cls) node.className = cls;
  return node;
}

export function createTable(host: HTMLElement, rows: readonly Row[], controller: SelectionController): TableView {
  let sortKey: SortKey = "id";
  let sortDir: SortDir = "asc";
  let filter: GroupFilter = "all";
  let selected: string | null = controller.current;

  const controls = el("div", undefined, "table-controls");
  const filterLabel = el("label", "Show ");
  const select = el("select");
  select.setAttribute("aria-label", "Filter by algorithmic group");
  const addOption = (value: string, label: string) => {
    const o = el("option", label);
    o.value = value;
    select.appendChild(o);
  };
  addOption("all", "All events");
  addOption("noise", "Noise only");
  const clusters = [...new Set(rows.filter((r) => r.analysis.cluster >= 0).map((r) => r.analysis.cluster))].sort((a, b) => a - b);
  for (const c of clusters) addOption(String(c), groupLabel(c));
  filterLabel.appendChild(select);
  const count = el("span", "", "table-count");
  count.setAttribute("role", "status");
  controls.append(filterLabel, count);

  const wrap = el("div", undefined, "table-scroll");
  wrap.tabIndex = 0;
  wrap.setAttribute("role", "region");
  wrap.setAttribute("aria-label", "Events table");
  const table = el("table");
  const caption = el("caption", "Events in this snapshot. Choose a row to select the same event on the globe and in the inspector.");
  caption.className = "sr-only";
  const thead = el("thead");
  const headRow = el("tr");
  const headButtons = new Map<SortKey, { th: HTMLTableCellElement; button: HTMLButtonElement }>();
  for (const col of COLUMNS) {
    const th = el("th");
    th.scope = "col";
    const button = el("button", col.label);
    button.type = "button";
    button.addEventListener("click", () => {
      if (sortKey === col.key) sortDir = sortDir === "asc" ? "desc" : "asc";
      else {
        sortKey = col.key;
        sortDir = "asc";
      }
      render();
    });
    th.appendChild(button);
    headRow.appendChild(th);
    headButtons.set(col.key, { th, button });
  }
  thead.appendChild(headRow);
  const tbody = el("tbody");
  table.append(caption, thead, tbody);
  wrap.appendChild(table);
  host.replaceChildren(controls, wrap);

  let trById = new Map<string, HTMLTableRowElement>();
  let visible: Row[] = [];

  function render() {
    visible = sortRows(filterRows(rows, filter), sortKey, sortDir);
    for (const [key, { th }] of headButtons) {
      th.setAttribute("aria-sort", key === sortKey ? (sortDir === "asc" ? "ascending" : "descending") : "none");
    }
    const frag = document.createDocumentFragment();
    trById = new Map();
    const tabStop = selected !== null && visible.some((r) => r.event.id === selected) ? selected : visible[0]?.event.id;
    for (const row of visible) {
      const e = row.event;
      const tr = el("tr");
      tr.dataset.id = e.id;
      const idCell = el("td");
      const btn = el("button", e.id, "id-button");
      btn.type = "button";
      btn.tabIndex = e.id === tabStop ? 0 : -1;
      idCell.appendChild(btn);
      const style = clusterStyle(row.analysis.cluster);
      const groupCell = el("td");
      const sym = el("span", SHAPE_SYMBOL[style.shape], "group-symbol");
      sym.style.color = style.color;
      sym.setAttribute("aria-hidden", "true");
      groupCell.append(sym, document.createTextNode(` ${groupLabel(row.analysis.cluster)}`));
      tr.append(
        idCell,
        el("td", formatUtc(e.origin_time_ms)),
        el("td", e.magnitude === null ? NOT_REPORTED : String(e.magnitude)),
        el("td", e.depth_km === null ? NOT_REPORTED : String(e.depth_km)),
        groupCell,
      );
      trById.set(e.id, tr);
      frag.appendChild(tr);
    }
    tbody.replaceChildren(frag);
    count.textContent = `${visible.length} of ${rows.length} events`;
    paintSelection(false);
  }

  function paintSelection(scroll: boolean) {
    for (const [id, tr] of trById) {
      const isSel = id === selected;
      tr.classList.toggle("selected", isSel);
      const btn = tr.querySelector("button");
      if (btn) {
        if (isSel) btn.setAttribute("aria-current", "true");
        else btn.removeAttribute("aria-current");
      }
    }
    if (scroll && selected !== null) trById.get(selected)?.scrollIntoView({ block: "nearest" });
  }

  const rowButtons = () => [...tbody.querySelectorAll<HTMLButtonElement>("button.id-button")];
  function focusButton(btn: HTMLButtonElement | undefined) {
    if (!btn) return;
    for (const b of rowButtons()) b.tabIndex = b === btn ? 0 : -1;
    btn.focus();
    const id = btn.closest("tr")?.dataset.id;
    if (id) controller.select(id, "table");
  }

  const onTbodyClick = (ev: Event) => {
    const id = (ev.target as Element).closest("tr")?.dataset.id;
    if (id) controller.select(id, "table");
  };
  const onTbodyKey = (ev: KeyboardEvent) => {
    const buttons = rowButtons();
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (current < 0) return;
    let target: number | null = null;
    if (ev.key === "ArrowDown") target = Math.min(buttons.length - 1, current + 1);
    else if (ev.key === "ArrowUp") target = Math.max(0, current - 1);
    else if (ev.key === "Home") target = 0;
    else if (ev.key === "End") target = buttons.length - 1;
    if (target === null) return;
    ev.preventDefault();
    focusButton(buttons[target]);
  };
  const onFilter = () => {
    filter = select.value === "all" ? "all" : select.value === "noise" ? "noise" : Number(select.value);
    render();
  };
  tbody.addEventListener("click", onTbodyClick);
  tbody.addEventListener("keydown", onTbodyKey);
  select.addEventListener("change", onFilter);
  render();

  return {
    setSelected(id, scrollIntoView) {
      selected = id;
      if (id !== null && !trById.has(id)) {
        // Selected event is hidden by the current filter; show everything so it is visible.
        filter = "all";
        select.value = "all";
        render();
      }
      paintSelection(scrollIntoView);
    },
    dispose() {
      tbody.removeEventListener("click", onTbodyClick);
      tbody.removeEventListener("keydown", onTbodyKey);
      select.removeEventListener("change", onFilter);
      host.replaceChildren();
      trById.clear();
    },
  };
}
