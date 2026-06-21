import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fmt, impactColor, SHIFT_HEX } from "../lib/data";
import type {
  Summary, Hotspot, LayerId, RailTab, ForecastCell, ForecastMetrics, DeployPlan,
  Validation, DeployRoi, Detection, Corridor, Tasking, StationTasking, WorkOrder,
} from "../types";

/* ---------------- Top bar ---------------- */
export function TopBar({ summary, onStory }: { summary: Summary; onStory: () => void }) {
  return (
    <motion.div className="topbar"
      initial={{ y: -30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.5 }}>
      <div className="glass" style={{ padding: "12px 18px" }}>
        <div className="brand">
          <div className="logo">◳</div>
          <div>
            <h1>Parking Intelligence<span className="tag">Bengaluru</span></h1>
            <div className="sub">
              AI illegal-parking hotspot & congestion-impact engine · {summary.date_min} → {summary.date_max}
            </div>
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 12 }}>
        <button className="story-launch glass" onClick={onStory}>▶ Story Mode</button>
        <div className="glass" style={{ padding: "10px 16px", display: "flex", gap: 22 }}>
          <Stat v={fmt(summary.total_violations)} l="Violations" cls="cy" />
          <Stat v={String(summary.stations)} l="Stations" />
          <Stat v={String(summary.hotspot_cells)} l="Hotspots" cls="hot" />
        </div>
      </div>
    </motion.div>
  );
}
function Stat({ v, l, cls = "" }: { v: string; l: string; cls?: string }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div className="mono" style={{ fontSize: 20, fontWeight: 800,
        color: cls === "hot" ? "var(--hot)" : cls === "cy" ? "var(--accent)" : "var(--text)" }}>{v}</div>
      <div style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 2, letterSpacing: 0.4 }}>{l}</div>
    </div>
  );
}

/* ---------------- Left KPI rail ---------------- */
const CAT_COLOR: Record<string, string> = {
  "WRONG PARKING": "#00e5ff", "NO PARKING": "#2bd9a0",
  "PARKING IN A MAIN ROAD": "#ff2e6a", "PARKING ON FOOTPATH": "#7c5cff",
  "DOUBLE PARKING": "#ffb020",
};
export function KpiRail({ summary }: { summary: Summary }) {
  const cats = Object.entries(summary.by_cat).slice(0, 5);
  const max = Math.max(...cats.map(([, v]) => v), 1);
  return (
    <motion.div className="rail-left"
      initial={{ x: -30, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ duration: 0.5, delay: 0.1 }}>
      <div className="glass">
        <div className="kpi-grid">
          <Kpi v={summary.top_hotspot_pcis.toFixed(0)} l="Peak Impact Score" cls="hot" />
          <Kpi v={summary.peak_share + "%"} l="In Rush Hours" cls="cy" />
          <Kpi v={summary.obstructive_share + "%"} l="Lane-Blocking" cls="gd" />
          <Kpi v={fmt(summary.carriageway_m2_stolen)} l="m² Road Stolen" />
        </div>
      </div>
      <div className="glass">
        <div className="section-title">Violation Mix</div>
        <div className="panel-pad" style={{ paddingTop: 8 }}>
          {cats.map(([k, v]) => {
            const c = CAT_COLOR[k] || "#789";
            // perceptual (sqrt) scale + min width so skewed categories stay visibly coloured
            const w = Math.max(8, Math.sqrt(v / max) * 100);
            return (
              <div className="bar-row" key={k}>
                <span className="lab" title={k}>{k.replace("PARKING ", "").replace(" A MAIN ROAD", " M.ROAD")}</span>
                <span className="bar-track">
                  <motion.span className="bar-fill" initial={{ width: 0 }} animate={{ width: `${w}%` }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    style={{ background: `linear-gradient(90deg, ${c}, ${c}cc)`, boxShadow: `0 0 10px ${c}77` }} />
                </span>
                <span className="num" style={{ color: c }}>{fmt(v)}</span>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
function Kpi({ v, l, cls = "" }: { v: string; l: string; cls?: string }) {
  return <div className="kpi"><div className={`v ${cls}`}>{v}</div><div className="l">{l}</div></div>;
}

/* ---------------- Right rail with tabs ---------------- */
const TABS: { id: RailTab; label: string }[] = [
  { id: "hotspots", label: "Detect" },
  { id: "impact", label: "Impact" },
  { id: "deploy", label: "Target" },
  { id: "forecast", label: "Forecast" },
];
export function RightRail(props: {
  tab: RailTab; onTab: (t: RailTab) => void; summary: Summary;
  hotspots: Hotspot[]; forecast: ForecastCell[] | null; metrics: ForecastMetrics | null;
  deploy: DeployPlan | null; validation: Validation | null; roi: DeployRoi | null;
  detection: Detection | null; corridors: Corridor[] | null; tasking: Tasking | null;
  selected: Hotspot | null;
  onSelectHot: (h: Hotspot) => void; onFly: (lng: number, lat: number) => void;
}) {
  const { tab, onTab } = props;
  const [detectMode, setDetectMode] = useState<"hotspots" | "exposure">("hotspots");
  const [impactMode, setImpactMode] = useState<"validation" | "corridors">("validation");
  const [deployMode, setDeployMode] = useState<"orders" | "plan">("orders");
  return (
    <motion.div className="rail-right glass"
      initial={{ x: 30, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ duration: 0.5, delay: 0.15 }}>
      <div className="rail-tabs">
        {TABS.map((t) => (
          <button key={t.id} className={`rail-tab ${tab === t.id ? "active" : ""}`} onClick={() => onTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={tab} className="rail-body"
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.18 }}>
          {tab === "hotspots" && (<>
            <SubToggle val={detectMode} onChange={setDetectMode}
              opts={[{ id: "hotspots", label: "Priority" }, { id: "exposure", label: "Bias-corrected" }]} />
            {detectMode === "hotspots" ? <HotspotList {...props} /> : <DetectionPanel {...props} />}
          </>)}
          {tab === "impact" && (<>
            <SubToggle val={impactMode} onChange={setImpactMode}
              opts={[{ id: "validation", label: "Validation" }, { id: "corridors", label: "Carriageways" }]} />
            {impactMode === "validation" ? <ImpactPanel {...props} /> : <CorridorPanel {...props} />}
          </>)}
          {tab === "deploy" && (<>
            <SubToggle val={deployMode} onChange={setDeployMode}
              opts={[{ id: "orders", label: "Work Orders" }, { id: "plan", label: "Map Plan" }]} />
            {deployMode === "orders" ? <TaskingPanel {...props} /> : <DeployPanel {...props} />}
          </>)}
          {tab === "forecast" && <ForecastPanel {...props} />}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}

function SubToggle<T extends string>({ opts, val, onChange }:
  { opts: { id: T; label: string }[]; val: T; onChange: (v: T) => void }) {
  return (
    <div className="subtoggle">
      {opts.map((o) => (
        <button key={o.id} className={`subbtn ${val === o.id ? "active" : ""}`} onClick={() => onChange(o.id)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

function HotspotList({ hotspots, selected, onSelectHot }:
  { hotspots: Hotspot[]; selected: Hotspot | null; onSelectHot: (h: Hotspot) => void }) {
  const maxP = Math.max(...hotspots.map((h) => h.pcis), 1);
  return (
    <>
      <div className="section-title">Enforcement Priority · Top {Math.min(40, hotspots.length)}</div>
      <div className="hot-list">
        {hotspots.slice(0, 40).map((h, i) => {
          const [r, g, b] = impactColor(h.pcis / maxP);
          const active = selected?.rank === h.rank;
          return (
            <motion.div key={h.rank} className={`hot-item ${active ? "active" : ""}`} onClick={() => onSelectHot(h)}
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.01 }}>
              <span className="hot-rank">{h.rank}</span>
              <div className="hot-meta">
                <div className="t">{h.top_junction !== "—" ? h.top_junction.replace(/^BTP\d+ - /, "") : h.top_ps}</div>
                <div className="s">{h.top_ps} · {fmt(h.n)} cases · {h.peak.toFixed(0)}% peak</div>
              </div>
              <span className="pcis-pill" style={{ background: `rgba(${r},${g},${b},0.16)`, color: `rgb(${r},${g},${b})` }}>
                {h.pcis.toFixed(0)}
              </span>
            </motion.div>
          );
        })}
      </div>
    </>
  );
}

/* ---------- ① Detect: bias-corrected / exposure ---------- */
const CLASS_COLOR: Record<string, string> = {
  "under-enforced": "#ff2e6a", saturated: "#7c5cff", hotspot: "#ffb020", normal: "#5b6a85",
};
function DetectionPanel({ detection, validation, onFly }:
  { detection: Detection | null; validation: Validation | null; onFly: (lng: number, lat: number) => void }) {
  if (!detection) return <Empty title="Detection not loaded" hint="Run pipeline/build_artifacts.py" />;
  const s = detection.summary;
  const total = Object.values(s).reduce((a, b) => a + b, 0);
  return (
    <div className="impact-panel">
      <div className="section-title">Bias-Corrected Detection</div>
      <div className="iv-lead">
        Hotspots from tickets are biased toward where police already patrol. We rank by
        <b> yield per visit</b> = violations caught per patrol session, exposing spots that are
        <b> hot but rarely policed</b>.
      </div>
      {validation?.bias_correction && (
        <div className="robust-line" style={{ margin: "0 12px 8px" }}>
          ✓ <b>Yield is a stable signal</b> — high-yield spots stay high-yield (ρ{" "}
          {validation.bias_correction.yield_stability_spearman.toFixed(2)} across held-out halves),
          so it reflects real demand, not patrol luck
        </div>
      )}
      <div className="class-bar">
        {Object.entries(s).map(([k, v]) => (
          <div key={k} className="class-seg" title={`${k}: ${v}`}
            style={{ flex: v || 0.001, background: CLASS_COLOR[k] }} />
        ))}
      </div>
      <div className="class-legend">
        {Object.entries(s).map(([k, v]) => (
          <span key={k} className="cl-item"><i style={{ background: CLASS_COLOR[k] }} />{k} {v}</span>
        ))}
      </div>
      <div className="under-head">
        <span className="uh-big">{s["under-enforced"]}</span>
        <span className="uh-sub">hotspots are <b>under-enforced</b> — dense when visited, but{" "}
          {(100 * s["under-enforced"] / total).toFixed(0)}% of priority spots get too few patrols</span>
      </div>
      <div className="section-title" style={{ paddingTop: 4 }}>Send patrols here first</div>
      <div className="hot-list" style={{ maxHeight: 260 }}>
        {detection.under_enforced.slice(0, 30).map((c, i) => (
          <motion.div key={i} className="hot-item" onClick={() => onFly(c.lng, c.lat)}
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.012 }}>
            <span className="hot-rank" style={{ color: "var(--hot)" }}>{c.intensity.toFixed(0)}</span>
            <div className="hot-meta">
              <div className="t">{c.top_junction !== "—" ? c.top_junction.replace(/^BTP\d+ - /, "") : c.top_ps}</div>
              <div className="s">{fmt(c.n)} cases in {c.sessions} patrol{c.sessions > 1 ? "s" : ""} · {c.top_ps}</div>
            </div>
            <span className="pcis-pill" style={{ background: "rgba(255,46,106,0.16)", color: "var(--hot)" }}>
              {c.intensity.toFixed(0)}×
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

/* ---------- ② Quantify-flow: choked carriageways ---------- */
function CorridorPanel({ corridors, onFly }:
  { corridors: Corridor[] | null; onFly: (lng: number, lat: number) => void }) {
  if (!corridors) return <Empty title="Corridors not loaded" hint="Run pipeline/build_artifacts.py" />;
  const maxP = Math.max(...corridors.map((c) => c.impact), 1);
  return (
    <div className="impact-panel">
      <div className="section-title">Most-Choked Carriageways</div>
      <div className="iv-lead">
        Impact aggregated to whole roads — so enforcement can clear a <b>corridor</b>, not
        just a point. Ranked by load × lane-blocking × peak concentration.
      </div>
      <div className="hot-list" style={{ maxHeight: 420 }}>
        {corridors.map((c, i) => {
          const [r, g, b] = impactColor(c.impact / maxP);
          return (
            <motion.div key={i} className="hot-item" onClick={() => onFly(c.lng, c.lat)}
              initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.01 }}>
              <span className="hot-rank">{i + 1}</span>
              <div className="hot-meta">
                <div className="t">{c.road}</div>
                <div className="s">{fmt(c.n)} cases · {(c.obstr_share * 100).toFixed(0)}% lane-blocking · {c.peak.toFixed(0)}% peak</div>
              </div>
              <span className="pcis-pill" style={{ background: `rgba(${r},${g},${b},0.16)`, color: `rgb(${r},${g},${b})` }}>
                {c.impact.toFixed(0)}
              </span>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------- ③ Enable: operational work orders ---------- */
function downloadCSV(st: StationTasking) {
  const rows = [["shift", "location", "window", "target_violation", "target_vehicle", "severity", "lane_m_blocked", "revisit", "cases"]];
  for (const [sh, orders] of Object.entries(st.shifts))
    for (const o of orders)
      rows.push([sh, o.loc, o.window, o.target_violation, o.target_vehicle, String(o.severity), String(o.lane_m), o.revisit, String(o.cases)]);
  const csv = rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a"); a.href = url;
  a.download = `briefing_${st.station.replace(/\s+/g, "_")}.csv`; a.click();
  URL.revokeObjectURL(url);
}
const SHIFT_ICON: Record<string, string> = { morning: "🌅", afternoon: "☀️", evening: "🌆", night: "🌙" };
function TaskingPanel({ tasking, onFly }:
  { tasking: Tasking | null; onFly: (lng: number, lat: number) => void }) {
  const [open, setOpen] = useState(0);
  if (!tasking) return <Empty title="Tasking not loaded" hint="Run pipeline/build_artifacts.py" />;
  const total = tasking.stations.reduce((a, s) => a + s.orders, 0);
  return (
    <div className="impact-panel">
      <div className="section-title">Roll-Call Work Orders</div>
      <div className="iv-lead">
        The priority map as a <b>shift briefing</b> — {total} work orders across{" "}
        {tasking.stations.length} stations. Drops into roll-call, zero workflow change.
      </div>
      <div className="task-stations">
        {tasking.stations.slice(0, 18).map((st, i) => (
          <div key={st.station} className={`task-station ${open === i ? "open" : ""}`}>
            <div className="ts-head" onClick={() => setOpen(open === i ? -1 : i)}>
              <span className="ts-name">{st.station}</span>
              <span className="ts-meta">{st.orders} orders
                <button className="ts-dl" title="Download CSV briefing"
                  onClick={(e) => { e.stopPropagation(); downloadCSV(st); }}>⤓</button>
              </span>
            </div>
            <AnimatePresence>
              {open === i && (
                <motion.div className="ts-body" initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
                  {Object.entries(st.shifts).map(([sh, orders]) => (
                    <div key={sh} className="ts-shift">
                      <div className="ts-shift-h">{SHIFT_ICON[sh]} {sh}</div>
                      {orders.map((o, k) => <WorkOrderCard key={k} o={o} onFly={onFly} />)}
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
    </div>
  );
}
function WorkOrderCard({ o, onFly }: { o: WorkOrder; onFly: (lng: number, lat: number) => void }) {
  const [r, g, b] = impactColor(o.severity / 100);
  return (
    <div className="wo-card" onClick={() => onFly(o.lng, o.lat)}>
      <div className="wo-top">
        <span className="wo-loc">{o.loc.replace(/^BTP\d+ - /, "")}</span>
        <span className="wo-sev" style={{ color: `rgb(${r},${g},${b})` }}>{o.severity.toFixed(0)}</span>
      </div>
      <div className="wo-detail">
        <span className="wo-pill">🕑 {o.window}</span>
        <span className="wo-pill">🎯 {o.target_violation}</span>
        <span className="wo-pill">🚗 {o.target_vehicle}</span>
        {o.lane_m > 0 && <span className="wo-pill">🚧 ~{o.lane_m} lane-m</span>}
        <span className="wo-pill rev">↻ {o.revisit}</span>
      </div>
    </div>
  );
}

function ImpactPanel({ validation, summary }: { validation: Validation | null; summary: Summary }) {
  if (!validation)
    return <Empty title="Validation not loaded" hint="Run pipeline/build_artifacts.py" />;
  const v = validation;
  const pc = v.spearman_pcis_vs_future_impact;
  const ct = v.spearman_rawcount_vs_future_impact;
  const maxAbl = Math.max(...v.ablation.map((a) => Math.abs(a.contribution)), 0.01);
  const iu = summary.impact_units;
  return (
    <div className="impact-panel">
      {iu && (
        <div className="rwi-card" title={iu.assumptions}>
          <div className="rwi-row">
            <div className="rwi-metric">
              <span className="rwi-big">{Math.round(iu.peak_lane_m_blocked)}</span>
              <span className="rwi-unit">lane-m</span>
            </div>
            <div className="rwi-metric">
              <span className="rwi-big">{iu.lane_km_hours_per_day}</span>
              <span className="rwi-unit">lane-km·h / day</span>
            </div>
          </div>
          <div className="rwi-cap">carriageway blocked at peak · road-time lost daily
            <span className="rwi-est">est.</span></div>
        </div>
      )}
      <div className="section-title">Does PCIS Predict Real Congestion?</div>
      <div className="iv-lead">
        Trained on the first half of the window, tested on the held-out second half —
        <b> {v.target}</b>. No leakage.
      </div>

      <div className="proof-card">
        <div className="proof-head">Predictive validity (Spearman ρ)</div>
        <div className="proof-bar">
          <span className="pb-lab">PCIS</span>
          <span className="pb-track"><motion.span className="pb-fill cy"
            initial={{ width: 0 }} animate={{ width: `${pc * 100}%` }} transition={{ duration: 0.9 }} /></span>
          <span className="pb-num">{pc.toFixed(2)}</span>
        </div>
        <div className="proof-bar">
          <span className="pb-lab">Raw count</span>
          <span className="pb-track"><motion.span className="pb-fill dim"
            initial={{ width: 0 }} animate={{ width: `${ct * 100}%` }} transition={{ duration: 0.9, delay: 0.1 }} /></span>
          <span className="pb-num">{ct.toFixed(2)}</span>
        </div>
        <div className="proof-edge">PCIS beats raw volume by <b>+{v.pcis_edge_over_count.toFixed(2)}</b> on flow-impact</div>
      </div>

      <div className="iv-stats">
        <M v={`${v.top_decile_future_lift.toFixed(1)}×`} l="Top-10% future burden" cls="cy" />
        <M v={v.n_cells_tested.toLocaleString()} l="Cells tested" />
        <M v={pc.toFixed(2)} l="Held-out ρ" />
      </div>

      {v.weight_sensitivity && (
        <div className="robust-line">
          ✓ <b>Weights are robust</b> — ranking holds at ρ {v.weight_sensitivity.mean_rank_spearman.toFixed(2)} and{" "}
          {(v.weight_sensitivity.mean_top50_overlap * 100).toFixed(0)}% top-50 overlap under ±25% weight perturbation
        </div>
      )}

      <div className="section-title" style={{ paddingTop: 6 }}>Component Contribution</div>
      <div className="ablation">
        {v.ablation.map((a) => {
          const pos = a.contribution >= 0;
          return (
            <div className="abl-row" key={a.component}>
              <span className="abl-lab">{a.component}</span>
              <span className="abl-track">
                <motion.span className={`abl-fill ${pos ? "pos" : "neg"}`}
                  initial={{ width: 0 }} animate={{ width: `${(Math.abs(a.contribution) / maxAbl) * 100}%` }}
                  transition={{ duration: 0.7 }} />
              </span>
              <span className="abl-num" style={{ color: pos ? "var(--good)" : "var(--text-faint)" }}>
                {pos ? "+" : ""}{a.contribution.toFixed(2)}
              </span>
            </div>
          );
        })}
      </div>

      <div className="bias-card">
        <div className="bias-head">⚠ Enforcement bias, audited</div>
        <div className="bias-nums">
          <span><b>{v.bias.morning_rush_share}%</b> morning rush</span>
          <span className="bias-vs">vs</span>
          <span><b className="hot">{v.bias.evening_rush_share}%</b> evening rush</span>
        </div>
        <div className="bias-note">{v.bias.note}</div>
      </div>
    </div>
  );
}

function RoiSparkline({ roi, units }: { roi: DeployRoi; units: number }) {
  const c = roi.curve;
  const maxC = c[c.length - 1]?.coverage_pct || 1;
  const W = 268, H = 64;
  const pts = c.map((p, i) => {
    const x = (i / (c.length - 1)) * W;
    const y = H - (p.coverage_pct / maxC) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const at = c.find((p) => p.units === units) || c[Math.min(units, c.length) - 1];
  const ax = ((units - 1) / (c.length - 1)) * W;
  const ay = H - (at.coverage_pct / maxC) * H;
  return (
    <div className="roi-wrap">
      <div className="roi-head"><span>Impact removed vs patrol units</span>
        <span className="roi-anno">{units}u · {at.coverage_pct}%</span></div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="roi-svg">
        <defs>
          <linearGradient id="roiG" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(43,217,160,0.5)" />
            <stop offset="100%" stopColor="rgba(43,217,160,0)" />
          </linearGradient>
        </defs>
        <polygon points={`0,${H} ${pts} ${W},${H}`} fill="url(#roiG)" />
        <polyline points={pts} fill="none" stroke="var(--good)" strokeWidth="2" />
        <line x1={ax} y1="0" x2={ax} y2={H} stroke="var(--accent)" strokeWidth="1" strokeDasharray="3 3" />
        <circle cx={ax} cy={ay} r="4" fill="var(--accent)" />
      </svg>
      <div className="roi-foot">Diminishing returns — the first units clear the worst chokepoints</div>
    </div>
  );
}

function ForecastPanel({ forecast, metrics, onFly }:
  { forecast: ForecastCell[] | null; metrics: ForecastMetrics | null; onFly: (lng: number, lat: number) => void }) {
  if (!forecast)
    return <Empty title="Forecast not loaded" hint="Drop forecast.json into /public/data" />;
  const maxP = Math.max(...forecast.map((f) => f.pred), 1);
  return (
    <>
      <div className="section-title">Next-{metrics?.horizon_days ?? 7}-Day Hotspot Forecast <span className="ext-tag">extension</span></div>
      {metrics && (
        <div className="metric-strip">
          <M v={metrics.ROC_AUC.toFixed(2)} l="ROC-AUC" cls="cy" />
          <M v={(metrics["Precision@50"] * 100).toFixed(0) + "%"} l="Top-50 Hit" />
          <M v={metrics["NDCG@50"].toFixed(2)} l="NDCG@50" />
          <M v={metrics.cells.toString()} l="Cells" />
        </div>
      )}
      <div className="fc-note">Walk-forward validated · ranks each cell by predicted parking load over the next {metrics?.horizon_days ?? 7} days — the horizon enforcement staffs shifts around</div>
      <div className="hot-list">
        {forecast.slice(0, 40).map((f, i) => {
          const [r, g, b] = impactColor(f.pred / maxP);
          const err = f.actual > 0 ? Math.abs(f.pred - f.actual) / f.actual : 0;
          const acc = Math.max(0, 1 - err);
          return (
            <motion.div key={f.h3} className="hot-item" onClick={() => onFly(f.lng, f.lat)}
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.01 }}>
              <span className="hot-rank">{f.rank}</span>
              <div className="hot-meta">
                <div className="t mono">{f.lat.toFixed(4)}, {f.lng.toFixed(4)}</div>
                <div className="s">next 7d <b style={{ color: `rgb(${r},${g},${b})` }}>{f.pred.toFixed(0)}</b> · last 7d {f.actual.toFixed(0)}
                  <span className="acc-dot" style={{ background: acc > 0.8 ? "var(--good)" : acc > 0.5 ? "var(--warn)" : "var(--hot)" }} />
                </div>
              </div>
              <span className="pcis-pill" style={{ background: `rgba(${r},${g},${b},0.16)`, color: `rgb(${r},${g},${b})` }}>
                {f.pred.toFixed(0)}
              </span>
            </motion.div>
          );
        })}
      </div>
    </>
  );
}

function DeployPanel({ deploy, roi, onFly }:
  { deploy: DeployPlan | null; roi: DeployRoi | null; onFly: (lng: number, lat: number) => void }) {
  if (!deploy)
    return <Empty title="Deployment plan not loaded" hint="Drop deployment_plan.json into /public/data" />;
  return (
    <>
      <div className="section-title">Targeted Enforcement Plan</div>
      <div className="deploy-hero">
        <div className="dh-big">{deploy.coverage_pct}%</div>
        <div className="dh-sub">of total congestion impact removed by<br /><b>{deploy.units} patrol units</b> across {fmt(deploy.hotspots_total)} hotspots</div>
      </div>
      {roi && <RoiSparkline roi={roi} units={deploy.units} />}
      <div className="shift-legend">
        {Object.entries(SHIFT_HEX).map(([s, c]) => (
          <span key={s} className="sl-item"><span className="sl-dot" style={{ background: c }} />{s}</span>
        ))}
      </div>
      <div className="hot-list">
        {deploy.roster.map((u, i) => (
          <motion.div key={u.unit} className="hot-item" onClick={() => onFly(u.lng, u.lat)}
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.012 }}>
            <span className="unit-badge" style={{ background: SHIFT_HEX[u.shift] || "#789" }}>{u.unit}</span>
            <div className="hot-meta">
              <div className="t">{u.police_station}</div>
              <div className="s">{u.shift} · clears {u.cells_cleared} cells · PCIS {u.anchor_pcis.toFixed(0)}</div>
            </div>
            <span className="pcis-pill" style={{ background: "rgba(43,217,160,0.14)", color: "var(--good)" }}>
              +{u.impact_removed.toFixed(0)}
            </span>
          </motion.div>
        ))}
      </div>
    </>
  );
}

function M({ v, l, cls = "" }: { v: string; l: string; cls?: string }) {
  return <div className="metric"><div className={`mv ${cls}`}>{v}</div><div className="ml">{l}</div></div>;
}
function Empty({ title, hint }: { title: string; hint: string }) {
  return <div className="empty"><div className="empty-icn">◳</div><div className="empty-t">{title}</div><div className="empty-h">{hint}</div></div>;
}

/* ---------------- Layer switcher ---------------- */
const LAYERS: { id: LayerId; label: string; color: string }[] = [
  { id: "heat", label: "Heatmap", color: "#ffb020" },
  { id: "hex", label: "3D Density", color: "#00e5ff" },
  { id: "columns", label: "Impact Columns", color: "#ff2e6a" },
  { id: "scatter", label: "Raw Points", color: "#7c5cff" },
];
export function LayerSwitcher({ layer, onChange }: { layer: LayerId; onChange: (l: LayerId) => void }) {
  return (
    <motion.div className="layers glass"
      initial={{ x: -30, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.3 }}>
      {LAYERS.map((l) => (
        <button key={l.id} className={`layer-btn ${layer === l.id ? "active" : ""}`} onClick={() => onChange(l.id)}>
          <span className="dot" style={{ color: l.color }} />{l.label}
        </button>
      ))}
    </motion.div>
  );
}

/* ---------------- Legend ---------------- */
export function Legend({ tab, layer }: { tab: RailTab; layer: LayerId }) {
  const title = tab === "forecast" ? "Predicted parking load (tomorrow)"
    : tab === "deploy" ? "Patrol shift · ring = coverage radius"
    : layer === "columns" ? "Parking Congestion Impact Score"
    : "Violation density (footprint-weighted)";
  if (tab === "deploy") {
    return (
      <motion.div className="legend glass" initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }}>
        <div className="lt">{title}</div>
        <div className="shift-legend">
          {Object.entries(SHIFT_HEX).map(([s, c]) => (
            <span key={s} className="sl-item"><span className="sl-dot" style={{ background: c }} />{s}</span>
          ))}
        </div>
      </motion.div>
    );
  }
  const isScore = tab === "forecast" || layer === "columns";
  return (
    <motion.div className="legend glass" initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }}>
      <div className="lt">{title}</div>
      <div className="ramp" />
      <div className="scale"><span>low</span><span>high</span></div>
    </motion.div>
  );
}

/* ---------------- Time bar ---------------- */
export function TimeBar({ hour, playing, byHour, onScrub, onToggle, onAll }: {
  hour: number | null; playing: boolean; byHour: number[];
  onScrub: (h: number) => void; onToggle: () => void; onAll: () => void;
}) {
  const max = Math.max(...byHour, 1);
  const label = hour === null ? "All day"
    : `${String(hour).padStart(2, "0")}:00 – ${String((hour + 1) % 24).padStart(2, "0")}:00`;
  return (
    <motion.div className="timebar glass" initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.25 }}>
      <button className="play-btn" onClick={onToggle} title={playing ? "Pause" : "Play 24h"}>{playing ? "❚❚" : "▶"}</button>
      <div className="time-wrap">
        <div className="time-head">
          <span className="lbl">Time of day</span>
          <span className="hr">{label}</span>
          <button className={`chip ${hour === null ? "active" : ""}`} onClick={onAll}>All</button>
        </div>
        <div className="histo">
          {byHour.map((v, h) => (
            <div key={h} className={`b ${hour === h ? "on" : ""} ${hour !== null && hour !== h ? "dim" : ""}`}
              style={{ height: `${(v / max) * 100}%` }} onClick={() => onScrub(h)} title={`${h}:00 · ${fmt(v)}`} />
          ))}
        </div>
        <input type="range" min={0} max={23} value={hour ?? 0} onChange={(e) => onScrub(Number(e.target.value))} />
      </div>
    </motion.div>
  );
}

/* ---------------- Story mode ---------------- */
export interface Chapter { n: number; title: string; narration: string; }
export function StoryBar({ chapters, idx, playing, onJump, onToggle, onClose }: {
  chapters: Chapter[]; idx: number; playing: boolean;
  onJump: (i: number) => void; onToggle: () => void; onClose: () => void;
}) {
  const ch = chapters[idx];
  return (
    <motion.div className="story-wrap" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <motion.div className="story-card glass" key={idx}
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <div className="sc-chip">Chapter {ch.n} / {chapters.length}</div>
        <div className="sc-title">{ch.title}</div>
        <div className="sc-text">{ch.narration}</div>
      </motion.div>
      <div className="story-ctrl glass">
        <button className="play-btn sm" onClick={onToggle}>{playing ? "❚❚" : "▶"}</button>
        <div className="story-dots">
          {chapters.map((c, i) => (
            <button key={c.n} className={`sdot ${i === idx ? "active" : ""} ${i < idx ? "done" : ""}`}
              onClick={() => onJump(i)} title={c.title}>
              <span>{c.n}</span><label>{c.title}</label>
            </button>
          ))}
        </div>
        <button className="story-x" onClick={onClose}>✕</button>
      </div>
    </motion.div>
  );
}

/* ---------------- Tooltip ---------------- */
export function Tooltip({ info, tab, layer }: { info: any; tab: RailTab; layer: LayerId }) {
  if (!info?.object || info.x == null) return null;
  const o = info.object;
  let title = ""; let body: React.ReactNode = null;

  if (tab === "deploy" && o.unit != null) {
    title = `Unit ${o.unit} · ${o.police_station}`;
    body = (<><Row k="Shift" v={o.shift} /><Row k="Anchor PCIS" v={o.anchor_pcis.toFixed(1)} />
      <Row k="Cells cleared" v={String(o.cells_cleared)} /><Row k="Impact removed" v={"+" + o.impact_removed.toFixed(1)} /></>);
  } else if (tab === "forecast" && o.pred != null) {
    title = `Forecast #${o.rank}`;
    body = (<><Row k="Predicted load" v={o.pred.toFixed(1)} /><Row k="Actual" v={o.actual.toFixed(1)} /></>);
  } else if (layer === "columns" && o.pcis != null) {
    title = o.top_junction !== "—" ? o.top_junction : o.top_ps;
    body = (<><Row k="Impact Score" v={o.pcis.toFixed(1)} /><Row k="Violations" v={fmt(o.n)} />
      <Row k="Lane-blocking" v={fmt(o.obstructive)} /><Row k="Peak share" v={o.peak.toFixed(0) + "%"} />
      <Row k="Active days" v={String(o.chronicity)} /></>);
  } else if (o.points) {
    title = "Density cell";
    body = (<><Row k="Records" v={fmt(o.points.length)} /><Row k="Footprint" v={fmt(o.colorValue ?? o.elevationValue ?? o.points.length)} /></>);
  } else return null;

  return (
    <div className="deck-tip" style={{ left: info.x, top: info.y }}>
      <div className="tt">{title}</div>{body}
    </div>
  );
}
function Row({ k, v }: { k: string; v: string }) {
  return <div className="row"><span className="k">{k}</span><span className="v">{v}</span></div>;
}
