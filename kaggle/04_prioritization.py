"""
04_prioritization.py  —  Enforcement deployment optimizer

Turns scores into an ACTION PLAN. Given a limited number of patrol units and
shift hours, decide which hotspots to cover, in which time window, to remove
the most parking-induced congestion per unit of effort.

Two things make this realistic:
  1. Impact is time-sliced — a cell only "earns" its PCIS during the hours it
     is actually active (its peak window), so a unit is assigned a cell *and*
     a shift.
  2. Spatial spacing — covering two adjacent cells wastes a unit, so we apply
     a coverage radius (one unit clears nearby cells).

Greedy marginal-gain selection (submodular coverage) gives a near-optimal,
explainable roster — exactly what a control room can act on.

KAGGLE SETUP: needs pcis.json (02) and events.parquet (01).
Output: deployment_plan.json  (frontend-ready roster + expected impact removed)
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

PCIS = "/kaggle/working/pcis.json"
EVENTS = "/kaggle/working/events.parquet"
OUT = "/kaggle/working"

N_UNITS = 30            # patrol units available per shift
COVER_RADIUS_M = 250    # one unit clears parking within this radius
SHIFTS = {"morning": range(7, 12), "afternoon": range(12, 17),
          "evening": range(17, 22), "night": list(range(22, 24)) + list(range(0, 7))}


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1); dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def dominant_shift(hours: pd.Series) -> str:
    best, bn = "morning", -1
    for name, hrs in SHIFTS.items():
        c = hours.isin(list(hrs)).sum()
        if c > bn:
            bn, best = c, name
    return best


def main():
    cells = pd.read_json(PCIS)
    ev = pd.read_parquet(EVENTS)

    # attach each cell's dominant active shift (when its impact is real)
    sh = ev.groupby("h3")["hour"].apply(dominant_shift).rename("shift")
    cells = cells.merge(sh, on="h3", how="left").fillna({"shift": "morning"})

    lat = cells["lat"].values; lng = cells["lng"].values
    impact = cells["pcis"].values.astype(float)
    remaining = impact.copy()
    chosen = []

    for _ in range(N_UNITS):
        i = int(np.argmax(remaining))
        if remaining[i] <= 0:
            break
        # marginal gain = this cell + spillover it clears within radius (same shift)
        d = haversine(lat[i], lng[i], lat, lng)
        near = (d <= COVER_RADIUS_M) & (cells["shift"].values == cells["shift"].values[i])
        gain = float(remaining[near].sum())
        chosen.append({
            "unit": len(chosen) + 1,
            "h3": cells.iloc[i]["h3"],
            "lat": round(float(lat[i]), 5),
            "lng": round(float(lng[i]), 5),
            "shift": cells.iloc[i]["shift"],
            "anchor_pcis": round(float(impact[i]), 1),
            "cells_cleared": int(near.sum()),
            "impact_removed": round(gain, 1),
            "police_station": cells.iloc[i].get("top_ps", "—"),
        })
        remaining[near] = 0.0  # covered

    total = float(impact.sum())
    removed = float(sum(c["impact_removed"] for c in chosen))
    plan = {
        "units": N_UNITS,
        "cover_radius_m": COVER_RADIUS_M,
        "hotspots_total": int(len(cells)),
        "total_impact": round(total, 1),
        "impact_removed": round(removed, 1),
        "coverage_pct": round(100 * removed / total, 1) if total else 0,
        "roster": chosen,
    }
    json.dump(plan, open(f"{OUT}/deployment_plan.json", "w"), indent=2)
    print(f"{N_UNITS} units cover {plan['coverage_pct']}% of total parking-congestion "
          f"impact across {len(cells)} hotspots")
    for c in chosen[:10]:
        print(f"  Unit {c['unit']:>2} [{c['shift']:<9}] {c['police_station']:<16} "
              f"PCIS {c['anchor_pcis']:>5}  clears {c['cells_cleared']:>2} cells "
              f"(+{c['impact_removed']})")


if __name__ == "__main__":
    main()
