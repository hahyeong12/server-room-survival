// Phase 6 (Issue #7): the global content catalog, read from the SAME file the Python engine uses
// (aidc/global_ops/catalog_v1.json). Sites, legacy country codes, map clusters and the virtual routes are derived
// from it here instead of being listed by hand in network-data.js, world-store.js and the adapter.
// Display data only: which requests exist and every rule result still come from the engine snapshot.
import data from '../../../aidc/global_ops/catalog_v1.json' with { type: 'json' };

function freeze(v) { Object.values(v).forEach(x => { if (x && typeof x === 'object') freeze(x); }); return Object.freeze(v); }
export const CATALOG = freeze(structuredClone(data));
export const SITES = CATALOG.sites;
export const LEGACY = CATALOG.legacy;
export const CLUSTERS = CATALOG.clusters;
export const JOB_TYPES = CATALOG.jobTypes;
export const AIDC = CATALOG.aidc;

// A legacy code (SG/JP/US from chapters 1-5 and older saves) is an alias of the catalog site at the same place.
export function siteOf(code) {
  if (Object.hasOwn(SITES, code)) return { id: code, ...SITES[code] };
  if (Object.hasOwn(LEGACY, code)) { const id = LEGACY[code].site; return { id, ...SITES[id], legacy: code }; }
  return null;
}
export function isKnownCode(code) { return code === 'KR' || Object.hasOwn(SITES, code) || Object.hasOwn(LEGACY, code); }

// The virtual route of a site as display legs: land access (metro/backhaul), sea corridors (chained), then the
// Korean landing station. Domestic sites have only a land leg straight to the Ulsan AIDC (domestic backbone).
export function routeOf(code) {
  if (Object.hasOwn(LEGACY, code)) return { legs: [{ kind: 'sea', points: LEGACY[code].sea }], landing: 'BUSAN', domestic: false };
  const s = SITES[code]; if (!s) return null;
  const legs = [];
  if (s.access?.length > 1) legs.push({ kind: 'land', points: s.access });
  if (s.domestic) return { legs, landing: null, domestic: true };
  let id = s.corridor, landing = null, guard = 0;
  while (id && guard++ < 6) { const c = CATALOG.corridors[id]; legs.push({ kind: 'sea', points: c.points, name: c.name }); landing = c.landing || landing; id = c.next; }
  return { legs, landing, domestic: false };
}

// Sites grouped by map cluster (the simple source list shown next to the map).
export function clusters() {
  const out = {};
  for (const [id, s] of Object.entries(SITES)) (out[s.cluster] ||= { id: s.cluster, name: CLUSTERS[s.cluster], sites: [] }).sites.push({ id, ...s });
  return Object.values(out);
}
