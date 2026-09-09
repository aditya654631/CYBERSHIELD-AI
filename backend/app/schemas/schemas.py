from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

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
    fraud_type: str
    amount: float
    victim_location: str
    state: str = "Madhya Pradesh"
    district: str = "Bhopal"
    payment_channel: str = "UPI"
    victim_name: Optional[str] = "Anonymous Victim"
    victim_phone: Optional[str] = "+91 98765 43210"

class ComplaintResponse(BaseModel):
    id: int
    complaint_number: str
    fraud_type: str
    amount: float
    victim_name: Optional[str]
    victim_phone: Optional[str]
    victim_location: str
    state: str
    district: str
    payment_channel: str
    reported_at: datetime
    incident_time: datetime
    risk_level: str
    risk_score: float
    prediction_status: str
    case_status: str
    created_at: datetime

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

# Graph Intelligence Schemas (Cytoscape compatible)
class CytoscapeNodeData(BaseModel):
    id: str
    label: str
    node_type: str  # victim, account, mule, atm, cluster, bank
    masked_id: str
    bank: str
    risk_score: float
    amount_received: float = 0.0
    amount_sent: float = 0.0
    connections_count: int = 0
    previous_complaints: int = 0
    is_hotspot: bool = False

class CytoscapeNode(BaseModel):
    data: CytoscapeNodeData

class CytoscapeEdgeData(BaseModel):
    id: str
    source: str
    target: str
    amount: float
    channel: str
    hop: int
    is_suspicious: bool = True

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
    probability: float
    risk_level: str
    distance_km: float
    reasoning: str
    latitude: float
    longitude: float

class PredictionResponse(BaseModel):
    prediction_id: int
    complaint_id: int
    complaint_number: str
    where_location: str
    when_window: str
    risk_score: float
    risk_percentage: int
    risk_level: str
    intervention_priority: int
    priority_level: str
    why_summary: str
    confidence_score: float
    ml_score: float
    graph_score: float
    geo_score: float
    temporal_score: float
    top_locations: List[PredictionLocationItem]
    prediction_mode: str = "deterministic_demo"
    model_version: str = "demo-provider-v1"
    created_at: datetime

class ExplanationFactor(BaseModel):
    name: str
    contribution_percentage: int
    description: str

class ExplanationResponse(BaseModel):
    prediction_id: int
    complaint_number: str
    prediction_mode: str = "deterministic_demo"
    model_version: str = "demo-provider-v1"
    factors: List[ExplanationFactor]
    narrative: str
    disclaimer: str

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

# Audit Schemas
class AuditLogResponse(BaseModel):
    id: int
    officer_name: str
    role: str
    action: str
    case_number: Optional[str]
    details: Optional[str]
    ip_address: str
    created_at: datetime

    class Config:
        from_attributes = True
