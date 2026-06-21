"""
02_impact_pcis_osm.py  —  Parking Congestion Impact Score (OSM-enriched)

THE DIFFERENTIATOR. The dataset has no traffic-flow column, so we *quantify*
each hotspot's impact on flow with a physically-grounded proxy:

    occupancy = parked carriageway area / available carriageway area

Available carriageway width comes from real OpenStreetMap road geometry
(highway class + lane count). A scooter on a 6-lane arterial barely matters;
a car double-parked on a 2-lane road at a junction is a chokepoint. PCIS
captures exactly that difference.

PCIS (0..100) = weighted blend of percentile-normalized:
    occupancy (carriageway stolen / available)   0.34
    road criticality (arterial > local)          0.18
    junction proximity (closer = worse)          0.16
    lane-blocking violation share                0.14
    peak-hour concentration                      0.12
    chronicity (persistent vs one-off)           0.06

KAGGLE SETUP
    Needs events.parquet (01). Enable INTERNET in notebook settings.
    !pip install -q osmnx scikit-learn
    (Falls back to a violation-derived road proxy if OSM is unavailable.)

Output: pcis.json  (frontend-ready ranked hotspots with impact breakdown)
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

EVENTS = "/kaggle/working/events.parquet"
OUT = "/kaggle/working"
MIN_N = 20

# default lanes by OSM highway class -> carriageway width (m), one direction
ROAD_WIDTH = {"motorway": 14, "trunk": 12, "primary": 10.5, "secondary": 8,
              "tertiary": 6.5, "residential": 5.5, "unclassified": 5.5, "service": 4}
ROAD_CRIT = {"motorway": 1.0, "trunk": 0.95, "primary": 0.9, "secondary": 0.7,
             "tertiary": 0.5, "residential": 0.3, "unclassified": 0.3, "service": 0.2}
PEAK = set(range(8, 12)) | set(range(17, 22))


def pct(s):  # outlier-safe 0..1
    return s.rank(pct=True).fillna(0.0)


def enrich_with_osm(cells: pd.DataFrame) -> pd.DataFrame:
    """Attach nearest-road class, carriageway width, junction distance."""
    try:
        import osmnx as ox
        from scipy.spatial import cKDTree
        print("Downloading Bengaluru drive network from OSM ...")
        G = ox.graph_from_bbox(13.30, 12.70, 77.90, 77.30, network_type="drive")
        Gp = ox.project_graph(G)
        edges = ox.graph_to_gdfs(G, nodes=False).reset_index()

        def hclass(h):
            h = h[0] if isinstance(h, list) else h
            return h if h in ROAD_WIDTH else "residential"
        edges["cls"] = edges["highway"].apply(hclass)
        edges["mid"] = edges.geometry.interpolate(0.5, normalized=True)
        ex = edges["mid"].x.values; ey = edges["mid"].y.values
        etree = cKDTree(np.c_[ex, ey])

        # junction nodes = degree >= 3
        deg = dict(G.degree())
        nodes = ox.graph_to_gdfs(G, edges=False)
        jn = nodes[[deg.get(i, 0) >= 3 for i in nodes.index]]
        jtree = cKDTree(np.c_[jn.geometry.x.values, jn.geometry.y.values])

        import pyproj
        crs = Gp.graph["crs"]
        tf = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        cx, cy = tf.transform(cells.lng.values, cells.lat.values)

        _, ei = etree.query(np.c_[cx, cy], k=1)
        cells["road_cls"] = edges.iloc[ei]["cls"].values
        cells["lanes"] = pd.to_numeric(
            edges.iloc[ei]["lanes"].apply(lambda x: x[0] if isinstance(x, list) else x),
            errors="coerce").values
        jd, _ = jtree.query(np.c_[cx, cy], k=1)
        cells["junction_dist_m"] = jd
        print("OSM enrichment OK")
    except Exception as e:
        print(f"[OSM unavailable: {e}] -> violation-derived road proxy")
        cells["road_cls"] = np.where(cells["main_road_share"] > 0.15, "primary", "residential")
        cells["lanes"] = np.nan
        cells["junction_dist_m"] = np.where(cells["has_junction"] > 0, 60.0, 300.0)

    cells["width_m"] = cells["road_cls"].map(ROAD_WIDTH).fillna(5.5)
    # widen by extra lanes when known
    extra = (cells["lanes"].fillna(2) - 2).clip(lower=0) * 3.0
    cells["width_m"] = cells["width_m"] + extra
    cells["road_crit"] = cells["road_cls"].map(ROAD_CRIT).fillna(0.3)
    return cells


def main():
    ev = pd.read_parquet(EVENTS)
    ev["date"] = pd.to_datetime(ev["date"])
    g = ev.groupby("h3")
    cells = pd.DataFrame({
        "n": g.size(),
        "load": g["footprint"].sum(),
        "obstructive_share": g["obstructive"].mean(),
        "main_road_share": g["main_road"].mean(),
        "peak_share": g["is_peak"].mean(),
        "chronicity": g["date"].nunique(),
        "has_junction": g["has_junction"].max(),
        "lat": g["lat"].mean(), "lng": g["lng"].mean(),
        "top_ps": g["police_station"].agg(lambda s: s.value_counts().idxmax()),
    }).reset_index()
    cells = cells[cells["n"] >= MIN_N].copy()
    print("hotspot cells:", len(cells))

    cells = enrich_with_osm(cells)

    # H3 res10 cell ~ 65m edge; assume one road segment ~110 m through the cell
    seg_len = 110.0
    avail_area = (cells["width_m"] * seg_len).clip(lower=50)
    cells["occupancy"] = (cells["load"] / avail_area).clip(upper=2.0)  # parked m2 / road m2

    # junction proximity score: 1 at junction, decays to 0 by ~250 m
    cells["junc_prox"] = np.exp(-cells["junction_dist_m"] / 120.0)

    cells["s_occ"]  = pct(cells["occupancy"])
    cells["s_crit"] = cells["road_crit"]
    cells["s_junc"] = cells["junc_prox"]
    cells["s_obst"] = pct(cells["obstructive_share"])
    cells["s_peak"] = cells["peak_share"]
    cells["s_chr"]  = pct(cells["chronicity"])
    cells["pcis"] = (100 * (
        0.34 * cells["s_occ"] + 0.18 * cells["s_crit"] + 0.16 * cells["s_junc"] +
        0.14 * cells["s_obst"] + 0.12 * cells["s_peak"] + 0.06 * cells["s_chr"]
    )).round(1)

    cells = cells.sort_values("pcis", ascending=False).reset_index(drop=True)
    cells["rank"] = cells.index + 1
    cols = ["rank", "h3", "lat", "lng", "n", "load", "occupancy", "road_cls",
            "width_m", "junction_dist_m", "peak_share", "chronicity", "pcis", "top_ps"]
    out = cells[cols].round({"lat": 5, "lng": 5, "load": 0, "occupancy": 3,
                             "width_m": 1, "junction_dist_m": 0, "peak_share": 3})
    out.to_json(f"{OUT}/pcis.json", orient="records")
    print("Saved pcis.json")
    print(out.head(10).to_string(index=False))

    # ---- EXTERNAL convergent validity: PCIS vs road betweenness centrality ----
    # Betweenness = how many shortest paths cross a road = independent structural
    # measure of traffic importance (not used inside PCIS). If PCIS is meaningful,
    # high-impact parking should sit on structurally busier roads.
    try:
        import osmnx as ox, networkx as nx
        from scipy.spatial import cKDTree
        print("Computing node betweenness centrality (external validity) ...")
        G = ox.graph_from_bbox(13.30, 12.70, 77.90, 77.30, network_type="drive")
        # approximate betweenness with k samples (full is O(VE), too slow citywide)
        node_bc = nx.betweenness_centrality(G, k=min(500, G.number_of_nodes()),
                                            weight="length", seed=1)
        nodes = ox.graph_to_gdfs(G, edges=False)
        node_ids = list(nodes.index)
        tree = cKDTree(np.c_[nodes.geometry.x.values, nodes.geometry.y.values])
        _, ni = tree.query(np.c_[cells.lng.values, cells.lat.values], k=1)
        cells["betweenness"] = [node_bc[node_ids[i]] for i in ni]
        rho = float(cells["pcis"].corr(cells["betweenness"], method="spearman"))
        json.dump({"spearman_pcis_vs_betweenness": round(rho, 3),
                   "n": int(len(cells)),
                   "interpretation": "positive rho = high-PCIS parking sits on "
                                     "structurally busier roads (convergent validity)"},
                  open(f"{OUT}/pcis_external_validity.json", "w"), indent=2)
        print(f"External validity: PCIS vs betweenness Spearman rho = {rho:.3f}")
    except Exception as e:
        print(f"[external validity skipped: {e}]")


if __name__ == "__main__":
    main()
