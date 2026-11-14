export type FieldGeometry = {
  id: string;
  // Coordinate GeoJSON Polygon: [anelli][vertici][longitudine, latitudine]
  coordinates: number[][][];
};

export type FieldItem = FieldGeometry & {
  number: number;
  name: string;
};

export type MapMode = "navigate" | "draw" | "select";
