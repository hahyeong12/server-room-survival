// Korea-centred map projection (Issue #3). Pure math, no Three.js.
// Plate carrée with the central meridian on Ulsan, so Korea sits in the middle and the
// Pacific (Japan, US) is continuous; the seam falls in the Atlantic (~50.6°W).
export const CENTER_LON = 129.36;
export const SCALE = .11;
export const HALF_WIDTH = 180 * SCALE;

// Longitude relative to the centre, in [-180, 180).
export function wrapLon(lon) { return ((lon - CENTER_LON + 540) % 360 + 360) % 360 - 180; }
export function toMap(lon, lat, y = 0) { return [wrapLon(lon) * SCALE, y, -lat * SCALE]; }

// Make a ring/polyline continuous across the seam (relative longitudes may leave [-180, 180)).
export function unwrap(points) {
  const out = []; let prev = null;
  for (const [lon, lat] of points) {
    let d = wrapLon(lon);
    if (prev !== null) { while (d - prev > 180) d -= 360; while (d - prev < -180) d += 360; }
    out.push([d, lat]); prev = d;
  }
  return out;
}
// Horizontal copies (in degrees) needed so a continuous ring fully covers the visible map; clipping trims the rest.
export function copyOffsets(relLons) {
  const min = Math.min(...relLons), max = Math.max(...relLons), offsets = [0];
  if (max > 180) offsets.push(-360);
  if (min < -180) offsets.push(360);
  return offsets;
}
