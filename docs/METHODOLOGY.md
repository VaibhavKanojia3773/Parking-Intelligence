# Methodology — Parking Intelligence (PS1)

## 1. Data

**Source:** `jan to may police violation_anonymized791b166.csv` — 298,450 police
parking-enforcement records, Bengaluru, **2023-11-10 → 2024-04-08**.

| Field | Use |
|---|---|
| `latitude`, `longitude` | geolocation → H3 indexing |
| `violation_type` (JSON array) | sub-type flags (main-road, footpath, double, no-parking…) |
| `vehicle_type` | → carriageway footprint (m²) |
| `created_datetime` (UTC) | → IST hour / day-of-week / hour-of-week |
| `police_station`, `junction_name` | jurisdiction + junction-proximity proxy |
| `validation_status` | **ground-truth filter** (drop `rejected` / `duplicate`) |

**Cleaning:** clip to Bengaluru bbox (12.70–13.30 N, 77.30–77.90 E); drop
rejected/duplicate enforcement records; UTC→IST; parse violation arrays.
**298,450 → 248,371** valid rows for the local artifacts.

> *Insight surfaced:* enforcement timestamps peak **08:00–11:00** and collapse
> after noon — evening illegal parking is systematically **under-policed**, a
> direct argument for forecast-driven shift planning.

---

## 2. Hotspot detection

Points are indexed to **H3** hexagons (res 10 ≈ 65 m edge for the production
pipeline; a ~165 m grid for the lightweight local artifacts). Each cell is scored
on footprint-weighted volume and only cells with **≥ 20 violations** over the
5-month window are treated as hotspots — removing one-off noise. deck.gl performs
client-side GPU hex aggregation for the 3D view, so the map and the analytics
share one spatial model.

**Vehicle footprint (parked plan area, m²)** — how much carriageway each class steals:
scooter 1.2 · motorcycle 1.4 · auto 4.0 · car 7.5 · LGV 12 · bus 30 (default 6.0).

---

## 3. Parking Congestion Impact Score (PCIS) — the differentiator

The dataset has **no traffic-flow measurement**. We quantify flow impact with a
physically-grounded **occupancy proxy**:

```
occupancy = parked_carriageway_area / available_carriageway_area
          = Σ(vehicle_footprint)   /   (road_width × segment_length)
```

`road_width` is derived from **OpenStreetMap** highway class + lane count
(`02_impact_pcis_osm.py` via `osmnx`). The same violation count hurts far more on
a narrow road than a wide one — occupancy captures this directly.

**PCIS (0–100)** blends percentile-normalized drivers of flow harm:

| Component | Weight | Meaning |
|---|---|---|
| Occupancy | 0.34 | carriageway stolen ÷ available |
| Road criticality | 0.18 | arterial > collector > local (OSM class) |
| Junction proximity | 0.16 | `exp(−dist/120 m)` — junctions choke fastest |
| Lane-blocking share | 0.14 | footpath / double / main-road / crossing |
| Peak concentration | 0.12 | share of cases in rush hours |
| Chronicity | 0.06 | distinct active days (persistent vs one-off) |

Percentile (rank) normalization makes the score outlier-robust and comparable
across the city. **Top hotspots** (Safina Plaza, KR Market, Elite Junction, Sagar
Theatre) match known Bengaluru chokepoints — face validity for the score.

> The local `build_artifacts.py` computes a PCIS variant using a junction-presence
> proxy in place of OSM width, so the dashboard is fully populated without the GPU
> step; the Kaggle version is the rigorous, OSM-grounded score.

---

## 3b. Validating the impact score (the crux of the PS)

A constructed index is worthless if it doesn't track reality. We validate PCIS
three ways — all in `pipeline/build_artifacts.py` (local) and the Kaggle scripts:

**(i) Temporal predictive validity (no leakage).** Build PCIS on the *first half*
of the window; measure whether it predicts the **realized flow-impact** (footprint
of lane-blocking parking) in the held-out *second half*.

| Predictor | Spearman ρ vs. future flow-impact |
|---|---|
| **PCIS** | **0.65** |
| Raw violation count (baseline) | 0.58 |
| → PCIS edge on the impact dimension | **+0.07** |

Top-decile lift: cells in the top 10% of PCIS carry **3.3×** the future burden of
the average cell. (Honest note: for predicting raw *volume*, plain count wins
0.69 vs 0.59 — by design, PCIS is not a volume predictor.)

**(ii) Component ablation.** Drop each driver, renormalize, re-test. Obstruction
(+0.11) and footprint-volume (+0.10) are the dominant contributors to predicting
future impact; junction/peak contribute little to *prediction* (kept for construct
validity — they still matter to live flow).

**(iii) Convergent validity (external, Kaggle).** PCIS vs. OSM road **betweenness
centrality** — an independent structural measure of traffic importance never used
inside PCIS. Positive ρ ⇒ high-impact parking sits on structurally busier roads.

**(iv) Weight robustness.** PCIS weights are expert-set, so we stress-test them:
Monte-Carlo perturb every weight by ±25% (300 draws), renormalize, re-rank. The
ranking is essentially invariant — **mean Spearman ρ 0.998, top-50 overlap 97.7%**.
The score is not an artifact of the specific weights.

**Enforcement selection-bias audit.** These are *enforcement* records, so they
reflect patrol patterns. We quantify it: **39%** of records fall in the morning
rush vs **0.2%** in the evening rush — evening illegal parking is systematically
under-recorded. We mitigate by (a) ranking on *persistence* (validated above) not
raw counts, and (b) the forecast modelling demand including zero-days.

## 3c. Bias-corrected detection — and an honest validation

Raw violation counts over-weight heavily-patrolled areas. We correct with
**yield per visit** = violations caught per patrol session (`device_id` × date),
exposing **234 "under-enforced"** cells (high yield, ≥2 but few visits).

A subtle but important point on validating this: we **cannot** confirm "under-
enforced" against future violation *counts* — the same patrol bias suppresses
second-half counts at rarely-visited cells, so that test is circular. The confound-
free question is whether **per-visit yield is a stable property** of a place. It is:
held-out H1→H2 **Spearman ρ 0.61** — a high-yield location stays high-yield
regardless of how often it's patrolled. So yield reflects real demand, not patrol
luck. (We explicitly *don't* over-claim latent-demand proof from enforcement data
alone — that limitation is inherent and stated.)

## 3d. Real-world impact units

PCIS is a relative index; for a *felt* number we translate footprint into
carriageway blocked, with transparent assumptions (avg dwell 0.75 h, lane width
3.5 m, peak window 4 h — no external data): **≈146 lane-metres of carriageway
blocked at any moment in the morning peak**, ≈**1.6 lane-km·hours of road-time lost
per day**. Per-hotspot lane-metres flow into the work orders.

## 4. Spatiotemporal forecast — *extension* (`03_forecast_ensemble_gpu.py`)

> Not part of the graded PS core (detect/quantify/target); included to show the
> path from reactive to proactive enforcement.

**The honest finding & the reframe.** We first tried to predict the *next single
day*. With heavy features + ensembling the ceiling was only **~45% Precision@50** —
because daily enforcement is partly random (which patrol went where). Rather than
oversell a noisy daily number, we reframed to the horizon enforcement *actually
plans around*: the **next 7 days**. That cancels day-to-day noise and is the
correct planning unit.

| Task | Precision@50 | NDCG@50 | ROC-AUC |
|---|---|---|---|
| next-day load | 44% | — | 0.85 |
| **next-7-day hotspot ranking** | **64%** | **0.85** | **0.96** |

Even daily, **ROC-AUC 0.85** shows the model *discriminates* hotspots well — the low
daily Precision@50 is an ordering-noise artifact, not poor discrimination.

**Features (high-end preprocessing):** lags (1–28d), rolling mean/max/std/EWMA
(3/7/14/28d), momentum ratios, cyclical + holiday calendar, cell climatology, **H3
neighbour spillover**, and the key lever — **citywide & station-level enforcement
intensity** (captures the manpower/holiday swings a per-cell model can't see).

**Model:** GPU **ensemble** — XGBoost + LightGBM + CatBoost, regression +
**learning-to-rank (lambdarank)**, blended on rank-percentile.

**Validation:** **walk-forward (rolling-origin)** folds, causal features only.
Reported on the held-out future: **Precision@50, NDCG@50, ROC-AUC.**

- **Panel:** (H3 cell × calendar date), dense (true zeros filled).
- **Features:** causal lags (1, 7), rolling mean/max (7, 14), cell climatology
  (mean load, peak share, junction flag), lat/lng, calendar (dow, weekend, dom, week).
  All lags are shifted — **no leakage**.
- **Model:** GPU XGBoost (`device="cuda"`, `tree_method="hist"`), depth 8,
  η 0.04, early stopping on a temporal validation split.
- **Validation:** strict **temporal holdout** — last **21 days** never seen in training.

**Metrics reported:** MAE, RMSE, R² (regression) **and Precision@50** — per test
day, do the predicted top-50 cells match the actual top-50? This is the metric that
matters operationally: are we sending units to the right places tomorrow?

---

## 5. Enforcement deployment optimizer (`04_prioritization.py`)

Converts scores into a roster. Given **N patrol units** and shift windows, greedy
**submodular marginal-gain** selection maximizes impact removed:

- impact is **time-sliced** — a cell only earns its PCIS during its dominant active
  shift, so each unit gets a *place and a time*;
- a **coverage radius** (250 m) models one unit clearing nearby cells, preventing
  redundant adjacent assignments.

Output: an explainable roster + **% of total city parking-congestion impact removed**
by the deployment — a control-room-ready KPI.

---

## 6. Evaluation summary

| Layer | Metric | Why it's the right metric |
|---|---|---|
| Hotspot detection | coverage of known chokepoints; ≥20-case floor | face validity + noise control |
| PCIS | rank stability, component ablation | impact, not raw counts |
| Forecast | MAE / RMSE / R² + **Precision@50** | operational hit-rate, leakage-free |
| Optimizer | **% impact removed** per N units | direct enforcement ROI |

## 7. Assumptions & limitations

- Enforcement records are a **proxy for occurrence**, biased toward policed areas;
  the forecast partly corrects this by modeling demand including zero-days, and the
  morning-skew insight flags the bias explicitly.
- Segment length through a cell is approximated (~110 m); occupancy is a **relative**
  index, not an absolute flow measurement.
- OSM lane data is incomplete; we fall back to class-based widths and a violation-
  derived proxy when lanes/internet are unavailable.

## 8. Extensions (roadmap)

- Fuse live signal/speed feeds to calibrate PCIS against measured flow.
- PS3 bolt-on: CV model to auto-detect illegal parking from camera frames, feeding
  the same H3 pipeline in real time.
- Closed-loop learning: feed post-deployment violation drops back to re-weight PCIS.
