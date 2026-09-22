from pydantic import BaseModel, Field, field_validator, model_validator, field_serializer
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone

def to_utc_datetime(v: Any) -> Optional[datetime]:
    """Ensures datetime represents a UTC instant with tzinfo=timezone.utc.
    Handles None, strings (with Z, +00:00, +05:30, or naive), and datetimes.
    """
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return v
    if isinstance(v, datetime):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
    return v

def to_utc_iso(v: Any) -> Optional[str]:
    """Formats datetime or string as UTC ISO 8601 string ending in 'Z'."""
    dt = to_utc_datetime(v)
    if dt is None:
        return None
    if isinstance(dt, datetime):
        iso = dt.astimezone(timezone.utc).isoformat()
        if iso.endswith("+00:00"):
            return iso[:-6] + "Z"
        return iso
    return str(v)

# Auth Schemas
class LoginRequest(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    badge_number: str
    organization_name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

# Complaint Schemas
class ComplaintCreate(BaseModel):
    fraud_type: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=999999999999.99, allow_inf_nan=False)
    victim_name: Optional[str] = None
    victim_phone: Optional[str] = None
    incident_time: Optional[datetime] = None
    reported_at: Optional[datetime] = None
    state: str = "Delhi"
    district: Optional[str] = None
    region_id: Optional[str] = None
    locality: Optional[str] = None
    victim_location: Optional[str] = None
    victim_lat: Optional[float] = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    victim_lon: Optional[float] = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    description: Optional[str] = None
    payment_channel: str = "UPI"
    victim_bank: Optional[str] = None
    beneficiary_bank: Optional[str] = None
    beneficiary_id: Optional[str] = None
    transaction_ref: Optional[str] = None
    transaction_time: Optional[datetime] = None
    beneficiary_account_number: Optional[str] = None
    beneficiary_upi_id: Optional[str] = None
    ifsc_code: Optional[str] = None
    additional_references: Optional[str] = None
    demo_mode: Optional[bool] = False

    @field_validator("*", mode="before")
    @classmethod
    def trim_input(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("reported_at", "incident_time", "transaction_time")
    @classmethod
    def normalize_utc(cls, value):
        # Database DateTime columns store UTC without an offset.
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def validate_timeline_and_coordinates(self):
        reported = self.reported_at or datetime.utcnow()
        incident = self.incident_time or reported
        if incident > reported:
            raise ValueError("Incident time cannot be after reporting time")
        if self.transaction_time and self.transaction_time > reported:
            raise ValueError("Transaction time cannot be after reporting time")
        if (self.victim_lat is None) != (self.victim_lon is None):
            raise ValueError("Latitude and longitude must be supplied together")
        return self

class ComplaintResponse(BaseModel):
    id: int
    complaint_number: str
    fraud_type: str
    amount: float
    victim_name: Optional[str]
    victim_phone: Optional[str]
    victim_location: Optional[str] = None
    locality: Optional[str] = None
    state: str
    district: str
    region_id: Optional[str] = "delhi"
    payment_channel: str
    reported_at: datetime
    incident_time: datetime
    victim_lat: Optional[float] = None
    victim_lon: Optional[float] = None
    risk_level: str
    risk_score: Optional[float] = None
    prediction_status: str
    alert_status: Optional[str] = "NOT GENERATED"
    case_status: str
    created_at: datetime
    description: Optional[str] = None
    provenance_mode: Optional[str] = None
    victim_bank: Optional[str] = None
    beneficiary_bank: Optional[str] = None
    beneficiary_id: Optional[str] = None
    transaction_ref: Optional[str] = None
    transaction_time: Optional[datetime] = None
    source_scenario: Optional[str] = None
    scenario_link_status: Optional[str] = None
    linked_account_count: Optional[int] = 0
    available_transaction_count: Optional[int] = 0

    @field_validator("reported_at", "incident_time", "created_at", "transaction_time", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

    @field_serializer("reported_at", "incident_time", "created_at", "transaction_time", when_used="json", check_fields=False)
    def serialize_utc(self, v: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(v)

    class Config:
        from_attributes = True

# Account & Transaction Schemas
class AccountResponse(BaseModel):
    id: int
    masked_account: str
    bank_name: str
    branch: Optional[str]
    holder_name: str
    account_type: str
    risk_score: float
    is_mule: bool
    flag_reason: Optional[str]

    class Config:
        from_attributes = True

class TransactionResponse(BaseModel):
    id: int
    transaction_ref: str
    sender_account: str
    receiver_account: str
    sender_bank: str
    receiver_bank: str
    amount: float
    payment_channel: str
    timestamp: datetime
    hop_number: int
    status: str
    suspicious_flag: bool
    context_type: Optional[str] = "DIRECT"
    source_scenario: Optional[str] = None
    received_at: Optional[datetime] = None
    source_system: Optional[str] = "DIRECT_OFFICER_INPUT"
    dedup_key: Optional[str] = None
    analysis_status: Optional[str] = "COMPLETED"
    prediction_id: Optional[int] = None
    is_reversal: Optional[bool] = False
    correction_of_ref: Optional[str] = None
    created_by_user_id: Optional[int] = None

    @field_validator("timestamp", "received_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

    class Config:
        from_attributes = True

class TransactionIngestRequest(BaseModel):
    transaction_ref: str = Field(..., min_length=3, max_length=100)
    sender_account_number: str = Field(..., min_length=4, max_length=100)
    receiver_account_number: str = Field(..., min_length=4, max_length=100)
    amount: float = Field(..., gt=0)
    payment_channel: str = Field(default="UPI")
    timestamp: datetime = Field(...)
    source_system: Optional[str] = Field(default="DIRECT_OFFICER_INPUT")
    sender_bank: Optional[str] = None
    receiver_bank: Optional[str] = None
    hop_number: Optional[int] = 1
    suspicious_flag: Optional[bool] = True
    is_reversal: Optional[bool] = False
    correction_of_ref: Optional[str] = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime) and v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v

class TransactionCorrectionRequest(BaseModel):
    transaction_ref: str = Field(..., min_length=3, max_length=100)
    correction_of_ref: str = Field(..., min_length=3, max_length=100)
    is_reversal: bool = Field(default=False)
    sender_account_number: Optional[str] = None
    receiver_account_number: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    payment_channel: Optional[str] = Field(default="UPI")
    timestamp: Optional[datetime] = None
    source_system: Optional[str] = Field(default="DIRECT_OFFICER_INPUT")
    sender_bank: Optional[str] = None
    receiver_bank: Optional[str] = None
    hop_number: Optional[int] = 1
    suspicious_flag: Optional[bool] = True

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime) and v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v

class TransactionIngestResponse(BaseModel):
    id: int
    transaction_ref: str
    amount: float
    payment_channel: str
    timestamp: datetime
    received_at: Optional[datetime]
    source_system: str
    analysis_status: str  # "COMPLETED", "TRIGGERED", "FAILED_RETRY_REQUIRED"
    prediction_id: Optional[int] = None
    is_idempotent_replay: bool = False
    message: str
    is_reversal: Optional[bool] = False
    correction_of_ref: Optional[str] = None
    created_by_user_id: Optional[int] = None

    class Config:
        from_attributes = True

class PredictionVersionSummary(BaseModel):
    prediction_id: int
    complaint_id: int
    version_number: int
    parent_prediction_id: Optional[int]
    analysis_as_of: Optional[datetime]
    analysis_purpose: Optional[str] = "OPERATIONAL"
    created_at: datetime
    primary_cluster_id: Optional[int]
    primary_location_name: Optional[str]
    risk_score: float
    risk_level: str
    operational_window: Optional[str]
    input_fingerprint: Optional[str]
    discrepancy_detected: bool = False

    class Config:
        from_attributes = True

class TransactionContextResponse(BaseModel):
    complaint_number: str
    context_type: str  # DIRECT, LINKED_SYNTHETIC_SCENARIO, EMPTY
    source_scenario: Optional[str] = None
    transaction_count: int
    provenance: Optional[str] = None
    transactions: List[TransactionResponse]

    class Config:
        from_attributes = True


# Graph Intelligence Schemas (Cytoscape compatible)
class CytoscapeNodeData(BaseModel):
    id: str
    label: str
    node_type: str  # victim, account, mule, atm, cluster, bank, source, sink, intermediary
    masked_id: str
    bank: str
    risk_score: float = 0.0
    amount_received: float = 0.0
    amount_sent: float = 0.0
    connections_count: int = 0
    previous_complaints: int = 0
    is_hotspot: bool = False
    in_degree: Optional[int] = 0
    out_degree: Optional[int] = 0
    net_flow: Optional[float] = 0.0
    hop_level: Optional[int] = 0
    degree_centrality: Optional[float] = 0.0
    betweenness_centrality: Optional[float] = 0.0
    is_source: Optional[bool] = False
    is_sink: Optional[bool] = False
    is_intermediary: Optional[bool] = False
    is_potential_mule_indicator: Optional[bool] = False
    pattern_flags: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class CytoscapeNode(BaseModel):
    data: CytoscapeNodeData

class CytoscapeEdgeData(BaseModel):
    id: str
    source: str
    target: str
    amount: float
    channel: str
    hop: int
    is_suspicious: bool = False
    total_amount: Optional[float] = None
    transaction_count: Optional[int] = 1
    transaction_ids: Optional[List[int]] = None
    channels: Optional[List[str]] = None
    min_hop: Optional[int] = None
    max_hop: Optional[int] = None
    pattern_flags: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    reference: Optional[str] = None
    label: Optional[str] = None

    class Config:
        from_attributes = True

class CytoscapeEdge(BaseModel):
    data: CytoscapeEdgeData


class GraphDataResponse(BaseModel):
    nodes: List[CytoscapeNode]
    edges: List[CytoscapeEdge]
    metrics: Dict[str, Any]

# Prediction & Explainability Schemas
class PredictionLocationItem(BaseModel):
    rank: int
    location_name: str
    cluster_id: Optional[int] = None
    cluster_name: Optional[str] = None
    zone: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    probability: float
    ml_probability: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: str = "MEDIUM"
    risk_band: Optional[str] = None
    score_label: Optional[str] = "Model ranking score"
    operational_priority: Optional[str] = None
    operational_priority_basis: Optional[str] = None
    distance_km: float = 0.0
    reasoning: str = ""
    evidence: Optional[List[str]] = None
    latitude: float
    longitude: float

    class Config:
        from_attributes = True

class TimePredictionDetail(BaseModel):
    predicted_minutes_to_cashout: Optional[float] = None
    model_version: Optional[str] = None
    prediction_reference_time: Optional[str] = None
    operational_window: Optional[str] = None
    reference_basis: Optional[str] = None
    predicted_cashout_at: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    window_status: Optional[str] = None
    uncertainty_minutes: Optional[float] = None
    window_basis: Optional[str] = None

    class Config:
        from_attributes = True

class PredictionRunRequest(BaseModel):
    analysis_as_of: Optional[datetime] = None

    @field_validator("analysis_as_of", mode="before")
    @classmethod
    def parse_cutoff(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime) and v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v

class PredictionResponse(BaseModel):
    prediction_id: Optional[int] = 0
    complaint_id: int
    complaint_number: str
    status: Optional[str] = "SUCCESS"
    where_location: Optional[str] = ""
    when_window: Optional[str] = ""
    risk_score: Optional[float] = 0.0
    risk_percentage: Optional[int] = 0
    risk_level: Optional[str] = "MEDIUM"
    risk_band: Optional[str] = None
    intervention_priority: Optional[int] = 50
    priority_level: Optional[str] = "MONITOR"
    why_summary: Optional[str] = ""
    confidence_score: Optional[float] = 0.0
    ml_score: Optional[float] = 0.0
    graph_score: Optional[float] = 0.0
    geo_score: Optional[float] = 0.0
    temporal_score: Optional[float] = 0.0
    top_locations: List[PredictionLocationItem] = []
    prediction_mode: str = "trained_ml"
    model_version: Optional[str] = "cashout-location-xgb-v3.1"
    operational_scope: Optional[str] = "DELHI_PILOT"
    region_id: Optional[str] = None
    region_name: Optional[str] = None
    model_support_status: Optional[str] = None
    candidate_pool_size: Optional[int] = 25
    primary_cluster_id: Optional[int] = None
    time_prediction: Optional[TimePredictionDetail] = None
    score_type: Optional[str] = None
    score_label: Optional[str] = "Model ranking score"
    training_data_source: Optional[str] = None
    analysis_basis: Optional[str] = None
    dataset_version: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None
    limitations: Optional[List[str]] = None
    version_number: Optional[int] = 1
    parent_prediction_id: Optional[int] = None
    analysis_as_of: Optional[datetime] = None
    analysis_purpose: Optional[str] = "OPERATIONAL"
    input_fingerprint: Optional[str] = None
    discrepancy_detected: Optional[bool] = False
    message: Optional[str] = None
    refusal_reason: Optional[str] = None
    explanation: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    @field_validator("created_at", "analysis_as_of", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

    class Config:
        from_attributes = True

class ExplanationFactor(BaseModel):
    name: str
    contribution_percentage: Union[int, float]
    description: str
    feature_code: Optional[str] = None
    direction: Optional[str] = None

class LimeContribution(BaseModel):
    feature_name: str
    friendly_label: Optional[str] = None
    category: Optional[str] = None
    provenance_type: Optional[str] = None  # DIRECT_INTAKE, DERIVED_TRANSFER, SPATIAL_DERIVED, SYNTHETIC_HISTORICAL_BASELINE, MODEL_PRIOR
    rule: str
    weight: float
    raw_weight: Optional[float] = None
    feature_value: float
    formatted_value: Optional[str] = None
    direction: Optional[str] = None
    contribution_share: Optional[float] = None
    share_denominator_formula: Optional[str] = None
    share_denominator_note: Optional[str] = None
    description: str
    honest_explanation: Optional[str] = None

class LimeCandidateExplanation(BaseModel):
    rank: int
    cluster_id: int
    location_name: str
    official_score: float
    lime_local_prediction: float
    absolute_approximation_error: float
    local_fidelity_r2: Optional[float] = None
    fidelity_status: str = "HIGH_FIDELITY"
    positive_contributions: List[LimeContribution] = []
    negative_contributions: List[LimeContribution] = []
    summary_statement: Optional[str] = None

class ExplanationResponse(BaseModel):
    prediction_id: int
    complaint_number: str
    prediction_mode: str = "trained_ml"
    model_version: str = "cashout-location-xgb-v8-debiased"
    location_model_version: Optional[str] = "cashout-location-xgb-v8-debiased"
    explanation_status: str = "AVAILABLE"  # AVAILABLE, UNAVAILABLE, LOW_FIDELITY, NOT_FOUND
    explanation_method: str = "LIME"
    explainer_version: Optional[str] = "lime_tabular_0.2.0.1"
    feature_schema_version: Optional[str] = "v8_debiased"
    generated_at: Optional[str] = None
    overall_fidelity_status: Optional[str] = "HIGH_FIDELITY"
    mean_local_fidelity_r2: Optional[float] = None
    background_sample_size: Optional[int] = 500
    background_seed: Optional[int] = 56100
    top3_explanations: Optional[List[LimeCandidateExplanation]] = []
    factors: Optional[List[ExplanationFactor]] = []
    narrative: Optional[str] = ""
    message: Optional[str] = None
    actionable_next_step: Optional[str] = None
    is_legacy_prediction: Optional[bool] = False
    cache_identity: Optional[str] = None
    snapshot_digest: Optional[str] = None
    snapshot_source: Optional[str] = None
    snapshot_provenance: Optional[bool] = False
    integrity_conflict: Optional[bool] = False
    disclaimer: str = (
        "LIME provides local surrogate linear explanations of model decisions for risk prioritization. "
        "This is an algorithmic approximation, not proof or causal evidence of criminal activity."
    )

# ============================================================================
# Model Performance, Runtime Governance & Evaluation Schemas (Phase 4)
# ============================================================================

class MetricComparisonItem(BaseModel):
    metric: str
    baseline: Optional[str] = None
    cybershield: Optional[str] = None
    delta: Optional[str] = None
    unit: Optional[str] = None
    comparable: bool = False
    comparability_note: Optional[str] = None

class FeatureImportanceItem(BaseModel):
    feature: str
    importance: float
    feature_code: Optional[str] = None

class RuntimeModelInfo(BaseModel):
    runtime_status: str  # "TRAINED_READY", "DEMO_ACTIVE", "LOAD_FAILED", "UNAVAILABLE"
    is_loaded: bool
    is_available: bool
    prediction_mode: str
    current_prediction_mode: str
    model_version: str
    location_model_version: Optional[str] = None
    time_model_version: Optional[str] = None
    algorithm: Optional[str] = None
    model_class: Optional[str] = None
    calibrator_class: Optional[str] = None
    calibration_method: Optional[str] = None
    feature_schema_version: Optional[str] = None
    location_features_count: Optional[int] = None
    time_features_count: Optional[int] = None
    location_artifact_file: Optional[str] = None
    location_artifact_hash: Optional[str] = None
    location_artifact_hash_short: Optional[str] = None
    calibrator_artifact_file: Optional[str] = None
    calibrator_artifact_hash: Optional[str] = None
    calibrator_artifact_hash_short: Optional[str] = None
    load_error: Optional[str] = None

class ModelEvaluationInfo(BaseModel):
    evaluation_status: str  # "AVAILABLE", "UNAVAILABLE", "VERSION_MISMATCH", "HASH_MISMATCH", "NOT_EVALUATED"
    availability_reason: Optional[str] = None
    evaluated_model_version: Optional[str] = None
    evaluation_timestamp: Optional[str] = None
    dataset_type: Optional[str] = None
    dataset_split: Optional[str] = None
    synthetic_disclosure: Optional[str] = None
    training_samples: Optional[int] = None
    validation_samples: Optional[int] = None
    test_samples: Optional[int] = None
    cold_start_test_samples: Optional[int] = None
    metrics_summary: Dict[str, Any] = Field(default_factory=dict)

class ResearchModelInfo(BaseModel):
    model_name: str
    model_type: Optional[str] = None
    status: str
    promotion_status: str
    qualification_gate: Optional[str] = None
    observed_gain: Optional[str] = None
    required_gain: Optional[str] = None
    official_production_model: Optional[str] = None
    production_affected: bool = False
    details: Optional[str] = None

class SavedPredictionProvenance(BaseModel):
    current_runtime_model: str
    historical_policy: str
    description: str

class ModelPerformanceResponse(BaseModel):
    prediction_mode: str
    current_prediction_mode: str
    model_version: str
    provider_version: str
    official_production_model: Optional[str] = None
    location_model_version: Optional[str] = None
    time_model_version: Optional[str] = None
    location_features_count: Optional[int] = None
    time_features_count: Optional[int] = None
    calibration_method: Optional[str] = None
    model_class: Optional[str] = None
    calibrator_class: Optional[str] = None
    dataset_type: Optional[str] = None
    dataset_split: Optional[str] = None
    evaluation_label: Optional[str] = None
    synthetic_disclosure: Optional[str] = None
    model_architecture: Optional[str] = None
    runtime_notice: Optional[str] = None
    production_notice: Optional[str] = None
    geographic_disclaimer: Optional[str] = None

    training_samples: Optional[int] = None
    validation_samples: Optional[int] = None
    test_samples: Optional[int] = None
    cold_start_test_samples: Optional[int] = None
    active_clusters_count: Optional[int] = 60
    atm_coverage_count: Optional[int] = 1200

    natural_candidate_recall: Optional[str] = None
    Recall_at_1: Optional[str] = Field(None, alias="Recall@1")
    Recall_at_3: Optional[str] = Field(None, alias="Recall@3")
    Recall_at_5: Optional[str] = Field(None, alias="Recall@5")
    Precision_at_3: Optional[str] = Field(None, alias="Precision@3")
    MRR: Optional[float] = None
    median_cluster_centroid_distance_error_km: Optional[str] = None
    within_5km: Optional[str] = None
    within_10km: Optional[str] = None
    within_25km: Optional[str] = None
    Brier_score: Optional[float] = None
    internal_ece: Optional[float] = None
    time_MAE_minutes: Optional[str] = None
    time_median_absolute_error: Optional[str] = None
    time_window_coverage: Optional[str] = None
    cold_start_candidate_recall: Optional[str] = None
    cold_start_recall_at_1: Optional[str] = None
    cold_start_recall_at_3: Optional[str] = None

    research_experiment: Optional[str] = None
    research_status: Optional[str] = None
    research_details: Optional[str] = None

    metrics_comparison: List[MetricComparisonItem] = Field(default_factory=list)
    feature_importances: List[FeatureImportanceItem] = Field(default_factory=list)

    runtime_info: Optional[RuntimeModelInfo] = None
    evaluation_info: Optional[ModelEvaluationInfo] = None
    research_models: List[ResearchModelInfo] = Field(default_factory=list)
    saved_prediction_provenance: Optional[SavedPredictionProvenance] = None

    class Config:
        populate_by_name = True

# GIS Schemas
class HotspotCluster(BaseModel):
    id: int
    cluster_name: str
    city: str
    district: str
    state: str
    latitude: float
    longitude: float
    radius_km: float
    risk_score: float
    risk_level: str
    active_cases: int
    amount_at_risk: float
    atm_count: int
    expected_window: str
    fraud_type: str

    # Additive fields for Phase 3
    is_active_candidate: bool = False
    data_basis: str = "historical_baseline"
    historical_risk: Optional[float] = None
    candidate_score: Optional[float] = None
    operational_priority: Optional[str] = None
    operational_priority_basis: Optional[str] = None
    associated_complaint_amount: float = 0.0
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    latest_window_end: Optional[str] = None
    window_status: Optional[str] = None
    linked_complaint_numbers: List[str] = Field(default_factory=list)
    region_id: Optional[str] = "delhi"

class ATMLocationItem(BaseModel):
    id: int
    atm_code: str
    bank_name: str
    address: str
    city: str
    district: str
    latitude: float
    longitude: float
    cash_available: bool
    risk_rating: str
    cluster_name: Optional[str]

class GISOverviewResponse(BaseModel):
    hotspots: List[HotspotCluster]
    atms: List[ATMLocationItem]
    summary: Dict[str, Any]
    active_candidates: List[HotspotCluster] = Field(default_factory=list)
    historical_hotspots: List[HotspotCluster] = Field(default_factory=list)

# Alert Schemas
class NotificationOutboxItem(BaseModel):
    id: int
    alert_id: int
    event_type: str
    prediction_id: Optional[int] = None
    prediction_version: Optional[int] = None
    channel: str
    recipient_role: Optional[str] = None
    recipient_organization_id: Optional[int] = None
    recipient_state: Optional[str] = None
    recipient_district: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    status: str
    attempt_count: int
    max_attempts: int
    next_retry_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    last_error: Optional[str] = None
    worker_id: Optional[str] = None
    delivered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    idempotency_key: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator("next_retry_at", "last_attempt_at", "delivered_at", "acknowledged_at", "created_at", "updated_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    complaint_id: int
    complaint_number: str
    prediction_id: Optional[int]
    title: str
    severity: str
    location_name: str
    risk_score: float
    expected_window: str
    amount_at_risk: float
    status: str
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    action_notes: Optional[str] = None
    superseded_by_prediction_id: Optional[int] = None
    superseded_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    delivery_status: Optional[str] = None
    attempt_count: Optional[int] = 0
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    channel_delivery_status: Optional[Dict[str, Any]] = None
    created_at: datetime

    @field_validator("acknowledged_at", "superseded_at", "expires_at", "next_retry_at", "created_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

    class Config:
        from_attributes = True


class AlertSyncResponse(BaseModel):
    items: List[AlertResponse]
    outbox_events: List[NotificationOutboxItem]
    synced_at: datetime
    cursor: int
    has_more: bool


class AlertChannelsStatusResponse(BaseModel):
    dashboard_websocket: Optional[Dict[str, Any]] = None
    email: Optional[Dict[str, Any]] = None
    sms: Optional[Dict[str, Any]] = None
    partner_webhook: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AlertActionRequest(BaseModel):
    notes: Optional[str] = "Officer action logged"

# Analytics Schemas
class AnalyticsOverviewResponse(BaseModel):
    active_complaints: int
    critical_risk_cases: int
    predicted_cashout_events: int
    high_risk_districts: int
    total_amount_at_risk: float
    alerts_acknowledged_today: int
    fraud_types: List[Dict[str, Any]]
    cases_over_time: List[Dict[str, Any]]
    hourly_risk: List[Dict[str, Any]]
    regional_risk: List[Dict[str, Any]]

# Dashboard Schemas
class DashboardKpis(BaseModel):
    active_complaints: int
    high_risk_predictions: int
    active_alerts: int
    acknowledged_alerts: int
    total_amount_at_risk: float
    avg_response_time_minutes: Optional[float] = None
    response_time_label: str = "Average response time"

class RiskDistribution(BaseModel):
    HIGH: int
    MEDIUM: int
    LOW: int
    CRITICAL: int
    total: int

class PredictionModeDistribution(BaseModel):
    trained_ml: int
    deterministic_demo: int
    total: int

class RecentComplaintItem(BaseModel):
    id: int
    complaint_number: str
    fraud_type: str
    amount: float
    district: Optional[str] = None
    state: Optional[str] = None
    victim_location: Optional[str] = None
    case_status: str
    reported_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    prediction_available: bool
    latest_prediction_id: Optional[int] = None
    latest_risk_level: Optional[str] = "NO PREDICTION"
    latest_mode: Optional[str] = None
    latest_rank1_location: Optional[str] = None

    @field_validator("reported_at", "created_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

class RecentPredictionItem(BaseModel):
    id: int
    complaint_id: int
    complaint_number: str
    prediction_mode: str
    model_version: str
    risk_level: str
    risk_score: float
    rank1_location: Optional[str] = None
    rank1_cluster_id: Optional[int] = None
    operational_window: str
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

class RecentAlertItem(BaseModel):
    id: int
    complaint_id: int
    complaint_number: str
    prediction_id: Optional[int] = None
    title: str
    severity: str
    location_name: str
    risk_score: float
    expected_window: str
    amount_at_risk: float
    status: str
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

class DashboardSummaryResponse(BaseModel):
    generated_at: datetime
    kpis: DashboardKpis
    risk_distribution: RiskDistribution
    mode_distribution: PredictionModeDistribution
    fraud_type_distribution: List[Dict[str, Any]]
    cases_over_time: List[Dict[str, Any]]
    hourly_risk: Optional[List[Dict[str, Any]]] = None
    regional_distribution: List[Dict[str, Any]]
    recent_complaints: List[RecentComplaintItem]
    recent_predictions: List[RecentPredictionItem]
    recent_alerts: List[RecentAlertItem]

    @field_validator("generated_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

# Audit Schemas
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    officer_name: str
    role: str
    action: str
    case_number: Optional[str]
    details: Optional[str]
    ip_address: str
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

    class Config:
        from_attributes = True

# Bank Action Schemas (Phase 8)
class BankActionResponse(BaseModel):
    id: int
    action_reference: str
    idempotency_key: Optional[str] = None
    complaint_id: int
    alert_id: Optional[int] = None
    account_id: Optional[int] = None
    bank_name: Optional[str] = None
    bank_organization_id: Optional[int] = None
    target_account_number: Optional[str] = None
    target_ifsc: Optional[str] = None
    action_type: str
    status: str
    environment: str = "SIMULATED"
    is_simulated: bool = True
    simulation_notes: Optional[str] = None
    requested_amount: Optional[float] = None
    held_amount: Optional[float] = 0.0
    currency: str = "INR"
    requested_by_user_id: Optional[int] = None
    reviewed_by_user_id: Optional[int] = None
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    action_notes: Optional[str] = None
    provider_reference_id: Optional[str] = None
    failure_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    release_reason: Optional[str] = None
    callback_evidence: Optional[Dict[str, Any]] = None
    status_history: Optional[List[Dict[str, Any]]] = None
    requested_at: datetime
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    held_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime

    @field_validator("requested_at", "approved_at", "sent_at", "acknowledged_at", "held_at", "completed_at", "released_at", "cancelled_at", "created_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

    class Config:
        from_attributes = True

class BankActionCreateRequest(BaseModel):
    complaint_id: int
    alert_id: Optional[int] = None
    account_id: Optional[int] = None
    target_account_number: Optional[str] = None
    target_ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    bank_organization_id: Optional[int] = None
    action_type: str = Field(default="ATM_DISBURSEMENT_HOLD")
    requested_amount: Optional[float] = Field(default=None, gt=0)
    currency: str = Field(default="INR")
    environment: str = Field(default="SIMULATED")  # SIMULATED, SANDBOX, LIVE
    action_notes: Optional[str] = None
    idempotency_key: Optional[str] = None

class BankActionReleaseRequest(BaseModel):
    release_reason: str = Field(..., min_length=5, max_length=500)
    release_amount: Optional[float] = Field(default=None, gt=0)
    notes: Optional[str] = None

class BankActionTransitionRequest(BaseModel):
    target_status: str
    notes: Optional[str] = None
    failure_reason: Optional[str] = None
    rejection_reason: Optional[str] = None

class BankPartnerCallbackPayload(BaseModel):
    action_reference: str
    provider_reference_id: Optional[str] = None
    target_account_number: Optional[str] = None
    status: str  # HELD, PARTIAL_HELD, REJECTED, FAILED, RELEASED
    held_amount: float = Field(default=0.0, ge=0)
    currency: str = Field(default="INR")
    failure_reason: Optional[str] = None
    release_reason: Optional[str] = None
    notes: Optional[str] = None

class SandboxSimulateRequest(BaseModel):
    simulated_outcome: str = Field(default="CONFIRMED_HOLD")  # CONFIRMED_HOLD, PARTIAL_HOLD, REJECTED, FAILED, TIMEOUT
    held_amount: Optional[float] = None
    reason: Optional[str] = None


# Evidence Schemas (Phase 6)
class EvidenceFileResponse(BaseModel):
    id: int
    complaint_id: int
    source: str
    uploader_user_id: Optional[int] = None
    uploader_role: str
    uploader_org_id: Optional[int] = None
    original_filename: str
    storage_key: str
    mime_type: str
    size_bytes: int
    sha256_hash: str
    version: int
    status: str
    malware_scan_status: str
    malware_scan_details: Optional[str] = None
    description: Optional[str] = None
    superseded_by_evidence_id: Optional[int] = None
    superseded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator("created_at", "updated_at", "superseded_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

    class Config:
        from_attributes = True


class EvidenceIntegrityResponse(BaseModel):
    evidence_id: int
    is_valid: bool
    stored_hash: Optional[str] = None
    computed_hash: Optional[str] = None
    size_bytes: Optional[int] = None
    status: Optional[str] = None
    error: Optional[str] = None
    checked_at: str


class EvidenceScanUpdateRequest(BaseModel):
    status: str
    details: Optional[str] = None


class InvestigatorReportDataResponse(BaseModel):
    report_metadata: Dict[str, Any]
    case_summary: Dict[str, Any]
    financial_intelligence: Dict[str, Any]
    predictive_intelligence: Dict[str, Any]
    operational_alerts: List[Dict[str, Any]]
    bank_actions: List[Dict[str, Any]]
    evidence_registry: List[Dict[str, Any]]
    legal_and_methodology_disclaimers: List[str]


# Case Handoff Schemas (Phase 7)
class CaseHandoffCreateRequest(BaseModel):
    target_state: str
    target_district: str
    destination_organization_id: Optional[int] = None
    purpose: str = "PHYSICAL_SURVEILLANCE"
    evidence_scope: str = "METADATA_ONLY"
    shared_evidence_ids: Optional[List[int]] = None
    prediction_id: Optional[int] = None
    prediction_version: Optional[int] = None
    acknowledgement_hours: int = 24


class CaseHandoffResponse(BaseModel):
    id: int
    complaint_id: int
    prediction_id: Optional[int] = None
    prediction_version: Optional[int] = None
    origin_organization_id: int
    origin_organization_name: Optional[str] = None
    destination_organization_id: int
    destination_organization_name: Optional[str] = None
    target_state: str
    target_district: str
    purpose: str
    evidence_scope: str
    shared_evidence_ids: Optional[List[int]] = None
    status: str
    initiator_user_id: int
    initiator_name: Optional[str] = None
    recipient_user_id: Optional[int] = None
    recipient_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    completed_notes: Optional[str] = None
    acknowledgement_deadline: datetime
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator("created_at", "updated_at", "acknowledgement_deadline", "accepted_at", "completed_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

    class Config:
        from_attributes = True


class HandoffRejectRequest(BaseModel):
    rejection_reason: str


class HandoffCancelRequest(BaseModel):
    cancellation_reason: str


class HandoffCompleteRequest(BaseModel):
    completed_notes: Optional[str] = None


# ─── Phase 09: Outcome Observation Schemas ────────────────────────────────────

class OutcomeCreateRequest(BaseModel):
    """Create a new outcome observation. Prediction is linked server-side by policy."""
    outcome_type: str  # CONFIRMED_CASHOUT | MULTIPLE_CASHOUT | NO_OBSERVED_CASHOUT | UNKNOWN | DATA_EXCLUDED
    source: str        # OFFICER_MANUAL | CFCFRMS_IMPORT | BANK_REPORT | COURT_RECORD | AUTOMATED_MONITORING
    observed_event_time: Optional[datetime] = None  # UTC; required for CONFIRMED/MULTIPLE_CASHOUT
    actual_lat: Optional[float] = None
    actual_lon: Optional[float] = None
    actual_location_name: Optional[str] = None
    actual_withdrawal_amount_inr: Optional[float] = Field(None, ge=0.0)
    cashout_events: Optional[List[Dict[str, Any]]] = None  # for MULTIPLE_CASHOUT
    actual_atm_id: Optional[int] = None
    actual_cluster_id: Optional[int] = None
    linked_alert_id: Optional[int] = None
    linked_bank_action_id: Optional[int] = None
    verified_held_amount_inr: Optional[float] = Field(None, ge=0.0)
    verified_released_amount_inr: Optional[float] = Field(None, ge=0.0)
    actual_recovered_amount_inr: Optional[float] = Field(None, ge=0.0)
    recovery_verified_by: Optional[str] = None
    recovery_verified_at: Optional[datetime] = None
    verifier_user_id: Optional[int] = None
    verification_status: str = "PENDING_VERIFICATION"
    is_synthetic: bool = False
    is_excluded: bool = False
    exclusion_reason: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("observed_event_time", "recovery_verified_at", mode="before")
    @classmethod
    def validate_datetimes(cls, v: Any) -> Optional[datetime]:
        return to_utc_datetime(v)


class OutcomeCorrectRequest(BaseModel):
    """Correct an existing ACTIVE outcome by superseding it and creating a new version."""
    correction_reason: str = Field(..., min_length=5)
    outcome_type: Optional[str] = None
    source: Optional[str] = None
    observed_event_time: Optional[datetime] = None
    actual_lat: Optional[float] = None
    actual_lon: Optional[float] = None
    actual_location_name: Optional[str] = None
    actual_withdrawal_amount_inr: Optional[float] = Field(None, ge=0.0)
    cashout_events: Optional[List[Dict[str, Any]]] = None
    actual_atm_id: Optional[int] = None
    actual_cluster_id: Optional[int] = None
    linked_alert_id: Optional[int] = None
    linked_bank_action_id: Optional[int] = None
    verified_held_amount_inr: Optional[float] = Field(None, ge=0.0)
    verified_released_amount_inr: Optional[float] = Field(None, ge=0.0)
    actual_recovered_amount_inr: Optional[float] = Field(None, ge=0.0)
    recovery_verified_by: Optional[str] = None
    recovery_verified_at: Optional[datetime] = None
    verifier_user_id: Optional[int] = None
    verification_status: Optional[str] = None
    is_excluded: Optional[bool] = None
    exclusion_reason: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("observed_event_time", "recovery_verified_at", mode="before")
    @classmethod
    def validate_datetimes(cls, v: Any) -> Optional[datetime]:
        return to_utc_datetime(v)


class OutcomeResponse(BaseModel):
    id: int
    complaint_id: int
    linked_prediction_id: Optional[int] = None
    linked_prediction_version: Optional[int] = None
    prediction_selection_policy: str
    linked_alert_id: Optional[int] = None
    linked_bank_action_id: Optional[int] = None
    outcome_type: str
    observed_event_time: Optional[datetime] = None
    actual_lat: Optional[float] = None
    actual_lon: Optional[float] = None
    actual_location_name: Optional[str] = None
    actual_withdrawal_amount_inr: Optional[float] = None
    cashout_events: Optional[List[Dict[str, Any]]] = None
    actual_atm_id: Optional[int] = None
    actual_cluster_id: Optional[int] = None
    verified_held_amount_inr: Optional[float] = None
    verified_released_amount_inr: Optional[float] = None
    actual_recovered_amount_inr: Optional[float] = None
    recovery_verified_by: Optional[str] = None
    recovery_verified_at: Optional[datetime] = None
    prediction_rank_matched: Optional[int] = None
    distance_error_km: Optional[float] = None
    prediction_lead_time_minutes: Optional[float] = None
    alert_lead_time_minutes: Optional[float] = None
    alert_acknowledgement_latency_minutes: Optional[float] = None
    bank_response_latency_minutes: Optional[float] = None
    is_synthetic: bool
    is_excluded: bool
    exclusion_reason: Optional[str] = None
    verification_status: str
    source: str
    verifier_user_id: Optional[int] = None
    verifier_name: Optional[str] = None
    verifier_role: Optional[str] = None
    ingested_by_user_id: Optional[int] = None
    ingested_by_role: str
    received_at: datetime
    version: int
    corrects_outcome_id: Optional[int] = None
    record_status: str
    correction_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator("observed_event_time", "recovery_verified_at", "received_at",
                     "created_at", "updated_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_utc_datetime(v)

    class Config:
        from_attributes = True


class OutcomeMetricsResponse(BaseModel):
    """Honest operational dashboard metrics with explicit denominators."""
    # Denominators — always shown so unknown/excluded cohorts are visible
    denominator_measured: int
    denominator_unknown: int
    denominator_excluded: int
    denominator_synthetic: int
    denominator_total_active: int
    denominator_cashout: int

    # Location accuracy (cashout outcomes only)
    rank1_count: int
    topk_count: int
    rank1_accuracy_rate: Optional[float] = None   # NULL when denominator_cashout=0
    topk_accuracy_rate: Optional[float] = None
    mean_distance_error_km: Optional[float] = None

    # Timing metrics
    mean_prediction_lead_time_minutes: Optional[float] = None
    mean_alert_lead_time_minutes: Optional[float] = None
    mean_alert_acknowledgement_latency_minutes: Optional[float] = None
    mean_bank_response_latency_minutes: Optional[float] = None

    # Financial figures (reported separately)
    total_verified_held_inr: float
    total_verified_released_inr: float
    total_actual_recovered_inr: float
    financial_note: str

    # Alert workload
    false_alert_count: int

    # Policy metadata
    prediction_selection_policy: str
    policy_description: str


# ── PHASE 10: MODEL EVALUATION & DATA READINESS SCHEMAS ───────────────────────

class RealDataImportMetadata(BaseModel):
    source_system: str
    batch_id: str
    authorized_officer_id: Optional[int] = None
    export_date: str
    jurisdiction_state: Optional[str] = "Delhi"
    pii_attestation: bool


class RealDataImportValidationRequest(BaseModel):
    metadata: RealDataImportMetadata
    records: List[Dict[str, Any]]


class RealDataImportValidationResponse(BaseModel):
    validation_status: str
    is_valid: bool
    metadata_submitted: Dict[str, Any]
    total_records_evaluated: int
    valid_records_count: int
    errors_count: int
    warnings_count: int
    errors: List[str]
    warnings: List[str]
    pii_compliance_status: str


class RealDataValidationStatusResponse(BaseModel):
    status: str
    evaluation_readiness: str
    message: str
    external_acceptance_gates: List[Dict[str, Any]]
    methodology_disclosures: Dict[str, Any]


# ── PHASE 12: GEOGRAPHY CATALOG & MULTI-REGION SCHEMAS ───────────────────────

class RegionCoordinates(BaseModel):
    lat: float
    lon: float

class RegionBounds(BaseModel):
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

class RegionSummaryItem(BaseModel):
    id: str
    name: str
    state: str
    catalog_version: str
    source: str
    license: str
    verification_time: Optional[str] = None
    center: RegionCoordinates
    bounds: RegionBounds
    cluster_radius_km: float
    districts: List[str] = []
    total_clusters: int = 0
    total_atms: int = 0
    data_completeness_status: str
    model_support_status: str
    supported_model_version: Optional[str] = None
    is_synthetic: bool = False
    is_active: bool = True

    class Config:
        from_attributes = True

class RegionDetailResponse(BaseModel):
    id: str
    name: str
    state: str
    catalog_version: str
    source: str
    license: str
    verification_time: Optional[str] = None
    center: RegionCoordinates
    bounds: RegionBounds
    cluster_radius_km: float
    districts: List[str] = []
    total_clusters: int = 0
    total_atms: int = 0
    data_completeness_status: str
    model_support_status: str
    supported_model_version: Optional[str] = None
    is_synthetic: bool = False
    is_active: bool = True
    region: Optional[RegionSummaryItem] = None
    clusters_sample: List[Dict[str, Any]] = []
    operational_limitations: List[str] = []

    class Config:
        from_attributes = True

class GeographyCatalogResponseItem(BaseModel):
    id: int
    catalog_id: str
    region_id: str
    catalog_version: str
    source: str
    license: str
    provenance_notes: Optional[str] = None
    verification_time: Optional[str] = None
    status: str
    data_completeness_status: str
    model_support_status: str
    supported_model_version: Optional[str] = None
    total_clusters: int = 0
    total_atms: int = 0
    cluster_radius_km: float = 2.5
    imported_at: Optional[str] = None

    class Config:
        from_attributes = True

class CatalogValidationRequest(BaseModel):
    catalog: Dict[str, Any]

class CatalogValidationResponse(BaseModel):
    is_valid: bool
    region_id: str
    catalog_version: str
    errors: List[str] = []
    warnings: List[str] = []
    summary: Dict[str, Any] = {}

class CatalogImportRequest(BaseModel):
    catalog: Dict[str, Any]

class CatalogImportResponse(BaseModel):
    status: str
    message: str
    catalog_id: str
    region_id: str
    total_clusters_imported: int
    total_atms_imported: int
    model_support_status: str
