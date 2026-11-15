/** Browser-only display preferences. These never alter field geometry or analysis results. */
import { useSyncExternalStore } from "react";

export type BasemapPreference = "cartographic" | "satellite";
export type UiPreferences = {
  textSize: "standard" | "large";
  contrast: "standard" | "high";
  reduceMotion: boolean;
  defaultBasemap: BasemapPreference;
};

export const DEFAULT_UI_PREFERENCES: UiPreferences = {
  textSize: "large",
  contrast: "high",
  reduceMotion: false,
  defaultBasemap: "cartographic",
};

const STORAGE_KEY = "fieldwise:ui-preferences:v1";
const UPDATED_EVENT = "fieldwise:ui-preferences-changed";
const DEFAULT_RAW = JSON.stringify(DEFAULT_UI_PREFERENCES);
let memoryRaw = DEFAULT_RAW;

function normalize(input: unknown): UiPreferences {
  const value = input && typeof input === "object" ? input as Partial<UiPreferences> : {};
  return {
    textSize: value.textSize === "standard" ? "standard" : "large",
    contrast: value.contrast === "standard" ? "standard" : "high",
    reduceMotion: value.reduceMotion === true,
    defaultBasemap: value.defaultBasemap === "satellite" ? "satellite" : "cartographic",
  };
}

function snapshot(): string {
  if (typeof window === "undefined") return DEFAULT_RAW;
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? DEFAULT_RAW;
  } catch {
    return memoryRaw;
  }
}

function serverSnapshot(): string { return DEFAULT_RAW; }

function subscribe(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const handleStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY || event.key === null) listener();
  };
  window.addEventListener("storage", handleStorage);
  window.addEventListener(UPDATED_EVENT, listener);
  return () => {
    window.removeEventListener("storage", handleStorage);
    window.removeEventListener(UPDATED_EVENT, listener);
  };
}

export function readUiPreferences(): UiPreferences {
  try { return normalize(JSON.parse(snapshot())); }
  catch { return { ...DEFAULT_UI_PREFERENCES }; }
}

export function useUiPreferences(): UiPreferences {
  const raw = useSyncExternalStore(subscribe, snapshot, serverSnapshot);
  try { return normalize(JSON.parse(raw)); }
  catch { return { ...DEFAULT_UI_PREFERENCES }; }
}

export function saveUiPreferences(patch: Partial<UiPreferences>): void {
  const normalized = normalize({ ...readUiPreferences(), ...patch });
  memoryRaw = JSON.stringify(normalized);
  try { window.localStorage.setItem(STORAGE_KEY, memoryRaw); }
  catch { /* Browser storage may be disabled; keep preferences in this tab. */ }
  window.dispatchEvent(new Event(UPDATED_EVENT));
}

export function resetUiPreferences(): void {
  memoryRaw = DEFAULT_RAW;
  try { window.localStorage.removeItem(STORAGE_KEY); }
  catch { /* Storage unavailable. */ }
  window.dispatchEvent(new Event(UPDATED_EVENT));
}

export function applyUiPreferences(prefs: UiPreferences): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.fwTextSize = prefs.textSize;
  document.documentElement.dataset.fwContrast = prefs.contrast;
  document.documentElement.dataset.fwMotion = prefs.reduceMotion ? "reduced" : "normal";
}
