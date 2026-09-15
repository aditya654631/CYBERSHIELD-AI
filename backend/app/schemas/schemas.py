from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

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
    model_version: str = "cashout-location-xgb-v3.1"
    operational_scope: Optional[str] = "DELHI_PILOT"
    candidate_pool_size: Optional[int] = 25
    primary_cluster_id: Optional[int] = None
    time_prediction: Optional[TimePredictionDetail] = None
    score_type: Optional[str] = None
    score_label: Optional[str] = None
    training_data_source: Optional[str] = None
    analysis_basis: Optional[str] = None
    dataset_version: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None
    limitations: Optional[List[str]] = None
    message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ExplanationFactor(BaseModel):
    name: str
    contribution_percentage: int
    description: str

class LimeContribution(BaseModel):
    feature_name: str
    rule: str
    weight: float
    feature_value: float
    description: str

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
    model_version: str = "cashout-location-xgb-v7-compat"
    location_model_version: Optional[str] = "cashout-location-xgb-v7-compat"
    explanation_status: str = "AVAILABLE"  # AVAILABLE, UNAVAILABLE, LOW_FIDELITY, NOT_FOUND
    explanation_method: str = "LIME"
    explainer_version: Optional[str] = "lime_tabular_0.2.0.1"
    feature_schema_version: Optional[str] = "v7_compat"
    generated_at: Optional[str] = None
    overall_fidelity_status: Optional[str] = "HIGH_FIDELITY"
    mean_local_fidelity_r2: Optional[float] = None
    background_sample_size: Optional[int] = 500
    background_seed: Optional[int] = 56100
    top3_explanations: Optional[List[LimeCandidateExplanation]] = []
    factors: Optional[List[ExplanationFactor]] = []
    narrative: Optional[str] = ""
    disclaimer: str = (
        "LIME provides local surrogate linear explanations of model decisions for risk prioritization. "
        "This is an algorithmic approximation, not proof or causal evidence of criminal activity."
    )

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

# Alert Schemas
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
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    action_notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True
