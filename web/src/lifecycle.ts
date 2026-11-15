import type { SelectionController } from "./selection";

export interface ViewPart {
  setSelected(id: string | null, focus: boolean): void;
  dispose(): void;
}

export interface LifecycleDeps {
  controller: SelectionController;
  createTable(): ViewPart;
  /** Returns null when the globe is unavailable; the factory is responsible for the fallback UI. */
  createGlobe(): ViewPart | null;
  /** Called on every selection change and once after each (re)mount with source "restore". */
  onSelection(id: string | null, source: string): void;
}

/**
 * Owns the table and globe so they can be torn down on `pagehide` and rebuilt when the browser
 * restores the page from the back-forward cache (`pageshow` with `persisted`). Selection state
 * lives in the controller, which survives the round trip. Every method is idempotent.
 */
export class ViewLifecycle {
  private table: ViewPart | null = null;
  private globe: ViewPart | null = null;
  private unsubscribe: (() => void) | null = null;
  mountCount = 0;

  constructor(private readonly deps: LifecycleDeps) {}

  get mounted(): boolean {
    return this.table !== null;
  }

  get hasGlobe(): boolean {
    return this.globe !== null;
  }

  get currentGlobe(): ViewPart | null {
    return this.globe;
  }

  mount(): void {
    if (this.mounted) return;
    this.mountCount++;
    this.table = this.deps.createTable();
    this.globe = this.deps.createGlobe();
    this.unsubscribe = this.deps.controller.subscribe((id, source) => {
      this.table?.setSelected(id, source !== "table");
      this.globe?.setSelected(id, source === "table");
      this.deps.onSelection(id, source);
    });
    const current = this.deps.controller.current;
    this.table.setSelected(current, false);
    this.globe?.setSelected(current, current !== null);
    this.deps.onSelection(current, "restore");
  }

  /** Drop only the globe (e.g. WebGL context lost); the table keeps working. */
  dropGlobe(): void {
    const g = this.globe;
    this.globe = null;
    g?.dispose();
  }

  unmount(): void {
    if (!this.mounted) return;
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.dropGlobe();
    const t = this.table;
    this.table = null;
    t?.dispose();
  }

  /** Always release GPU resources and listeners. Only a page that is really going away also
   * discards the selection; a page entering the back-forward cache keeps it. */
  handlePageHide(persisted: boolean): void {
    this.unmount();
    if (!persisted) this.deps.controller.dispose();
  }

  /** `persisted` is false on the initial load, so only a bfcache restore remounts. */
  handlePageShow(persisted: boolean): void {
    if (persisted) this.mount();
  }
}
