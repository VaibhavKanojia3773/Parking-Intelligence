"""
build_forecast.py  —  generate the production forecast artifacts (7-day horizon).

Reframes the forecast to the operational horizon: rank each cell by its predicted
PARKING LOAD OVER THE NEXT 7 DAYS — what enforcement staffs shifts around. Far
more predictable than gambling on one exact day, and the right planning unit.

Outputs (frontend/public/data/):
    forecast_metrics.json  - walk-forward P@50, NDCG@50, ROC-AUC (+ next-day AUC)
    forecast.json          - next-7-day predicted top hotspots (frontend-ready)
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
import xgboost as xgb
from pathlib import Path
from sklearn.metrics import roc_auc_score
from forecast_experiment import load_events, build_panel, add_features, BASE, CONTEXT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data"
FEATS = BASE + CONTEXT
TOPK = 50


def fit(tr, target, rounds=650):
    d = xgb.DMatrix(tr[FEATS], label=np.log1p(tr[target]))
    return xgb.train(dict(objective="reg:squarederror", max_depth=8, eta=0.04, subsample=0.85,
                          colsample_bytree=0.8, min_child_weight=4, tree_method="hist"),
                     d, num_boost_round=rounds)


def eval_at_k(te, tcol):
    precs, ndcgs, aucs = [], [], []
    for _, grp in te.groupby("date"):
        if len(grp) < TOPK or grp[tcol].sum() == 0:
            continue
        top = grp.sort_values("pred", ascending=False).head(TOPK)
        actual = set(grp.sort_values(tcol, ascending=False).head(TOPK).cell)
        precs.append(len(set(top.cell) & actual) / TOPK)
        rel = top[tcol].values
        dcg = (rel / np.log2(np.arange(2, 2 + len(rel)))).sum()
        ideal = np.sort(grp[tcol].values)[::-1][:TOPK]
        ndcgs.append(dcg / ideal_sum if (ideal_sum := (ideal / np.log2(np.arange(2, 2 + len(ideal)))).sum()) > 0 else 0)
        y = grp.cell.isin(actual).astype(int).values
        try:
            aucs.append(roc_auc_score(y, grp["pred"].values))
        except Exception:
            pass
    return (float(np.mean(precs)), float(np.mean(ndcgs)),
            float(np.mean(aucs)) if aucs else float("nan"))


def main():
    print("Loading + engineering ...")
    df = load_events()
    panel, stat = build_panel(df)
    p = add_features(panel, stat)
    g = p.sort_values(["cell", "date"]).groupby("cell")["load"]
    p["fwd7"] = sum(g.shift(-k) for k in range(1, 8))          # next-7-day load (target)
    p["last7"] = g.shift(1).rolling(7).sum().reset_index(0, drop=True)  # observed last week
    p = p.dropna(subset=["rmean28", "nbr_lag7", "city_roll7"]).reset_index(drop=True)
    last = p.date.max()

    # ---- walk-forward eval on the 7-day horizon ----
    pv = p[p.date <= last - pd.Timedelta(days=7)].dropna(subset=["fwd7"])
    lastv = pv.date.max()
    folds = [(lastv - pd.Timedelta(days=14 - i*7), lastv - pd.Timedelta(days=7 - i*7)) for i in range(2)]
    P, N, A = [], [], []
    for a, b in folds:
        tr = pv[pv.date < a]; te = pv[(pv.date >= a) & (pv.date < b)].copy()
        if len(te) == 0:
            continue
        te["pred"] = fit(tr, "fwd7").predict(xgb.DMatrix(te[FEATS]))
        pp, nn, aa = eval_at_k(te, "fwd7"); P.append(pp); N.append(nn); A.append(aa)

    # next-day AUC (secondary, to show discrimination is strong even daily)
    dfolds = [(last - pd.Timedelta(days=14 - i*7), last - pd.Timedelta(days=7 - i*7)) for i in range(2)]
    dA = []
    for a, b in dfolds:
        tr = p[p.date < a].dropna(subset=["load"]); te = p[(p.date >= a) & (p.date < b)].copy()
        if len(te) == 0:
            continue
        te["pred"] = fit(tr, "load").predict(xgb.DMatrix(te[FEATS]))
        dA.append(eval_at_k(te, "load")[2])

    metrics = {
        "horizon_days": 7,
        "Precision@50": round(float(np.mean(P)), 3),
        "NDCG@50": round(float(np.mean(N)), 3),
        "ROC_AUC": round(float(np.mean(A)), 3),
        "next_day_ROC_AUC": round(float(np.mean(dA)), 3),
        "folds": len(P), "cells": int(p.cell.nunique()),
        "model": "XGBoost, next-7-day demand ranking (walk-forward)",
    }
    (OUT / "forecast_metrics.json").write_text(json.dumps(metrics, indent=2))
    print("METRICS:", json.dumps(metrics, indent=2))

    # ---- final forecast: train on all known, score the latest origin (true future) ----
    train = p.dropna(subset=["fwd7"])
    model = fit(train, "fwd7", rounds=750)
    origin = p[p.date == last].copy()
    origin["pred"] = np.expm1(model.predict(xgb.DMatrix(origin[FEATS])))  # back to load scale
    origin = origin.sort_values("pred", ascending=False).head(150).reset_index(drop=True)
    fc = pd.DataFrame({
        "h3": origin["cell"], "lat": origin["lat"].round(5), "lng": origin["lng"].round(5),
        "pred": origin["pred"].round(1), "actual": origin["last7"].fillna(0).round(0),
        "rank": np.arange(1, len(origin) + 1),
    })
    (OUT / "forecast.json").write_text(fc.to_json(orient="records"))
    print(f"forecast.json: {len(fc)} next-7-day hotspots (origin {last.date()})")


if __name__ == "__main__":
    main()
