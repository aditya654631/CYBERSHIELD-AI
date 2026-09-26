# CyberShield AI

**AxiomSix · Smart India Hackathon 2026 · SIH26184 · Delhi pilot**

CyberShield AI is a decision-support prototype for predicting likely cash-withdrawal areas from cybercrime complaints and transaction context. It ranks three candidate locations, estimates an operational time window, and helps authorized officers review the supporting signals and coordinate a response. An officer makes the final decision.

[Prototype](https://cybershield-ai-ruddy.vercel.app/) · [Problem-statement traceability](docs/implementation/FINAL_PS_ACCEPTANCE_MATRIX.md) · [Pilot readiness checklist](docs/implementation/PILOT_READINESS_CHECKLIST.md)

> **Pilot boundary:** The location model is supported for the synthetic Delhi pilot only. This repository has no live NCRP/CFCFRMS feed or certified bank integration. Predictions are investigative leads, not confirmed cash-out locations or evidence of criminal activity.

## What the prototype does

| Area | Current capability |
| --- | --- |
| Complaint and transaction intake | Records cases and multi-hop transfers; new transaction information can create a new prediction version without overwriting earlier versions. |
| Location and time | Ranks the top three Delhi candidate clusters with a relative risk signal and an operational time estimate. The displayed window is not a calibrated confidence interval. |
| Case intelligence | Shows the transaction network, prediction history, ATM/CSP context, and on-demand LIME explanations with fidelity warnings. |
| GIS dashboard | Displays active candidates and historical hotspots with region, district, crime category, risk, and explicit time-basis filters. |
| Alerts and coordination | Uses a persistent notification outbox with retry, delivery state, acknowledgement, expiry, and controlled cross-jurisdiction handoff. External SMS/email delivery depends on configured providers. |
| Bank actions | Tracks requests and signed sandbox callbacks with separate simulated, sandbox, and live labels. No real fund hold is claimed without a verified external response. |
| Evidence and outcomes | Stores evidence metadata and SHA-256 integrity checks, exports case reports, and records observed outcomes separately from predictions. |
| Access control | Applies role, jurisdiction, case, and bank scoping on backend APIs. |

The second registered geography, `mumbai_mmr`, is a **synthetic workflow fixture**. It does not have a qualified location model; unsupported-region inference returns `MODEL_NOT_SUPPORTED_FOR_REGION` rather than silently using Delhi predictions.

## Architecture

```text
Complaint + transaction updates
          │
          ▼
Feature extraction and transaction graph
          │
          ▼
Delhi location model (V8-debiased) + time model (V3)
          │
          ▼
Versioned top-3 prediction and operational window
          ├── Case intelligence, GIS map, ATM/CSP context
          ├── Durable alerts and controlled LEA handoff
          ├── Sandbox bank-action workflow
          ├── Evidence, reports, and verified outcome records
          └── On-demand LIME explanation

Optional Hyperledger Fabric components support consortium signals and
tamper-evident audit records. They are not required for core prediction.
```

The experimental Fabric-signal re-ranker did **not** meet its predefined promotion gate and is inactive. Its result is not a deployed accuracy gain.

## Run locally with Docker

Prerequisite: Docker Engine with Compose. Copy the configuration template and set local secrets before using any shared environment.

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec backend alembic upgrade head
# Optional: populate the local database with synthetic demo records
docker compose --profile demo run --rm seed-demo
```

- Frontend: [http://localhost:5173](http://localhost:5173) (also exposed at `http://localhost:3000`)
- Backend health: [http://localhost:8000/health](http://localhost:8000/health)
- API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

The seed command changes the **local** database. Do not run it against a database containing real cases. Demo accounts are for isolated development only; change credentials before sharing an instance. Keep `.env`, local databases, uploaded evidence, and generated reports outside Git.

## Run without Docker (Windows PowerShell)

Python, Node.js/npm, and a configured database are required. `.env.example` defaults to local SQLite for development; use PostgreSQL for a deployment environment.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
# Optional synthetic demo data:
python -m database.seed.seed_data
```

Start the two application servers in separate terminals:

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
Set-Location frontend
npm ci
npm run dev
```

## Verification

```powershell
python -m pytest tests -k "not benchmark"
python -m pytest tests/test_phase13_integrated_workflow.py tests/test_phase13_unhappy_and_recovery.py
Set-Location frontend
npm run build
```

The functional suite and frontend build have passed in the recorded local audit. **Production performance acceptance remains open:** local latency benchmark results have varied, and a production-like PostgreSQL load test is still needed. See the [latest upload/readiness audit](docs/implementation/UPLOAD_READINESS_RESULT.md) for measured results and pending gates.

## Evaluation and limitations

- The project uses controlled **synthetic Delhi data**. Its accuracy and impact have not been established on authorized, independent real-world cases.
- The active runtime uses a V8-debiased location model. The separate Phase 10 baseline evaluator measures V7-compat; do not quote its uplift as a V8 result. [Evaluation handoff](docs/implementation/PHASE_10_RESULT.md).
- Time windows are operational estimates. Missing observed withdrawal times are excluded from timing evaluation, and uncalibrated windows are not advertised as 95% intervals. [Timing and LIME handoff](docs/implementation/PHASE_11_RESULT.md).
- LIME approximates the model near one prediction. Low local fidelity is displayed as a warning; an explanation neither proves causation nor changes the ranking.
- Outcome reporting separates known, unknown, excluded, and synthetic cases, and separates confirmed held funds from recovered funds. It does not infer savings from missing observations.
- Live government intake, bank core-system actions, provider-backed notifications, second-region model qualification, and external field validation require authorized partner access and additional testing.

For implementation evidence, see the [Phase 13 handoff](docs/implementation/PHASE_13_RESULT.md), [acceptance matrix](docs/implementation/FINAL_PS_ACCEPTANCE_MATRIX.md), and [operational runbook](docs/implementation/OPERATIONAL_RUNBOOK.md).
