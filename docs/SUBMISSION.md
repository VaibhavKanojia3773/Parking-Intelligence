# Submission — ready-to-paste content

## Title
Parking Intelligence — AI Hotspot Detection, Congestion-Impact Scoring & Targeted Enforcement (Bengaluru)

## Theme
Poor Visibility on Parking-Induced Congestion

## Description
(plain text — paste directly, no markdown)

Bengaluru's traffic police write thousands of parking tickets every month, and most of that data just sits in a spreadsheet. We turned 298,450 of those records into a system that tells enforcement exactly where to go, why it matters, and what to do when they get there.

The problem statement asks for three things. We deliver all three, and we prove the hard one.

Find the real hotspots. Raw ticket counts only show you where police already patrol. We rank instead by how many violations each patrol visit actually catches, which exposes 234 hotspots that are packed with illegal parking but barely policed. And we checked it holds up: high-yield locations stay high-yield on data the model never saw (held-out correlation 0.61).

Quantify the damage to traffic flow. The dataset has no flow column, so we built one. The Parking Congestion Impact Score weighs how much carriageway a vehicle steals, on what class of road, how close to a junction, and at what hour. Then we validated it. Trained on the first half of the data, it predicts the worst congestion in the held-out second half at a correlation of 0.65, beating a plain ticket-count baseline. The top 10% of locations carry 3.3x the future load. In plain terms, that's roughly 146 lane-metres of road blocked at every peak.

Make it actionable. The system doesn't stop at a map. It generates 668 ready-to-run work orders across all 54 stations: where to stand, which vehicles to target, what time window, and how often to come back (the revisit interval is read straight from the data). One click exports a station's shift briefing as a CSV, so it slots into how the police already operate.

On top of that there's a next-week hotspot forecast (ROC-AUC 0.96) so units can move before congestion forms, and a 3D command center built with deck.gl that you can actually fly through. It's deployed and live.

Every number above comes from the dataset we were given. No external feeds, no live APIs, no hand-waving. We also state our assumptions openly, including the things enforcement data alone cannot prove.

Live demo: https://parking-intelligence.vercel.app/
Stack: React, TypeScript, deck.gl, MapLibre, Python (pandas, scikit-learn, XGBoost, LightGBM, CatBoost).

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
Live demo: https://parking-intelligence.vercel.app/
Repo: https://github.com/VaibhavKanojia3773/Parking-Intelligence
Demo video: <VIDEO_URL>

## Demo recording — silent screen capture (~75–90s)
No voiceover. Just record the screen clicking through this order. Optional: add a
short text caption (bottom of screen) per shot so it still reads on its own. Record
fullscreen at 1080p; move slowly and pause ~2s on each view.

1. **Open the app** (hero 3D map loads) — caption: *"298,450 parking violations → live impact map"* (~8s)
2. **Hit Story Mode** and let one or two chapters auto-play (camera flies, panels change) (~12s)
3. **Detect → Bias-corrected** — scroll the under-enforced list — caption: *"234 hotspots that are busy but rarely policed"* (~10s)
4. **Impact tab** — show the lane-metres card + the PCIS validation bars — caption: *"Impact score, validated ρ 0.65"* (~12s)
5. **Impact → Carriageways** — top choked roads (~8s)
6. **Target → Work Orders** — expand a station, show the shift cards, click the CSV download — caption: *"668 ready-to-run work orders"* (~14s)
7. **Forecast tab** — the next-7-day list + AUC 0.96 metric (~8s)
8. **Zoom into the map** so the 3D columns rise, slow orbit, end on the hero (~8s)

End screen (optional still frame): project name + parking-intelligence.vercel.app + repo URL.
