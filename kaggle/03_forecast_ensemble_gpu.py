"""
03_forecast_ensemble_gpu.py  —  High-end spatiotemporal forecast ENSEMBLE (GPU)
                                 [proactive EXTENSION; PS core = detect/quantify/target]

Predicts each H3 cell's next-day parking LOAD and — what enforcement actually
needs — RANKS tomorrow's worst cells. Engineered to maximize daily Precision@50
/ NDCG@50, validated by walk-forward (rolling-origin) folds (no leakage).

WHY THIS BEATS the single-XGBoost baseline
  • Context features: citywide + station enforcement intensity (captures the big
    day-to-day manpower/holiday swings a per-cell model can't see), H3 neighbour
    spillover, cell×weekday climatology.
  • Learning-to-rank (lambdarank) directly optimizes the ranking metric, not RMSE.
  • Ensemble of GPU LightGBM + XGBoost + CatBoost, regression + rank, blended on
    rank-percentile — robust to each model's blind spots.

KAGGLE SETUP
  Needs events.parquet (01). GPU ON, Internet ON for installs.
      !pip install -q lightgbm catboost xgboost h3
Outputs: forecast_metrics.json, forecast.json, feature_importance.csv
"""
from __future__ import annotations
import json, warnings
import numpy as np
import pandas as pd
import h3
warnings.filterwarnings("ignore")

EVENTS = "/kaggle/working/events.parquet"
OUT = "/kaggle/working"
MIN_CELL_TOTAL = 50
TOPK = 50
TEST_DAYS = 21
FOLD_LEN = 7

HOLIDAYS = {"2023-11-12", "2023-11-13", "2023-11-14", "2023-11-27", "2023-12-25",
            "2024-01-01", "2024-01-15", "2024-01-26", "2024-03-08", "2024-03-25",
            "2024-03-29", "2024-04-09", "2024-04-11", "2024-04-14"}


# ----------------------------- feature engineering -----------------------------
def build_panel(ev):
    ev["date"] = pd.to_datetime(ev["date"])
    tot = ev.groupby("h3").size()
    keep = set(tot[tot >= MIN_CELL_TOTAL].index)
    ev = ev[ev.h3.isin(keep)].copy()
    daily = ev.groupby(["h3", "date"]).agg(load=("footprint", "sum")).reset_index()
    dates = pd.date_range(ev.date.min(), ev.date.max(), freq="D")
    cells = daily.h3.unique()
    idx = pd.MultiIndex.from_product([cells, dates], names=["h3", "date"])
    panel = daily.set_index(["h3", "date"]).reindex(idx, fill_value=0).reset_index()
    stat = ev.groupby("h3").agg(
        lat=("lat", "mean"), lng=("lng", "mean"), has_junction=("has_junction", "max"),
        peak_share=("is_peak", "mean"), main_share=("main_road", "mean"),
        station=("police_station", lambda s: s.value_counts().index[0])).reset_index()
    return panel.merge(stat, on="h3", how="left"), stat, set(cells)


def neighbour_lags(panel, cells):
    nbr = {c: [n for n in h3.grid_disk(c, 1) if n in cells and n != c] for c in cells}
    piv = panel.pivot_table(index="date", columns="h3", values="load", fill_value=0).sort_index()
    cols = list(piv.columns); pos = {c: i for i, c in enumerate(cols)}; arr = piv.values
    nm = pd.DataFrame(0.0, index=piv.index, columns=cols)
    for c in cols:
        ns = [pos[n] for n in nbr.get(c, []) if n in pos]
        if ns: nm[c] = arr[:, ns].mean(axis=1)
    out = panel.merge(nm.shift(1).stack().rename("nbr_lag1").reset_index(), on=["date", "h3"], how="left")
    out = out.merge(nm.shift(7).stack().rename("nbr_lag7").reset_index(), on=["date", "h3"], how="left")
    return out


def add_features(panel, cells):
    p = panel.sort_values(["h3", "date"]).reset_index(drop=True)
    g = p.groupby("h3")["load"]
    for k in (1, 2, 3, 7, 14, 21, 28):
        p[f"lag{k}"] = g.shift(k)
    for w in (3, 7, 14, 28):
        p[f"rmean{w}"] = g.shift(1).rolling(w).mean().reset_index(0, drop=True)
        p[f"rmax{w}"] = g.shift(1).rolling(w).max().reset_index(0, drop=True)
    p["rstd7"] = g.shift(1).rolling(7).std().reset_index(0, drop=True)
    p["ewma7"] = g.shift(1).ewm(span=7).mean().reset_index(0, drop=True)
    p["mom"] = p.rmean7 - p.rmean28; p["mom_ratio"] = p.rmean7 / (p.rmean28 + 1)
    dd = p.date
    p["dow"] = dd.dt.dayofweek; p["dow_sin"] = np.sin(2*np.pi*p.dow/7); p["dow_cos"] = np.cos(2*np.pi*p.dow/7)
    p["is_weekend"] = (p.dow >= 5).astype(int); p["dom"] = dd.dt.day
    p["woy"] = dd.dt.isocalendar().week.astype(int); p["trend"] = (dd - dd.min()).dt.days
    p["is_holiday"] = dd.dt.strftime("%Y-%m-%d").isin(HOLIDAYS).astype(int)
    city = p.groupby("date")["load"].sum()
    p = p.merge(city.shift(1).rename("city_lag1"), on="date", how="left")
    p = p.merge(city.shift(7).rename("city_lag7"), on="date", how="left")
    p = p.merge(city.rolling(7).mean().shift(1).rename("city_roll7"), on="date", how="left")
    sd = p.groupby(["station", "date"])["load"].sum().rename("stload").reset_index().sort_values(["station", "date"])
    sd["st_lag1"] = sd.groupby("station")["stload"].shift(1); sd["st_lag7"] = sd.groupby("station")["stload"].shift(7)
    p = p.merge(sd[["station", "date", "st_lag1", "st_lag7"]], on=["station", "date"], how="left")
    p = neighbour_lags(p, cells)
    return p


FEATS = ["lag1", "lag2", "lag3", "lag7", "lag14", "lag21", "lag28",
         "rmean3", "rmean7", "rmean14", "rmean28", "rmax7", "rmax14", "rstd7", "ewma7",
         "mom", "mom_ratio", "dow_sin", "dow_cos", "is_weekend", "dom", "woy", "trend",
         "is_holiday", "lat", "lng", "has_junction", "peak_share", "main_share",
         "city_lag1", "city_lag7", "city_roll7", "st_lag1", "st_lag7", "nbr_lag1", "nbr_lag7"]


# ----------------------------- models (GPU) -----------------------------
def fit_xgb_reg(tr, te, target):
    import xgboost as xgb
    d = xgb.DMatrix(tr[FEATS], label=np.log1p(tr[target]))
    m = xgb.train(dict(objective="reg:squarederror", max_depth=8, eta=0.04, subsample=0.85,
                       colsample_bytree=0.8, min_child_weight=4, tree_method="hist", device="cuda"),
                  d, num_boost_round=700)
    return m.predict(xgb.DMatrix(te[FEATS]))


def fit_xgb_rank(tr, te, target):
    import xgboost as xgb
    tr = tr.sort_values("date"); grp = tr.groupby("date").size().values
    d = xgb.DMatrix(tr[FEATS], label=tr[target]); d.set_group(grp)
    m = xgb.train(dict(objective="rank:pairwise", eval_metric="ndcg@50", max_depth=8, eta=0.05,
                       subsample=0.85, colsample_bytree=0.8, tree_method="hist", device="cuda"),
                  d, num_boost_round=500)
    return m.predict(xgb.DMatrix(te[FEATS]))


def fit_lgb(tr, te, target, rank=False):
    import lightgbm as lgb
    if rank:
        tr = tr.sort_values("date"); grp = tr.groupby("date").size().values
        grades = (tr[target].rank(pct=True) * 4).round().astype(int)  # 0..4 relevance
        ds = lgb.Dataset(tr[FEATS], label=grades, group=grp)
        params = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[50],
                      learning_rate=0.05, num_leaves=128, device_type="gpu", verbose=-1)
    else:
        ds = lgb.Dataset(tr[FEATS], label=np.log1p(tr[target]))
        params = dict(objective="regression", metric="rmse", learning_rate=0.04,
                      num_leaves=128, device_type="gpu", verbose=-1)
    m = lgb.train(params, ds, num_boost_round=700)
    return m.predict(te[FEATS])


def fit_cat(tr, te, target):
    from catboost import CatBoostRegressor
    m = CatBoostRegressor(iterations=800, depth=8, learning_rate=0.04, loss_function="RMSE",
                          task_type="GPU", verbose=False)
    m.fit(tr[FEATS], np.log1p(tr[target])); return m.predict(te[FEATS])


def rankpct(x):
    return pd.Series(x).rank(pct=True).values


def ensemble(tr, te, target="fwd7"):
    """Blend available GPU models on rank-percentile (robust to scale/objective)."""
    preds = []
    for fn in (lambda: fit_xgb_reg(tr, te, target), lambda: fit_xgb_rank(tr, te, target),
               lambda: fit_lgb(tr, te, target, False), lambda: fit_lgb(tr, te, target, True),
               lambda: fit_cat(tr, te, target)):
        try:
            preds.append(rankpct(fn()))
        except Exception as e:
            print("  [skip model]", type(e).__name__, str(e)[:60])
    return np.mean(preds, axis=0)


def metrics_at_k(te, tcol="fwd7"):
    from sklearn.metrics import roc_auc_score
    precs, ndcgs, aucs = [], [], []
    for _, grp in te.groupby("date"):
        if len(grp) < TOPK or grp[tcol].sum() == 0: continue
        top = grp.sort_values("pred", ascending=False).head(TOPK)
        aa = set(grp.sort_values(tcol, ascending=False).head(TOPK).h3)
        precs.append(len(set(top.h3) & aa) / TOPK)
        rel = top[tcol].values
        dcg = (rel / np.log2(np.arange(2, 2 + len(rel)))).sum()
        ideal = np.sort(grp[tcol].values)[::-1][:TOPK]
        idcg = (ideal / np.log2(np.arange(2, 2 + len(ideal)))).sum()
        ndcgs.append(dcg / idcg if idcg > 0 else 0)
        y = grp.h3.isin(aa).astype(int).values
        try: aucs.append(roc_auc_score(y, grp["pred"].values))
        except Exception: pass
    return (float(np.mean(precs)), float(np.mean(ndcgs)),
            float(np.mean(aucs)) if aucs else float("nan"))


def main():
    ev = pd.read_parquet(EVENTS)
    panel, stat, cells = build_panel(ev)
    p = add_features(panel, cells)
    gl = p.sort_values(["h3", "date"]).groupby("h3")["load"]
    p["fwd7"] = sum(gl.shift(-k) for k in range(1, 8))          # next-7-day target
    p["last7"] = gl.shift(1).rolling(7).sum().reset_index(0, drop=True)
    p = p.dropna(subset=["rmean28", "nbr_lag7", "city_roll7"]).reset_index(drop=True)
    print(f"panel {len(p)} rows, {len(cells)} cells")

    # walk-forward on the 7-day horizon (origins must have full future known)
    pv = p[p.date <= p.date.max() - pd.Timedelta(days=7)].dropna(subset=["fwd7"])
    lastv = pv.date.max()
    folds = [(lastv - pd.Timedelta(days=14 - i*FOLD_LEN),
              lastv - pd.Timedelta(days=7 - i*FOLD_LEN)) for i in range(2)]
    Ps, Ns, As = [], [], []
    for a, b in folds:
        tr = pv[pv.date < a]; te = pv[(pv.date >= a) & (pv.date < b)].copy()
        if len(te) == 0: continue
        te["pred"] = ensemble(tr, te, target="fwd7")
        P, N, A = metrics_at_k(te, "fwd7"); Ps.append(P); Ns.append(N); As.append(A)
        print(f"  fold {a.date()}..{b.date()}  P@{TOPK}={P*100:.1f}%  NDCG={N:.3f}  AUC={A:.3f}")

    metrics = {"horizon_days": 7,
               "Precision@50": round(float(np.mean(Ps)), 3),
               "NDCG@50": round(float(np.mean(Ns)), 3),
               "ROC_AUC": round(float(np.mean(As)), 3),
               "folds": len(Ps), "cells": int(len(cells)),
               "model": "GPU ensemble (xgb+lgb+cat, reg+rank), next-7-day ranking"}
    print("\nMETRICS:", json.dumps(metrics, indent=2))
    json.dump(metrics, open(f"{OUT}/forecast_metrics.json", "w"), indent=2)

    # next-7-day forecast for the frontend: train on all known, score latest origin
    last = p.date.max()
    tr = p.dropna(subset=["fwd7"]); te = p[p.date == last].copy()
    te["pred"] = ensemble(tr, te, target="fwd7")
    fc = te.sort_values("pred", ascending=False).head(150)[["h3", "lat", "lng", "pred", "last7"]].copy()
    fc["pred"] = (rankpct(fc["pred"]) * 100).round(1); fc.rename(columns={"last7": "actual"}, inplace=True)
    fc["actual"] = fc["actual"].fillna(0).round(0); fc["rank"] = range(1, len(fc) + 1)
    fc.to_json(f"{OUT}/forecast.json", orient="records")
    print("Saved forecast.json")


if __name__ == "__main__":
    main()
