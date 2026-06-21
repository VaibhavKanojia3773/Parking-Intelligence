# Kaggle GPU Pipeline — Parking Intelligence

Heavy compute runs here (GPU). Each script writes artifacts to `/kaggle/working/`
that the local dashboard consumes (copy them into `frontend/public/data/`).

## Run order

| # | Script | Runtime | Needs | Produces |
|---|--------|---------|-------|----------|
| 1 | `01_data_engine.py` | CPU | raw CSV + `pip install h3` | `events.parquet`, `cells_h3.parquet` |
| 2 | `02_impact_pcis_osm.py` | CPU + **internet** | `events.parquet` + `pip install osmnx scikit-learn` | `pcis.json` |
| 3 | `03_forecast_ensemble_gpu.py` | **GPU** | `events.parquet` + `pip install lightgbm catboost` | `forecast_metrics.json`, `forecast.json` |
| 4 | `04_prioritization.py` | CPU | `pcis.json`, `events.parquet` | `deployment_plan.json` |

## Setup
1. Upload the dataset CSV as a Kaggle Dataset; set `RAW` at the top of `01_data_engine.py`.
2. Notebook settings → **Accelerator: GPU**, **Internet: On**.
3. First cell:
   ```python
   !pip install -q h3 osmnx scikit-learn xgboost lightgbm catboost
   ```
4. Run `01 → 02 → 03 → 04`.
5. Download the four JSON artifacts and drop them in `frontend/public/data/`
   (the dashboard auto-detects `pcis.json`, `forecast.json`, `deployment_plan.json`).

## Notes
- `03` is a GPU **ensemble** (XGBoost + LightGBM + CatBoost, regression + lambdarank) on the **next-7-day** horizon; reports Precision@50, NDCG@50, ROC-AUC via walk-forward. Any missing model lib is skipped gracefully.
- `02` degrades gracefully to a violation-derived road proxy if OSM/internet is off.
- All scripts are deterministic and self-contained; no cross-cell global state.
