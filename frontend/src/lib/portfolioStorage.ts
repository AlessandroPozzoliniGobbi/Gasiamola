import type { CompletedReport } from "./reportTypes";

/** Independent snapshots: deleting an original field or old single report never
 * changes a completed farm comparison. All data stays in this browser. */
export type PortfolioFailure = { fieldId: string; fieldName: string; message: string };
export type PortfolioReport = {
  schemaVersion: 1;
  id: string;
  createdAt: string;
  requestedFields: number;
  reports: CompletedReport[];
  failures: PortfolioFailure[];
};
export type PortfolioSummary = {
  id: string; createdAt: string; requestedFields: number; completedFields: number;
  fieldNames: string[]; failures: number;
};
export const MAX_PORTFOLIOS = 5;
const NAME = "fieldwise-portfolio-reports";
const STORE = "portfolios";

function valid(value: unknown): value is PortfolioReport {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const x = value as Partial<PortfolioReport>;
  return x.schemaVersion === 1 && typeof x.id === "string" && x.id.length > 0 && x.id.length <= 128 &&
    typeof x.createdAt === "string" && Number.isFinite(Date.parse(x.createdAt)) &&
    typeof x.requestedFields === "number" && Number.isSafeInteger(x.requestedFields) && x.requestedFields >= 1 &&
    Array.isArray(x.reports) && x.reports.length > 0 && x.reports.length <= x.requestedFields &&
    x.reports.every(r => r?.status === "completed" && r.schemaVersion === 1 && !!r.field?.id && !!r.results?.current) &&
    Array.isArray(x.failures) && x.failures.every(f => typeof f.fieldId === "string" && typeof f.fieldName === "string" && typeof f.message === "string");
}
function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") return reject(new Error("Browser portfolio storage is not available."));
    const req = indexedDB.open(NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: "id" }).createIndex("createdAt", "createdAt");
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("Could not open portfolio storage."));
    req.onblocked = () => reject(new Error("Portfolio storage is blocked by another tab."));
  });
}
function txDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error ?? new Error("Portfolio save failed."));
    tx.onabort = () => reject(tx.error ?? new Error("Portfolio save was cancelled."));
  });
}
export async function savePortfolio(report: PortfolioReport): Promise<void> {
  if (!valid(report)) throw new Error("The portfolio report is incomplete or invalid.");
  const db = await openDB();
  try {
    const tx = db.transaction(STORE, "readwrite");
    const done = txDone(tx);
    const store = tx.objectStore(STORE);
    store.put(report);
    let count = 0;
    store.index("createdAt").openCursor(null, "prev").onsuccess = event => {
      const cursor = (event.target as IDBRequest<IDBCursorWithValue | null>).result;
      if (!cursor) return;
      count++;
      if (count > MAX_PORTFOLIOS) cursor.delete();
      cursor.continue();
    };
    await done;
  } finally { db.close(); }
}
export async function listPortfolios(): Promise<PortfolioSummary[]> {
  const db = await openDB();
  try {
    const results = await new Promise<unknown[]>((resolve, reject) => {
      const req = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error ?? new Error("Could not read saved comparisons."));
    });
    return results.filter(valid).sort((a,b) => b.createdAt.localeCompare(a.createdAt))
      .slice(0, MAX_PORTFOLIOS).map(p => ({id:p.id, createdAt:p.createdAt, requestedFields:p.requestedFields,
        completedFields:p.reports.length, fieldNames:p.reports.map(r=>r.field.name), failures:p.failures.length}));
  } finally { db.close(); }
}
export async function getPortfolio(id: string): Promise<PortfolioReport | null> {
  const db = await openDB();
  try {
    const result = await new Promise<unknown>((resolve, reject) => {
      const req = db.transaction(STORE,"readonly").objectStore(STORE).get(id);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error ?? new Error("Could not open the comparison."));
    });
    return valid(result) ? result : null;
  } finally { db.close(); }
}
export async function deletePortfolio(id: string): Promise<void> {
  const db = await openDB();
  try {
    const tx = db.transaction(STORE,"readwrite");
    const done = txDone(tx);
    tx.objectStore(STORE).delete(id);
    await done;
  } finally { db.close(); }
}
