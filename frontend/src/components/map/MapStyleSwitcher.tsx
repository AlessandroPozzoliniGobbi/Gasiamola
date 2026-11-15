
import styles from "../../styles/map.module.css";

type Basemap = "cartographic" | "satellite";

type MapStyleSwitcherProps = {
  basemap: Basemap;
  onToggle: () => void;
  disabled?: boolean;
  unavailableReason?: string | null;
};

export default function MapStyleSwitcher({
  basemap,
  onToggle,
  disabled = false,
  unavailableReason,
}: MapStyleSwitcherProps) {
  // Modalità a cui passeremo
  const nextMode =
    basemap === "cartographic"
      ? "satellite"
      : "cartographic";

  const label =
    nextMode === "satellite"
      ? "Satellite"
      : "Street map";

  // A decorative preview avoids requesting MapTiler tiles before access is verified.
  const previewClass = nextMode === "satellite" ? styles.basemapPreviewSatellite : styles.basemapPreviewStreet;

  return (
    <button
      type="button"
      className={styles.basemapToggle}
      onClick={onToggle}
      disabled={disabled}
      title={unavailableReason ?? `Switch to ${label.toLowerCase()}`}
      aria-label={`Switch to ${label.toLowerCase()}`}
    >
      <span
        className={`${styles.basemapToggleImage} ${previewClass}`}
        aria-hidden="true"
      />

      <span className={styles.basemapToggleLabel}>
        {label}
      </span>
    </button>
  );
}
