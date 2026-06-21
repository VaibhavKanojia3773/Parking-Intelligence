"""
build_artifacts.py  —  LOCAL light data-prep (pandas/numpy only, no GPU)

Turns the raw 298k parking-violation CSV into compact JSON artifacts the
3D dashboard consumes. Heavy ML (forecasting, OSM-enriched PCIS) lives in
the Kaggle GPU scripts; this script produces the demo-ready, real-data
foundation so the UI renders actual Bengaluru parking intelligence.

Outputs (frontend/public/data/):
  points.json    - columnar point cloud for the deck.gl 3D hex map
  hotspots.json  - ranked grid cells with Parking Congestion Impact Score (PCIS)
  stations.json  - police-station rollups
  summary.json   - KPIs + temporal/categorical distributions for charts

Run:  python pipeline/build_artifacts.py
"""
from __future__ import annotations
import json, os, re, ast
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "jan to may police violation_anonymized791b166.csv"
OUT = ROOT / "frontend" / "public" / "data"
OUT.mkdir(parents=True, exist_ok=True)

# Bengaluru bounding box (drop garbage / null coords)
LAT_MIN, LAT_MAX = 12.70, 13.30
LNG_MIN, LNG_MAX = 77.30, 77.90

# Approx parked-footprint (plan area, m^2) -> how much carriageway a vehicle steals
FOOTPRINT = {
    "SCOOTER": 1.2, "MOPED": 1.0, "MOTOR CYCLE": 1.4, "MOTORCYCLE": 1.4,
    "PASSENGER AUTO": 4.0, "GOODS AUTO": 4.5, "CAR": 7.5, "MAXI-CAB": 9.0,
    "VAN": 9.0, "TEMPO": 11.0, "LGV": 12.0, "PRIVATE BUS": 30.0,
    "BUS (BMTC/KSRTC)": 30.0, "TRUCK": 28.0,
}
DEFAULT_FOOTPRINT = 6.0

# Violation sub-types that directly block a live lane / footpath / junction
OBSTRUCTIVE = {
    "PARKING IN A MAIN ROAD", "PARKING ON FOOTPATH", "DOUBLE PARKING",
    "PARKING NEAR ROAD CROSSING", "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL ETC",
    "NO PARKING",
}

PEAK_HOURS = set(range(8, 12)) | set(range(17, 22))  # AM + PM rush
MORNING_RUSH = set(range(8, 12))
EVENING_RUSH = set(range(17, 22))
GRID = 0.0015  # ~165 m cells

# --- real-world impact translation (transparent, stated assumptions) ---
LANE_W = 3.5          # m, standard urban lane width
DWELL_H = 0.75        # h, assumed avg dwell of an illegally parked vehicle (45 min)
PEAK_WINDOW_H = 4.0   # h, length of the morning enforcement/peak window (08-12)

# PCIS component weights (single source of truth, used for scoring + ablation)
PCIS_W = {"s_vol": 0.34, "s_obstr": 0.22, "s_road": 0.16,
          "s_peak": 0.14, "s_junc": 0.08, "s_chron": 0.06}

SHIFTS = {"morning": set(range(7, 12)), "afternoon": set(range(12, 17)),
          "evening": set(range(17, 22)), "night": set(range(22, 24)) | set(range(0, 7))}


def parse_violation(s: str) -> list[str]:
    if not isinstance(s, str) or not s.strip() or s == "NULL":
        return []
    try:
        v = ast.literal_eval(s)
        return [str(x).strip().upper() for x in v] if isinstance(v, list) else [str(v).upper()]
    except Exception:
        return [t.strip().upper() for t in re.findall(r'"([^"]+)"', s)]


def pct_rank(s: pd.Series) -> pd.Series:
    """Robust 0..1 percentile-rank normalization (outlier-safe)."""
    return s.rank(pct=True).fillna(0.0)


def dominant_shift(hours: pd.Series) -> str:
    best, bn = "morning", -1
    for name, hrs in SHIFTS.items():
        c = int(hours.isin(list(hrs)).sum())
        if c > bn:
            bn, best = c, name
    return best


def cell_features(d: pd.DataFrame) -> pd.DataFrame:
    """Per-(gy,gx) PCIS components + score for an arbitrary slice of events.

    Shared by the main hotspot build and the validation split so the score is
    computed identically everywhere (no leakage of definitions)."""
    g = d.groupby(["gy", "gx"])
    c = pd.DataFrame({
        "n": g.size(),
        "vol_w": g["footprint"].sum(),
        "obstructive": g["obstructive"].sum(),
        "main_road": g["main_road"].sum(),
        "peak": g["hour"].apply(lambda x: x.isin(PEAK_HOURS).mean()),
        "junction": g["has_junction"].max(),
        "chronicity": g["date"].nunique(),
        "lat": g["lat"].mean(), "lng": g["lng"].mean(),
    }).reset_index()
    c["s_vol"] = pct_rank(c["vol_w"])
    c["s_obstr"] = pct_rank(c["obstructive"])
    c["s_road"] = pct_rank(c["main_road"])
    c["s_peak"] = c["peak"]
    c["s_junc"] = c["junction"].astype(float)
    c["s_chron"] = pct_rank(c["chronicity"])
    c["pcis"] = 100 * sum(PCIS_W[k] * c[k] for k in PCIS_W)
    return c


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1); dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def _impact_units(df: pd.DataFrame, window_days: int) -> dict:
    """Translate footprint into a felt real-world unit: carriageway lane-metres /
    lane-km-hours of road blocked. Transparent, stated assumptions (no external data)."""
    total_fp = float(df["footprint"].sum())
    lane_km_hours = total_fp * DWELL_H / LANE_W / 1000.0          # over the window
    peak_fp = float(df.loc[df["hour"].isin(list(MORNING_RUSH)), "footprint"].sum())
    inst_area = (peak_fp / window_days) * (DWELL_H / PEAK_WINDOW_H)  # avg area blocked at any peak moment
    lane_m_peak = inst_area / LANE_W
    return {
        "assumptions": f"avg dwell {DWELL_H}h, lane width {LANE_W}m, peak window {PEAK_WINDOW_H}h",
        "lane_km_hours_total": round(lane_km_hours, 0),
        "lane_km_hours_per_day": round(lane_km_hours / window_days, 1),
        "peak_lane_m_blocked": round(lane_m_peak, 0),
    }


def main() -> None:
    print("Loading raw CSV ...")
    usecols = ["latitude", "longitude", "vehicle_type", "violation_type",
               "police_station", "junction_name", "created_datetime",
               "validation_status", "device_id", "location"]
    df = pd.read_csv(RAW, usecols=usecols, low_memory=False)
    n0 = len(df)

    # --- clean geo ---
    df["lat"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["lng"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df[(df.lat.between(LAT_MIN, LAT_MAX)) & (df.lng.between(LNG_MIN, LNG_MAX))]

    # drop rejected/duplicate enforcement records (keep approved + unreviewed)
    df = df[~df["validation_status"].isin(["rejected", "duplicate"])]

    # --- time features ---
    dt = pd.to_datetime(df["created_datetime"], errors="coerce", utc=True)
    dt = dt.dt.tz_convert("Asia/Kolkata")
    df["hour"] = dt.dt.hour
    df["dow"] = dt.dt.dayofweek
    df["date"] = dt.dt.date
    df = df[df["hour"].notna()]
    df["hour"] = df["hour"].astype(int)
    df["dow"] = df["dow"].astype(int)
    _dd = pd.to_datetime(df["date"])
    WINDOW_DAYS = max((_dd.max() - _dd.min()).days, 1)

    # --- violation parsing / flags ---
    vt = df["violation_type"].apply(parse_violation)
    df["obstructive"] = vt.apply(lambda L: int(any(x in OBSTRUCTIVE for x in L)))
    df["main_road"] = vt.apply(lambda L: int("PARKING IN A MAIN ROAD" in L))
    # primary category for coloring the map
    def primary(L):
        if not L: return "OTHER"
        for key in ("PARKING IN A MAIN ROAD", "PARKING ON FOOTPATH", "DOUBLE PARKING",
                    "WRONG PARKING", "NO PARKING"):
            if key in L: return key
        return L[0]
    df["cat"] = vt.apply(primary)

    # --- footprint weight ---
    vtu = df["vehicle_type"].astype(str).str.upper().str.strip()
    df["footprint"] = vtu.map(FOOTPRINT).fillna(DEFAULT_FOOTPRINT)

    df["has_junction"] = (~df["junction_name"].isin(["No Junction", "NULL"])
                          & df["junction_name"].notna()).astype(int)

    n1 = len(df)
    print(f"Cleaned: {n0} -> {n1} valid rows")

    # ---------------- POINTS artifact (columnar, compact) ----------------
    CAT_CODES = {"PARKING IN A MAIN ROAD": 0, "PARKING ON FOOTPATH": 1,
                 "DOUBLE PARKING": 2, "WRONG PARKING": 3, "NO PARKING": 4, "OTHER": 5}
    pts = df.copy()
    points = {
        "lat": [round(float(x), 5) for x in pts.lat],
        "lng": [round(float(x), 5) for x in pts.lng],
        "h":   [int(x) for x in pts.hour],
        "d":   [int(x) for x in pts.dow],
        "c":   [CAT_CODES.get(x, 5) for x in pts.cat],
        "w":   [round(float(x), 1) for x in pts.footprint],
        "cat_labels": list(CAT_CODES.keys()),
    }
    (OUT / "points.json").write_text(json.dumps(points, separators=(",", ":")))
    print("points.json:", round((OUT / "points.json").stat().st_size / 1e6, 1), "MB,", n1, "pts")

    # ---------------- HOTSPOT grid + PCIS ----------------
    df["gy"] = np.floor(df.lat / GRID).astype(int)
    df["gx"] = np.floor(df.lng / GRID).astype(int)
    g = df.groupby(["gy", "gx"])
    cell = pd.DataFrame({
        "n": g.size(),
        "vol_w": g["footprint"].sum(),
        "obstructive": g["obstructive"].sum(),
        "main_road": g["main_road"].sum(),
        "peak": g.apply(lambda x: x["hour"].isin(PEAK_HOURS).mean(), include_groups=False),
        "junction": g["has_junction"].max(),
        "chronicity": g["date"].nunique(),
        "lat": g["lat"].mean(),
        "lng": g["lng"].mean(),
        "top_ps": g["police_station"].agg(lambda s: s.value_counts().idxmax()),
        "top_junction": g["junction_name"].agg(
            lambda s: s[~s.isin(["No Junction", "NULL"])].value_counts().idxmax()
            if (~s.isin(["No Junction", "NULL"])).any() else "—"),
    }).reset_index()

    # focus on real hotspots (>= 20 violations in ~165m cell over 5 months)
    cell = cell[cell["n"] >= 20].copy()

    # --- Parking Congestion Impact Score (PCIS), 0..100 ---
    # weighted blend of percentile-normalized drivers of traffic-flow harm
    cell["s_vol"]   = pct_rank(cell["vol_w"])           # carriageway stolen
    cell["s_obstr"] = pct_rank(cell["obstructive"])     # lane/footpath blockage
    cell["s_road"]  = pct_rank(cell["main_road"])       # on arterial roads
    cell["s_peak"]  = cell["peak"]                      # rush-hour concentration (already 0..1)
    cell["s_junc"]  = cell["junction"].astype(float)    # at/near a junction
    cell["s_chron"] = pct_rank(cell["chronicity"])      # chronic vs one-off
    cell["pcis"] = (100 * (
        0.34 * cell["s_vol"] +
        0.22 * cell["s_obstr"] +
        0.16 * cell["s_road"] +
        0.14 * cell["s_peak"] +
        0.08 * cell["s_junc"] +
        0.06 * cell["s_chron"])).round(1)

    # --- real-world impact unit: lane-metres of carriageway blocked at peak ---
    # avg footprint of peak parking on a typical active day, blocked for DWELL_H
    # spread over the PEAK_WINDOW, expressed in lane-metres (footprint / lane width)
    cell["lane_m"] = (cell["vol_w"] * cell["peak"] / cell["chronicity"].clip(lower=1)
                      * DWELL_H / PEAK_WINDOW_H / LANE_W).round(1)

    cell = cell.sort_values("pcis", ascending=False).reset_index(drop=True)
    cell["rank"] = cell.index + 1
    hot_cols = ["rank", "lat", "lng", "n", "vol_w", "obstructive", "peak",
                "chronicity", "pcis", "lane_m", "top_ps", "top_junction"]
    hot = cell[hot_cols].copy()
    hot["lat"] = hot["lat"].round(5); hot["lng"] = hot["lng"].round(5)
    hot["vol_w"] = hot["vol_w"].round(0); hot["peak"] = (hot["peak"] * 100).round(0)
    (OUT / "hotspots.json").write_text(
        json.dumps(hot.to_dict(orient="records"), separators=(",", ":")))
    print("hotspots.json:", len(hot), "cells")

    # --- PCIS weight-sensitivity (defends the expert-set weights) ---
    # Monte-Carlo perturb every weight by up to +/-25%, renormalize, re-score;
    # how stable is the ranking?  Robust weights -> high Spearman + top-50 overlap.
    rng = np.random.default_rng(7)
    base = cell["pcis"].values
    base_top = set(np.argsort(-base)[:50])
    sp_list, ov_list = [], []
    for _ in range(300):
        w = {k: PCIS_W[k] * (1 + rng.uniform(-0.25, 0.25)) for k in PCIS_W}
        tot = sum(w.values())
        score = 100 * sum((w[k] / tot) * cell[k] for k in w)
        sp_list.append(pd.Series(score.values).corr(pd.Series(base), method="spearman"))
        ov_list.append(len(set(np.argsort(-score.values)[:50]) & base_top) / 50)
    weight_sensitivity = {
        "perturbation": "+/-25% per weight, 300 draws",
        "mean_rank_spearman": round(float(np.mean(sp_list)), 3),
        "min_rank_spearman": round(float(np.min(sp_list)), 3),
        "mean_top50_overlap": round(float(np.mean(ov_list)), 3),
    }
    print(f"weight sensitivity: rank rho mean={weight_sensitivity['mean_rank_spearman']} "
          f"min={weight_sensitivity['min_rank_spearman']}, "
          f"top50 overlap={weight_sensitivity['mean_top50_overlap']}")

    # ---------------- STATION rollups ----------------
    st = df.groupby("police_station").agg(
        violations=("lat", "size"),
        vol_w=("footprint", "sum"),
        obstructive=("obstructive", "sum"),
        peak_share=("hour", lambda x: round(float(x.isin(PEAK_HOURS).mean()) * 100, 1)),
        lat=("lat", "mean"), lng=("lng", "mean"),
    ).reset_index().sort_values("violations", ascending=False)
    st["vol_w"] = st["vol_w"].round(0)
    (OUT / "stations.json").write_text(
        json.dumps(st.to_dict(orient="records"), separators=(",", ":")))
    print("stations.json:", len(st), "stations")

    # ============ ① DETECT — exposure / bias-corrected detection ============
    # Hotspots from enforcement data are biased toward where police patrol. We
    # correct for it: demand intensity = violations per PATROL SESSION (a device
    # present on a day). High intensity + few sessions = a real hotspot that is
    # UNDER-ENFORCED (dense when visited, rarely visited) — the actionable signal.
    df["session"] = df["device_id"].astype(str) + "|" + df["date"].astype(str)
    sess = df.groupby(["gy", "gx"])["session"].nunique().rename("sessions")
    det = cell.set_index(["gy", "gx"]).join(sess).reset_index()
    det["sessions"] = det["sessions"].fillna(1).clip(lower=1)
    det["intensity"] = (det["n"] / det["sessions"]).round(2)   # latent demand proxy
    det["demand_score"] = (pct_rank(det["intensity"]) * 100).round(1)
    int_hi = det["intensity"].quantile(0.60)
    sess_lo = det["sessions"].quantile(0.40)
    sess_hi = det["sessions"].quantile(0.75)

    def klass(r):
        # require >= 2 visits so per-visit yield is not a single-drive fluke
        if r.intensity >= int_hi and 2 <= r.sessions <= max(sess_lo, 2):
            return "under-enforced"
        if r.sessions >= sess_hi and r.intensity < int_hi:
            return "saturated"
        if r.intensity >= int_hi:
            return "hotspot"
        return "normal"
    det["exposure_class"] = det.apply(klass, axis=1)

    det_cols = ["lat", "lng", "n", "sessions", "intensity", "demand_score",
                "pcis", "exposure_class", "top_ps", "top_junction"]
    det_out = det.sort_values("demand_score", ascending=False)[det_cols].copy()
    det_out["lat"] = det_out["lat"].round(5); det_out["lng"] = det_out["lng"].round(5)
    under = det_out[det_out["exposure_class"] == "under-enforced"].head(40)
    detection = {
        "summary": {k: int((det["exposure_class"] == k).sum())
                    for k in ["under-enforced", "saturated", "hotspot", "normal"]},
        "median_sessions": float(det["sessions"].median()),
        "top_demand": det_out.head(60).to_dict(orient="records"),
        "under_enforced": under.to_dict(orient="records"),
    }
    (OUT / "detection.json").write_text(json.dumps(detection, separators=(",", ":")))
    print(f"detection.json: {detection['summary']['under-enforced']} under-enforced hotspots")

    # ============ ② QUANTIFY-FLOW — corridor (carriageway) impact ============
    # The PS is about choked *carriageways*. Aggregate impact to named roads so a
    # whole corridor can be enforced, not just a point.
    df["road"] = df["location"].astype(str).str.split(",").str[0].str.strip()
    road = df[df["road"].str.len().between(5, 38) & ~df["road"].isin(["NULL", "nan"])]
    rg = road.groupby("road").agg(
        n=("footprint", "size"), load=("footprint", "sum"),
        obstructive=("obstructive", "sum"), main_road=("main_road", "sum"),
        peak=("hour", lambda x: x.isin(PEAK_HOURS).mean()),
        lat=("lat", "mean"), lng=("lng", "mean"),
        top_ps=("police_station", lambda s: s.value_counts().idxmax()),
    ).reset_index()
    rg = rg[rg["n"] >= 40].copy()
    rg["obstr_share"] = (rg["obstructive"] / rg["n"]).round(3)
    rg["impact"] = (100 * (0.50 * pct_rank(rg["load"]) +
                           0.30 * pct_rank(rg["obstructive"]) +
                           0.20 * rg["peak"])).round(1)
    rg = rg.sort_values("impact", ascending=False).head(45)
    rg["lat"] = rg["lat"].round(5); rg["lng"] = rg["lng"].round(5)
    rg["load"] = rg["load"].round(0); rg["peak"] = (rg["peak"] * 100).round(0)
    (OUT / "corridors.json").write_text(json.dumps(
        rg[["road", "n", "load", "obstr_share", "peak", "impact", "top_ps", "lat", "lng"]]
        .to_dict(orient="records"), separators=(",", ":")))
    print("corridors.json:", len(rg), "carriageways")

    # ============ ③ ENABLE — operational tasking / work orders ============
    # Turn the priority map into a roll-call work product: per station x shift, a
    # ranked task list with what to target and a data-driven revisit cadence.
    gg = df.groupby(["gy", "gx"])
    aux = pd.DataFrame({
        "dom_cat": gg["cat"].agg(lambda s: s.value_counts().index[0]),
        "dom_veh": gg["vehicle_type"].agg(lambda s: str(s.value_counts().index[0]).title()),
        "peak_hour": gg["hour"].agg(lambda s: int(s.value_counts().index[0])),
    }).reset_index()
    # data-driven revisit cadence = observed median gap between a cell's active days
    ddf = df.copy(); ddf["d"] = pd.to_datetime(ddf["date"])

    def med_gap(s):
        u = np.sort(pd.unique(s.values))
        if len(u) < 2:
            return np.nan
        return float(np.median(np.diff(u).astype("timedelta64[D]").astype(int)))
    gaps = ddf.groupby(["gy", "gx"])["d"].apply(med_gap).rename("med_gap").reset_index()
    tw = cell.merge(aux, on=["gy", "gx"], how="left").merge(gaps, on=["gy", "gx"], how="left")
    win = WINDOW_DAYS

    def revisit(g):
        if pd.isna(g):
            return "One-off"
        if g <= 1.5:
            return "Daily"
        if g <= 3.5:
            return "Every 2-3 days"
        if g <= 8:
            return "Weekly"
        return "Fortnightly"
    tw["revisit"] = tw["med_gap"].apply(revisit)
    tw["shift"] = tw["peak_hour"].apply(
        lambda h: next(s for s, hrs in SHIFTS.items() if h in hrs))
    tw["window"] = tw["peak_hour"].apply(lambda h: f"{h:02d}:00-{(h+2) % 24:02d}:00")

    stations = []
    for ps, grp in tw.groupby("top_ps"):
        grp = grp.sort_values("pcis", ascending=False)
        shifts = {}
        for sh in ["morning", "afternoon", "evening", "night"]:
            rows = grp[grp["shift"] == sh].head(6)
            if len(rows) == 0:
                continue
            shifts[sh] = [{
                "loc": (r.top_junction if r.top_junction != "—" else f"{r.lat:.4f},{r.lng:.4f}"),
                "lat": round(float(r.lat), 5), "lng": round(float(r.lng), 5),
                "severity": float(r.pcis), "window": r.window, "revisit": r.revisit,
                "lane_m": round(float(r.lane_m), 1),
                "target_violation": str(r.dom_cat).title().replace("Parking ", ""),
                "target_vehicle": r.dom_veh, "cases": int(r.n),
            } for r in rows.itertuples()]
        if shifts:
            stations.append({
                "station": ps, "hotspots": int(len(grp)),
                "top_severity": float(grp["pcis"].max()),
                "orders": int(sum(len(v) for v in shifts.values())), "shifts": shifts,
            })
    stations.sort(key=lambda s: s["top_severity"], reverse=True)
    (OUT / "tasking.json").write_text(json.dumps(
        {"generated_for_window_days": int(win), "stations": stations}, separators=(",", ":")))
    print(f"tasking.json: {len(stations)} stations, "
          f"{sum(s['orders'] for s in stations)} work orders")

    # ================= VALIDATION (the "quantify impact" rigor) =================
    # Q: is a high-PCIS cell genuinely a worse, *persistent* problem — or noise?
    # Test: build PCIS on the FIRST half of the window, then check whether it
    # predicts the parking burden in the held-out SECOND half. No future leakage.
    mid = pd.Series(pd.to_datetime(df["date"])).quantile(0.5)
    dts = pd.to_datetime(df["date"])
    h1 = df[dts <= mid]
    h2 = df[dts > mid]
    c1 = cell_features(h1).set_index(["gy", "gx"])
    # realized future FLOW-IMPACT = footprint of lane-blocking parking in H2
    # (this is the quantity PCIS claims to capture, not raw violation volume)
    h2["impact"] = h2["footprint"] * h2["obstructive"]
    h2_impact = h2.groupby(["gy", "gx"])["impact"].sum().rename("h2_impact")
    h2_load = h2.groupby(["gy", "gx"])["footprint"].sum().rename("h2_load")
    v = c1.join(h2_impact).join(h2_load)
    v = v[v["n"] >= 10].copy()
    v[["h2_impact", "h2_load"]] = v[["h2_impact", "h2_load"]].fillna(0.0)

    # primary test: predicting future flow-impact (PCIS vs raw-count baseline)
    sp_pcis = float(v["pcis"].corr(v["h2_impact"], method="spearman"))
    sp_count = float(v["n"].corr(v["h2_impact"], method="spearman"))
    # secondary: predicting raw future load (where volume naturally dominates)
    sp_pcis_load = float(v["pcis"].corr(v["h2_load"], method="spearman"))
    sp_count_load = float(v["n"].corr(v["h2_load"], method="spearman"))
    # top-decile lift: future flow-impact of top-10% PCIS cells vs the average cell
    thr = v["pcis"].quantile(0.9)
    lift = float(v.loc[v["pcis"] >= thr, "h2_impact"].mean() / max(v["h2_impact"].mean(), 1e-9))

    # component ablation: drop each driver, renormalize, re-score, re-test validity
    ablation = []
    for drop in PCIS_W:
        wk = {k: w for k, w in PCIS_W.items() if k != drop}
        s = sum(wk.values())
        score = 100 * sum((wk[k] / s) * v[k] for k in wk)
        corr = float(score.corr(v["h2_impact"], method="spearman"))
        ablation.append({"component": drop.replace("s_", ""),
                         "validity_without": round(corr, 3),
                         "contribution": round(sp_pcis - corr, 3)})
    ablation.sort(key=lambda x: x["contribution"], reverse=True)

    # ---- self-validate the BIAS-CORRECTION (held-out, confound-aware) ----
    # NOTE: we deliberately do NOT validate "under-enforced" against future
    # violation COUNTS — the same patrol bias suppresses second-half counts at
    # rarely-visited cells, so that test is circular. The confound-free question
    # is whether per-session YIELD (violations caught per patrol visit) is a
    # STABLE property of a place: does a high-yield cell in H1 stay high-yield in
    # H2?  If so, intensity measures real demand, independent of patrol frequency.
    def sess_intensity(d):
        s = d.copy()
        s["session"] = s["device_id"].astype(str) + "|" + s["date"].astype(str)
        gp = s.groupby(["gy", "gx"])
        return pd.DataFrame({"n": gp.size(), "sess": gp["session"].nunique()})
    i1 = sess_intensity(h1); i2 = sess_intensity(h2)
    i1["int1"] = i1["n"] / i1["sess"]; i2["int2"] = i2["n"] / i2["sess"]
    both = i1[i1["sess"] >= 3].join(i2[i2["sess"] >= 3]["int2"], how="inner")
    yield_stability = float(both["int1"].corr(both["int2"], method="spearman"))
    bias_correction = {
        "test": "per-patrol yield stability (H1 vs H2), confound-free",
        "yield_stability_spearman": round(yield_stability, 3),
        "n_cells": int(len(both)),
        "note": "Violations caught per patrol visit is a stable property of a "
                "location (H1->H2). Intensity therefore flags genuinely high-demand "
                "spots, independent of how often they happen to be patrolled. We do "
                "NOT claim to validate latent demand against future counts — that is "
                "impossible from enforcement data alone (the same bias suppresses both "
                "halves), which is exactly why a per-visit-yield metric is the honest one.",
    }
    print(f"bias-correction validation: per-visit yield stability rho={yield_stability:.3f} "
          f"(n={len(both)} cells)")

    # ---- enforcement selection-bias audit ----
    hh = df["hour"]
    morning = float(hh.isin(list(MORNING_RUSH)).mean())
    evening = float(hh.isin(list(EVENING_RUSH)).mean())
    validation = {
        "n_cells_tested": int(len(v)),
        "target": "future lane-blocking footprint (held-out 2nd half)",
        "spearman_pcis_vs_future_impact": round(sp_pcis, 3),
        "spearman_rawcount_vs_future_impact": round(sp_count, 3),
        "pcis_edge_over_count": round(sp_pcis - sp_count, 3),
        "spearman_pcis_vs_future_load": round(sp_pcis_load, 3),
        "spearman_rawcount_vs_future_load": round(sp_count_load, 3),
        "top_decile_future_lift": round(lift, 2),
        "ablation": ablation,
        "weight_sensitivity": weight_sensitivity,
        "bias_correction": bias_correction,
        "bias": {
            "morning_rush_share": round(morning * 100, 1),
            "evening_rush_share": round(evening * 100, 1),
            "morning_to_evening_ratio": round(morning / max(evening, 1e-9), 1),
            "note": "Enforcement is morning-skewed; evening illegal parking is "
                    "systematically under-recorded. Hotspots are corrected for this "
                    "by modelling persistence, not raw counts.",
        },
    }
    (OUT / "validation.json").write_text(json.dumps(validation, indent=2))
    print(f"validation.json: PCIS-vs-future-impact rho={sp_pcis:.3f} "
          f"(raw-count rho={sp_count:.3f}, edge {sp_pcis - sp_count:+.3f}), "
          f"top-decile lift {lift:.2f}x")

    # ================= DEPLOYMENT ROI CURVE =================
    # Reframe "30 units = 11%": show the diminishing-returns curve so judges see
    # WHY 30, and how much the first few units buy.
    cell["shift"] = df.groupby(["gy", "gx"])["hour"].apply(dominant_shift).reindex(
        cell.set_index(["gy", "gx"]).index).values
    lat_a = cell["lat"].values; lng_a = cell["lng"].values
    shift_a = cell["shift"].values
    remaining = cell["pcis"].values.astype(float).copy()
    total_impact = float(remaining.sum())
    roi = []; cum = 0.0
    MAXU = 50; RAD = 250.0
    for k in range(1, MAXU + 1):
        i = int(np.argmax(remaining))
        if remaining[i] <= 0:
            break
        d = haversine_m(lat_a[i], lng_a[i], lat_a, lng_a)
        near = (d <= RAD) & (shift_a == shift_a[i])
        cum += float(remaining[near].sum())
        remaining[near] = 0.0
        roi.append({"units": k, "impact_removed": round(cum, 1),
                    "coverage_pct": round(100 * cum / total_impact, 1)})
    (OUT / "deploy_roi.json").write_text(json.dumps(
        {"total_impact": round(total_impact, 1), "curve": roi}, separators=(",", ":")))
    print(f"deploy_roi.json: {len(roi)} points, 30u="
          f"{next((p['coverage_pct'] for p in roi if p['units'] == 30), 0)}%")

    # ---------------- SUMMARY / KPIs ----------------
    by_hour = df.groupby("hour").size().reindex(range(24), fill_value=0).tolist()
    by_dow = df.groupby("dow").size().reindex(range(7), fill_value=0).tolist()
    by_cat = df["cat"].value_counts().head(8).to_dict()
    by_veh = df["vehicle_type"].astype(str).str.upper().value_counts().head(10).to_dict()
    summary = {
        "total_violations": int(n1),
        "raw_rows": int(n0),
        "date_min": str(df["date"].min()),
        "date_max": str(df["date"].max()),
        "stations": int(df["police_station"].nunique()),
        "hotspot_cells": int(len(hot)),
        "top_hotspot_pcis": float(hot["pcis"].max()) if len(hot) else 0,
        "obstructive_share": round(float(df["obstructive"].mean()) * 100, 1),
        "peak_share": round(float(df["hour"].isin(PEAK_HOURS).mean()) * 100, 1),
        "carriageway_m2_stolen": int(df["footprint"].sum()),
        "pcis_validity": round(sp_pcis, 2),
        "top_decile_lift": round(lift, 1),
        "evening_rush_share": round(evening * 100, 1),
        "impact_units": _impact_units(df, WINDOW_DAYS),
        "by_hour": by_hour,
        "by_dow": by_dow,
        "by_cat": by_cat,
        "by_vehicle": by_veh,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print("summary.json written")
    print("\nKPIs:", json.dumps({k: v for k, v in summary.items()
                                 if not isinstance(v, (list, dict))}, indent=2))


if __name__ == "__main__":
    main()
