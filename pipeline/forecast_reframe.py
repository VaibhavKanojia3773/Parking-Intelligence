"""
forecast_reframe.py  —  test the horizon reframe: next-DAY vs next-7-DAY ranking.

Hypothesis: daily enforcement is noisy (P@50 ceiling ~45%), but the 7-day
hotspot ranking — what enforcement actually plans around — is far more
predictable. Also report ROC-AUC for "is this cell a top-50 hotspot next week".
Reuses the heavy feature engineering from forecast_experiment.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import xgboost as xgb
from forecast_experiment import load_events, build_panel, add_features, BASE, CONTEXT

TOPK = 50
FEATS = BASE + CONTEXT


def pAtk_auc(te, tcol):
    from sklearn.metrics import roc_auc_score
    precs, aucs = [], []
    for _, grp in te.groupby("date"):
        if len(grp) < TOPK or grp[tcol].sum() == 0:
            continue
        top = grp.sort_values("pred", ascending=False).head(TOPK)
        actual = set(grp.sort_values(tcol, ascending=False).head(TOPK).cell)
        precs.append(len(set(top.cell) & actual) / TOPK)
        y = grp.cell.isin(actual).astype(int).values
        try:
            aucs.append(roc_auc_score(y, grp["pred"].values))
        except Exception:
            pass
    return float(np.mean(precs)), float(np.mean(aucs)) if aucs else float("nan")


def train_pred(tr, te, target):
    d = xgb.DMatrix(tr[FEATS], label=np.log1p(tr[target]))
    m = xgb.train(dict(objective="reg:squarederror", max_depth=8, eta=0.04, subsample=0.85,
                       colsample_bytree=0.8, min_child_weight=4, tree_method="hist"),
                  d, num_boost_round=600)
    return m.predict(xgb.DMatrix(te[FEATS]))


def main():
    print("Loading + engineering ...")
    df = load_events()
    panel, stat = build_panel(df)
    p = add_features(panel, stat)
    # forward 7-day load (causal target): sum of next 7 days
    g = p.sort_values(["cell", "date"]).groupby("cell")["load"]
    p["fwd7"] = sum(g.shift(-k) for k in range(1, 8))
    p = p.dropna(subset=["rmean28", "nbr_lag7", "city_roll7"]).reset_index(drop=True)
    last = p.date.max()

    # ---- next-DAY (target = load) ----
    folds = [(last - pd.Timedelta(days=21 - i*7), last - pd.Timedelta(days=14 - i*7)) for i in range(3)]
    dP, dA = [], []
    for a, b in folds:
        tr = p[p.date < a].dropna(subset=["load"]); te = p[(p.date >= a) & (p.date < b)].copy()
        if len(te) == 0: continue
        te["pred"] = train_pred(tr, te, "load")
        P, A = pAtk_auc(te, "load"); dP.append(P); dA.append(A)

    # ---- next-7-DAY (target = fwd7) ----  origins must have full future known (<= last-7)
    pv = p[p.date <= last - pd.Timedelta(days=7)].dropna(subset=["fwd7"]).copy()
    lastv = pv.date.max()
    wfolds = [(lastv - pd.Timedelta(days=14 - i*7), lastv - pd.Timedelta(days=7 - i*7)) for i in range(2)]
    wP, wA = [], []
    for a, b in wfolds:
        tr = pv[pv.date < a]; te = pv[(pv.date >= a) & (pv.date < b)].copy()
        if len(te) == 0: continue
        te["pred"] = train_pred(tr, te, "fwd7")
        P, A = pAtk_auc(te, "fwd7"); wP.append(P); wA.append(A)

    print("\n=== HORIZON REFRAME ===")
    print(f"{'task':<26}{'Precision@50':>14}{'ROC-AUC':>10}")
    print(f"{'next-DAY (load)':<26}{np.mean(dP)*100:>13.1f}%{np.mean(dA):>10.3f}")
    print(f"{'next-7-DAY (fwd7)':<26}{np.mean(wP)*100:>13.1f}%{np.mean(wA):>10.3f}")


if __name__ == "__main__":
    main()
