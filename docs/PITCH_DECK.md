# Parking Intelligence — Pitch Deck

Slide-by-slide content. Each slide has a **headline**, on-slide **bullets** (keep them
short on the actual slide), **speaker notes** (what you say), and a **visual** cue.
Live demo: https://parking-intelligence.vercel.app/ ·
Repo: https://github.com/VaibhavKanojia3773/Parking-Intelligence

---

## Slide 1 — Title

**Parking Intelligence**
*Detecting illegal-parking hotspots, scoring their impact on traffic flow, and turning both into targeted enforcement.*

- Problem Statement 1 — Poor Visibility on Parking-Induced Congestion
- Bengaluru · 298,450 enforcement records · Nov 2023 – Apr 2024
- Live demo + GitHub link

**Visual:** the 3D hero shot (`docs/img/hero.png`).
**Notes:** "On-street illegal parking chokes Bengaluru's carriageways and junctions.
We built a system that finds where, measures how badly, and tells enforcement exactly
where to go — using only the dataset provided."

---

## Slide 2 — The problem

**Enforcement is blind and reactive.**

- Illegal & spillover parking near markets, metro stations and events blocks live lanes and intersections
- Enforcement today is **patrol-based and reactive** — officers go where they always go
- **No view** of violations vs. their actual congestion impact
- Hard to **prioritize** which zones to enforce, with limited staff

**Visual:** a congested street photo / simple "patrol guesswork" diagram.
**Notes:** "The core gap is visibility. Without knowing where impact is highest, limited
enforcement staff are spread by habit, not by need."

---

## Slide 3 — What the data gives us

**298,450 anonymized parking-violation records.**

- Geolocation, timestamp, violation type, vehicle class, police station, junction, enforcing device
- 5 months, 54 stations, city-wide coverage
- **No traffic-flow field** — impact has to be *derived*, not read off

**Visual:** a few sample rows (anonymized) + a coverage heatmap thumbnail.
**Notes:** "It's rich, but it's enforcement data — it tells us where tickets were
written, not directly how traffic flows. Two consequences shape our whole approach:
we must *model* impact, and we must *correct* for patrol bias."

---

## Slide 4 — Our approach maps 1:1 to the problem

**Detect → Quantify impact → Enable enforcement.**

- **Detect** illegal-parking hotspots — and correct for patrol bias
- **Quantify** each hotspot's impact on traffic flow — a validated score
- **Enable** targeted enforcement — an operational, station-level plan
- *(Extension)* forecast next week's hotspots

**Visual:** three-column pipeline graphic (Detect | Quantify | Enable).
**Notes:** "Everything we built sits on one of these three verbs from the problem
statement. Nothing is decoration."

---

## Slide 5 — Detect, corrected for patrol bias

**Not 'where we ticket' — 'where parking is actually dense'.**

- Violations indexed to H3 hexagons → 1,391 hotspot cells
- Rank by **yield per patrol visit** (violations caught per session), not raw counts
- Surfaces **234 under-enforced** spots — busy, but rarely policed
- Per-visit yield is **stable across held-out halves (ρ 0.61)** → reflects real demand, not patrol luck

**Visual:** `docs/img/detect.png` (bias-corrected view + under-enforced list).
**Notes:** "Raw counts just rediscover the patrol routes. By normalizing per visit, we
find the blind spots — and we tested that this signal is stable, not noise."

---

## Slide 6 — Quantify: the Parking Congestion Impact Score

**A scooter on a 6-lane arterial ≠ a car double-parked by a junction.**

- PCIS = carriageway occupancy × road criticality × junction proximity × peak timing × chronicity
- Derived entirely from the given data (OSM road geometry is an optional enhancer)
- **Validated** on held-out data — predicts future flow-impact at **ρ 0.65**, beating a raw-count baseline (0.58)
- Top-10% PCIS cells carry **3.3× the future burden** of an average cell
- Weights stress-tested: ranking holds at **ρ 0.998** under ±25% perturbation

**Visual:** `docs/img/impact.png` (validation bars + ablation).
**Notes:** "This is the hard part of the problem — quantifying impact with no flow
column. We model it as carriageway stolen, weighted by where and when it hurts, and
then we *prove* it predicts real future congestion on data it never saw."

---

## Slide 7 — Impact in a number people feel

**~146 lane-metres of carriageway blocked at peak.**

- Footprint translated to road space, with transparent assumptions (dwell 0.75 h, lane 3.5 m, peak 4 h)
- ≈ **1.6 lane-km·hours** of road-time lost per day
- Impact also aggregated to **45 whole carriageways** — enforce a corridor, not a dot

**Visual:** the lane-metres hero card + top-carriageways list (`docs/img/corridors.png`).
**Notes:** "Scores are abstract, so we convert to road space. It reframes parking from
'a ticket' to 'this much carriageway, gone, every peak hour'."

---

## Slide 8 — Enable: roll-call work orders

**The map becomes what a constable does at 9 a.m.**

- Coverage optimizer → **668 work orders** across 54 stations
- Each order: location · target violation + vehicle · time window · lane-metre impact · **revisit cadence**
- Revisit cadence is **derived from the data** (observed recurrence interval), not guessed
- One-click **CSV briefing** per station

**Visual:** `docs/img/work-orders.png` (a station expanded into shift cards).
**Notes:** "This is the difference between a dashboard and a tool. It drops into the
existing station-and-shift workflow with zero change to how they operate."

---

## Slide 9 — Forecast (proactive extension)

**Position units before congestion forms.**

- Gradient-boosted ensemble ranks each cell's parking load over the **next 7 days**
- Walk-forward validated: **ROC-AUC 0.96 · Precision@50 64% · NDCG@50 0.85**
- Honest framing: single-day prediction is noisy (~45%); the *weekly* horizon is what enforcement actually staffs around

**Visual:** `docs/img/forecast.png`.
**Notes:** "We're upfront that you can't reliably predict one exact day from this data —
so we forecast the planning horizon that matters, the week, where the signal is strong."

---

## Slide 10 — The product: a 3D command center

**Built to be used, not just shown.**

- deck.gl + MapLibre WebGL — extruded 3D impact hexagons & PCIS columns over a dark map
- **Adaptive rendering**: clean heatmap zoomed out, 3D detail on zoom-in
- 24-hour time-lapse · hover inspection · cinematic fly-to · guided **story mode**
- Dedicated views: detection, impact, carriageways, work orders, forecast

**Visual:** short screen-capture GIF or the hero shot; mention the live link.
**Notes:** "Everything we just described is one interactive surface. Let me show you live."
*(Switch to demo here.)*

---

## Slide 11 — How it's built

**Light where it can be, heavy where it must be.**

- `pipeline/` — pandas analytics generate all dashboard artifacts locally (no GPU)
- `kaggle/` — GPU scripts (H3, OSM-PCIS, **XGBoost + LightGBM + CatBoost** ensemble, optimizer) for full-scale reproduction
- `frontend/` — React + TypeScript + deck.gl, deployed on Vercel
- Runs end-to-end on the provided dataset; artifacts are versioned so the demo works anywhere

**Visual:** the architecture diagram from the README.
**Notes:** "Clean separation — the heavy ML lives in reproducible GPU notebooks; the app
reads pre-built artifacts, so it loads instantly."

---

## Slide 12 — Rigor & honesty

**We validated what we claim — and named what we can't.**

- PCIS impact: held-out predictive validity (ρ 0.65) + weight-robustness (ρ 0.998)
- Detection: per-visit-yield stability (ρ 0.61), with a ≥2-visit floor to remove noise
- Enforcement bias **audited** (39% morning vs 0.2% evening) and corrected
- Stated limitation: enforcement data alone can't *prove* latent demand — so we use a confound-free metric and say so

**Visual:** a compact "claim → test → result" table.
**Notes:** "We deliberately tested our own methods, including one that failed first and
made us fix it. The honesty is part of the credibility."

---

## Slide 13 — Why it matters

**From habit-based patrols to impact-based enforcement.**

- Enforce by **measured impact**, not by routine → more congestion relief per officer-hour
- Find the **blind spots** routine patrols miss (234 under-enforced)
- Clear **corridors**, not points; revisit at the **right cadence**
- A control-room-ready plan today; a foundation for live operation tomorrow

**Visual:** before/after framing (patrol guesswork → targeted plan).
**Notes:** "Same staff, redirected by data. That's the operational win the problem
statement is asking for."

---

## Slide 14 — Roadmap

**Clear path from prototype to deployment.**

- **Now:** validated analytics + operational work orders, on the provided data
- **Next:** officer check-in app to close the loop and capture outcomes
- **Then:** controlled pilot with an independent flow signal (road speed) → measured impact
- **Later:** live ingestion; CV-based automatic detection feeding the same pipeline

**Visual:** a 4-step timeline.
**Notes:** "We're honest that proving real-world congestion reduction needs a pilot with
an outcome signal — and we've designed exactly how that would work."

---

## Slide 15 — Close

**Parking Intelligence**

- Detect (bias-corrected) · Quantify (validated PCIS) · Enable (work orders) · Forecast
- Live demo: **parking-intelligence.vercel.app**
- Code: **github.com/VaibhavKanojia3773/Parking-Intelligence**
- Built on the provided dataset, end to end.

**Visual:** hero shot + QR codes to demo and repo.
**Notes:** "Thank you — happy to take questions or walk through any view live."

---

### Appendix slides (optional, for Q&A)
- **A1 — PCIS formula & weights** (with ablation contributions)
- **A2 — Validation protocol** (temporal split, walk-forward, perturbation)
- **A3 — Forecast features** (lags, rolling stats, neighbour H3, city/station intensity, calendar)
- **A4 — Bias-correction math** (yield per session, why future-count validation is circular)
- **A5 — Assumptions & limitations** (dwell, lane width, 5-month window, enforcement bias)
