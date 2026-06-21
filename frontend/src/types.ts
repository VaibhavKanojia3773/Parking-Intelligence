export interface Points {
  lat: number[];
  lng: number[];
  h: number[]; // hour 0-23
  d: number[]; // day of week 0-6
  c: number[]; // category code
  w: number[]; // footprint weight
  cat_labels: string[];
}

export interface Hotspot {
  rank: number;
  lat: number;
  lng: number;
  n: number;
  vol_w: number;
  obstructive: number;
  peak: number; // %
  chronicity: number;
  pcis: number;
  lane_m: number;
  top_ps: string;
  top_junction: string;
}

export interface Station {
  police_station: string;
  violations: number;
  vol_w: number;
  obstructive: number;
  peak_share: number;
  lat: number;
  lng: number;
}

export interface Summary {
  total_violations: number;
  raw_rows: number;
  date_min: string;
  date_max: string;
  stations: number;
  hotspot_cells: number;
  top_hotspot_pcis: number;
  obstructive_share: number;
  peak_share: number;
  carriageway_m2_stolen: number;
  pcis_validity: number;
  top_decile_lift: number;
  evening_rush_share: number;
  impact_units: {
    assumptions: string;
    lane_km_hours_total: number;
    lane_km_hours_per_day: number;
    peak_lane_m_blocked: number;
  };
  by_hour: number[];
  by_dow: number[];
  by_cat: Record<string, number>;
  by_vehicle: Record<string, number>;
}

export interface ForecastCell {
  h3: string;
  lat: number;
  lng: number;
  pred: number;
  actual: number;
  rank: number;
}

export interface ForecastMetrics {
  horizon_days: number;
  "Precision@50": number;
  "NDCG@50": number;
  ROC_AUC: number;
  next_day_ROC_AUC: number;
  folds: number;
  cells: number;
  model: string;
}

export interface DeployUnit {
  unit: number;
  h3: string;
  lat: number;
  lng: number;
  shift: string;
  anchor_pcis: number;
  cells_cleared: number;
  impact_removed: number;
  police_station: string;
}

export interface DeployPlan {
  units: number;
  cover_radius_m: number;
  hotspots_total: number;
  total_impact: number;
  impact_removed: number;
  coverage_pct: number;
  roster: DeployUnit[];
}

export interface Ablation {
  component: string;
  validity_without: number;
  contribution: number;
}
export interface Validation {
  n_cells_tested: number;
  target: string;
  spearman_pcis_vs_future_impact: number;
  spearman_rawcount_vs_future_impact: number;
  pcis_edge_over_count: number;
  spearman_pcis_vs_future_load: number;
  spearman_rawcount_vs_future_load: number;
  top_decile_future_lift: number;
  ablation: Ablation[];
  weight_sensitivity: {
    perturbation: string;
    mean_rank_spearman: number;
    min_rank_spearman: number;
    mean_top50_overlap: number;
  };
  bias_correction: {
    test: string;
    yield_stability_spearman: number;
    n_cells: number;
    note: string;
  };
  bias: {
    morning_rush_share: number;
    evening_rush_share: number;
    morning_to_evening_ratio: number;
    note: string;
  };
}
export interface DeployRoi {
  total_impact: number;
  curve: { units: number; impact_removed: number; coverage_pct: number }[];
}

export interface DetectionCell {
  lat: number; lng: number; n: number; sessions: number;
  intensity: number; demand_score: number; pcis: number;
  exposure_class: string; top_ps: string; top_junction: string;
}
export interface Detection {
  summary: Record<string, number>;
  median_sessions: number;
  top_demand: DetectionCell[];
  under_enforced: DetectionCell[];
}

export interface Corridor {
  road: string; n: number; load: number; obstr_share: number;
  peak: number; impact: number; top_ps: string; lat: number; lng: number;
}

export interface WorkOrder {
  loc: string; lat: number; lng: number; severity: number;
  window: string; revisit: string; lane_m: number; target_violation: string;
  target_vehicle: string; cases: number;
}
export interface StationTasking {
  station: string; hotspots: number; top_severity: number;
  orders: number; shifts: Record<string, WorkOrder[]>;
}
export interface Tasking {
  generated_for_window_days: number;
  stations: StationTasking[];
}

export type LayerId = "hex" | "heat" | "columns" | "scatter";
export type RailTab = "hotspots" | "impact" | "deploy" | "forecast";
