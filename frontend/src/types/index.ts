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
  payment_channel: string;
  reported_at: string;
  incident_time: string;
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  risk_score: number;
  prediction_status: 'PENDING' | 'COMPLETED' | 'IN_PROGRESS';
  case_status: 'ACTIVE' | 'UNDER_INVESTIGATION' | 'ALERTED' | 'RESOLVED';
  created_at: string;
}

export interface PredictionLocationItem {
  rank: number;
  location_name: string;
  probability: number;
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM';
  distance_km: number;
  reasoning: string;
  latitude: number;
  longitude: number;
}

export interface Prediction {
  prediction_id: number;
  complaint_id: number;
  complaint_number: string;
  where_location: string;
  when_window: string;
  risk_score: number;
  risk_percentage: number;
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
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
  created_at: string;
}

export interface ExplanationFactor {
  name: string;
  contribution_percentage: number;
  description: string;
}

export interface Explanation {
  prediction_id: number;
  complaint_number: string;
  factors: ExplanationFactor[];
  narrative: string;
  disclaimer: string;
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
  time_window_coverage: string;
  metrics_comparison: MetricComparisonItem[];
  feature_importances: FeatureImportanceItem[];
}
