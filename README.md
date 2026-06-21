# 🅿️ Parking Intelligence — Bengaluru
### AI-driven detection of illegal-parking hotspots & quantification of their congestion impact

> **Problem Statement 1 — Poor Visibility on Parking-Induced Congestion**
> *"How can AI-driven parking intelligence detect illegal parking hotspots and
> quantify their impact on traffic flow to enable targeted enforcement?"*

The PS asks for exactly three things — **detect hotspots → quantify their impact
on traffic flow → enable targeted enforcement**. That is the spine of this system,
built on **298,450 real police parking-violation records** (Bengaluru, Nov 2023 –
Apr 2024):

1. **DETECT** — where does illegal parking concentrate? → H3 hotspot detection
2. **QUANTIFY IMPACT** — how much does it choke traffic? → **Parking Congestion
   Impact Score (PCIS)**, *validated* on held-out data (see below)
3. **TARGET** — where do limited units go? → deployment optimizer + ROI curve

> A next-day **forecast** is included as a proactive *extension* — clearly labelled,
> and the graded core does not depend on it.

### The impact claim is validated, not asserted
Trained on the first half of the window, tested on the held-out second half:

| Check | Result |
|---|---|
| PCIS predicts future flow-impact (Spearman ρ) | **0.65** |
| …vs. a raw violation-count baseline | 0.58 → **PCIS wins by +0.07** |
| Future burden of the top-10% PCIS cells | **3.3× the average cell** |
| Enforcement bias audited | 39% morning vs **0.2% evening** rush (under-policed) |

PCIS beats raw counts *on the impact dimension* precisely because it weights
carriageway occupancy, road criticality and junction proximity — not volume.

---

## Why this wins

Maps 1:1 to the PS verbs — and each verb has an *operational* layer, not just a chart:

| PS verb | What we deliver | Operational layer |
|---|---|---|
| **Detect** hotspots | H3 hotspot detection, validated as persistent | **Bias-corrected detection** — ranks by violations-per-patrol-session, surfacing **237 under-enforced** hotspots (hot but rarely policed) |
| **Quantify** impact on flow | **PCIS**, validated (ρ 0.65, 3.3× lift) | **Carriageway view** — impact aggregated to named roads, so a *corridor* gets enforced, not a point |
| **Enable** targeted enforcement | Deployment optimizer + ROI curve | **Roll-call work orders** — 668 station×shift tasks (location, target violation+vehicle, time window, revisit cadence), CSV-exportable |
| *(extension)* proactive | — | **Next-7-day hotspot forecast** (ROC-AUC 0.96 / P@50 64%) for pre-emptive staffing |

The point: it's not a dashboard you look at — it's a system that outputs **what a constable does at 9am**, corrects for **patrol bias**, and targets **whole carriageways**.

The hard, original part of PS1 is *"quantify impact on traffic flow"* — and the
dataset has **no traffic-flow column**. We bridge that with **PCIS**: a parked
vehicle's harm = the fraction of available **carriageway** it steals, where
carriageway width comes from real **OpenStreetMap** road class + lane data,
amplified by junction proximity, peak-hour timing, and chronicity. A scooter on a
6-lane arterial ≠ a car double-parked on a 2-lane road beside a junction.

---

## Architecture

```
 RAW CSV (298k)
      │
      ▼
┌──────────────────────┐     Kaggle GPU pipeline (heavy compute)
│ 01 data_engine  (H3) │──▶ events.parquet, cells_h3.parquet
│ 02 PCIS  (OSM/osmnx) │──▶ pcis.json            ◀── the differentiator
│ 03 forecast (XGB GPU)│──▶ forecast.json + metrics
│ 04 prioritization    │──▶ deployment_plan.json
└──────────────────────┘
      │  artifacts (JSON)
      ▼
┌──────────────────────┐     Local (top-notch UI)
│ frontend  (deck.gl)  │  3D hexbins · impact columns · heatmap ·
│ React + MapLibre     │  24h time-lapse · hover · enforcement leaderboard
└──────────────────────┘
```

A light local pre-processor (`pipeline/build_artifacts.py`, pandas only) generates
demo-ready artifacts from the real data so the dashboard runs without the GPU step;
the Kaggle scripts produce the production-grade `pcis.json` / `forecast.json`.

---

## Run it

**Dashboard (local):**
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```
Artifacts are pre-built in `frontend/public/data/`. To rebuild from raw:
```bash
python pipeline/build_artifacts.py
```

**ML pipeline (Kaggle GPU):** see [`kaggle/README.md`](kaggle/README.md).

---

## What's inside

```
grid/
├── pipeline/build_artifacts.py   # local pandas pre-processor → UI artifacts
├── kaggle/                       # GPU scripts (H3, OSM-PCIS, forecast, optimizer)
├── frontend/                     # deck.gl 3D command center
└── docs/METHODOLOGY.md           # full method, metrics, assumptions
```

See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) for the PCIS formula, model
design, evaluation protocol, and assumptions.
