# Submission — ready-to-paste content

## Title
Parking Intelligence — AI Hotspot Detection, Congestion-Impact Scoring & Targeted Enforcement (Bengaluru)

## Theme
Poor Visibility on Parking-Induced Congestion

## Description
**Parking Intelligence** turns **298,450 real Bengaluru police parking-violation
records** into a decision system that answers the three questions patrol-based
enforcement cannot: **where** illegal parking concentrates, **how much** it chokes
traffic, and **where to send enforcement next** — mapped 1:1 to the problem
statement (*detect hotspots → quantify impact on traffic flow → enable targeted
enforcement*).

**🔍 Detect** — H3 hotspot detection, validated as *persistent* (held-out Spearman
ρ 0.65), and **bias-corrected** for patrol skew using per-visit yield (stable at
ρ 0.61) — surfacing **234 under-enforced** hotspots that are hot but rarely policed.

**📊 Quantify impact on flow** — the **Parking Congestion Impact Score (PCIS)**:
carriageway occupancy × road criticality × junction proximity × peak timing ×
chronicity. It *beats raw violation counts* at predicting held-out flow-impact,
its weights are stress-tested (ρ 0.998 under ±25% perturbation), and it's
translated to a felt unit — **≈146 lane-metres of carriageway blocked at peak**.
Impact is also aggregated to whole **carriageways**, not just points.

**🚓 Enable targeted enforcement** — a deployment optimizer plus **668 roll-call
work orders** (per police-station × shift: location, target violation + vehicle,
time window, and a data-driven revisit cadence), **exportable to CSV**. A proactive
**next-7-day hotspot forecast** (ROC-AUC 0.96) moves enforcement from reactive to
pre-emptive.

All wrapped in an interactive **3D command center** (deck.gl + MapLibre) with
extruded impact hexes, a 24-hour time-lapse, choked-carriageway ranking, and a
guided story mode for judging.

Heavy ML trains on Kaggle GPU (XGBoost + LightGBM + CatBoost ensemble); the
dashboard runs locally on pre-built artifacts derived from the given dataset only.

**Stack:** React · deck.gl · MapLibre · Python (pandas, scikit-learn, XGBoost).

## Instructions to Run
```bash
# 1) Run the dashboard (data artifacts are committed — no dataset needed)
cd frontend
npm install
npm run dev            # opens http://localhost:5173
#   Tip: append ?story=1 for the guided demo walkthrough.

# 2) (Optional) Rebuild artifacts from the raw dataset
#    Place the two provided CSVs in the repo root, then:
pip install pandas numpy scikit-learn xgboost
python pipeline/build_artifacts.py     # detection / PCIS / corridors / work orders / validation
python pipeline/build_forecast.py      # next-7-day forecast artifacts

# 3) (Optional) Heavy GPU training on Kaggle — see kaggle/README.md
```
Live demo: <DEPLOYED_URL>  ·  Repo: <GITHUB_URL>  ·  Demo video: <VIDEO_URL>
