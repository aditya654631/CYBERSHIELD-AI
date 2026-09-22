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
  state?: string;
  district?: string;
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
  disputed_amount?: number;
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
  region_id?: string | null;
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
  demo_mode?: boolean;
  region_id?: string;
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
  score_label?: string;
  operational_priority?: string;
  operational_priority_basis?: string | null;
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
  version_number?: number;
  parent_prediction_id?: number | null;
  analysis_as_of?: string | null;
  analysis_purpose?: 'OPERATIONAL' | 'HISTORICAL_REPLAY' | string;
  input_fingerprint?: string | null;
  discrepancy_detected?: boolean;
  created_at: string;
}

export interface PredictionVersionSummary {
  prediction_id: number;
  complaint_id: number;
  version_number: number;
  parent_prediction_id?: number | null;
  analysis_as_of?: string | null;
  analysis_purpose?: 'OPERATIONAL' | 'HISTORICAL_REPLAY' | string;
  created_at: string;
  primary_cluster_id?: number | null;
  primary_location_name?: string | null;
  risk_score: number;
  risk_level: string;
  operational_window?: string | null;
  input_fingerprint?: string | null;
  discrepancy_detected: boolean;
}

export interface Transaction {
  id: number;
  transaction_ref: string;
  sender_account: string;
  receiver_account: string;
  sender_bank: string;
  receiver_bank: string;
  amount: number;
  payment_channel: string;
  timestamp: string;
  hop_number: number;
  status: string;
  suspicious_flag: boolean;
  context_type?: string;
  source_scenario?: string | null;
  received_at?: string | null;
  source_system?: string;
  dedup_key?: string | null;
  analysis_status?: string;
  prediction_id?: number | null;
  is_reversal?: boolean;
  correction_of_ref?: string | null;
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
  friendly_label?: string;
  category?: string;
  formatted_value?: string;
  direction?: 'SUPPORTING' | 'OPPOSING';
  contribution_share?: number;
  honest_explanation?: string;
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
  mean_local_fidelity_r2?: number | null;
  background_sample_size?: number | null;
  background_seed?: number | null;
  top3_explanations?: LimeCandidateExplanation[];
  factors: ExplanationFactor[];
  narrative: string;
  disclaimer: string;
  message?: string;
  actionable_next_step?: string;
  is_legacy_prediction?: boolean;
  /** Discriminator for calibrator hash mismatch — set to "CALIBRATOR_HASH_MISMATCH" */
  reason?: string;
  /** Safe display prefix of the snapshot calibrator hash (first 16 chars + "...") */
  snapshot_calibrator_hash_prefix?: string;
  /** Safe display prefix of the current runtime calibrator hash (first 16 chars + "...") */
  runtime_calibrator_hash_prefix?: string;
  cache_identity?: string;
  snapshot_provenance?: boolean;
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
  node_type: 'victim' | 'account' | 'mule' | 'atm' | 'cluster' | 'bank' | 'intermediary' | 'sink';
  masked_id: string;
  bank: string;
  risk_score: number;
  amount_received: number;
  amount_sent: number;
  connections_count: number;
  previous_complaints: number;
  is_hotspot?: boolean;
  is_source?: boolean;
  is_sink?: boolean;
  is_intermediary?: boolean;
  is_potential_mule_indicator?: boolean;
  risk_band?: string;
  display_label?: string;
  hop_level?: number;
  pattern_flags?: Record<string, any>;
}

export interface CytoscapeEdgeData {
  id: string;
  source: string;
  target: string;
  amount: number;
  channel: string;
  hop: number;
  is_suspicious: boolean;
  label?: string;
  timestamp?: string;
  reference?: string;
  total_amount?: number;
  transaction_count?: number;
  pattern_flags?: Record<string, any>;
}

export interface GraphData {
  nodes: { data: CytoscapeNodeData }[];
  edges: { data: CytoscapeEdgeData }[];
  metrics: {
    node_count: number;
    edge_count: number;
    max_hop: number;
    transaction_hop_depth?: number;
    branching_factor: number;
    connected_components: number;
    high_risk_mule_nodes: number;
    withdrawal_count?: number;
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
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string;
  active_cases: number;
  amount_at_risk: number;
  atm_count: number;
  expected_window: string;
  fraud_type: string;

  // Additive fields for Phase 3
  is_active_candidate?: boolean;
  data_basis?: string;
  historical_risk?: number | null;
  candidate_score?: number | null;
  operational_priority?: string | null;
  operational_priority_basis?: string | null;
  associated_complaint_amount?: number;
  window_start?: string | null;
  window_end?: string | null;
  latest_window_end?: string | null;
  window_status?: string | null;
  linked_complaint_numbers?: string[];
  region_id?: string | null;
}

export interface GISOverviewResponse {
  hotspots: HotspotCluster[];
  active_candidates?: HotspotCluster[];
  historical_hotspots?: HotspotCluster[];
  atms: ATMLocationItem[];
  summary: {
    total_hotspots: number;
    total_active_candidates?: number;
    total_historical_hotspots?: number;
    critical_clusters: number;
    total_associated_amount?: number;
    total_unique_active_cases?: number;
    total_monitored_atms: number;
    primary_threat_epicenter: string;
    state: string;
    region_id?: string | null;
    data_basis: string;
    [key: string]: any;
  };
}

export interface GISFilterParams {
  region_id?: string;
  district?: string;
  risk_level?: string;
  crime_category?: string;
  time_basis?: 'predicted_window' | 'complaint_time' | 'incident_time' | string;
  start_time?: string;
  end_time?: string;
}

export interface RegionBounds {
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
}

export interface RegionItem {
  id: string;
  name: string;
  state: string;
  catalog_version: string;
  source: string;
  license: string;
  verification_time?: string | null;
  center: { lat: number; lon: number };
  bounds: RegionBounds;
  cluster_radius_km: number;
  districts: string[];
  total_clusters: number;
  total_atms: number;
  data_completeness_status: 'COMPLETE' | 'PARTIAL' | 'SYNTHETIC_STUB' | string;
  model_support_status: 'MODEL_SUPPORTED' | 'VALIDATION_PENDING' | 'UNSUPPORTED' | string;
  supported_model_version?: string | null;
  is_synthetic: boolean;
  is_active: boolean;
}

export interface GeographyCatalogItem {
  id: number;
  region_id: string;
  catalog_version: string;
  data_type: string;
  record_count: number;
  source: string;
  license: string;
  checksum?: string | null;
  is_active: boolean;
  notes?: string | null;
  created_at: string;
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

export interface NotificationOutboxItem {
  id: number;
  alert_id: number;
  event_type: string;
  prediction_id?: number;
  prediction_version?: number;
  channel: string;
  recipient_role?: string;
  recipient_organization_id?: number;
  recipient_state?: string;
  recipient_district?: string;
  payload?: Record<string, any>;
  status: string;
  attempt_count: number;
  max_attempts: number;
  next_retry_at?: string;
  last_attempt_at?: string;
  last_error?: string;
  worker_id?: string;
  delivered_at?: string;
  acknowledged_at?: string;
  acknowledged_by?: string;
  idempotency_key: string;
  created_at: string;
  updated_at?: string;
}

export interface AlertSyncResponse {
  items: AlertItem[];
  outbox_events: NotificationOutboxItem[];
  synced_at: string;
  cursor: number;
  has_more: boolean;
}

export interface ChannelStatusInfo {
  configured: boolean;
  mode: string;
  details?: Record<string, any>;
  [key: string]: any;
}

export interface AlertChannelsStatusResponse {
  dashboard_websocket?: ChannelStatusInfo;
  email?: ChannelStatusInfo;
  sms?: ChannelStatusInfo;
  partner_webhook?: ChannelStatusInfo;
  timestamp?: string;
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
  status: 'NEW' | 'DELIVERED' | 'ACKNOWLEDGED' | 'ACTION_INITIATED' | 'EXPIRED' | 'SUPERSEDED' | 'RESOLVED' | string;
  acknowledged_by?: string;
  acknowledged_at?: string;
  action_notes?: string;
  superseded_by_prediction_id?: number;
  superseded_at?: string;
  expires_at?: string;
  delivery_status?: string;
  attempt_count?: number;
  next_retry_at?: string;
  last_error?: string;
  channel_delivery_status?: Record<string, {
    status: string;
    attempt_count?: number;
    last_attempt_at?: string;
    delivered_at?: string;
    last_error?: string;
    mode?: string;
    recipient?: string;
  }>;
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

export interface FeatureImportanceItem {
  feature: string;
  importance: number;
  feature_code?: string;
}

export interface MetricComparisonItem {
  metric: string;
  baseline?: string | null;
  cybershield?: string | null;
  delta?: string | null;
  unit?: string | null;
  comparable?: boolean;
  comparability_note?: string | null;
}

export interface RuntimeModelInfo {
  runtime_status: 'TRAINED_READY' | 'DEMO_ACTIVE' | 'LOAD_FAILED' | 'UNAVAILABLE' | string;
  is_loaded: boolean;
  is_available: boolean;
  prediction_mode: string;
  current_prediction_mode: string;
  model_version: string;
  location_model_version?: string | null;
  time_model_version?: string | null;
  algorithm?: string | null;
  model_class?: string | null;
  calibrator_class?: string | null;
  calibration_method?: string | null;
  feature_schema_version?: string | null;
  location_features_count?: number | null;
  time_features_count?: number | null;
  location_artifact_file?: string | null;
  location_artifact_hash?: string | null;
  location_artifact_hash_short?: string | null;
  calibrator_artifact_file?: string | null;
  calibrator_artifact_hash?: string | null;
  calibrator_artifact_hash_short?: string | null;
  load_error?: string | null;
}

export interface ModelEvaluationInfo {
  evaluation_status: 'AVAILABLE' | 'UNAVAILABLE' | 'VERSION_MISMATCH' | 'HASH_MISMATCH' | 'NOT_EVALUATED' | string;
  availability_reason?: string | null;
  evaluated_model_version?: string | null;
  evaluation_timestamp?: string | null;
  dataset_type?: string | null;
  dataset_split?: string | null;
  synthetic_disclosure?: string | null;
  training_samples?: number | null;
  validation_samples?: number | null;
  test_samples?: number | null;
  cold_start_test_samples?: number | null;
  metrics_summary?: Record<string, any>;
}

export interface ResearchModelInfo {
  model_name: string;
  model_type?: string | null;
  status: string;
  promotion_status: string;
  qualification_gate?: string | null;
  observed_gain?: string | null;
  required_gain?: string | null;
  official_production_model?: string | null;
  production_affected: boolean;
  details?: string | null;
}

export interface SavedPredictionProvenance {
  current_runtime_model: string;
  historical_policy: string;
  description: string;
}

export interface ModelPerformanceData {
  prediction_mode: string;
  current_prediction_mode: string;
  model_version: string;
  provider_version: string;
  official_production_model?: string | null;
  location_model_version?: string | null;
  time_model_version?: string | null;
  location_features_count?: number | null;
  time_features_count?: number | null;
  calibration_method?: string | null;
  geographic_focus?: string | null;
  cluster_count?: number | null;
  dataset_type?: string | null;
  model_class?: string | null;
  calibrator_class?: string | null;
  training_samples?: number | null;
  validation_samples?: number | null;
  test_samples?: number | null;
  cold_start_test_samples?: number | null;
  evaluation_label?: string | null;
  dataset_split?: string | null;
  synthetic_disclosure?: string | null;
  model_architecture?: string | null;
  runtime_notice?: string | null;
  production_notice?: string | null;
  geographic_disclaimer?: string | null;
  natural_candidate_recall?: string | null;
  'Recall@1'?: string | null;
  'Recall@3'?: string | null;
  'Recall@5'?: string | null;
  'Precision@3'?: string | null;
  MRR?: number | null;
  median_cluster_centroid_distance_error_km?: string | null;
  within_5km?: string | null;
  within_10km?: string | null;
  within_25km?: string | null;
  Brier_score?: number | null;
  internal_ece?: number | null;
  cold_start_candidate_recall?: string | null;
  cold_start_recall_at_1?: string | null;
  cold_start_recall_at_3?: string | null;
  time_MAE_minutes?: string | null;
  time_median_absolute_error?: string | null;
  time_window_coverage?: string | null;
  active_clusters_count?: number | null;
  atm_coverage_count?: number | null;
  research_experiment?: string | null;
  research_status?: string | null;
  promotion_gate?: string | null;
  research_ablation_gain?: string | null;
  research_decision_rationale?: string | null;
  research_details?: string | null;
  metrics_comparison: MetricComparisonItem[];
  feature_importances: FeatureImportanceItem[];
  runtime_info?: RuntimeModelInfo;
  evaluation_info?: ModelEvaluationInfo;
  research_models?: ResearchModelInfo[];
  saved_prediction_provenance?: SavedPredictionProvenance;
}

export interface BankActionItem {
  id: number;
  action_reference: string;
  idempotency_key?: string | null;
  complaint_id: number;
  alert_id?: number | null;
  account_id?: number | null;
  bank_name?: string | null;
  bank_organization_id?: number | null;
  target_account_number?: string | null;
  target_ifsc?: string | null;
  action_type: string;
  status: 'REQUESTED' | 'APPROVED' | 'SENT' | 'ACKNOWLEDGED' | 'PARTIAL_HOLD' | 'CONFIRMED_HOLD' | 'COMPLETED' | 'RELEASED' | 'REJECTED' | 'FAILED' | 'CANCELLED';
  environment: 'SIMULATED' | 'SANDBOX' | 'LIVE';
  is_simulated: boolean;
  simulation_notes?: string | null;
  requested_amount?: number | null;
  held_amount?: number | null;
  currency: string;
  requested_by_user_id?: number | null;
  reviewed_by_user_id?: number | null;
  actor_name?: string | null;
  actor_role?: string | null;
  action_notes?: string | null;
  provider_reference_id?: string | null;
  failure_reason?: string | null;
  rejection_reason?: string | null;
  release_reason?: string | null;
  callback_evidence?: Record<string, any> | null;
  status_history?: Array<Record<string, any>> | null;
  requested_at: string;
  approved_at?: string | null;
  sent_at?: string | null;
  acknowledged_at?: string | null;
  held_at?: string | null;
  completed_at?: string | null;
  released_at?: string | null;
  cancelled_at?: string | null;
  created_at: string;
}

export interface SystemStatus {
  environment: string;
  service: string;
  version: string;
  timestamp?: string;
  database: {
    status: string;
    engine: string;
    latency_ms?: number;
    is_persistent: boolean;
  };
  ml_engine: {
    status: string;
    model_version: string;
    time_model_version: string;
    artifact_verification: string;
    artifacts_verified: boolean;
    runtime_versions?: Record<string, string>;
    artifact_details?: Record<string, any>;
  };
  websocket: {
    mode: string;
    active_clients: number;
    status: string;
  };
  integrations: {
    bank_gateway: {
      status: string;
      is_simulated: boolean;
      description: string;
    };
    blockchain_gateway: {
      status: string;
      is_simulated: boolean;
      description: string;
    };
  };
  requesting_officer?: {
    id: number;
    role: string;
    state: string;
    district: string;
  };
}

export interface EvidenceFileItem {
  id: number;
  complaint_id: number;
  source: string;
  uploader_user_id?: number | null;
  uploader_role: string;
  uploader_org_id?: number | null;
  original_filename: string;
  storage_key: string;
  mime_type: string;
  size_bytes: number;
  sha256_hash: string;
  version: number;
  status: 'ACTIVE' | 'SUPERSEDED' | 'ARCHIVED' | 'DELETED' | string;
  malware_scan_status: 'PENDING_SCAN' | 'QUARANTINED' | 'FAILED_SCAN' | 'UNSCANNED' | 'CLEAN' | string;
  malware_scan_details?: string | null;
  description?: string | null;
  superseded_by_evidence_id?: number | null;
  superseded_at?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface EvidenceIntegrityResult {
  evidence_id: number;
  is_valid: boolean;
  stored_hash?: string;
  computed_hash?: string;
  size_bytes?: number;
  status?: string;
  error?: string;
  checked_at: string;
}

export interface InvestigatorReportData {
  report_metadata: {
    title: string;
    generated_at: { utc: string; ist: string };
    requested_by_officer: string;
    requested_by_role: string;
    requested_by_org: string;
    requested_by_badge: string;
    classification: string;
  };
  case_summary: {
    id: number;
    complaint_number: string;
    fraud_type: string;
    loss_amount: number;
    case_status: string;
    risk_level: string;
    payment_channel: string;
    state: string;
    district: string;
    locality: string;
    reported_at: { utc: string; ist: string };
    incident_time: { utc: string; ist: string };
    victim_phone_masked: string;
    provenance_mode: string;
    description: string;
  };
  financial_intelligence: {
    transaction_count: number;
    total_observed_flow: number;
    transactions: Array<{
      id: number;
      transaction_ref: string;
      amount: number;
      timestamp: { utc: string; ist: string };
      sender_bank: string;
      sender_account: string;
      receiver_bank: string;
      receiver_account: string;
      receiver_holder: string;
      status: string;
    }>;
  };
  predictive_intelligence: {
    total_prediction_runs: number;
    current_prediction?: {
      id: number;
      version: number;
      predicted_window_start: { utc: string; ist: string };
      predicted_window_end: { utc: string; ist: string };
      window_duration_label: string;
      top_hotspots: Array<{
        rank: number;
        location_name: string;
        district: string;
        ml_score: number;
        operational_priority: string;
        evidence: string[];
      }>;
    };
  };
  operational_alerts: Array<{
    id: number;
    severity: string;
    status: string;
    location_name: string;
    amount_at_risk: number;
    acknowledged_by?: string | null;
    created_at: { utc: string; ist: string };
  }>;
  bank_actions: Array<any>;
  evidence_registry: EvidenceFileItem[];
  legal_and_methodology_disclaimers: string[];
}

export interface CaseHandoffItem {
  id: number;
  complaint_id: number;
  prediction_id?: number | null;
  prediction_version?: number | null;
  origin_organization_id: number;
  origin_organization_name?: string | null;
  destination_organization_id: number;
  destination_organization_name?: string | null;
  target_state: string;
  target_district: string;
  purpose: string;
  evidence_scope: 'METADATA_ONLY' | 'SPECIFIC_EVIDENCE' | 'ALL_EVIDENCE';
  shared_evidence_ids?: number[] | null;
  status: 'REQUESTED' | 'ACCEPTED' | 'REJECTED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED' | 'EXPIRED';
  initiator_user_id: number;
  initiator_name?: string | null;
  recipient_user_id?: number | null;
  recipient_name?: string | null;
  rejection_reason?: string | null;
  cancellation_reason?: string | null;
  completed_notes?: string | null;
  acknowledgement_deadline: string;
  accepted_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface CreateHandoffPayload {
  target_state: string;
  target_district: string;
  destination_organization_id?: number;
  purpose: string;
  evidence_scope: 'METADATA_ONLY' | 'SPECIFIC_EVIDENCE' | 'ALL_EVIDENCE';
  shared_evidence_ids?: number[];
  prediction_id?: number;
  prediction_version?: number;
  acknowledgement_hours?: number;
}

export interface BankActionRecord {
  id: number;
  action_reference: string;
  idempotency_key?: string | null;
  complaint_id: number;
  alert_id?: number | null;
  account_id?: number | null;
  bank_name?: string | null;
  bank_organization_id?: number | null;
  target_account_number?: string | null;
  target_ifsc?: string | null;
  action_type: string;
  status: 'REQUESTED' | 'APPROVED' | 'SENT' | 'ACKNOWLEDGED' | 'PARTIAL_HOLD' | 'CONFIRMED_HOLD' | 'COMPLETED' | 'RELEASED' | 'REJECTED' | 'FAILED' | 'CANCELLED';
  environment: 'SIMULATED' | 'SANDBOX' | 'LIVE';
  is_simulated: boolean;
  simulation_notes?: string | null;
  requested_amount?: number | null;
  held_amount?: number | null;
  currency: string;
  requested_by_user_id?: number | null;
  reviewed_by_user_id?: number | null;
  actor_name?: string | null;
  actor_role?: string | null;
  action_notes?: string | null;
  provider_reference_id?: string | null;
  failure_reason?: string | null;
  rejection_reason?: string | null;
  release_reason?: string | null;
  callback_evidence?: Record<string, any> | null;
  status_history?: Array<Record<string, any>> | null;
  requested_at: string;
  approved_at?: string | null;
  sent_at?: string | null;
  acknowledged_at?: string | null;
  held_at?: string | null;
  completed_at?: string | null;
  released_at?: string | null;
  cancelled_at?: string | null;
  created_at: string;
}

export interface CreateBankActionPayload {
  complaint_id: number;
  alert_id?: number;
  account_id?: number;
  target_account_number?: string;
  target_ifsc?: string;
  bank_name?: string;
  bank_organization_id?: number;
  action_type?: string;
  requested_amount?: number;
  currency?: string;
  environment?: 'SIMULATED' | 'SANDBOX' | 'LIVE';
  action_notes?: string;
  idempotency_key?: string;
}

export interface ReleaseBankActionPayload {
  release_reason: string;
  release_amount?: number;
  notes?: string;
}

export interface SandboxSimulatePayload {
  simulated_outcome: 'CONFIRMED_HOLD' | 'PARTIAL_HOLD' | 'REJECTED' | 'FAILED' | 'TIMEOUT';
  held_amount?: number;
  reason?: string;
}

// ─── Phase 09: Outcome Observations ──────────────────────────────────────────

export type OutcomeType =
  | 'CONFIRMED_CASHOUT'
  | 'MULTIPLE_CASHOUT'
  | 'NO_OBSERVED_CASHOUT'
  | 'UNKNOWN'
  | 'DATA_EXCLUDED';

export type OutcomeSource =
  | 'OFFICER_MANUAL'
  | 'CFCFRMS_IMPORT'
  | 'BANK_REPORT'
  | 'COURT_RECORD'
  | 'AUTOMATED_MONITORING';

export type OutcomeVerificationStatus = 'VERIFIED' | 'UNVERIFIED' | 'PENDING_VERIFICATION';
export type OutcomeRecordStatus = 'ACTIVE' | 'SUPERSEDED';

export interface OutcomeObservation {
  id: number;
  complaint_id: number;
  linked_prediction_id: number | null;
  linked_prediction_version: number | null;
  prediction_selection_policy: string;
  linked_alert_id: number | null;
  linked_bank_action_id: number | null;
  outcome_type: OutcomeType;
  observed_event_time: string | null;
  actual_lat: number | null;
  actual_lon: number | null;
  actual_location_name: string | null;
  actual_withdrawal_amount_inr: number | null;
  cashout_events: Array<Record<string, unknown>> | null;
  actual_atm_id: number | null;
  actual_cluster_id: number | null;
  verified_held_amount_inr: number | null;
  verified_released_amount_inr: number | null;
  actual_recovered_amount_inr: number | null;
  recovery_verified_by: string | null;
  recovery_verified_at: string | null;
  prediction_rank_matched: number | null;
  distance_error_km: number | null;
  prediction_lead_time_minutes: number | null;
  alert_lead_time_minutes: number | null;
  alert_acknowledgement_latency_minutes: number | null;
  bank_response_latency_minutes: number | null;
  is_synthetic: boolean;
  is_excluded: boolean;
  exclusion_reason: string | null;
  verification_status: OutcomeVerificationStatus;
  source: OutcomeSource;
  verifier_user_id: number | null;
  verifier_name: string | null;
  verifier_role: string | null;
  ingested_by_user_id: number | null;
  ingested_by_role: string;
  received_at: string;
  version: number;
  corrects_outcome_id: number | null;
  record_status: OutcomeRecordStatus;
  correction_reason: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface OutcomeCreatePayload {
  outcome_type: OutcomeType;
  source: OutcomeSource;
  observed_event_time?: string;
  actual_lat?: number;
  actual_lon?: number;
  actual_location_name?: string;
  actual_withdrawal_amount_inr?: number;
  cashout_events?: Array<Record<string, unknown>>;
  actual_atm_id?: number;
  actual_cluster_id?: number;
  linked_alert_id?: number;
  linked_bank_action_id?: number;
  verified_held_amount_inr?: number;
  verified_released_amount_inr?: number;
  actual_recovered_amount_inr?: number;
  recovery_verified_by?: string;
  recovery_verified_at?: string;
  verifier_user_id?: number;
  verification_status?: OutcomeVerificationStatus;
  is_synthetic?: boolean;
  is_excluded?: boolean;
  exclusion_reason?: string;
  notes?: string;
}

export interface OutcomeCorrectPayload {
  correction_reason: string;
  outcome_type?: OutcomeType;
  source?: OutcomeSource;
  observed_event_time?: string;
  actual_lat?: number;
  actual_lon?: number;
  actual_location_name?: string;
  actual_withdrawal_amount_inr?: number;
  cashout_events?: Array<Record<string, unknown>>;
  verified_held_amount_inr?: number;
  verified_released_amount_inr?: number;
  actual_recovered_amount_inr?: number;
  recovery_verified_by?: string;
  recovery_verified_at?: string;
  verifier_user_id?: number;
  verification_status?: OutcomeVerificationStatus;
  is_excluded?: boolean;
  exclusion_reason?: string;
  notes?: string;
}

export interface OutcomeMetrics {
  // Denominators — always visible
  denominator_measured: number;
  denominator_unknown: number;
  denominator_excluded: number;
  denominator_synthetic: number;
  denominator_total_active: number;
  denominator_cashout: number;

  // Location accuracy
  rank1_count: number;
  topk_count: number;
  rank1_accuracy_rate: number | null;
  topk_accuracy_rate: number | null;
  mean_distance_error_km: number | null;

  // Timing
  mean_prediction_lead_time_minutes: number | null;
  mean_alert_lead_time_minutes: number | null;
  mean_alert_acknowledgement_latency_minutes: number | null;
  mean_bank_response_latency_minutes: number | null;

  // Financial (separate; not summed)
  total_verified_held_inr: number;
  total_verified_released_inr: number;
  total_actual_recovered_inr: number;
  financial_note: string;

  // Alert workload
  false_alert_count: number;

  // Policy
  prediction_selection_policy: string;
  policy_description: string;
}
