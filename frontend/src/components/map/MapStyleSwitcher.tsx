
import styles from "../../styles/map.module.css";

type Basemap = "cartographic" | "satellite";

type MapStyleSwitcherProps = {
  basemap: Basemap;
  onToggle: () => void;
  disabled?: boolean;
};

export default function MapStyleSwitcher({
  basemap,
  onToggle,
  disabled = false,
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

  // Miniatura satellitare: MapTiler
  const mapTilerKey =
    process.env.NEXT_PUBLIC_MAPTILER_KEY ?? "";

  const satellitePreview =
    `https://api.maptiler.com/tiles/satellite-v2/12/2164/1470.jpg?key=${encodeURIComponent(mapTilerKey)}`;

  // Miniatura cartografica: OpenStreetMap
  const streetPreview =
    "https://tile.openstreetmap.org/12/2164/1470.png";

  // Visualizza l'anteprima della modalità successiva
  const previewImage =
    nextMode === "satellite"
      ? satellitePreview
      : streetPreview;

  return (
    <button
      type="button"
      className={styles.basemapToggle}
      onClick={onToggle}
      disabled={disabled}
      title={`Switch to ${label.toLowerCase()}`}
      aria-label={`Switch to ${label.toLowerCase()}`}
    >
      <span
        className={styles.basemapToggleImage}
        style={{
          backgroundImage: `url("${previewImage}")`,
        }}
        aria-hidden="true"
      />

      <span className={styles.basemapToggleLabel}>
        {label}
      </span>
    </button>
  );
}
