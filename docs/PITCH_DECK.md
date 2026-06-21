# Parking Intelligence — Pitch Deck (7 slides)

Live: https://parking-intelligence.vercel.app/ ·
Code: https://github.com/VaibhavKanojia3773/Parking-Intelligence
Keep slide text short and bold. Notes are optional talking points.

---

## Slide 1 — Title / Hook

# Parking Intelligence
### From 298,450 raw parking tickets to a deployable enforcement plan.

`PS1 — Poor Visibility on Parking-Induced Congestion`

**Banner stats:** 298K records · 1,391 hotspots · PCIS validated ρ 0.65 · forecast AUC 0.96 · 668 work orders · live on Vercel

**Visual:** `docs/img/hero.png` (3D command center).
**Note:** "We find where illegal parking is worst, prove how much it chokes traffic, and hand enforcement a ready-to-run plan — all from the dataset given."

---

## Slide 2 — The problem (and the twist)

## Enforcement runs on habit, not impact.

- Patrols go where they always go — **reactive, blind to actual congestion**
- The data has **no traffic-flow column** → impact must be *engineered*
- The data is **patrol-biased** → raw counts just rediscover the patrol routes

**That's exactly the two hard problems we solve.**

**Visual:** congested junction photo + a "tickets ≠ impact" arrow.
**Note:** "Most teams will map ticket counts. That's a map of where police already are. The real problem is hidden underneath it."

---

## Slide 3 — The system: Detect → Quantify → Enable

## A full pipeline, mapped 1:1 to the problem statement.

| | What we do | Flex |
|---|---|---|
| **Detect** | Bias-corrected hotspots | **234 under-enforced** spots exposed |
| **Quantify** | Parking Congestion Impact Score | **validated** ρ 0.65, beats raw counts |
| **Enable** | Roll-call work orders | **668** tasks, 54 stations, CSV-ready |
| *+ Forecast* | Next-7-day hotspots | **ROC-AUC 0.96** |

**Visual:** three-column Detect/Quantify/Enable graphic.
**Note:** "Not a dashboard you stare at — an end-to-end system that outputs what a constable does at 9am."

---

## Slide 4 — The innovation: PCIS (validated)

## We built the traffic-flow signal the data was missing.

**PCIS** = carriageway occupancy × road criticality × junction proximity × peak timing × chronicity

- Trained on first half, tested on held-out second half → predicts real future congestion at **ρ 0.65** (beats raw-count baseline 0.58)
- Top-10% locations carry **3.3× the future burden**
- Weights stress-tested: ranking holds at **ρ 0.998** under ±25% shake
- Translated to plain English: **~146 lane-metres of road blocked at every peak**

**Visual:** `docs/img/impact.png`.
**Note:** "This is the hard sentence in the PS — quantify impact on flow with no flow data. We engineered it and then proved it on data it never saw."

---

## Slide 5 — From map to roll-call (the operational flex)

## It tells you where to stand, when, and what to target.

- **234 under-enforced** hotspots — busy but barely policed (per-visit yield, stable ρ 0.61)
- **45 choked carriageways** ranked — clear a corridor, not a dot
- **668 work orders**: location · violation + vehicle · time window · lane-metres · **revisit cadence from the data**
- One-click **CSV briefing** per station — drops into the existing shift workflow, zero change

**Visual:** `docs/img/work-orders.png` + `docs/img/detect.png`.
**Note:** "Feasibility isn't a slide for us — the output is already in the format a control room uses."

---

## Slide 6 — The product + the forecast

## A 3D command center you can fly through.

- **deck.gl + MapLibre** — extruded 3D impact hexagons & PCIS columns over a dark map
- Adaptive zoom, 24-hour time-lapse, hover, cinematic fly-to, guided **story mode**
- **Next-7-day forecast** (XGBoost + LightGBM + CatBoost ensemble): **AUC 0.96 · P@50 64% · NDCG 0.85**
- **Live now:** parking-intelligence.vercel.app *(switch to demo)*

**Visual:** live demo / `docs/img/forecast.png`.
**Note:** "Everything we described is one interactive surface, deployed and reproducible."

---

## Slide 7 — Why it stands out / Close

## Impact-based enforcement, validated and live.

- **Impact:** same officers, redirected by measured impact — more relief per patrol-hour
- **Innovation:** an engineered, *validated* congestion-impact score + bias correction
- **Feasibility:** runs end-to-end on the given data, deployed, exportable to CSV
- **Honesty:** we state every assumption and even what the data *can't* prove

**Live:** parking-intelligence.vercel.app · **Code:** github.com/VaibhavKanojia3773/Parking-Intelligence

**Visual:** hero shot + QR codes.
**Note:** "Built entirely on the provided dataset. Happy to walk any view live."
