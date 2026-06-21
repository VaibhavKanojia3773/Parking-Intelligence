"""
forecast_experiment.py  —  LOCAL CPU prototype to find what lifts the score.

Goal: discover which features / objectives actually improve next-day hotspot
ranking (Precision@50, NDCG@50) BEFORE writing the heavy Kaggle GPU ensemble.
Uses xgboost (already installed) on CPU over the real raw CSV. No GPU, no new deps.

We compare, on identical rolling-origin folds:
    M0  baseline    : lags + rolls + calendar, reg:squarederror on log1p
    M1  + context   : + city-total + neighbour + cell/dow climatology + station
    M2  rank        : M1 features, rank:pairwise (learning-to-rank)
    M3  ensemble     : blend of M1(reg) + M2(rank) normalized ranks
"""
from __future__ import annotations
import ast, re, warnings
import numpy as np
import pandas as pd
import xgboost as xgb
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "jan to may police violation_anonymized791b166.csv"

LAT = (12.70, 13.30); LNG = (77.30, 77.90)
GRID = 0.0015
MIN_CELL_TOTAL = 40
TOPK = 50
PEAK = set(range(8, 12)) | set(range(17, 22))
FOOT = {"SCOOTER": 1.2, "MOPED": 1.0, "MOTOR CYCLE": 1.4, "PASSENGER AUTO": 4.0,
        "GOODS AUTO": 4.5, "CAR": 7.5, "MAXI-CAB": 9.0, "VAN": 9.0, "TEMPO": 11.0,
        "LGV": 12.0, "PRIVATE BUS": 30.0, "BUS (BMTC/KSRTC)": 30.0, "TRUCK": 28.0}
OBSTRUCTIVE = {"PARKING IN A MAIN ROAD", "PARKING ON FOOTPATH", "DOUBLE PARKING",
               "PARKING NEAR ROAD CROSSING", "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL ETC", "NO PARKING"}
HOLIDAYS = {"2023-11-12", "2023-11-13", "2023-11-14", "2023-11-27", "2023-12-25",
            "2024-01-01", "2024-01-15", "2024-01-26", "2024-03-08", "2024-03-25",
            "2024-03-29", "2024-04-09", "2024-04-11", "2024-04-14"}


def parse_v(s):
    if not isinstance(s, str) or s in ("", "NULL"):
        return []
    try:
        v = ast.literal_eval(s); return [str(x).upper() for x in v] if isinstance(v, list) else [str(v).upper()]
    except Exception:
        return [t.upper() for t in re.findall(r'"([^"]+)"', s)]


def load_events():
    df = pd.read_csv(RAW, usecols=["latitude", "longitude", "vehicle_type", "violation_type",
                                   "police_station", "junction_name", "created_datetime",
                                   "validation_status"], low_memory=False)
    df["lat"] = pd.to_numeric(df.latitude, errors="coerce")
    df["lng"] = pd.to_numeric(df.longitude, errors="coerce")
    df = df[df.lat.between(*LAT) & df.lng.between(*LNG)]
    df = df[~df.validation_status.isin(["rejected", "duplicate"])]
    dt = pd.to_datetime(df.created_datetime, errors="coerce", utc=True).dt.tz_convert("Asia/Kolkata")
    df = df[dt.notna()]; df["date"] = dt.dt.normalize().dt.tz_localize(None); df["hour"] = dt.dt.hour
    vt = df.violation_type.apply(parse_v)
    df["obstructive"] = vt.apply(lambda L: int(any(x in OBSTRUCTIVE for x in L)))
    df["main_road"] = vt.apply(lambda L: int("PARKING IN A MAIN ROAD" in L))
    df["foot"] = df.vehicle_type.astype(str).str.upper().str.strip().map(FOOT).fillna(6.0)
    df["is_peak"] = df.hour.isin(PEAK).astype(int)
    df["has_junction"] = (~df.junction_name.isin(["No Junction", "NULL"]) & df.junction_name.notna()).astype(int)
    df["gy"] = np.floor(df.lat / GRID).astype(int); df["gx"] = np.floor(df.lng / GRID).astype(int)
    df["cell"] = df.gy.astype(str) + "_" + df.gx.astype(str)
    return df


def build_panel(df):
    tot = df.groupby("cell").size()
    keep = set(tot[tot >= MIN_CELL_TOTAL].index)
    df = df[df.cell.isin(keep)].copy()
    daily = df.groupby(["cell", "date"]).agg(load=("foot", "sum")).reset_index()
    dates = pd.date_range(df.date.min(), df.date.max(), freq="D")
    cells = daily.cell.unique()
    idx = pd.MultiIndex.from_product([cells, dates], names=["cell", "date"])
    panel = daily.set_index(["cell", "date"]).reindex(idx, fill_value=0).reset_index()
    stat = df.groupby("cell").agg(gy=("gy", "first"), gx=("gx", "first"),
                                  lat=("lat", "mean"), lng=("lng", "mean"),
                                  peak_share=("is_peak", "mean"), main_share=("main_road", "mean"),
                                  has_junction=("has_junction", "max"),
                                  station=("police_station", lambda s: s.value_counts().index[0])).reset_index()
    panel = panel.merge(stat, on="cell", how="left")
    return panel, stat


def add_features(panel, stat):
    p = panel.sort_values(["cell", "date"]).reset_index(drop=True)
    g = p.groupby("cell")["load"]
    for k in (1, 2, 3, 7, 14, 21, 28):
        p[f"lag{k}"] = g.shift(k)
    for w in (3, 7, 14, 28):
        p[f"rmean{w}"] = g.shift(1).rolling(w).mean().reset_index(0, drop=True)
        p[f"rmax{w}"] = g.shift(1).rolling(w).max().reset_index(0, drop=True)
    p["rstd7"] = g.shift(1).rolling(7).std().reset_index(0, drop=True)
    p["ewma7"] = g.shift(1).ewm(span=7).mean().reset_index(0, drop=True)
    p["mom"] = p["rmean7"] - p["rmean28"]
    p["mom_ratio"] = p["rmean7"] / (p["rmean28"] + 1)

    dd = p["date"]
    p["dow"] = dd.dt.dayofweek
    p["dow_sin"] = np.sin(2 * np.pi * p.dow / 7); p["dow_cos"] = np.cos(2 * np.pi * p.dow / 7)
    p["is_weekend"] = (p.dow >= 5).astype(int)
    p["dom"] = dd.dt.day; p["woy"] = dd.dt.isocalendar().week.astype(int)
    p["trend"] = (dd - dd.min()).dt.days
    p["is_holiday"] = dd.dt.strftime("%Y-%m-%d").isin(HOLIDAYS).astype(int)

    # ---- context features (the hypothesis) ----
    # city-wide enforcement intensity (captures manpower/holiday days)
    city = p.groupby("date")["load"].sum().rename("city")
    p = p.merge(city.shift(1).rename("city_lag1"), on="date", how="left")
    p = p.merge(city.shift(7).rename("city_lag7"), on="date", how="left")
    p = p.merge(city.rolling(7).mean().shift(1).rename("city_roll7"), on="date", how="left")
    # station-level daily intensity (lagged)
    sd = p.groupby(["station", "date"])["load"].sum().rename("stload").reset_index()
    sd = sd.sort_values(["station", "date"])
    sd["st_lag1"] = sd.groupby("station")["stload"].shift(1)
    sd["st_lag7"] = sd.groupby("station")["stload"].shift(7)
    p = p.merge(sd[["station", "date", "st_lag1", "st_lag7"]], on=["station", "date"], how="left")
    # neighbour (8-grid) lagged mean
    p["key"] = p.gy.astype(str) + "_" + p.gx.astype(str)
    load_map = p.set_index(["date", "key"])["load"]
    # build neighbour mean via shift on a (date x cell) pivot
    piv = p.pivot_table(index="date", columns="cell", values="load", fill_value=0).sort_index()
    gy = stat.set_index("cell")["gy"].to_dict(); gx = stat.set_index("cell")["gx"].to_dict()
    cell_of = {(gy[c], gx[c]): c for c in piv.columns}
    nbr_mean = pd.DataFrame(0.0, index=piv.index, columns=piv.columns)
    arr = piv.values; pos = {c: i for i, c in enumerate(piv.columns)}
    for c in piv.columns:
        ns = []
        for dyx in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            nb = cell_of.get((gy[c]+dyx[0], gx[c]+dyx[1]))
            if nb is not None: ns.append(pos[nb])
        if ns: nbr_mean[c] = arr[:, ns].mean(axis=1)
    nb1 = nbr_mean.shift(1).stack().rename("nbr_lag1").reset_index()
    nb7 = nbr_mean.shift(7).stack().rename("nbr_lag7").reset_index()
    p = p.merge(nb1, on=["date", "cell"], how="left").merge(nb7, on=["date", "cell"], how="left")
    return p


BASE = ["lag1", "lag2", "lag3", "lag7", "lag14", "lag21", "lag28",
        "rmean3", "rmean7", "rmean14", "rmean28", "rmax7", "rmax14", "rstd7", "ewma7",
        "mom", "mom_ratio", "dow_sin", "dow_cos", "is_weekend", "dom", "woy", "trend",
        "is_holiday", "lat", "lng", "has_junction", "peak_share", "main_share"]
CONTEXT = ["city_lag1", "city_lag7", "city_roll7", "st_lag1", "st_lag7", "nbr_lag1", "nbr_lag7"]


def precision_ndcg(te):
    precs, ndcgs = [], []
    for _, grp in te.groupby("date"):
        if len(grp) < TOPK: continue
        gp = grp.sort_values("pred", ascending=False)
        topp = gp.head(TOPK)
        aa = set(grp.sort_values("load", ascending=False).head(TOPK).cell)
        precs.append(len(set(topp.cell) & aa) / TOPK)
        # NDCG@k with relevance = actual load
        rel = topp["load"].values
        dcg = (rel / np.log2(np.arange(2, 2 + len(rel)))).sum()
        ideal = np.sort(grp["load"].values)[::-1][:TOPK]
        idcg = (ideal / np.log2(np.arange(2, 2 + len(ideal)))).sum()
        ndcgs.append(dcg / idcg if idcg > 0 else 0)
    return float(np.mean(precs)), float(np.mean(ndcgs))


def run_model(tr, te, feats, mode):
    if mode == "rank":
        tr = tr.sort_values("date"); grp = tr.groupby("date").size().values
        dtr = xgb.DMatrix(tr[feats], label=tr["load"]); dtr.set_group(grp)
        params = dict(objective="rank:pairwise", eval_metric="ndcg@50",
                      max_depth=8, eta=0.05, subsample=0.85, colsample_bytree=0.8,
                      min_child_weight=4, tree_method="hist")
        m = xgb.train(params, dtr, num_boost_round=400, verbose_eval=False)
    else:
        dtr = xgb.DMatrix(tr[feats], label=np.log1p(tr["load"]))
        params = dict(objective="reg:squarederror", eval_metric="rmse",
                      max_depth=8, eta=0.04, subsample=0.85, colsample_bytree=0.8,
                      min_child_weight=4, tree_method="hist")
        m = xgb.train(params, dtr, num_boost_round=600, verbose_eval=False)
    pred = m.predict(xgb.DMatrix(te[feats]))
    return pred


def main():
    print("Loading + engineering ..."); df = load_events()
    panel, stat = build_panel(df)
    p = add_features(panel, stat).dropna(subset=["rmean28", "nbr_lag7", "city_roll7"]).reset_index(drop=True)
    print(f"panel {len(p)} rows, {p.cell.nunique()} cells, dates {p.date.min().date()}..{p.date.max().date()}")

    # rolling-origin folds: predict last 3 weeks in 3 x 7-day blocks
    last = p.date.max()
    folds = [(last - pd.Timedelta(days=21 - i*7), last - pd.Timedelta(days=14 - i*7)) for i in range(3)]
    configs = {"M0 baseline (reg)": (BASE, "reg"),
               "M1 +context (reg)": (BASE + CONTEXT, "reg"),
               "M2 +context (rank)": (BASE + CONTEXT, "rank")}
    results = {k: {"P": [], "N": []} for k in configs}
    results["M3 ensemble"] = {"P": [], "N": []}

    for (a, b) in folds:
        tr = p[p.date < a]; te = p[(p.date >= a) & (p.date < b)].copy()
        if len(te) == 0: continue
        preds = {}
        for name, (feats, mode) in configs.items():
            te["pred"] = run_model(tr, te, feats, mode)
            P, N = precision_ndcg(te); results[name]["P"].append(P); results[name]["N"].append(N)
            preds[name] = te["pred"].values
        # ensemble: average of rank-normalized M1 + M2
        r1 = pd.Series(preds["M1 +context (reg)"]).rank(pct=True).values
        r2 = pd.Series(preds["M2 +context (rank)"]).rank(pct=True).values
        te["pred"] = (r1 + r2) / 2
        P, N = precision_ndcg(te); results["M3 ensemble"]["P"].append(P); results["M3 ensemble"]["N"].append(N)

    print("\n=== ROLLING-ORIGIN RESULTS (mean over folds) ===")
    print(f"{'model':<24}{'Precision@50':>14}{'NDCG@50':>10}")
    for k, v in results.items():
        print(f"{k:<24}{np.mean(v['P'])*100:>13.1f}%{np.mean(v['N']):>10.3f}")


if __name__ == "__main__":
    main()
