"""
01_data_engine.py  —  Kaggle data engine (CPU; light, run first)

Cleans the raw parking-violation CSV and builds the H3-indexed,
time-featured event table that every downstream model consumes.

KAGGLE SETUP
------------
1. Add the dataset CSV to the notebook  (e.g. /kaggle/input/blr-parking/...)
2. First cell:
       !pip install -q h3
3. Set RAW below to the input path, then run.

Outputs (to /kaggle/working/):
    events.parquet   - cleaned, featurized per-violation rows  (+ H3 cell)
    cells_h3.parquet - per-(h3, hour-of-week) aggregates for forecasting
"""
from __future__ import annotations
import ast, re
import numpy as np
import pandas as pd
import h3

RAW = "/kaggle/input/blr-parking/jan to may police violation_anonymized791b166.csv"
OUT = "/kaggle/working"
H3_RES = 10           # ~65 m edge hexagons
LAT = (12.70, 13.30)
LNG = (77.30, 77.90)

FOOTPRINT = {
    "SCOOTER": 1.2, "MOPED": 1.0, "MOTOR CYCLE": 1.4, "MOTORCYCLE": 1.4,
    "PASSENGER AUTO": 4.0, "GOODS AUTO": 4.5, "CAR": 7.5, "MAXI-CAB": 9.0,
    "VAN": 9.0, "TEMPO": 11.0, "LGV": 12.0, "PRIVATE BUS": 30.0,
    "BUS (BMTC/KSRTC)": 30.0, "TRUCK": 28.0,
}
OBSTRUCTIVE = {
    "PARKING IN A MAIN ROAD", "PARKING ON FOOTPATH", "DOUBLE PARKING",
    "PARKING NEAR ROAD CROSSING", "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL ETC",
    "NO PARKING",
}
PEAK = set(range(8, 12)) | set(range(17, 22))


def parse_violation(s):
    if not isinstance(s, str) or s in ("", "NULL"):
        return []
    try:
        v = ast.literal_eval(s)
        return [str(x).strip().upper() for x in v] if isinstance(v, list) else [str(v).upper()]
    except Exception:
        return [t.strip().upper() for t in re.findall(r'"([^"]+)"', s)]


def main():
    print("Loading ...")
    df = pd.read_csv(RAW, low_memory=False)
    n0 = len(df)

    df["lat"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["lng"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df[df.lat.between(*LAT) & df.lng.between(*LNG)]
    df = df[~df["validation_status"].isin(["rejected", "duplicate"])]

    dt = pd.to_datetime(df["created_datetime"], errors="coerce", utc=True).dt.tz_convert("Asia/Kolkata")
    df = df[dt.notna()]
    df["ts"] = dt
    df["hour"] = dt.dt.hour
    df["dow"] = dt.dt.dayofweek
    df["how"] = df["dow"] * 24 + df["hour"]          # hour-of-week 0..167
    df["date"] = dt.dt.date
    df["is_peak"] = df["hour"].isin(PEAK).astype(int)
    df["is_weekend"] = (df["dow"] >= 5).astype(int)

    vt = df["violation_type"].apply(parse_violation)
    df["obstructive"] = vt.apply(lambda L: int(any(x in OBSTRUCTIVE for x in L)))
    df["main_road"] = vt.apply(lambda L: int("PARKING IN A MAIN ROAD" in L))
    df["footprint"] = df["vehicle_type"].astype(str).str.upper().str.strip().map(FOOTPRINT).fillna(6.0)
    df["has_junction"] = (~df["junction_name"].isin(["No Junction", "NULL"]) & df["junction_name"].notna()).astype(int)

    print(f"H3 indexing @res{H3_RES} ...")
    df["h3"] = [h3.latlng_to_cell(la, lo, H3_RES) for la, lo in zip(df.lat, df.lng)]

    keep = ["h3", "lat", "lng", "ts", "hour", "dow", "how", "date", "is_peak",
            "is_weekend", "obstructive", "main_road", "footprint", "has_junction",
            "police_station", "junction_name", "vehicle_type"]
    df[keep].to_parquet(f"{OUT}/events.parquet", index=False)
    print(f"events.parquet: {n0} -> {len(df)} rows")

    # ---- per (h3, hour-of-week) aggregate for forecasting ----
    g = df.groupby(["h3", "how"])
    cells = pd.DataFrame({
        "n": g.size(),
        "load": g["footprint"].sum(),
        "obstructive": g["obstructive"].sum(),
        "main_road": g["main_road"].sum(),
        "lat": g["lat"].mean(),
        "lng": g["lng"].mean(),
        "has_junction": g["has_junction"].max(),
    }).reset_index()
    cells.to_parquet(f"{OUT}/cells_h3.parquet", index=False)
    print(f"cells_h3.parquet: {len(cells)} (h3 x how) rows, {df.h3.nunique()} distinct cells")


if __name__ == "__main__":
    main()
