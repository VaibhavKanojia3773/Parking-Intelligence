import { useEffect, useMemo, useRef, useState } from "react";
import { FlyToInterpolator } from "@deck.gl/core";
import { AnimatePresence } from "framer-motion";
import MapView, { INITIAL_VIEW } from "./components/MapView";
import {
  TopBar, KpiRail, RightRail, LayerSwitcher, Legend, TimeBar, Tooltip, StoryBar,
} from "./components/Hud";
import type { Chapter } from "./components/Hud";
import { loadAll, toPoints } from "./lib/data";
import type { Pt } from "./lib/data";
import type {
  Hotspot, Station, Summary, LayerId, RailTab, ForecastCell, ForecastMetrics, DeployPlan,
  Validation, DeployRoi, Detection, Corridor, Tasking,
} from "./types";

export default function App() {
  const [ready, setReady] = useState(false);
  const [points, setPoints] = useState<Pt[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [, setStations] = useState<Station[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [forecast, setForecast] = useState<ForecastCell[] | null>(null);
  const [metrics, setMetrics] = useState<ForecastMetrics | null>(null);
  const [deploy, setDeploy] = useState<DeployPlan | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [roi, setRoi] = useState<DeployRoi | null>(null);
  const [detection, setDetection] = useState<Detection | null>(null);
  const [corridors, setCorridors] = useState<Corridor[] | null>(null);
  const [tasking, setTasking] = useState<Tasking | null>(null);

  const qp = new URLSearchParams(window.location.search);
  const [tab, setTab] = useState<RailTab>((qp.get("tab") as RailTab) || "hotspots");
  const [layer, setLayer] = useState<LayerId>((qp.get("layer") as LayerId) || "heat");
  const [hour, setHour] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState<Hotspot | null>(null);
  const [hover, setHover] = useState<any>(null);
  const [viewState, setViewState] = useState<any>(() => {
    const z = parseFloat(qp.get("z") || "");
    const lng = parseFloat(qp.get("lng") || "");
    const lat = parseFloat(qp.get("lat") || "");
    return {
      ...INITIAL_VIEW,
      ...(isFinite(z) ? { zoom: z } : {}),
      ...(isFinite(lng) ? { longitude: lng } : {}),
      ...(isFinite(lat) ? { latitude: lat } : {}),
    };
  });

  // story mode
  const [storyOn, setStoryOn] = useState(false);
  const [chapterIdx, setChapterIdx] = useState(0);
  const [storyPlaying, setStoryPlaying] = useState(false);

  const playRef = useRef<number | null>(null);
  const storyRef = useRef<number | null>(null);

  useEffect(() => {
    loadAll().then((d) => {
      setPoints(toPoints(d.points));
      setHotspots(d.hotspots);
      setStations(d.stations);
      setSummary(d.summary);
      setForecast(d.forecast);
      setMetrics(d.metrics);
      setDeploy(d.deploy);
      setValidation(d.validation);
      setRoi(d.roi);
      setDetection(d.detection);
      setCorridors(d.corridors);
      setTasking(d.tasking);
      setTimeout(() => setReady(true), 200);
      if (qp.get("story") === "1") setTimeout(openStory, 400);
    });
  }, []);

  const flyTo = (lng: number, lat: number, zoom = 14.4) =>
    setViewState((v: any) => ({
      ...v, longitude: lng, latitude: lat, zoom, pitch: 55,
      transitionDuration: 1400, transitionInterpolator: new FlyToInterpolator({ speed: 1.6 }),
    }));

  const selectHot = (h: Hotspot) => { setSelected(h); flyTo(h.lng, h.lat); };

  const handleTab = (t: RailTab) => {
    setTab(t);
    if (t === "impact") setLayer("columns");
    if (t === "hotspots") setLayer((l) => l);
  };

  // 24h playback
  useEffect(() => {
    if (!playing) { if (playRef.current) window.clearInterval(playRef.current); return; }
    playRef.current = window.setInterval(() => setHour((h) => (h === null ? 0 : (h + 1) % 24)), 850);
    return () => { if (playRef.current) window.clearInterval(playRef.current); };
  }, [playing]);

  /* ----- Story chapters ----- */
  const chapters: Chapter[] = useMemo(() => [
    { n: 1, title: "The Problem", narration:
      `${summary ? (summary.total_violations / 1000).toFixed(0) : "248"}k parking violations, zero visibility on which ones actually choke traffic. Enforcement is reactive and blind.` },
    { n: 2, title: "Where It's Worst", narration:
      "H3 hotspot detection surfaces the chronic chokepoints — Safina Plaza, KR Market, Elite Junction — invisible in spreadsheets, obvious here." },
    { n: 3, title: "How Much It Hurts", narration:
      `The Parking Congestion Impact Score quantifies flow harm — and it's validated: on held-out data it predicts future congestion at ρ ${validation ? validation.spearman_pcis_vs_future_impact.toFixed(2) : "0.65"}, beating raw counts. Top-decile cells carry ${validation ? validation.top_decile_future_lift.toFixed(1) : "3.3"}× the burden.` },
    { n: 4, title: "Targeted Enforcement", narration:
      `${deploy ? deploy.units : 30} patrol units, time-sliced by shift, remove ${deploy ? deploy.coverage_pct : 11}% of total parking-congestion impact — concentrated on the worst chokepoints first. An action plan, not a report.` },
    { n: 5, title: "Proactive (Extension)", narration:
      `A forecast ranks each cell by parking load over the next 7 days${metrics ? ` — ROC-AUC ${metrics.ROC_AUC.toFixed(2)}, top-50 hit-rate ${(metrics["Precision@50"] * 100).toFixed(0)}%` : ""} — moving enforcement from reactive to pre-emptive.` },
  ], [summary, metrics, deploy, validation]);

  const applyChapter = (i: number) => {
    setChapterIdx(i);
    const top = hotspots[0];
    const f0 = forecast?.[0];
    switch (i) {
      case 0: setTab("hotspots"); setLayer("heat"); setHour(null);
        setViewState((v: any) => ({ ...v, longitude: 77.595, latitude: 12.972, zoom: 11.3, pitch: 35, bearing: -12,
          transitionDuration: 1600, transitionInterpolator: new FlyToInterpolator({ speed: 1.4 }) })); break;
      case 1: setTab("hotspots"); setLayer("columns");
        if (top) { setSelected(top); flyTo(top.lng, top.lat, 14.4); } break;
      case 2: setTab("impact"); setLayer("columns");
        setViewState((v: any) => ({ ...v, zoom: 13, pitch: 58, bearing: 20,
          transitionDuration: 1600, transitionInterpolator: new FlyToInterpolator({ speed: 1.3 }) })); break;
      case 3: setTab("deploy");
        setViewState((v: any) => ({ ...v, longitude: 77.595, latitude: 12.972, zoom: 12.1, pitch: 48, bearing: -10,
          transitionDuration: 1600, transitionInterpolator: new FlyToInterpolator({ speed: 1.3 }) })); break;
      case 4: setTab("forecast");
        if (f0) flyTo(f0.lng, f0.lat, 14); break;
    }
  };

  const openStory = () => { setStoryOn(true); setStoryPlaying(true); applyChapter(0); };
  const closeStory = () => { setStoryOn(false); setStoryPlaying(false); };

  // story auto-advance
  useEffect(() => {
    if (!storyOn || !storyPlaying) { if (storyRef.current) window.clearTimeout(storyRef.current); return; }
    storyRef.current = window.setTimeout(() => {
      setChapterIdx((i) => {
        if (i >= chapters.length - 1) { setStoryPlaying(false); return i; }
        const next = i + 1; applyChapter(next); return next;
      });
    }, 7000);
    return () => { if (storyRef.current) window.clearTimeout(storyRef.current); };
  }, [storyOn, storyPlaying, chapterIdx, chapters.length]);

  const byHour = summary?.by_hour ?? new Array(24).fill(0);

  if (!summary) {
    return (
      <div className="loader">
        <div style={{ textAlign: "center" }}>
          <div className="ring" style={{ margin: "0 auto" }} />
          <div className="lt">Loading Bengaluru parking intelligence…</div>
        </div>
      </div>
    );
  }

  return (
    <>
      <MapView
        points={points} hotspots={hotspots} forecast={forecast} deploy={deploy}
        tab={tab} layer={layer} hour={hour}
        viewState={viewState} onViewState={setViewState} onHover={setHover} selected={selected}
      />
      <div className="vignette" />
      <div className="shell">
        <TopBar summary={summary} onStory={openStory} />
        <KpiRail summary={summary} />
        <RightRail
          tab={tab} onTab={handleTab} summary={summary} hotspots={hotspots} forecast={forecast} metrics={metrics}
          deploy={deploy} validation={validation} roi={roi}
          detection={detection} corridors={corridors} tasking={tasking}
          selected={selected} onSelectHot={selectHot}
          onFly={(lng, lat) => flyTo(lng, lat)}
        />
        {(tab === "hotspots" || tab === "impact") && <LayerSwitcher layer={layer} onChange={setLayer} />}
        <Legend tab={tab} layer={layer} />
        <TimeBar hour={hour} playing={playing} byHour={byHour}
          onScrub={(h) => { setHour(h); setPlaying(false); }}
          onToggle={() => setPlaying((p) => !p)}
          onAll={() => { setHour(null); setPlaying(false); }} />
        <AnimatePresence>
          {storyOn && (
            <StoryBar chapters={chapters} idx={chapterIdx} playing={storyPlaying}
              onJump={(i) => { setStoryPlaying(false); applyChapter(i); }}
              onToggle={() => setStoryPlaying((p) => !p)} onClose={closeStory} />
          )}
        </AnimatePresence>
      </div>
      <Tooltip info={hover} tab={tab} layer={layer} />
      {!ready && (
        <div className="loader" style={{ opacity: 0, pointerEvents: "none" }}>
          <div className="ring" />
        </div>
      )}
    </>
  );
}
