export type UserRole = 
  | 'I4C_ADMIN' 
  | 'STATE_LEA' 
  | 'DISTRICT_LEA' 
  | 'BANK_OFFICER' 
  | 'ANALYST' 
  | 'AUDITOR';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  badge_number: string;
  organization_name?: string;
  is_active: boolean;
}

export interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
}

export interface Complaint {
  id: number;
  complaint_number: string;
  fraud_type: string;
  amount: number;
  victim_name?: string;
  victim_phone?: string;
  victim_location: string;
  state: string;
  district: string;
  locality?: string | null;
  payment_channel: string;
  reported_at: string;
  incident_time: string;
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'PENDING_EVALUATION' | string;
  risk_score: number | null;
  prediction_status: 'NOT RUN' | 'AVAILABLE' | 'PROCESSING' | 'UNAVAILABLE' | 'PENDING' | 'COMPLETED' | 'IN_PROGRESS' | string;
  alert_status?: 'NOT GENERATED' | 'GENERATED' | 'ACKNOWLEDGED' | string;
  case_status: 'ACTIVE' | 'UNDER_INVESTIGATION' | 'ALERTED' | 'RESOLVED' | string;
  victim_lat?: number | null;
  victim_lon?: number | null;
  description?: string | null;
  provenance_mode?: string | null;
  victim_bank?: string | null;
  beneficiary_bank?: string | null;
  beneficiary_id?: string | null;
  transaction_ref?: string | null;
  transaction_time?: string | null;
  ifsc_code?: string | null;
  upi_id?: string | null;
  created_at: string;
  source_scenario?: string | null;
  scenario_link_status?: string | null;
  linked_account_count?: number;
  available_transaction_count?: number;
}

export interface ComplaintCreate {
  fraud_type: string;
  amount: number;
  victim_name: string;
  incident_time?: string;
  reported_at?: string;
  state?: string;
  district: string;
  locality?: string;
  victim_location?: string;
  payment_channel: string;
  victim_bank?: string;
  beneficiary_bank?: string;
  beneficiary_id: string;
  transaction_ref: string;
  transaction_time?: string;
  description?: string;
  victim_lat?: number | null;
  victim_lon?: number | null;
  beneficiary_account?: string;
  beneficiary_upi?: string;
  ifsc_code?: string;
  phone_or_merchant?: string;
  additional_refs?: string;
}

export interface PredictionLocationItem {
  rank: number;
  location_name: string;
  cluster_id?: number | null;
  cluster_name?: string;
  zone?: string;
  district?: string;
  state?: string;
  probability: number;
  ml_probability?: number;
  risk_level: string;
  risk_band?: string;
  distance_km: number;
  reasoning: string;
  latitude: number;
  longitude: number;
}

export interface Prediction {
  prediction_id: number;
  id?: number;
  complaint_id: number;
  complaint_number: string;
  where_location: string;
  primary_cluster_id?: number | null;
  when_window: string;
  risk_score: number;
  risk_percentage: number;
  risk_level: string;
  risk_band?: string;
  intervention_priority: number;
  priority_level: string;
  why_summary: string;
  confidence_score: number;
  ml_score: number;
  graph_score: number;
  geo_score: number;
  temporal_score: number;
  top_locations: PredictionLocationItem[];
  prediction_mode: string;
  model_version: string;
  operational_scope?: string | null;
  time_prediction?: {
    predicted_minutes_to_cashout?: number | null;
    model_version?: string | null;
    prediction_reference_time?: string | null;
    reference_basis?: string;
    operational_window?: string;
    window_start?: string | null;
    window_end?: string | null;
    predicted_cashout_at?: string | null;
    window_status?: 'upcoming' | 'active' | 'elapsed';
    window_basis?: string;
    uncertainty_minutes?: number | null;
  } | null;
  time_model_version?: string | null;
  score_note?: string;
  score_type?: string;
  score_label?: string;
  training_data_source?: string;
  analysis_basis?: string;
  dataset_type?: string;
  limitations?: string[];
  candidate_pool_size?: number;
  created_at: string;
}

export interface ExplanationFactor {
  name: string;
  contribution_percentage: number;
  description: string;
}

export interface LimeContribution {
  feature_name: string;
  rule: string;
  weight: number;
  feature_value: number;
  description: string;
}

export interface LimeCandidateExplanation {
  rank: number;
  cluster_id: number;
  location_name: string;
  official_score: number;
  lime_local_prediction: number;
  absolute_approximation_error: number;
  local_fidelity_r2?: number;
  fidelity_status: string;
  positive_contributions: LimeContribution[];
  negative_contributions: LimeContribution[];
  summary_statement?: string;
}

export interface Explanation {
  prediction_id: number;
  complaint_number: string;
  prediction_mode?: string;
  model_version?: string;
  location_model_version?: string;
  explanation_status?: string;
  explanation_method?: string;
  explainer_version?: string;
  feature_schema_version?: string;
  generated_at?: string;
  overall_fidelity_status?: string;
  mean_local_fidelity_r2?: number;
  background_sample_size?: number;
  background_seed?: number;
  top3_explanations?: LimeCandidateExplanation[];
  factors: ExplanationFactor[];
  narrative: string;
  disclaimer: string;
}

export interface PredictionAuditVerification {
  prediction_id: number;
  complaint_number: string;
  verified: boolean;
  status: 'VERIFIED' | 'HASH_MISMATCH' | 'ANCHOR_NOT_FOUND' | 'FABRIC_UNAVAILABLE' | string;
  computed_hash?: string;
  ledger_hash?: string;
  fabric_tx_id?: string;
  anchored_at?: string;
  error?: string;
}

export interface CytoscapeNodeData {
  id: string;
  label: string;
  node_type: 'victim' | 'account' | 'mule' | 'atm' | 'cluster' | 'bank';
  masked_id: string;
  bank: string;
  risk_score: number;
  amount_received: number;
  amount_sent: number;
  connections_count: number;
  previous_complaints: number;
  is_hotspot: boolean;
}

export interface CytoscapeEdgeData {
  id: string;
  source: string;
  target: string;
  amount: number;
  channel: string;
  hop: number;
  is_suspicious: boolean;
}

export interface GraphData {
  nodes: { data: CytoscapeNodeData }[];
  edges: { data: CytoscapeEdgeData }[];
  metrics: {
    node_count: number;
    edge_count: number;
    max_hop: number;
    branching_factor: number;
    connected_components: number;
    high_risk_mule_nodes: number;
    pagerank?: Record<string, number>;
    betweenness?: Record<string, number>;
    target_cashout_cluster?: string;
  };
}

export interface HotspotCluster {
  id: number;
  cluster_name: string;
  city: string;
  district: string;
  state: string;
  latitude: number;
  longitude: number;
  radius_km: number;
  risk_score: number;
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM';
  active_cases: number;
  amount_at_risk: number;
  atm_count: number;
  expected_window: string;
  fraud_type: string;
}

export interface ATMLocationItem {
  id: number;
  atm_code: string;
  bank_name: string;
  address: string;
  city: string;
  district: string;
  latitude: number;
  longitude: number;
  cash_available: boolean;
  risk_rating: string;
  cluster_name?: string;
}

export interface AlertItem {
  id: number;
  complaint_id: number;
  complaint_number: string;
  prediction_id?: number;
  title: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  location_name: string;
  risk_score: number;
  expected_window: string;
  amount_at_risk: number;
  status: 'NEW' | 'ACKNOWLEDGED' | 'ACTION_INITIATED' | 'RESOLVED';
  acknowledged_by?: string;
  acknowledged_at?: string;
  action_notes?: string;
  created_at: string;
}

export interface AnalyticsOverview {
  active_complaints: number;
  critical_risk_cases: number;
  predicted_cashout_events: number;
  high_risk_districts: number;
  total_amount_at_risk: number;
  alerts_acknowledged_today: number;
  fraud_types: { name: string; count: number; amount: number; percentage: number }[];
  cases_over_time: { date: string; cases: number; risk: number }[];
  hourly_risk: { hour: string; risk: number; cashouts: number }[];
  regional_risk: { district: string; risk_index: number; active_clusters: number; amount: number }[];
}

export interface DashboardKpis {
  active_complaints: number;
  high_risk_predictions: number;
  active_alerts: number;
  acknowledged_alerts: number;
  total_amount_at_risk: number;
  avg_response_time_minutes: number | null;
  response_time_label: string;
}

export interface RiskDistribution {
  HIGH: number;
  MEDIUM: number;
  LOW: number;
  CRITICAL: number;
  total: number;
}

export interface PredictionModeDistribution {
  trained_ml: number;
  deterministic_demo: number;
  total: number;
}

export interface RecentComplaintItem {
  id: number;
  complaint_number: string;
  fraud_type: string;
  amount: number;
  district?: string | null;
  state?: string | null;
  victim_location?: string | null;
  case_status: string;
  reported_at?: string | null;
  created_at?: string | null;
  prediction_available: boolean;
  latest_prediction_id?: number | null;
  latest_risk_level?: string | null;
  latest_mode?: string | null;
  latest_rank1_location?: string | null;
}

export interface RecentPredictionItem {
  id: number;
  complaint_id: number;
  complaint_number: string;
  prediction_mode: string;
  model_version: string;
  risk_level: string;
  risk_score: number;
  rank1_location?: string | null;
  rank1_cluster_id?: number | null;
  operational_window: string;
  created_at: string;
}

export interface RecentAlertItem {
  id: number;
  complaint_id: number;
  complaint_number: string;
  prediction_id?: number | null;
  title: string;
  severity: string;
  location_name: string;
  risk_score: number;
  expected_window: string;
  amount_at_risk: number;
  status: string;
  created_at: string;
}

export interface DashboardSummary {
  generated_at: string;
  kpis: DashboardKpis;
  risk_distribution: RiskDistribution;
  mode_distribution: PredictionModeDistribution;
  fraud_type_distribution: { name: string; count: number; amount: number; percentage: number }[];
  cases_over_time: { date: string; cases: number; risk: number }[];
  hourly_risk?: { hour: string; risk: number; cashouts: number }[];
  regional_distribution: { district: string; cases: number; risk_index: number; amount: number }[];
  recent_complaints: RecentComplaintItem[];
  recent_predictions: RecentPredictionItem[];
  recent_alerts: RecentAlertItem[];
}

export interface AuditLogItem {
  id: number;
  officer_name: string;
  role: string;
  action: string;
  case_number?: string;
  details?: string;
  ip_address: string;
  created_at: string;
}

export interface MetricComparisonItem {
  metric: string;
  baseline: string;
  cybershield: string;
  delta: string;
  unit?: string;
}

export interface FeatureImportanceItem {
  feature: string;
  importance: number;
}

export interface ModelPerformanceData {
  prediction_mode: string;
  current_prediction_mode: string;
  model_version: string;
  location_model_version?: string;
  time_model_version?: string;
  location_features_count?: number;
  time_features_count?: number;
  calibration_method?: string;
  geographic_focus?: string;
  cluster_count?: number;
  provider_version: string;
  dataset_type: string;
  model_class: string;
  calibrator_class?: string;
  training_samples: number;
  validation_samples: number;
  test_samples: number;
  cold_start_test_samples?: number;
  evaluation_label: string;
  dataset_split: string;
  model_architecture: string;
  runtime_notice: string;
  production_notice: string;
  geographic_disclaimer: string;
  natural_candidate_recall: string;
  'Recall@1': string;
  'Recall@3': string;
  'Recall@5': string;
  'Precision@3': string;
  MRR: number;
  median_cluster_centroid_distance_error_km: string;
  within_5km: string;
  within_10km: string;
  within_25km: string;
  Brier_score: number;
  cold_start_candidate_recall?: string;
  cold_start_recall_at_1?: string;
  cold_start_recall_at_3?: string;
  time_MAE_minutes: string;
  time_median_absolute_error: string;
  time_window_coverage?: string;
  active_clusters_count?: number;
  atm_coverage_count?: number;
  official_production_model?: string;
  research_experiment?: string;
  research_status?: string;
  promotion_gate?: string;
  research_ablation_gain?: string;
  research_decision_rationale?: string;
  metrics_comparison: MetricComparisonItem[];
  feature_importances: FeatureImportanceItem[];
}
