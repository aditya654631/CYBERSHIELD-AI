# CyberShield AI — Operational Runbook & Production Administration Manual

**Document Version:** 1.0.0  
**Target Environment:** Cloud / On-Premise Production (State Police Data Centers & I4C Gateway)  
**Standard Compliance:** ISO 27001, CERT-In Cyber Security Guidelines, MHA I4C Inter-operability Standards  
**Last Audited:** September 2026 (Phase 13 Pilot Readiness)

---

## 1. System Overview & Architecture

CyberShield AI is a cyber-crime intelligence, pattern-analysis, and cash-out prediction engine designed for Law Enforcement Agencies (LEAs), I4C, and financial institutions.

```
+-----------------------------------------------------------------------------------+
|                                Client Applications                                |
|  (State LEA Portal | District Investigator | Bank Officer Portal | I4C Dashboard) |
+------------------------------------------+----------------------------------------+
                                           | HTTPS / TLS 1.3
                                           v
+-----------------------------------------------------------------------------------+
|                        Reverse Proxy / Load Balancer (Nginx)                      |
|                  Rate Limiting, Header Sanitization, SSL Termination               |
+------------------------------------------+----------------------------------------+
                                           | Internal ASGI
                                           v
+-----------------------------------------------------------------------------------+
|                            FastAPI Application Servers                            |
|             RBAC Engine, Cryptographic Audit Trail, Outbox Event Publisher        |
+---------------------+-------------------------------+-----------------------------+
                      |                               |
                      v                               v
+-------------------------------+   +-----------------------------------------------+
|    ML Inference Engine        |   |           Background Outbox Worker            |
| - XGBoost / LightGBM Ensembles|   | - Polling / Lease Locks                       |
| - NetworkX Multi-Hop Analyzer |   | - Exponential Backoff Retries                 |
| - Scikit-Learn Spatial DBSCAN |   | - Channel Adapters (SMS/Email/API/Dashboard)  |
+-------------------------------+   +-----------------------------------------------+
                      |                               |
                      +---------------+---------------+
                                      |
                                      v
+-----------------------------------------------------------------------------------+
|                        Primary PostgreSQL Database Engine                         |
|   Schema Partitioning, Row-Level Constraints, Audit Hash Chains, JSONB Evidence   |
+-----------------------------------------------------------------------------------+
```

---

## 2. Database Migrations (Alembic SOP)

### 2.1 Pre-Migration Health Checks
Before applying schema migrations to staging or production:
1. Confirm connectivity and current schema revision:
   ```bash
   alembic current
   ```
2. Verify head revision identifier against release notes:
   ```bash
   alembic heads
   ```
3. Take a pre-migration database snapshot (see Section 3).

### 2.2 Applying Upgrades
Run database migrations using the isolated CLI command:
```bash
alembic upgrade head
```

### 2.3 Rollback Procedure
If a migration fails or must be aborted immediately:
```bash
# Roll back single revision
alembic downgrade -1

# Roll back to specific baseline revision
alembic downgrade <target_revision_id>
```

### 2.4 Zero-Downtime Migration Guidelines
- Additive columns must always be `nullable=True` or have a server default.
- Never drop columns in the same release as code that reads them.
- Large index additions on production tables must use PostgreSQL `CONCURRENTLY`:
  ```sql
  CREATE INDEX CONCURRENTLY idx_complaints_reported_at ON complaints(reported_at);
  ```

---

## 3. Disaster Recovery: Backup & Restore Playbook

### 3.1 Backup Strategy & Schedule
- **Full Logical Dump:** Automated daily at 02:00 IST using `pg_dump`.
- **WAL Archiving:** Continuous streaming WAL archiving to secure off-site object storage (S3/MinIO/GCS) with 15-minute RPO.
- **Retention:** 30 days daily, 12 months monthly snapshots for statutory compliance.

### 3.2 Executing a Manual Backup
```bash
export PGPASSWORD="$DB_PASSWORD"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
pg_dump -Fc -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  --file="/var/backups/cybershield/cybershield_prod_${TIMESTAMP}.dump"
unset PGPASSWORD
```

### 3.3 Restoration & Point-in-Time Recovery
> **MANDATORY SAFETY RULE:** Never restore directly into the live production database. Always verify restore into an isolated staging/sandbox database first.

```bash
# 1. Provision or clean target database
createdb -h "$STAGING_HOST" -U "$DB_USER" cybershield_restore_test

# 2. Restore schema and data
pg_restore -h "$STAGING_HOST" -U "$DB_USER" -d cybershield_restore_test \
  --clean --if-exists --no-owner --no-privileges \
  /var/backups/cybershield/cybershield_prod_${TIMESTAMP}.dump

# 3. Run validation smoke tests against restored database
pytest tests/test_schema_hardening.py -q
```

---

## 4. Notification Outbox Worker Operations

### 4.1 Worker Architecture & Lifecycle
The Notification Outbox guarantees at-least-once delivery of investigator alerts and bank dispatch requests without distributed transaction locks.

```
[QUEUED] --(Worker Claims Item)--> [PROCESSING (Lease 300s)]
                                         |
                       +-----------------+-----------------+
                       | (Success)                         | (Error / Timeout)
                       v                                   v
                  [COMPLETED]                           [FAILED]
                                                           |
                                           (Attempts < 5)  |  (Attempts >= 5)
                                                   +-------+-------+
                                                   v               v
                                            [Re-queued]    [PERMANENT_FAILURE]
                                            (Backoff Exp)       (DLQ Alert)
```

### 4.2 Stale Lease Reclamation (Worker Crash Recovery)
If an outbox worker container or pod crashes while processing events:
1. Active workers query `NotificationOutbox` where `status = 'PROCESSING'` and `lease_expires_at < NOW()`.
2. Stale leases are automatically reclaimed and reset to `PROCESSING` under the new worker's ID.
3. No manual database intervention is needed under ordinary container restarts.

### 4.3 Poison-Pill & Dead-Letter Queue (DLQ) Remediation
When an event exceeds `max_attempts` (default: 5 attempts), it transitions to `PERMANENT_FAILURE`.
To investigate and remediate dead-letter events:
```python
# In backend administrative console:
from backend.app.models.db import SessionLocal
from backend.app.models.models import NotificationOutbox
from backend.app.services.outbox_service import outbox_service

db = SessionLocal()
failed_events = db.query(NotificationOutbox).filter_by(status="PERMANENT_FAILURE").all()
for ev in failed_events:
    print(f"Event #{ev.id} | Type: {ev.event_type} | Last Error: {ev.last_error}")

# To re-queue an event after root cause is resolved:
failed_events[0].status = "QUEUED"
failed_events[0].attempt_count = 0
failed_events[0].next_retry_at = None
db.commit()
```

---

## 5. Bank Sandbox vs. Live Production Isolation

### 5.1 Environment Isolation Boundaries
| Capability | SANDBOX Mode | PRODUCTION Mode |
|---|---|---|
| **Endpoint Target** | Internal Sandbox Simulator | NPCI / Direct Core Banking API |
| **Shared Secret** | `SANDBOX_SHARED_SECRET` | Hardware Security Module (HSM) / Vault |
| **Signatures** | HMAC-SHA256 test key | RSA-SHA256 / Mutual TLS (mTLS) |
| **Monetary Holds** | Simulated Database Hold | Actual Core Banking Ledger Hold |
| **Callback Spoofing** | Strictly Blocked (400/401/409) | Strictly Blocked (400/401/409) |

### 5.2 HMAC Secret Rotation Playbook
1. Generate a new high-entropy 256-bit key:
   ```bash
   openssl rand -hex 32
   ```
2. Store the key in AWS Secrets Manager / HashiCorp Vault.
3. Update server configuration with dual-key support during the 24-hour transition window:
   `BANK_ACTIVE_SECRET` and `BANK_PREVIOUS_SECRET`.
4. Partner banks transition signature generation to the new key.
5. Decommission `BANK_PREVIOUS_SECRET` after zero callbacks use old signature.

---

## 6. Model Operations & Region Boundary Guardrails

### 6.1 Delhi Production Baseline & Multi-Region Support
The machine learning pipeline (XGBoost, LightGBM, Random Forest ensembles) is strictly calibrated and validated for the **Delhi National Capital Territory (NCT)** pilot.

```
                      Inference Request
                              |
                   [Validate region_id]
                              |
             +----------------+----------------+
             |                                 |
      region_id == "delhi"              region_id != "delhi"
             v                                 v
   [Run Active ML Pipeline]          [Strict Model Refusal]
   - XGBoost Lat/Lon Inference       - Return MODEL_NOT_SUPPORTED_FOR_REGION
   - Window Prediction               - 0 Candidate Locations
   - Cluster Ranking (p95 < 55ms)    - Explicit Refusal Reason Logged
                                     - NO Silent Delhi Fallback
```

### 6.2 Model Artifact Verification
Before starting production instances, verify that all 45 production model artifact SHA-256 hashes match the baseline:
```bash
.\.venv\Scripts\python.exe scratch/verify_artifacts.py
```
If any hash fails, application boot halts with `CriticalIntegrityError`.

---

## 7. Security, Audit Trails & Incident Response

### 7.1 Cryptographic Audit Hash Chain Verification
Every mutation in CyberShield AI generates an entry in `audit_logs` chained cryptographically to the preceding entry:
$$\text{Hash}_n = \text{SHA-256}(\text{Hash}_{n-1} \parallel \text{Timestamp} \parallel \text{User} \parallel \text{Action} \parallel \text{Payload})$$

To verify audit chain integrity:
```bash
.\.venv\Scripts\python.exe -c "
from backend.app.models.db import SessionLocal
from backend.app.services.audit_service import verify_full_audit_chain
db = SessionLocal()
is_valid, broken_id = verify_full_audit_chain(db)
print('Chain Valid:', is_valid, 'Broken ID:', broken_id)
"
```

### 7.2 Evidence Tampering Alert
If an investigator or external actor alters evidence bytes directly on disk, the periodic integrity auditor detects the discrepancy immediately:
- Stored SHA-256 vs. Disk SHA-256 mismatch
- Endpoint `GET /api/v1/complaints/{id}/evidence/{ev_id}/integrity` flags `is_valid: false`
- Critical incident alert dispatched to I4C Auditor role.

### 7.3 Emergency Contact & Escalation Matrix
- **Level 1 (Operations / L1 Support):** System monitoring, outbox stuck events, account lockouts.
- **Level 2 (Lead Engineer / DBA):** Database replication lag, Alembic migration failure, API latency spikes.
- **Level 3 (Security Officer / I4C Liaison):** Evidence hash mismatches, unauthorized cross-state handoff attempts, bank HMAC verification anomalies.
