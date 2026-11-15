export interface Disposable {
  dispose(): void;
}

/** Owns every GPU-side resource the globe creates. A shared resource is tracked once and
 * disposed once; disposeAll is idempotent. Tests use it as a resource ledger. */
export class ResourceLedger {
  private readonly live = new Map<Disposable, string>();
  private disposed = 0;

  track<T extends Disposable>(item: T, label: string): T {
    if (!this.live.has(item)) this.live.set(item, label);
    return item;
  }

  get liveCount(): number {
    return this.live.size;
  }

  get disposedTotal(): number {
    return this.disposed;
  }

  liveLabels(): string[] {
    return [...this.live.values()];
  }

  disposeAll(): void {
    const failures: unknown[] = [];
    for (const item of [...this.live.keys()]) {
      this.live.delete(item);
      try {
        item.dispose();
        this.disposed++;
      } catch (err) {
        failures.push(err);
      }
    }
    if (failures.length > 0) throw new AggregateError(failures, "some resources failed to dispose");
  }
}
