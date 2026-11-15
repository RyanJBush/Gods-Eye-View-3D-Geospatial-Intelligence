import { describeRow } from "./rows";
import type { Row } from "./types";

/** Renders one event's source fields, missing values included. Text only, links only if safe. */
export function renderInspector(host: HTMLElement, row: Row | null): void {
  if (row === null) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "No event selected. Click a marker on the globe or choose a row in the table.";
    host.replaceChildren(p);
    return;
  }
  const dl = document.createElement("dl");
  for (const field of describeRow(row)) {
    const dt = document.createElement("dt");
    dt.textContent = field.label;
    const dd = document.createElement("dd");
    if (field.href) {
      const a = document.createElement("a");
      a.href = field.href;
      a.textContent = field.value;
      a.rel = "noopener noreferrer";
      a.target = "_blank";
      dd.appendChild(a);
    } else {
      dd.textContent = field.value;
    }
    dl.append(dt, dd);
  }
  host.replaceChildren(dl);
}
