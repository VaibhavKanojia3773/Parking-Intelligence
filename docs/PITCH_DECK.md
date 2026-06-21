# Parking Intelligence — Pitch Deck (5 slides)

Live: https://parking-intelligence.vercel.app/ ·
Code: https://github.com/VaibhavKanojia3773/Parking-Intelligence
Bold the numbers on the actual slides. `[PHOTO]` = drop your own image there.

---

## Slide 1 — Title / Hook   *(keep as-is)*

# Parking Intelligence
### From 298,450 raw parking tickets to a deployable enforcement plan.

`PS1 — Poor Visibility on Parking-Induced Congestion`

**Banner stats:** 298K records · 1,391 hotspots · PCIS validated 0.65 · forecast AUC 0.96 · 668 work orders · live on Vercel

`[PHOTO: hero 3D map]`
*Hook line: "We find where illegal parking is worst, prove how much it chokes traffic, and hand enforcement a ready-to-run plan — all from the dataset given."*

---

## Slide 2 — The problem, and why it's hard

### Enforcement runs on habit, not impact.

**The gap (from the problem statement)**
- Illegal & spillover parking chokes carriageways and junctions near markets, metros, events
- Enforcement is **patrol-based and reactive** — officers go where they always go
- No view of violations vs. their **actual congestion impact**; hard to prioritize with limited staff

**The two catches in the data — which we solve**
- It has **no traffic-flow column** → impact has to be *engineered*
- It's **patrol-biased** → raw ticket counts just re-draw the patrol routes

**Our answer — one pipeline, mapped 1:1 to the PS**
> **Detect** (bias-corrected) → **Quantify** (validated score) → **Enable** (work orders) → *+ Forecast*

`298,450 records · 54 stations · Nov 2023 – Apr 2024`
`[PHOTO: congested junction OR a "patrol guesswork vs targeted" graphic]`

---

## Slide 3 — Quantify the impact (our core innovation)

### We built the traffic-flow signal the data was missing — and validated it.

**Parking Congestion Impact Score (PCIS)**
`carriageway occupancy × road criticality × junction proximity × peak timing × chronicity`

**Proven on held-out data (trained on first half, tested on second)**
- Predicts the worst future congestion at **correlation 0.65** — beats a raw ticket-count baseline (0.58)
- Top-10% locations carry **3.3× the future load** of an average spot
- Weights are robust: ranking holds at **0.998** under ±25% perturbation

**Made tangible**
- ≈ **146 lane-metres** of carriageway blocked at every peak (~**1.6 lane-km·hours/day** of road-time lost)
- Rolled up to **45 most-choked carriageways** — clear a corridor, not a dot

`[PHOTO: Impact tab — validation bars + lane-metres card]`

---

## Slide 4 — What it actually does (operational output)

### From a heatmap to a 9 a.m. roll-call briefing.

**Detect — corrected for patrol bias**
- Ranks by **yield per patrol visit**, not raw counts → surfaces **234 under-enforced** hotspots (busy, but rarely policed)
- That yield is **stable across held-out halves (0.61)** → real demand, not patrol luck

**Enable — the deliverable enforcement can use today**
- **668 ready-to-run work orders** across **54 stations**
- Each order: **location · target violation + vehicle · time window · lane-metres of impact · revisit cadence** (read straight from the data)
- **One-click CSV briefing** per station — slots into the existing shift workflow, zero change

`[PHOTO: Work Orders view (station expanded) + Bias-corrected list]`

---

## Slide 5 — Proactive, interactive, live

### A forecast, a 3D command center, and a real deployment.

**Forecast — move before congestion forms**
- Next-7-day hotspot ranking, ensemble of **XGBoost + LightGBM + CatBoost**
- Walk-forward validated: **ROC-AUC 0.96 · Precision@50 64% · NDCG@50 0.85**

**3D command center — built to be used**
- deck.gl + MapLibre: extruded 3D impact hexagons, 24-hour time-lapse, adaptive zoom, guided story mode
- **Deployed and live** — not a mockup

**Why it stands out**
- **Impact:** same officers, redirected by measured impact
- **Feasibility:** runs end-to-end on the given data, exportable to CSV, already deployed
- **Honesty:** every assumption stated — including what enforcement data alone can't prove

`Live: parking-intelligence.vercel.app · Code: github.com/VaibhavKanojia3773/Parking-Intelligence`
`[PHOTO: forecast view OR hero shot + QR codes]`
