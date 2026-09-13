# CyberShield AI — Production API Contract Freeze
**Phase A.4O-MASTER Document**  
**Status: FROZEN & PROTECTED**  
**Target: Protected Production Baseline (`b7fe4ac4aa31b4c76a6becc32ed4fd5fe011b97f`)**

---

## 1. Scope & Purpose
This document formally freezes the production API contracts for CyberShield AI (SIH 26184). These endpoints govern complaint registration, transaction graph context, predictive ML execution, GIS visualization, and alert workflows.

This contract freeze ensures that upcoming Phase B (Hyperledger Fabric Consortium Blockchain) development operates strictly as an additive, fault-tolerant layer without modifying or breaking existing REST API interfaces.

---

## 2. Core Endpoints & Payloads

### 2.1 Health Check (`GET /health`)
* **Purpose**: System health, database connectivity, and ML model availability audit.
* **Authentication**: None (Public).
* **Response Schema**:
```json
{
  "status": "healthy" | "degraded",
  "service": "CyberShield AI",
  "version": "1.0.0",
  "engine": "Online" | "Unavailable",
  "database": {
    "status": "connected" | "disconnected",
    "engine": "postgresql" | "sqlite"
  },
  "schema_ready": true,
  "predictive_pipeline": "Active (Delhi synthetic prototype)" | "Unavailable",
  "models": {
    "available": true,
    "location": "cashout-location-xgb-v4",
    "time": "cashout-time-xgb-v3"
  }
}
```

---

### 2.2 Complaint Registration (`POST /api/v1/complaints/`)
* **Purpose**: Register a citizen cybercrime complaint. Independent from prediction execution.
* **Authentication**: Authorized Officer / User.
* **Request Fields**: `complaint_number`, `victim_name`, `victim_phone`, `victim_location`, `state`, `district`, `locality`, `fraud_type`, `amount`, `payment_channel`, `incident_time`.
* **Response Status**: `200 OK` or `201 Created` with persisted `Complaint` ORM representation.

---

### 2.3 Run Predictive Intelligence (`POST /api/v1/predictions/{complaint_id}`)
* **Purpose**: Execute ML inference pipeline for a complaint, persisting exactly one `Prediction` and three `PredictionLocation` records.
* **Authentication**: Bearer JWT.
* **Request Parameters**: `complaint_id` (numeric ID or complaint number string).
* **Response Schema (`PredictionResponse`)**:
```json
{
  "prediction_id": 84,
  "complaint_id": 3090,
  "complaint_number": "CMP-TEST-GOLDEN-1789311890",
  "status": "SUCCESS" | "OUTSIDE_OPERATIONAL_SCOPE",
  "where_location": "Rohini Sector 10, Delhi",
  "primary_cluster_id": 50,
  "when_window": "Next 2–4 Hours (operational estimate window)",
  "risk_score": 0.0642,
  "risk_percentage": 6,
  "risk_level": "MEDIUM" | "HIGH" | "CRITICAL" | "LOW",
  "risk_band": "MEDIUM" | "HIGH" | "CRITICAL" | "LOW",
  "intervention_priority": 50,
  "priority_level": "MONITOR" | "HIGH PRIORITY" | "IMMEDIATE ACTION" | "ROUTINE",
  "why_summary": "Cash-out cluster ranking from transaction context and synthetic Delhi historical patterns.",
  "confidence_score": 0.0642,
  "ml_score": 0.0642,
  "graph_score": 0.25,
  "geo_score": 0.65,
  "temporal_score": 0.85,
  "top_locations": [
    {
      "rank": 1,
      "cluster_id": 50,
      "cluster_name": "Rohini Sector 10, Delhi",
      "location_name": "Rohini Sector 10, Delhi",
      "zone": "NORTH_WEST",
      "district": "NORTH_WEST",
      "state": "Delhi",
      "probability": 0.0642,
      "ml_probability": 0.0642,
      "risk_score": 0.0642,
      "risk_level": "MEDIUM",
      "risk_band": "MEDIUM",
      "distance_km": 1.45,
      "reasoning": "Ranked #1 by Location V4 for the current complaint context.",
      "evidence": ["Ranked #1 by Location V4 for the current complaint context."],
      "latitude": 28.7155,
      "longitude": 77.1189
    },
    { "rank": 2, "...": "..." },
    { "rank": 3, "...": "..." }
  ],
  "prediction_mode": "trained_ml" | "deterministic_demo" | "unavailable",
  "model_version": "cashout-location-xgb-v4",
  "operational_scope": "DELHI_PILOT",
  "candidate_pool_size": 25,
  "time_prediction": {
    "predicted_minutes_to_cashout": 88.5,
    "model_version": "cashout-time-xgb-v3",
    "prediction_reference_time": "2026-09-13T20:34:00Z",
    "operational_window": "Next 2–4 Hours (operational estimate window)"
  },
  "limitations": [
    "Operational scope is strictly calibrated for Delhi Pilot 60 clusters."
  ]
}
```

---

### 2.4 Get Persisted Prediction (`GET /api/v1/predictions/{complaint_id}`)
* **Purpose**: Strictly read-only query returning the latest persisted prediction.
* **Guarantees**: Zero ML inference, zero recalculation, zero DB mutations. Returns `404 Not Found` if no prediction has been persisted yet.

---

### 2.5 GIS Prediction Overlay (`GET /api/v1/risk-map/prediction/{complaint_id}`)
* **Purpose**: Retrieve map overlay coordinates and risk layers for an active case.
* **Guarantees**: Exactly mirrors the persisted `Prediction` and `PredictionLocation` records with 100% ID and cluster alignment.

---

### 2.6 Generate Case Alert (`POST /api/v1/alerts/generate/{complaint_id}`)
* **Purpose**: Generate a nodal officer alert referencing the active case and its persisted `prediction_id`.
* **Guarantees**: Links directly to the existing Prediction without inventing new scores or locations.
