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
1. Navigate to `http://localhost:5173/login` and select **District Cyber Cell (Indore)**.
2. On `/dashboard`, click the glowing **RUN SIH DEMO** button.
3. Observe case **CMP-1042** with:
   - Ranked locations: **Vijay Nagar (87% CRITICAL)**, **Palasia (61% HIGH)**, **Rau (34% MEDIUM)**.
   - Cash-out window: **Next 2–4 Hours**.
   - Intervention Priority: **94 / 100 IMMEDIATE ACTION**.
4. Click **ANALYZE NETWORK** to explore the Cytoscape.js directed graph from the victim to the Vijay Nagar cluster.
5. Click **GENERATE ALERT** to dispatch tactical alarms and inspect the audit log on `/audit`.
