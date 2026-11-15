/** Renderer-independent selection state shared by the table, the inspector and the globe. */
export type SelectionListener = (id: string | null, source: string) => void;

export class SelectionController {
  private selected: string | null = null;
  private readonly listeners = new Set<SelectionListener>();

  constructor(private readonly validIds: ReadonlySet<string>) {}

  get current(): string | null {
    return this.selected;
  }

  /** Select an event by id (or clear with null). Unknown ids are ignored. Returns true if the
   * selection changed. `source` lets a listener skip echoes of its own selections. */
  select(id: string | null, source: string): boolean {
    if (id !== null && !this.validIds.has(id)) return false;
    if (id === this.selected) return false;
    this.selected = id;
    for (const fn of [...this.listeners]) {
      try {
        fn(id, source);
      } catch (err) {
        console.error("selection listener failed", err);
      }
    }
    return true;
  }

  subscribe(fn: SelectionListener): () => void {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  }

  get listenerCount(): number {
    return this.listeners.size;
  }

  dispose(): void {
    this.listeners.clear();
    this.selected = null;
  }
}
