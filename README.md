# CyberShield AI | National Cybercrime Predictive Intelligence Platform
**Smart India Hackathon SIH26184**

Predicting likely fraudulent cash-withdrawal locations and time windows from cybercrime complaint and transaction data using **Machine Learning + Graph Intelligence + Geospatial Intelligence + Temporal Intelligence**.

---

## 🎯 Core Capabilities: WHERE, WHEN, RISK, WHY

| Dimension | Engine Output | Explanation / Value |
| :--- | :--- | :--- |
| **WHERE** | **Vijay Nagar, Indore** | High-risk ATM cluster predicted through geospatial & mule co-occurrence |
| **WHEN** | **Next 2–4 Hours** | Bounded temporal window preventing cash extraction before dispersal |
| **RISK** | **87% CRITICAL** | Hybrid fusion score (0.40 ML + 0.25 Graph + 0.20 Geo + 0.15 Temporal) |
| **WHY** | **Mule History (+21%), Hotspot (+17%)** | Explainable AI factor contribution and decision support |

---

## 🚀 Quick Start Guide (Windows Powershell)

### 1. Environment Setup
```powershell
# Clone or navigate inside the workspace
cd "c:\Users\adity\Downloads\CrimeTrace-AI-SIH-main\CyberShield AI"

# Copy environment variables
Copy-Item .env.example .env
```

### 2. Backend Installation & Database Setup
```powershell
# Install Python backend dependencies
python -m pip install -r backend/requirements.txt

# Run initial database initialization and seed demo data (CMP-1042 + 6 LEA roles)
python database/seed/seed_data.py

# Optional: Train ML models (GradientBoosting candidate ranker & time regressor)
python ml/training/train_pipeline.py
```

### 3. Frontend Installation
```powershell
# Navigate into frontend and install Node dependencies
cd frontend
npm install
cd ..
```

### 4. Running the Complete System
Open two terminals in the project root:

**Terminal 1 — Run Backend Server (FastAPI):**
```powershell
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Run Frontend Server (Vite):**
```powershell
cd frontend
npm run dev
```

- **Frontend Application**: [http://localhost:5173](http://localhost:5173)
- **Backend API & Health**: [http://localhost:8000/health](http://localhost:8000/health)
- **Swagger Interactive API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔑 Demo Stakeholder Credentials

The system supports 1-click demo login on the `/login` screen or direct password authentication:

| Stakeholder Role | Official Police Email / ID | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **I4C_ADMIN** | `admin@cybershield.gov.in` | `CyberAdmin@2026` | National Command & All LEA Nodes |
| **STATE_LEA** | `state.lea@mp.police.gov.in` | `StateLea@2026` | State Cyber Cell Headquarters (MP) |
| **DISTRICT_LEA** | `district.lea@indore.police.gov.in` | `IndoreLea@2026` | Field Units, Interception & ATM Hold |
| **BANK_OFFICER** | `officer@sbi.co.in` | `BankOfficer@2026` | ATM Hold & Account Lien Placement |
| **ANALYST** | `analyst@cybershield.gov.in` | `Analyst@2026` | Graph Analytics & Temporal Triage |
| **AUDITOR** | `auditor@mha.gov.in` | `Auditor@2026` | Regulatory & Chain of Custody Audit |

---

## 🧪 Automated Testing
To run the automated test suite verifying all 10 core integration requirements:
```powershell
python -m pytest tests/test_backend.py -v
```

---

## 📂 Project Architecture

```
CyberShield AI/
├── frontend/                     # React 18 + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── components/           # Sidebar, Topbar
│   │   ├── layouts/              # DashboardLayout
│   │   ├── pages/                # Dashboard, CaseIntelligence, Network, RiskMap, Alerts, Analytics, Audit
│   │   ├── maps/                 # Leaflet CashOutRiskMap
│   │   ├── graphs/               # CytoscapeNetwork
│   │   ├── services/             # Axios API Client
│   │   ├── store/                # AuthContext
│   │   └── types/                # TypeScript Interfaces
├── backend/                      # Python FastAPI + SQLAlchemy + Pydantic
│   ├── app/
│   │   ├── api/                  # Complaints, Predictions, GIS, Alerts, Analytics, Model, Audit
│   │   ├── auth/                 # JWT Tokens & Salted Password Verification
│   │   ├── models/               # SQLAlchemy ORM Models (User, Complaint, Account, Alert, etc.)
│   │   ├── schemas/              # Pydantic Request/Response Models
│   │   ├── services/             # PredictionService, GraphService, AlertService, AuditService
│   │   ├── websocket/            # Live Alert Broadcast Manager
│   │   ├── config/               # Settings
│   │   └── main.py               # Application Entrypoint & Lifespan
├── ml/                           # ML & Explainability Subsystem
│   ├── features/                 # Feature Extractor
│   ├── training/                 # Model Training Pipeline
│   └── artifacts/                # Saved Scikit-Learn / Joblib Models
├── synthetic_data/               # Dataset Generator (500 to 20,000 complaints)
├── database/seed/                # Seed script with CMP-1042 and MP ATM clusters
├── docs/                         # Architecture, ML pipeline, Schema, API docs, Demo script
└── tests/                        # Pytest Integration Test Suite
```

---

## 🛡️ Hackathon SIH Demo Workflow
1. Navigate to `http://localhost:5173/login` and select **National Command (I4C)** or **District Cyber Cell**.
2. On `/dashboard`, click the glowing **RUN SIH DEMO** button.
3. Observe case **CMP-1042** or submit a new Delhi NCT cybercrime complaint:
   - Official Top-3 ranked cash-out locations with calibrated probability and operational risk level.
   - Bounded cash-out time window (`cashout-time-xgb-v3`).
   - Intervention Priority and dispatch recommendation.
4. On **Case Intelligence**:
   - Inspect Model Provenance (`cashout-location-xgb-v7-compat`).
   - Run on-demand **Explain Prediction** to generate local LIME feature attributions and fidelity diagnostics.
   - Run **Verify on Ledger** to audit prediction hash anchoring against the Hyperledger Fabric ledger.
5. On **Model Performance**:
   - Review official production model validation metrics.
   - Inspect the **Research Pipeline & Ablation Audit (Phase B.6)** card distinguishing official production from the unpromoted shadow model.

---

## 🏛️ System Architecture & Subsystems

```
Complaint Intake
       │
       ▼
Feature Extraction (V7-compat Schema: 39 Features)
       │
       ▼
Official Trained ML Engine (cashout-location-xgb-v7-compat + cashout-time-xgb-v3)
       │
       ▼
Authoritative Top-3 Cash-Out Predictions
       ├── PostgreSQL Persistence (Atomic 1 Prediction + 3 Locations)
       ├── Case Intelligence & Triage
       ├── GIS Risk Map (Cluster Centroids & Radii)
       ├── Tactical Alerts & Dispatch
       ├── Hyperledger Fabric Prediction Audit Anchor (Canonical SHA-256)
       └── On-Demand LIME Tabular Explainability (Non-blocking Local Surrogate)

Separately (Consortium Layer):
BankA / BankB / BankC / I4C / LEA
       │
       ▼
Hyperledger Fabric Blockchain Consortium (Channel: cyber-intelligence)
       │
       ├── geo-intelligence chaincode (Multi-org mule & ATM corridor signals)
       ├── prediction-audit chaincode (Tamper-evident hash ledger)
       ▼
Fabric Gateway & Blockchain Feature Engine (Operational Intelligence Infrastructure)
```

---

## 🔬 Research Qualification & Ablation Audit (Phase B.6)

During Phase B.6, an experimental second-stage **Blockchain Shadow Re-Ranker V1** was ablated against the official production baseline:
- **Baseline (Model B — Official V7 Features)**: 33.60% Top-3 Recall
- **Candidate (Model C — V7 + Fabric Consortium Signals)**: 33.67% Top-3 Recall
- **Incremental Gain**: +0.07 percentage points
- **Pre-Registered Promotion Gate**: `>= +1.0 pp Top-3 Gain`
- **Qualification Decision**: **DID NOT MEET PROMOTION GATE**

Following scientific integrity standards, the promotion gate was not relaxed. The experimental re-ranker remains inactive, and the validated official **cashout-location-xgb-v7-compat** model remains authoritative in production. Consortium blockchain signals function as operational intelligence and immutable audit infrastructure.

---

## ⚖️ Explainability (Phase B.7 LIME)

LIME provides a non-blocking, on-demand local surrogate explanation for official predictions:
- Explains feature contributions for Top-3 candidate locations without modifying probabilities or rankings.
- Conservative Fidelity Policy:
  - $R^2 \ge 0.70$: `HIGH_FIDELITY`
  - $0.40 \le R^2 < 0.70$: `MODERATE_FIDELITY`
  - $R^2 < 0.40$: `LOW_FIDELITY`
- Explicit Disclaimer: *LIME provides a local approximation of model behavior and does not prove causality or criminal activity.*

---

## 🔒 Security, Compliance & Judge-Safe Claims

### Approved Scientific Statement:
> "We trained our own XGBoost-based cash-out location prediction pipeline on controlled synthetic Delhi cybercrime data. Hyperledger Fabric provides a permissioned multi-organization intelligence and tamper-evident audit layer. Verified consortium signals can be converted into geo-risk features. We experimentally tested those features in a second-stage shadow ranker, but it did not meet our pre-defined promotion threshold (+1.0 pp Top-3), so we retained the validated V7 production model. LIME provides local explanations for the official prediction on demand without altering the prediction itself."

### Ground Truth & Limitations:
- **Dataset**: Controlled synthetic prototype data modeled after Delhi NCT cybercrime topology. No real NCRP production data or victim PII is used.
- **Consortium**: Simulated multi-bank/LEA consortium nodes (BankA, BankB, BankC, I4C, LEA). No live bank API keys or customer credentials.
- **Explainability**: LIME is a local surrogate approximation, not proof of criminal intent or causal proof.
- **Accuracy Claim**: We do NOT claim that blockchain improved production ML accuracy, as B.6 did not qualify for promotion.
