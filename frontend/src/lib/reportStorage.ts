import { getRecommendation, recommendationHeadline, type CompletedReport, type ReportSummary } from "./reportTypes";

/** Latest 10 completed reports, stored only on the current browser/device.
 *  No demo/preview data enters this database. */
export const MAX_SAVED_REPORTS = 10;
const DB_NAME = "fieldwise-analysis-reports";
const STORE = "completedReports";
const DB_VERSION = 1;

function isCompletedReport(value: unknown): value is CompletedReport {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const r = value as Partial<CompletedReport>;
  return r.schemaVersion === 1 && r.status === "completed" &&
    typeof r.id === "string" && r.id.length > 0 && r.id.length <= 128 &&
    typeof r.createdAt === "string" && !Number.isNaN(Date.parse(r.createdAt)) &&
    !!r.field && typeof r.field.id === "string" && typeof r.field.name === "string" &&
    !!r.inputs && !!r.results && typeof r.results.scenario === "string" &&
    !!r.results.current && Array.isArray(r.results.alternatives) &&
    !!r.engine && Array.isArray(r.results.notes);
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("Browser report storage is unavailable."));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id" });
        store.createIndex("createdAt", "createdAt");
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Could not open report storage."));
    request.onblocked = () => reject(new Error("Report storage is busy in another tab."));
  });
}

function completeTransaction(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error ?? new Error("Could not update report storage."));
    tx.onabort = () => reject(tx.error ?? new Error("Report storage update was cancelled."));
  });
}

/** Called only after a *real*, successfully completed backend analysis.
 *  Deliberately no UI calls this function until integration exists. */
export async function saveCompletedReport(report: CompletedReport): Promise<void> {
  if (!isCompletedReport(report) || report.id === "demo-preview") {
    throw new Error("Only valid completed analyses can be saved.");
  }
  const db = await openDB();
  try {
    const tx = db.transaction(STORE, "readwrite");
    const done = completeTransaction(tx);
    const store = tx.objectStore(STORE);
    store.put(report);
    let count = 0;
    store.index("createdAt").openCursor(null, "prev").onsuccess = (event) => {
      const cursor = (event.target as IDBRequest<IDBCursorWithValue | null>).result;
      if (!cursor) return;
      count += 1;
      if (count > MAX_SAVED_REPORTS) cursor.delete();
      cursor.continue();
    };
    await done;
  } finally {
    db.close();
  }
}

export async function listRecentReports(): Promise<ReportSummary[]> {
  const db = await openDB();
  try {
    const tx = db.transaction(STORE, "readonly");
    const request = tx.objectStore(STORE).getAll();
    const reports = await new Promise<unknown[]>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error ?? new Error("Could not read reports."));
    });
    return reports.filter(isCompletedReport)
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .slice(0, MAX_SAVED_REPORTS)
      .map((r) => ({ id: r.id, createdAt: r.createdAt, field: r.field,
        rotationLabel: r.results.current.label,
        recommendedLabel: getRecommendation(r).recommended?.label ?? null,
        recommendationText: recommendationHeadline(r) }));
  } finally {
    db.close();
  }
}

export async function getCompletedReport(id: string): Promise<CompletedReport | null> {
  const db = await openDB();
  try {
    const tx = db.transaction(STORE, "readonly");
    const request = tx.objectStore(STORE).get(id);
    const value: unknown = await new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error ?? new Error("Could not open the report."));
    });
    return isCompletedReport(value) ? value : null;
  } finally {
    db.close();
  }
}

export async function deleteCompletedReport(id: string): Promise<void> {
  const db = await openDB();
  try {
    const tx = db.transaction(STORE, "readwrite");
    const done = completeTransaction(tx);
    tx.objectStore(STORE).delete(id);
    await done;
  } finally {
    db.close();
  }
}
