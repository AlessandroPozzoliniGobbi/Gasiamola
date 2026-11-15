"use client";

import { useRouter } from "next/navigation";
import { DEFAULT_UI_PREFERENCES, resetUiPreferences, saveUiPreferences, useUiPreferences } from "../../lib/uiPreferences";
import styles from "../../styles/settings.module.css";

export default function SettingsPage() {
  const router = useRouter();
  const preferences = useUiPreferences();
  const isDefault = Object.entries(DEFAULT_UI_PREFERENCES).every(([key, value]) =>
    preferences[key as keyof typeof DEFAULT_UI_PREFERENCES] === value,
  );

  function goBack() {
    const index = window.history.state?.idx;
    if (typeof index === "number" && index > 0) {
      router.back();
      return;
    }
    let fallback = "/";
    try {
      const saved = sessionStorage.getItem("fieldwise-settings-return-to");
      if (saved?.startsWith("/") && !saved.startsWith("//") && !saved.startsWith("/impostazioni")) {
        fallback = saved;
      }
    } catch { /* Navigation still works without session storage. */ }
    router.push(fallback);
  }

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <button type="button" className={styles.back} onClick={goBack}>
          <span aria-hidden="true">←</span> Go back
        </button>
        <header className={styles.heading}>
          <span className={styles.eyebrow}>FIELDWISE / PREFERENCES</span>
          <h1>Settings</h1>
          <p>Make FIELDWISE easier to read and use. Changes are applied immediately and remembered in this browser.</p>
        </header>

        <div className={styles.grid}>
          <section className={styles.panel} aria-labelledby="accessibility-heading">
            <div className={styles.panelHeading}>
              <span className={styles.sectionNo}>01</span>
              <div>
                <h2 id="accessibility-heading">Reading & accessibility</h2>
                <p>Adjust how the interface looks without changing your analysis results.</p>
              </div>
            </div>

            <fieldset className={styles.preference}>
              <legend>Text size</legend>
              <p>Increase labels and report text for easier reading.</p>
              <div className={styles.choiceGroup}>
                <label className={`${styles.choice} ${preferences.textSize === "standard" ? styles.selected : ""}`}>
                  <input type="radio" name="text-size" checked={preferences.textSize === "standard"} onChange={() => saveUiPreferences({ textSize: "standard" })} />
                  Standard
                </label>
                <label className={`${styles.choice} ${preferences.textSize === "large" ? styles.selected : ""}`}>
                  <input type="radio" name="text-size" checked={preferences.textSize === "large"} onChange={() => saveUiPreferences({ textSize: "large" })} />
                  Larger text
                </label>
              </div>
            </fieldset>

            <fieldset className={styles.preference}>
              <legend>Contrast</legend>
              <p>Use darker captions and clearer borders on data-heavy screens.</p>
              <div className={styles.choiceGroup}>
                <label className={`${styles.choice} ${preferences.contrast === "standard" ? styles.selected : ""}`}>
                  <input type="radio" name="contrast" checked={preferences.contrast === "standard"} onChange={() => saveUiPreferences({ contrast: "standard" })} />
                  Standard
                </label>
                <label className={`${styles.choice} ${preferences.contrast === "high" ? styles.selected : ""}`}>
                  <input type="radio" name="contrast" checked={preferences.contrast === "high"} onChange={() => saveUiPreferences({ contrast: "high" })} />
                  High contrast
                </label>
              </div>
            </fieldset>

            <label className={styles.toggleRow}>
              <span>
                <strong>Reduce motion</strong>
                <small>Minimize transitions and animated loading effects.</small>
              </span>
              <input type="checkbox" className={styles.switch} checked={preferences.reduceMotion} onChange={(event) => saveUiPreferences({ reduceMotion: event.target.checked })} />
            </label>
          </section>

          <div className={styles.sideColumn}>
            <section className={styles.panel} aria-labelledby="map-heading">
              <div className={styles.panelHeading}>
                <span className={styles.sectionNo}>02</span>
                <div>
                  <h2 id="map-heading">Map defaults</h2>
                  <p>Choose which layer you see when opening the map.</p>
                </div>
              </div>
              <fieldset className={styles.preference}>
                <legend>Default map style</legend>
                <div className={styles.choiceGroup}>
                  <label className={`${styles.choice} ${preferences.defaultBasemap === "cartographic" ? styles.selected : ""}`}>
                    <input type="radio" name="map-style" checked={preferences.defaultBasemap === "cartographic"} onChange={() => saveUiPreferences({ defaultBasemap: "cartographic" })} />
                    Street map
                  </label>
                  <label className={`${styles.choice} ${preferences.defaultBasemap === "satellite" ? styles.selected : ""}`}>
                    <input type="radio" name="map-style" checked={preferences.defaultBasemap === "satellite"} onChange={() => saveUiPreferences({ defaultBasemap: "satellite" })} />
                    Satellite
                  </label>
                </div>
                <p className={styles.hint}>Satellite imagery requires the map provider configuration. You can always switch layers on the map.</p>
              </fieldset>
            </section>

            <section className={styles.panel} aria-labelledby="language-heading">
              <div className={styles.panelHeading}>
                <span className={styles.sectionNo}>03</span>
                <div>
                  <h2 id="language-heading">Language & preferences</h2>
                  <p>Current interface language: <strong>English</strong>.</p>
                </div>
              </div>
              <p className={styles.hint}>Preferences are stored in this browser. They do not change your saved fields, reports, or scientific calculations.</p>
              <div className={styles.resetArea}>
                <button type="button" className={styles.reset} onClick={resetUiPreferences} disabled={isDefault}>
                  Restore default preferences
                </button>
                <span className={styles.saved} role="status">{isDefault ? "Using default preferences" : "Preferences saved automatically"}</span>
              </div>
            </section>
          </div>
        </div>
      </div>
    </main>
  );
}
