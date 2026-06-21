import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { Map } from "react-map-gl/maplibre";
import { HexagonLayer, HeatmapLayer } from "@deck.gl/aggregation-layers";
import { ColumnLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { AmbientLight, PointLight, LightingEffect } from "@deck.gl/core";
import type { Pt } from "../lib/data";
import { COLOR_RANGE, CAT_COLORS, impactColor, SHIFT_COLOR } from "../lib/data";
import type { Hotspot, LayerId, RailTab, ForecastCell, DeployPlan } from "../types";

const BASEMAP =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export const INITIAL_VIEW = {
  longitude: 77.595,
  latitude: 12.972,
  zoom: 11.4,
  pitch: 50,
  bearing: -18,
  maxZoom: 18,
};

// Below this zoom, 3D bars collapse to a clean heatmap so place names stay legible.
const ZOOM_3D = 12.4;

const ambient = new AmbientLight({ color: [255, 255, 255], intensity: 1.0 });
const pl1 = new PointLight({ color: [120, 200, 255], intensity: 1.4, position: [77.55, 12.9, 8000] });
const pl2 = new PointLight({ color: [255, 120, 180], intensity: 1.0, position: [77.66, 13.05, 8000] });
const lightingEffect = new LightingEffect({ ambient, pl1, pl2 });
const material = {
  ambient: 0.55, diffuse: 0.65, shininess: 48,
  specularColor: [60, 110, 160] as [number, number, number],
};

interface Props {
  points: Pt[];
  hotspots: Hotspot[];
  forecast: ForecastCell[] | null;
  deploy: DeployPlan | null;
  tab: RailTab;
  layer: LayerId;
  hour: number | null;
  viewState: any;
  onViewState: (v: any) => void;
  onHover: (info: any) => void;
  selected: Hotspot | null;
}

function baseHeat(data: Pt[], intensity = 1.2, opacity = 1) {
  return new HeatmapLayer({
    id: "heat", data, getPosition: (d: Pt) => d.position, getWeight: (d: Pt) => d.w,
    radiusPixels: 40, intensity, threshold: 0.04, colorRange: COLOR_RANGE, opacity,
  });
}

export default function MapView({
  points, hotspots, forecast, deploy, tab, layer, hour,
  viewState, onViewState, onHover, selected,
}: Props) {
  const zoom = viewState?.zoom ?? INITIAL_VIEW.zoom;
  const show3D = zoom >= ZOOM_3D;

  const filtered = useMemo(
    () => (hour === null ? points : points.filter((p) => p.h === hour)),
    [points, hour]
  );

  const layers = useMemo(() => {
    const L: any[] = [];

    /* ---------- FORECAST overlay ---------- */
    if (tab === "forecast" && forecast) {
      L.push(baseHeat(filtered, 0.7, 0.5));
      const maxP = Math.max(...forecast.map((f) => f.pred), 1);
      L.push(
        new ColumnLayer({
          id: "forecast", data: forecast, diskResolution: 12, radius: 38, extruded: true,
          pickable: true, elevationScale: 9, radiusUnits: "meters",
          getPosition: (d: ForecastCell) => [d.lng, d.lat],
          getElevation: (d: ForecastCell) => d.pred,
          getFillColor: (d: ForecastCell) => {
            const [r, g, b] = impactColor(d.pred / maxP);
            return [r, g, b, 190];
          },
          material, transitions: { getElevation: 700 },
        })
      );
      if (show3D) {
        L.push(new TextLayer({
          id: "fc-labels", data: forecast.slice(0, 10),
          getPosition: (d: ForecastCell) => [d.lng, d.lat],
          getText: (d: ForecastCell) => `#${d.rank} · ${d.pred.toFixed(0)}`,
          getSize: 12, getColor: [230, 240, 255], getPixelOffset: [0, -16],
          fontWeight: 700, background: true, getBackgroundColor: [10, 14, 22, 200],
          backgroundPadding: [5, 3], outlineWidth: 0,
        }));
      }
      return L;
    }

    /* ---------- DEPLOY overlay ---------- */
    if (tab === "deploy" && deploy) {
      L.push(baseHeat(filtered, 0.6, 0.4));
      // coverage radius rings
      L.push(new ScatterplotLayer({
        id: "cover", data: deploy.roster,
        getPosition: (d) => [d.lng, d.lat],
        getRadius: deploy.cover_radius_m, radiusUnits: "meters",
        getFillColor: (d) => { const c = SHIFT_COLOR[d.shift] || [120, 140, 170]; return [c[0], c[1], c[2], 28]; },
        getLineColor: (d) => { const c = SHIFT_COLOR[d.shift] || [120, 140, 170]; return [c[0], c[1], c[2], 200]; },
        stroked: true, lineWidthMinPixels: 1.5,
      }));
      // unit columns sized by impact removed, colored by shift
      const maxR = Math.max(...deploy.roster.map((u) => u.impact_removed), 1);
      L.push(new ColumnLayer({
        id: "units", data: deploy.roster, diskResolution: 12, radius: 34, extruded: true,
        pickable: true, elevationScale: 5, radiusUnits: "meters",
        getPosition: (d) => [d.lng, d.lat],
        getElevation: (d) => 150 + (d.impact_removed / maxR) * 450,
        getFillColor: (d) => { const c = SHIFT_COLOR[d.shift] || [120, 140, 170]; return [c[0], c[1], c[2], 205]; },
        material, transitions: { getElevation: 700 },
      }));
      L.push(new TextLayer({
        id: "unit-labels", data: deploy.roster,
        getPosition: (d) => [d.lng, d.lat],
        getText: (d) => String(d.unit), getSize: 13, getColor: [10, 14, 22],
        fontWeight: 800, getPixelOffset: [0, 0],
      }));
      return L;
    }

    /* ---------- EXPLORE layers (hotspots tab) ---------- */
    const wantHex = layer === "hex";
    const wantCol = layer === "columns";

    if (layer === "heat" || ((wantHex || wantCol) && !show3D)) {
      L.push(baseHeat(filtered));
      if ((wantHex || wantCol) && !show3D) {
        L.push(new TextLayer({
          id: "zoom-hint", data: [{ p: [viewState.longitude, viewState.latitude] }],
          getPosition: (d: any) => d.p, getText: () => "zoom in for 3D impact ↑",
          getSize: 11, getColor: [120, 150, 190], getPixelOffset: [0, 120], sizeUnits: "pixels",
        }));
      }
    }

    if (wantHex && show3D) {
      L.push(new HexagonLayer({
        id: "hex", data: filtered, getPosition: (d: Pt) => d.position,
        getColorWeight: (d: Pt) => d.w, getElevationWeight: (d: Pt) => d.w,
        colorAggregation: "SUM", elevationAggregation: "SUM",
        radius: 95, elevationScale: 4.5, extruded: true, coverage: 0.72,
        upperPercentile: 99, colorRange: COLOR_RANGE, material, opacity: 0.7,
        pickable: true, transitions: { elevationScale: 500 },
        updateTriggers: { getColorWeight: hour, getElevationWeight: hour },
      }));
    }

    if (wantCol && show3D) {
      const maxP = Math.max(...hotspots.map((h) => h.pcis), 1);
      L.push(new ColumnLayer({
        id: "columns", data: hotspots, diskResolution: 12, radius: 32, extruded: true,
        pickable: true, elevationScale: 11, radiusUnits: "meters", coverage: 0.85,
        getPosition: (d: Hotspot) => [d.lng, d.lat],
        getElevation: (d: Hotspot) => d.pcis,
        getFillColor: (d: Hotspot) => { const [r, g, b] = impactColor(d.pcis / maxP); return [r, g, b, 188]; },
        material, transitions: { getElevation: 700 },
      }));
      L.push(new TextLayer({
        id: "col-labels", data: hotspots.slice(0, 18),
        getPosition: (d: Hotspot) => [d.lng, d.lat],
        getText: (d: Hotspot) => (d.top_junction !== "—"
          ? d.top_junction.replace(/^BTP\d+ - /, "") : d.top_ps),
        getSize: 11, getColor: [225, 238, 255], getPixelOffset: [0, -14],
        fontWeight: 700, background: true, getBackgroundColor: [10, 14, 22, 190],
        backgroundPadding: [5, 3],
      }));
    }

    if (layer === "scatter") {
      L.push(new ScatterplotLayer({
        id: "scatter", data: filtered, getPosition: (d: Pt) => d.position,
        getFillColor: (d: Pt) => CAT_COLORS[d.c] || [120, 140, 170],
        getRadius: (d: Pt) => 6 + d.w * 0.5, radiusMinPixels: 1.3, radiusMaxPixels: 7, opacity: 0.55,
      }));
    }

    if (selected) {
      L.push(new ScatterplotLayer({
        id: "beacon", data: [selected], getPosition: (d: Hotspot) => [d.lng, d.lat],
        getFillColor: [0, 229, 255, 55], getLineColor: [0, 229, 255, 255],
        getRadius: 170, stroked: true, lineWidthMinPixels: 2, radiusUnits: "meters",
      }));
    }
    return L;
  }, [filtered, layer, hotspots, forecast, deploy, tab, hour, selected, show3D, viewState]);

  return (
    <div id="map-root">
      <DeckGL
        layers={layers}
        effects={[lightingEffect]}
        viewState={viewState}
        onViewStateChange={(e: any) => onViewState(e.viewState)}
        controller={true}
        onHover={onHover}
        getTooltip={() => null}
      >
        <Map mapStyle={BASEMAP} reuseMaps attributionControl={false} />
      </DeckGL>
    </div>
  );
}
