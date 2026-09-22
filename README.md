# CyberShield AI | Delhi Pilot Cybercrime Predictive Intelligence Platform
**Smart India Hackathon SIH26184**

Predicting likely fraudulent cash-withdrawal locations and time windows from cybercrime complaint and transaction data using **Machine Learning + Graph Intelligence + Geospatial Intelligence + Temporal Intelligence**.

---

## 🎯 Core Capabilities: WHERE, WHEN, RISK, WHY

| Dimension | Engine Output | Explanation / Value |
| :--- | :--- | :--- |
| **WHERE** | **Top-ranked candidate clusters** | Versioned candidate ranking for the supported Delhi pilot geography |
| **WHEN** | **Operational time window** | A complaint-report-relative estimate; its basis and uncertainty are shown with each prediction |
| **RISK** | **Relative risk score** | A dynamic model/graph/geography/temporal signal, not a confirmed crime probability |
| **WHY** | **Local LIME factors** | A local approximation of the selected candidate score; never causal proof of criminal activity |

> The production model is supported only for the Delhi pilot catalog. Other registered
> regions can be used for workflow testing but return `MODEL_NOT_SUPPORTED_FOR_REGION`
> until independently qualified with authorized geography and outcome data.

---

## 🐳 Local Docker Sandbox

Run the local prototype stack (PostgreSQL 16, FastAPI Backend, React Frontend Nginx) using Docker Compose:

```bash
# 1. Start core services in background
docker compose up --build -d

# 2. Run database migrations to head
docker compose exec backend alembic upgrade head

# 3. Seed demo accounts & sample complaints (optional, explicit command)
docker compose --profile seed run --rm seed-demo
```

- **Frontend Application**: [http://localhost:5173](http://localhost:5173) (or `http://localhost:3000` via Nginx)
- **Backend API & Health**: [http://localhost:8000/health](http://localhost:8000/health)
- **System Diagnostics**: [http://localhost:8000/api/v1/system/status](http://localhost:8000/api/v1/system/status)
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🚀 Local Development Setup

### 1. Environment & Dependencies
```powershell
# Copy environment configuration
Copy-Item .env.example .env

# Create & activate Python virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install pinned production & development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Database Migrations & Seeding
```powershell
# Run authoritative Alembic migrations
alembic upgrade head

# Seed initial prototype demo data (CMP-1042 + Delhi NCT topology)
python -m database.seed.seed_data
```

### 3. Running Development Servers
**Terminal 1 — Backend (FastAPI):**
```powershell
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend (Vite):**
```powershell
cd frontend
npm run dev
```

---

## 🧪 Testing & Verification

CyberShield AI includes an isolated test suite using session-scoped temporary SQLite databases with safeguards against mutating production databases:

```powershell
# Run complete test suite (unit + integration + security + migrations)
pytest -v

# Run backend isolated tests only (excluding blockchain testnet)
pytest -m "not live" --ignore=blockchain/ -v

# Run Phase 1 security & RBAC tests
pytest tests/test_phase1_security_authorization.py -v

# Run Phase 2 database migration tests
pytest tests/test_database_migrations_phase2.py -v

# Run ML model & artifact verification tests
pytest tests/test_model_verification.py -v

# Run frontend production bundle build
cd frontend
npm run build
```

---


```bash
# 1. Start core services in background
docker compose up --build -d

# 2. Run database migrations to head
docker compose exec backend alembic upgrade head

# 3. Seed demo accounts & sample complaints (optional, explicit command)
docker compose --profile seed run --rm seed-demo
```

- **Frontend Application**: [http://localhost:5173](http://localhost:5173) (or `http://localhost:3000` via Nginx)
- **Backend API & Health**: [http://localhost:8000/health](http://localhost:8000/health)
- **System Diagnostics**: [http://localhost:8000/api/v1/system/status](http://localhost:8000/api/v1/system/status)
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🚀 Local Development Setup

### 1. Environment & Dependencies
```powershell
# Copy environment configuration
Copy-Item .env.example .env

# Create & activate Python virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install pinned production & development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Database Migrations & Seeding
```powershell
# Run authoritative Alembic migrations
alembic upgrade head

# Seed initial prototype demo data (CMP-1042 + Delhi NCT topology)
python -m database.seed.seed_data
```

### 3. Running Development Servers
**Terminal 1 — Backend (FastAPI):**
```powershell
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend (Vite):**
```powershell
cd frontend
npm run dev
```

---

## 🧪 Testing & Verification

CyberShield AI includes an isolated test suite using session-scoped temporary SQLite databases with safeguards against mutating production databases:

```powershell
# Run complete test suite (unit + integration + security + migrations)
pytest -v

# Run backend isolated tests only (excluding blockchain testnet)
pytest -m "not live" --ignore=blockchain/ -v

# Run Phase 1 security & RBAC tests
pytest tests/test_phase1_security_authorization.py -v

# Run Phase 2 database migration tests
pytest tests/test_database_migrations_phase2.py -v

# Run ML model & artifact verification tests
pytest tests/test_model_verification.py -v

# Run frontend production bundle build
cd frontend
npm run build
```

---

## 🔑 Local Demo Credentials

The seeded prototype has role-based access control and jurisdiction isolation. These are
public demo credentials for a locally seeded database only; never reuse them in a shared
or production deployment.

| Stakeholder Role | Police / Bank Email | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **I4C_ADMIN** | `admin@cybershield.gov.in` | `CyberAdmin@2026` | National Command (All jurisdictions) |
| **STATE_LEA** | `state.lea@delhi.cyber.gov.in` | `StateLea@2026` | Delhi Cyber Crime Unit (NCT) |
| **DISTRICT_LEA** | `district.lea@southdelhi.cyber.gov.in` | `DistrictLea@2026` | District Cyber Cell (South Delhi) |
| **BANK_OFFICER** | `officer@sbi.co.in` | `BankOfficer@2026` | Bank Hold Actions & Account Liens |
| **ANALYST** | `analyst@cybershield.gov.in` | `Analyst@2026` | Analytics & Graph Investigation |
| **AUDITOR** | `auditor@mha.gov.in` | `Auditor@2026` | Regulatory & Audit Log Review |

---

## 🏛️ System Architecture & Subsystems

```
Complaint Intake
       │
       ▼
Feature Extraction (V7-compat Schema: 47 Features)
       │
       ▼
Official Trained ML Engine (cashout-location-xgb-v7-compat + cashout-time-xgb-v3)
       │
       ▼
Authoritative Top-3 Cash-Out Predictions
       ├── Database Persistence (Atomic 1 Prediction + 3 Locations)
       ├── Case Intelligence & Triage
       ├── GIS Risk Map (Cluster Centroids & Radii)
       ├── Tactical Alerts & Dispatch (Authenticated WebSocket streaming)
       ├── Hyperledger Fabric Prediction Audit Anchor (Canonical SHA-256)
       └── On-Demand LIME Tabular Explainability (Non-blocking Local Surrogate)

Separately (Consortium Layer):
BankA / BankB / BankC / I4C / LEA
       │
       ▼
Hyperledger Fabric Blockchain Consortium (Channel: cyber-intelligence)
       ├── geo-intelligence chaincode (Multi-org mule & ATM corridor signals)
       └── prediction-audit chaincode (Tamper-evident hash ledger)
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
- Fidelity Thresholds:
  - $R^2 \ge 0.70$: `HIGH_FIDELITY`
  - $0.40 \le R^2 < 0.70$: `MODERATE_FIDELITY`
  - $R^2 < 0.40$: `LOW_FIDELITY`
- Explicit Disclaimer: *LIME provides a local approximation of model behavior and does not prove causality or criminal activity.*

---

## 🔒 Security, Compliance & Truthful Disclosures

### Approved Scientific Statement:
> "We trained our own XGBoost-based cash-out location prediction pipeline on controlled synthetic Delhi cybercrime data. Hyperledger Fabric provides a permissioned multi-organization intelligence and tamper-evident audit layer. Verified consortium signals can be converted into geo-risk features. We experimentally tested those features in a second-stage shadow ranker, but it did not meet our pre-defined promotion threshold (+1.0 pp Top-3), so we retained the validated V7 production model. LIME provides local explanations for the official prediction on demand without altering the prediction itself."

### Operational Prototype Truthfulness:
- **Dataset**: Controlled synthetic prototype data modeled after Delhi NCT cybercrime topology. No real NCRP production data or victim PII is used.
- **Banking Actions**: Bank actions remain explicitly labelled `SIMULATED` or `SANDBOX` unless verified partner callback evidence supports a configured integration. The system does not claim external core-banking settlement.
- **Consortium Network**: Simulated multi-bank/LEA consortium nodes (BankA, BankB, BankC, I4C, LEA). No live bank API keys or customer credentials.
- **Explainability**: LIME is a local surrogate approximation, not causal proof of criminal intent.
