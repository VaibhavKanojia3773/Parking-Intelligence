import type {
  Points, Hotspot, Station, Summary, ForecastCell, ForecastMetrics, DeployPlan,
  Validation, DeployRoi, Detection, Corridor, Tasking,
} from "../types";

const base = import.meta.env.BASE_URL || "/";

/** Optional fetch — returns null if the artifact isn't present yet. */
async function optional<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${base}data/${path}`);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

export async function loadAll() {
  const [points, hotspots, stations, summary, forecast, metrics, deploy, validation, roi,
         detection, corridors, tasking] =
    await Promise.all([
      fetch(`${base}data/points.json`).then((r) => r.json() as Promise<Points>),
      fetch(`${base}data/hotspots.json`).then((r) => r.json() as Promise<Hotspot[]>),
      fetch(`${base}data/stations.json`).then((r) => r.json() as Promise<Station[]>),
      fetch(`${base}data/summary.json`).then((r) => r.json() as Promise<Summary>),
      optional<ForecastCell[]>("forecast.json"),
      optional<ForecastMetrics>("forecast_metrics.json"),
      optional<DeployPlan>("deployment_plan.json"),
      optional<Validation>("validation.json"),
      optional<DeployRoi>("deploy_roi.json"),
      optional<Detection>("detection.json"),
      optional<Corridor[]>("corridors.json"),
      optional<Tasking>("tasking.json"),
    ]);
  return { points, hotspots, stations, summary, forecast, metrics, deploy, validation, roi,
           detection, corridors, tasking };
}

/** Flatten columnar Points -> array of {position,w,h,d,c} for deck.gl. */
export interface Pt {
  position: [number, number];
  w: number;
  h: number;
  d: number;
  c: number;
}
export function toPoints(p: Points): Pt[] {
  const out: Pt[] = new Array(p.lat.length);
  for (let i = 0; i < p.lat.length; i++) {
    out[i] = { position: [p.lng[i], p.lat[i]], w: p.w[i], h: p.h[i], d: p.d[i], c: p.c[i] };
  }
  return out;
}

/** Blue -> teal -> amber -> hot-pink ramp (matches CSS legend). t in 0..1 */
export function impactColor(t: number): [number, number, number] {
  t = Math.max(0, Math.min(1, t));
  const stops: [number, [number, number, number]][] = [
    [0.0, [43, 108, 255]],
    [0.4, [43, 217, 160]],
    [0.72, [255, 176, 32]],
    [1.0, [255, 46, 106]],
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const [a, ca] = stops[i];
    const [b, cb] = stops[i + 1];
    if (t >= a && t <= b) {
      const f = (t - a) / (b - a);
      return [
        Math.round(ca[0] + (cb[0] - ca[0]) * f),
        Math.round(ca[1] + (cb[1] - ca[1]) * f),
        Math.round(ca[2] + (cb[2] - ca[2]) * f),
      ];
    }
  }
  return stops[stops.length - 1][1];
}

export const COLOR_RANGE: [number, number, number][] = [
  [43, 108, 255],
  [38, 180, 220],
  [43, 217, 160],
  [180, 210, 70],
  [255, 176, 32],
  [255, 46, 106],
];

export const CAT_COLORS: Record<number, [number, number, number]> = {
  0: [255, 46, 106], // main road
  1: [124, 92, 255], // footpath
  2: [255, 176, 32], // double
  3: [0, 229, 255], // wrong
  4: [43, 217, 160], // no parking
  5: [120, 140, 170], // other
};

export function fmt(n: number): string {
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(Math.round(n));
}

export const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export const SHIFT_COLOR: Record<string, [number, number, number]> = {
  morning: [255, 196, 64],
  afternoon: [0, 229, 255],
  evening: [124, 92, 255],
  night: [255, 46, 106],
};
export const SHIFT_HEX: Record<string, string> = {
  morning: "#ffc440",
  afternoon: "#00e5ff",
  evening: "#7c5cff",
  night: "#ff2e6a",
};
