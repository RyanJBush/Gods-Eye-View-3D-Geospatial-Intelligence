/** Latitude/longitude (degrees) to a point on a sphere, y up, longitude 0 toward +z. */
export function latLonToXYZ(latDeg: number, lonDeg: number, radius = 1): [number, number, number] {
  const lat = (latDeg * Math.PI) / 180;
  const lon = (lonDeg * Math.PI) / 180;
  return [radius * Math.cos(lat) * Math.sin(lon), radius * Math.sin(lat), radius * Math.cos(lat) * Math.cos(lon)];
}
