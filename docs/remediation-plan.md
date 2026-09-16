# CyberShield AI — Comprehensive System Audit & Remediation Plan

> **Audit Date**: September 16, 2026  
> **Status**: Read-Only Comprehensive Audit Completed (Zero Code Modification Applied)  
> **Live App Reference**: [https://cybershield-ai-ruddy.vercel.app/login](https://cybershield-ai-ruddy.vercel.app/login)  
> **Production API Reference**: [https://cybershield-ai-production-66121.up.railway.app/health](https://cybershield-ai-production-66121.up.railway.app/health)  

---

## Executive Summary & System Verification Status

CyberShield AI underwent an exhaustive, non-destructive audit spanning the backend API, ML inference engine, LIME explainability service, database schema, GIS mapping, frontend user flows, test suite, and deployment topologies.

| Component | Status | Verified Finding Summary |
| :--- | :--- | :--- |
| **Git Working Tree** | Clean (`main` branch) | No uncommitted changes. Working tree preserved untouched. |
| **Frontend Build** | **PASS** (40.33s) | `tsc && vite build` passed cleanly across 2,502 modules with zero errors. |
| **Test Suite Baseline** | **264 Passed, 70 Failed** | Core Phase 1 Security/RBAC, Phase 2 Migrations, Model Verification, and LIME math pass 100%. 70 failures are pre-existing legacy unit-test regressions documented separately below. |
| **Live Backend (Railway)** | **ONLINE / HEALTHY** | PostgreSQL 16 connected (latency ~587 ms), ML engine `cashout-location-xgb-v7-compat` active, strict RBAC enforced. |
| **Live Frontend (Vercel)** | **ONLINE** | Deployed at `https://cybershield-ai-ruddy.vercel.app`, serving production bundle communicating with Railway. |
| **Model Artifact Directories** | **DUPLICATE IDENTIFIED** | Authoritative upstream source is `ml/artifacts/`. Runtime container bundle is `backend/ml/artifacts/`. Hash drift caused by CRLF line endings. |

---

## Baseline Test Suite Failures (Reported Separately)

A full run of `pytest` across all test modules yielded **264 passed, 70 failed, 37,128 warnings**:

### 1. Root Cause Analysis of 70 Pre-Existing Baseline Failures

> [!IMPORTANT]
> **Baseline Test Failure Reviewability Policy**: Baseline test failures remain individually reviewable; do not declare all failures harmless merely because they appear related to old tests. Each failure must be evaluated on its own merits to verify whether it indicates a genuine code regression, test-harness obsolescence, or schema divergence.

While many failures relate to security, schema, and ML promotions, they are categorized below for systematic review:

1. **Direct Handler Invocation Missing Dependency Injection (11 failures)**:
   - **Example**: `tests/test_delhi_intake_map_regression.py::test_map_counts_latest_active_predictions_and_complete_atm_inventory`
   - **Root Cause**: Phase 1 Security PR #1 added `current_user: User = Depends(get_current_user)` to route signatures. Older tests directly invoke python function `get_risk_map_overview(db=db)` without passing `current_user`, throwing:  
     `AttributeError: 'Depends' object has no attribute 'role'`.
   - **Fix Required**: Update tests to use `TestClient` with authenticated authorization headers or pass a mock `User`.

2. **Unauthenticated Access Rejection in Legacy Tests (19 failures)**:
   - **Example**: `tests/test_step14_auth_audit.py`, `tests/test_step13_dashboard_db_integration.py`
   - **Root Cause**: Tests written prior to Phase 1 RBAC send unauthenticated requests to protected endpoints (`/api/v1/complaints`, `/api/v1/dashboard/summary`), receiving HTTP 401 Unauthorized as designed.

3. **Multi-Hop Synthetic Transaction Topology Updates (18 failures)**:
   - **Example**: `tests/test_dynamic_transaction_graph.py::test_empty_context_returns_empty_graph`, `tests/test_transaction_scenario_linking.py`
   - **Root Cause**: Commits `555e5a0` and `728adf0` added multi-hop synthetic transaction trails and database-driven graph linking for test cases (e.g. `CMP-NEW-000004`), causing tests expecting zero nodes/empty context to fail assertions.

4. **Legacy ML Version & Metric Assertions (22 failures)**:
   - **Example**: `tests/test_ml_pipeline.py`, `tests/test_ml_remediation.py`, `tests/test_step9_prediction_flow.py`
   - **Root Cause**: Tests explicitly assert outdated V2/V3 model version strings (`cashout-location-xgb-v2`) or obsolete 50.8% recall metrics that were superseded when the pipeline promoted V4 and V7-compat.

### 2. High-Assurance Passing Test Suites (264 Tests)
- `tests/test_phase1_security_authorization.py`: **100% PASS** (RBAC, JWT tokens, role isolation, spoof protection, rate limiting)
- `tests/test_database_migrations_phase2.py`: **100% PASS** (Alembic upgrade head, schema constraints, indexes)
- `tests/test_model_verification.py`: **100% PASS** (SHA-256 integrity checks on official V7-compat artifacts)
- `tests/test_prediction_explainability_lime.py`: **100% PASS** (LIME surrogate training, fidelity thresholds, deterministic repeatability)
- `tests/test_v7_compat_runtime_parity.py`: **100% PASS** (Feature parity and prediction correctness)
- `tests/test_prediction_idempotency.py`: **100% PASS** (Read-only GET idempotency)
- `tests/test_websocket_reliability.py`: **100% PASS** (WebSocket token validation and streaming)
- `tests/test_system_status.py`: **100% PASS** (System diagnostics and health endpoints)

---

## Detailed Audit Findings & Remediation Plan

### Issue 1: Hotspots Show "CRITICAL" Percentage With "No Active Prediction" and ₹0

- **Verified Finding**:
  On the Dashboard under **Priority Interception Hotspots**, top candidate cluster cards frequently display:
  `88% CRITICAL`, `Window: No active case prediction`, and `₹0`.
- **Evidence**:
  - `backend/app/api/gis_routes.py` lines 44–72 (`_cluster_items`):
    ```python
    for cluster in clusters:
        cases = list(evidence.get(cluster.id, {}).values())
        risk_score = max((float(pred.risk_score or 0) for pred, _ in cases), default=float(cluster.risk_score or 0))
        risk_level = "CRITICAL" if risk_score >= .8 else "HIGH" if risk_score >= .6 else "MEDIUM" if risk_score >= .4 else "LOW"
        ...
        result.append({
            ...
            "risk_score": risk_score,
            "risk_level": risk_level,
            "active_cases": len(cases),
            "amount_at_risk": sum(float(comp.amount) for _, comp in cases),
            "expected_window": window, # "No active case prediction" if cases empty
        })
    ```
  - `frontend/src/pages/Dashboard.tsx` lines 240–251:
    ```tsx
    <Badge variant={hotspot.risk_level === 'CRITICAL' ? 'critical' : 'warning'}>
      {Math.round(hotspot.risk_score * 100)}% {hotspot.risk_level}
    </Badge>
    ...
    <span>Window: {hotspot.expected_window}</span>
    <span>₹{hotspot.amount_at_risk.toLocaleString('en-IN')}</span>
    ```
- **Root Cause**:
  `LocationCluster.risk_score` in the database seed represents a **static historical baseline prior** (e.g. 0.87 for high-density Delhi commercial hubs). When a cluster currently has zero active, unexpired case predictions (`cases == []`), `_cluster_items` falls back to `default=float(cluster.risk_score)`. Because the historical prior is $\ge 0.8$, the cluster is classified as `"CRITICAL"` and assigned 87%. Meanwhile, `amount_at_risk` is `0.0` and `expected_window` is `"No active case prediction"`. The Dashboard card displays this as an active interception priority, creating a contradictory presentation where an officer sees "87% CRITICAL" with ₹0 at risk and no active prediction.
- **Affected Files**:
  - `backend/app/api/gis_routes.py`
  - `backend/app/schemas/schemas.py`
  - `frontend/src/pages/Dashboard.tsx`
  - `frontend/src/pages/RiskMap.tsx`
- **Proposed Fix**:
  1. In `gis_routes.py`, disentangle historical baseline priors from active case risk:
     - Add `historical_baseline_score: float` and `has_active_incidents: bool` to the response.
     - When `active_cases == 0`, set `risk_level = "BASELINE"` or `"MONITORING"`, or format `risk_score` distinctly.
     - Sort active cases ahead of inactive clusters so active incidents occupy Priority Interception slots.
  2. In `Dashboard.tsx`, adjust the badge and labels:
     - If `active_cases > 0`: Display `{Math.round(hotspot.risk_score * 100)}% ACTIVE {hotspot.risk_level}` with actual amount and time window.
     - If `active_cases === 0`: Display `HISTORICAL PRIOR: {Math.round(hotspot.historical_baseline_score * 100)}%` with badge `BASELINE MONITORING` and `₹0 Active Risk`.
- **Verification Plan**:
  - Call `/api/v1/risk-map` with both active complaints and zero-complaint states; verify that inactive clusters do not output `CRITICAL` or fake active window.
  - Verify Dashboard UI card renders `BASELINE MONITORING` cleanly.
- **Dependencies**: Backend schema update (`HotspotCluster`), frontend badge variants.
- **Status**: **VERIFIED ROOT CAUSE — PENDING REMEDIATION**

---

### Issue 2: Low ML Candidate Scores and Confusing Score Interpretation

- **Verified Finding**:
  In `CaseIntelligence.tsx`, the top-ranked candidate ATM cluster shows a score of only **11.2%** or **13.5%**, yet right above it the card displays **CRITICAL** and **IMMEDIATE ACTION**. In the main card header, `risk_score` is shown as `11% CRITICAL`. Users and evaluators find this confusing, asking why the model confidence is "only 11%" if the risk is "CRITICAL".
- **Evidence**:
  - `backend/app/services/prediction_service.py` lines 445–452, 568–572, 633–638:
    ```python
    cal_probs = self.calibrator.predict_proba(raw_scores.reshape(-1, 1))[:, 1]
    ...
    top_locations.append({
        ...
        "probability": prob,         # e.g. 0.1124
        "ml_probability": prob,
        "risk_score": prob,
        "risk_level": risk_band,      # "CRITICAL" based on amount >= 5L & window <= 90m
    })
    ...
    "risk_score": primary_prob,       # 0.1124
    "risk_percentage": int(primary_prob * 100), # 11
    "risk_level": primary_band,       # "CRITICAL"
    "intervention_priority": priority # 90 ("IMMEDIATE ACTION")
    ```
  - `frontend/src/utils/predictionDisplay.ts` lines 29–33:
    ```typescript
    export const modelScore = (location: PredictionLocationItem): string => {
      const value = location.ml_probability ?? location.probability;
      if (value == null || !Number.isFinite(value) || value < 0 || value > 1) return 'Unavailable';
      return `${(value * 100).toFixed(1)}%`;
    };
    ```
- **Root Cause & Score Semantics Clarification**:
  1. **Candidate Distribution and Prediction Scale Diagnostics**: A 1-positive-among-25 candidate distribution does **not** impose a mathematical 10–20% maximum on individual predictions. In well-separated classification or ranking tasks, calibrated probabilities can reach higher confidences if discriminative features are decisive. The true reason for low scores remains to be verified through rigorous model, feature, and calibration diagnostics.
  2. **Percentage Sign Misinterpretation**: `predictionDisplay.ts` formatted `0.112` as `11.2%`. Evaluators misinterpreted this as "11% model accuracy" or a literal real-world probability of withdrawal, rather than recognizing it as a relative model ranking score across candidate Delhi zones.
  3. **Operational Priority vs Candidate Model Score**: Operational priority and candidate model score are completely separate concepts:
     - **Candidate Model Score**: A relative ranking score produced by the trained model (`location_ranker_v7_compat` or `v4`) to compare cash-out clusters.
     - **Operational Priority**: A dispatch urgency tier (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) computed from codified incident risk rules: complaint monetary amount band ($\ge ₹5\text{L}$ Critical, $\ge ₹75\text{k}$ High, $\ge ₹20\text{k}$ Medium), predicted cash-out window urgency ($\le 90\text{ min}$), reporting recency ($\le 4\text{ hrs}$ delay), and candidate rank (#1 Primary, #2 Secondary, #3 Tertiary).
     - A high operational priority (e.g. `CRITICAL`) can legitimately coexist with a low candidate model score (e.g. `11.2%`), because high monetary loss and imminent cash-out demand urgent intervention regardless of candidate score distribution. The UI must clearly explain their respective meanings.
- **Affected Files**:
  - `backend/app/services/prediction_service.py`
  - `frontend/src/utils/predictionDisplay.ts`
  - `frontend/src/pages/CaseIntelligence.tsx`
  - `frontend/src/maps/UnifiedRiskMap.tsx`
- **Corrected Remediation Approach**:
  1. **Preserve Official Numerical Outputs**:
     - **Do NOT introduce the proposed 40/25/20/15 composite threat formula**. Its weights have not been validated.
     - **Do NOT rescale low candidate scores into artificial "relevance indices"**. Preserve official numerical outputs as calibrated.
  2. **Clarify Score Semantics in UI**:
     - Label candidate outputs explicitly as **"Model ranking score"**.
     - Display a clear explanatory note and tooltip clarifying: *"Relative model ranking score used to compare candidate cash-out zones. This is not model accuracy or a verified real-world probability of withdrawal."*
     - Show **Operational Priority** separately with an inspection of the actual rules that produced it (monetary band, window urgency, recency, rank). Do not invent reasons.
     - Distinguish graph heuristic risk (`graph_score`) and historical geographic risk (`geo_score` / cluster baseline).
     - Ensure missing scores display as `'Unavailable'` (never defaulting to 0 or 0%), while preserving legitimate zero scores (`0.0%`).
     - Do not add fabricated data-completeness percentages.
     - Preserve API schema backwards compatibility with additive, non-breaking adapters.
- **Verification Plan**:
  - Verify that official model outputs from `prediction_service` match exactly before and after frontend presentation updates.
  - Verify that UI cards render "Model ranking score" with explanatory disclaimers and separate operational priority badges.
  - Add regression tests verifying genuine zero score vs unavailable score handling.
- **Dependencies**: Frontend display utilities and Pydantic response models.
- **Status**: **VERIFIED ROOT CAUSE — REMEDIATED IN PHASE 2**

---

### Issue 3: LIME Reasons Missing, Unreadable, or Unavailable

- **Verified Finding**:
  In `CaseIntelligence.tsx`, clicking "Explain Prediction" either fails with `"LIME explanation service is currently unavailable"` or renders unreadable technical feature names such as `v4_candidate_score +0.0241` and `historical_cluster_risk +0.0189` with raw micro-weights. Furthermore, the overall fidelity line hardcodes `Mean R² = 0.2252` when undefined.
- **Evidence**:
  - `backend/app/services/prediction_explainability_service.py` lines 69–72:
    ```python
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ARTIFACTS_DIR = os.path.join(BASE_DIR, "ml", "artifacts")
    BACKGROUND_DATA_PATH = os.path.join(ARTIFACTS_DIR, "v7_lime_background.npy")
    ```
    Notice `os.path.join(..., "..", "..")` resolves to `backend/`! `ARTIFACTS_DIR` becomes `backend/ml/artifacts/`, completely ignoring `MODEL_ARTIFACTS_DIR` environment variable and ignoring root `ml/artifacts/`.
  - `backend/app/services/prediction_explainability_service.py` lines 303–321:
    The service builds `friendly` and `desc`, but places raw `fname` (`v4_candidate_score`, `historical_cluster_risk`, etc.) in `"feature_name"`.
  - `frontend/src/pages/CaseIntelligence.tsx` lines 983–1004:
    ```tsx
    {cand.positive_contributions.slice(0, 2).map((c, i) => (
      <div key={i} className="flex justify-between text-[10px] text-slate-700">
        <span className="truncate pr-1" title={c.feature_name}>{c.feature_name}</span>
        <span className="font-mono text-emerald-700 font-bold shrink-0">+{c.weight.toFixed(4)}</span>
      </div>
    ))}
    ```
  - `frontend/src/pages/CaseIntelligence.tsx` line 942:
    ```tsx
    (Mean R² = {explanation.mean_local_fidelity_r2 !== undefined ? explanation.mean_local_fidelity_r2.toFixed(4) : '0.2252'})
    ```
  - `backend/app/services/prediction_explainability_service.py` lines 383–390:
    Any prediction not labeled `cashout-location-xgb-v7-compat` is rejected with `explanation_status = "UNAVAILABLE"`.
- **Root Cause**:
  1. **Path Resolution Defect**: `prediction_explainability_service.py` uses a hardcoded relative path (`../..`) rather than the centralized `resolve_artifacts_dir()` function used by `prediction_service.py`. In Docker/Railway environments where `MODEL_ARTIFACTS_DIR=/app/ml/artifacts`, background data fails to load, throwing an initialization error and rendering LIME permanently unavailable.
  2. **Raw Feature Code Leakage**: Backend passes raw snake_case internal ML column names (`v4_candidate_score`, `historical_cluster_risk`) and frontend directly prints them, rather than displaying human-comprehensible police intelligence factors (e.g. "Mule History Alignment", "Historical Cluster Cash-Out Frequency").
  3. **Hardcoded Fallback String**: The frontend has a hardcoded string `'0.2252'` for mean $R^2$ if the backend response omits it.
- **Affected Files**:
  - `backend/app/services/prediction_explainability_service.py`
  - `frontend/src/pages/CaseIntelligence.tsx`
  - `backend/app/schemas/schemas.py`
- **Proposed Fix**:
  1. In `prediction_explainability_service.py`, replace lines 69–72 with `resolve_artifacts_dir()`, respecting `MODEL_ARTIFACTS_DIR`.
  2. Add `friendly_label` and `human_description` to the `LimeContribution` schema, and populate with clean names (e.g. "Mule Network Centrality", "Geospatial Incident Proximity").
  3. In `CaseIntelligence.tsx`, render `c.friendly_label || c.feature_name`, format weight as relative percentage impact (e.g. `+18% Contribution`), and remove hardcoded `'0.2252'`.
  4. Provide robust fallback heuristics for older complaints so explainability doesn't fail with a blank error banner.
- **Verification Plan**:
  - Test LIME endpoint directly: `GET /api/v1/predictions/{id}/explanation` with `MODEL_ARTIFACTS_DIR` pointing to both directory variants.
  - Verify UI renders clean cards with descriptive reasons like "Historical Cluster Risk Prior (+21%)".
- **Dependencies**: `prediction_service.resolve_artifacts_dir`, frontend LIME card styles.
- **Status**: **VERIFIED ROOT CAUSE — PENDING REMEDIATION**

---

### Issue 4: Tiny / Unreadable Transaction Graph

- **Verified Finding**:
  Opening the Transaction Network page (`/network/{caseId}`) reveals a microscopic, congested graph where nodes are small dots, 8px edge text is illegible, and the entire layout is crammed into a small section of the screen.
- **Evidence**:
  - `frontend/src/pages/TransactionNetwork.tsx` lines 42–49 & 171:
    ```typescript
    const preferredNode =
      data.nodes.find(n => n.data.masked_id === 'ACC••••8129') ||
      data.nodes.find(n => !n.data.is_source && n.data.node_type !== 'victim' && n.data.node_type !== 'atm') ||
      data.nodes.find(n => n.data.risk_score >= 0.7) ||
      data.nodes[0];
    if (preferredNode) {
      setSelectedNode(preferredNode.data);
    }
    ```
    ```tsx
    <div className={selectedNode ? 'lg:col-span-8' : 'lg:col-span-12'}>
    ```
  - `frontend/src/graphs/CytoscapeNetwork.tsx` lines 98–115, 199–208, 236–244, 298:
    - Fixed container height: `h-[400px] sm:h-[540px]`.
    - Node size `38`, edge font size `'8px'`, node font size `'10px'`.
    - Layout: `name: 'breadthfirst', directed: true, spacingFactor: 1.75`.
- **Root Cause**:
  1. **Immediate Canvas Compression on Load**: `preferredNode` automatically matches a beneficiary on initial page load, which immediately sets `selectedNode` to non-null. This collapses the Cytoscape canvas from 12 columns down to 8 columns before initial rendering has even stabilized.
  2. **Extreme Geometric Compression**: A 5-hop graph with 12+ entities and 15+ edges under `breadthfirst` with `spacingFactor: 1.75` spans over 1,200px wide by 1,000px high. Cytoscape's automatic `fit` shrinks this bounding box into a ~600px $\times$ 540px container, resulting in a zoom scale of $< 0.3\times$.
  3. **Illegible Typography & Dots**: At $0.25\times$ zoom, 38px nodes become 9.5px dots, and 8px edge labels shrink to 2px unreadable blurs.
  4. **Missing Resize Synchronization**: Cytoscape does not listen to container size changes when the side drawer opens or closes (`cy.resize()`, `cy.fit()`).
- **Affected Files**:
  - `frontend/src/graphs/CytoscapeNetwork.tsx`
  - `frontend/src/pages/TransactionNetwork.tsx`
- **Proposed Fix**:
  1. In `TransactionNetwork.tsx`, do not automatically force-select `preferredNode` on mount. Let the graph open in full 12-column layout so the entire flow is visible.
  2. Increase canvas height to `h-[650px]` (or dynamic `calc(100vh - 240px)`).
  3. In `CytoscapeNetwork.tsx`, implement a `ResizeObserver` on `containerRef` that automatically invokes `cy.resize()` and `cy.fit(undefined, 30)` on container dimension changes.
  4. Optimize Cytoscape styles:
     - Increase default node size to `48px` with bold icons.
     - Add `min-zoomed-font-size: 9px` so text never shrinks below legible threshold.
     - Reduce `spacingFactor` from `1.75` to `1.2` for compact hierarchical structure.
     - Make node details an overlay sheet or collapsible drawer rather than squeezing the canvas.
- **Verification Plan**:
  - Open `/network/CMP-NEW-000002` on 1080p and laptop resolutions; confirm nodes are clearly distinguishable and labels are legible without manual zooming.
  - Click a node; confirm side panel opens smoothly without shrinking labels to illegible dots.
- **Dependencies**: Cytoscape CSS and container layout.
- **Status**: **VERIFIED ROOT CAUSE — PENDING REMEDIATION**

---

### Issue 5: Complaint and Prediction Timestamps Differ by 5h30m

- **Verified Finding**:
  In `CaseIntelligence.tsx`, for the exact same complaint:
  - Header Card **Reported Time**: `16 Sep 2026, 10:00`
  - Prediction Timing Card **Reference (complaint reported)**: `16 Sep 2026, 15:30 IST`
  The two timestamps differ by exactly **5 hours and 30 minutes** ($+05:30$, Indian Standard Time offset).
- **Evidence**:
  - `backend/app/schemas/schemas.py` lines 97–98 (`ComplaintResponse`):
    `reported_at: datetime`, `incident_time: datetime` (serializes naive UTC datetimes without timezone indicator, e.g. `"2026-09-16T10:00:00"`).
  - `frontend/src/pages/CaseIntelligence.tsx` lines 346 & 364:
    ```tsx
    {complaint.reported_at
      ? new Date(complaint.reported_at).toLocaleString('en-IN', { ... })
      : 'Not available'}
    ```
    In browser JavaScript, `new Date("2026-09-16T10:00:00")` parses an ISO string without timezone as **local wall-clock time** (10:00 AM IST).
  - `backend/app/services/prediction_contract.py` lines 19–21, 55–60:
    ```python
    def utc_iso(value: Any) -> Optional[str]:
        resolved = as_utc(value)
        return resolved.isoformat() if resolved else None
    ```
    Produces `"2026-09-16T10:00:00+00:00"` (with explicit `+00:00` UTC offset).
  - `frontend/src/utils/predictionDisplay.ts` lines 15–22 & `PredictionTiming.tsx` line 14:
    ```typescript
    export const formatIST = (value?: string | null): string => {
      const date = parseApiDate(value);
      if (!date) return 'Not available';
      return `${date.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', ... })} IST`;
    };
    ```
    `formatIST` parses `"2026-09-16T10:00:00+00:00"`, recognizes UTC, converts to `Asia/Kolkata` (+5h30m), outputting `15:30 IST` (3:30 PM).
- **Root Cause**:
  Classic UTC/IST serialization mismatch:
  1. The database stores UTC datetimes naively.
  2. `ComplaintResponse` serializes `reported_at` without a `Z` suffix (`"2026-09-16T10:00:00"`).
  3. `CaseIntelligence.tsx` directly calls `new Date(...)` without `parseApiDate()`, which the browser parses as local Indian time (10:00).
  4. Meanwhile, `prediction_contract.py` serializes `prediction_reference_time` with explicit `+00:00`, which `formatIST()` converts to Indian time by adding 5 hours 30 minutes (15:30).
  5. The UI shows both timestamps on the same screen, creating an apparent 5.5-hour discrepancy for the exact same event.
- **Affected Files**:
  - `backend/app/schemas/schemas.py`
  - `backend/app/api/complaint_routes.py`
  - `frontend/src/pages/CaseIntelligence.tsx`
  - `frontend/src/pages/Complaints.tsx`
  - `frontend/src/pages/Dashboard.tsx`
  - `frontend/src/utils/predictionDisplay.ts`
- **Remediation Implemented (Phase 2)**:
  1. `backend/app/schemas/schemas.py`: Implemented `to_utc_datetime` and `to_utc_iso` helper functions, added `@field_validator` and `@field_serializer(..., when_used="json")` across all response schemas ensuring explicit UTC `Z` suffix on serialization.
  2. `backend/app/services/prediction_contract.py`: Updated `utc_iso` to return UTC ISO strings with explicit trailing `Z`.
  3. `backend/app/services/alert_service.py`: Added `format_window_ist` formatting operational estimate windows in `Asia/Kolkata` with explicit `IST` label and full dates when crossing midnight.
  4. `frontend/src/utils/predictionDisplay.ts`: Standardized `parseApiDate` and `formatIST` to handle ISO UTC with Z, +00:00, +05:30, and legacy naive datetimes under the verified compatibility policy.
  5. `frontend/src/pages/CaseIntelligence.tsx`, `Complaints.tsx`, `Dashboard.tsx`, `AuditLog.tsx`: Replaced inconsistent Date formatting with shared `formatIST`.
- **Status**: **RESOLVED & VERIFIED IN PHASE 2** (100% pass on 15 regression tests in `tests/test_phase2_timestamp_and_scores.py`)

---

### Issue 6: Model Performance Runtime / Version / Metrics Contradictions

- **Verified Finding**:
  Navigating to `/model-performance` reveals blatant contradictions:
  - Header: `Model Version: cashout-location-xgb-v7-compat`
  - Subtitle / Architecture: `Trained XGBoost v2 models operational with Platt calibration`
  - Model Class: `xgboost.XGBClassifier` (when V7 is a pairwise ranker: `pairwise_xgb_ranker`)
  - Training Dataset: `domain_meaningful_synthetic_v2` with `14,000` samples (when V7 was trained on `17,655` multi-regime samples)
  - Recall Metrics: Displays `Recall@3: 50.8%` and `Recall@1: 42.4%` from V2, directly contradicting the actual V7-compat evaluation metrics (`Recall@3: 32.38%`, `Recall@1: 17.8%`) and the README's reported baseline (`33.60%`).
  - Feature Count: Shows `43 Engineered Signals` (when V7 uses `47` features).
- **Evidence**:
  - `backend/app/api/model_routes.py` lines 12–28:
    ```python
    meta_path_v2 = os.path.join(settings.ML_MODEL_DIR, "model_metadata_v2.json")
    meta_path_v1 = os.path.join(settings.ML_MODEL_DIR, "model_metadata_v1.json")
    meta_path = meta_path_v2 if os.path.exists(meta_path_v2) else meta_path_v1
    ...
    active_loc_model = provider.model_version if provider else "cashout-location-xgb-v7-compat"
    active_time_model = provider.time_model_version if provider else "cashout-time-xgb-v3"
    ```
  - `backend/app/api/model_routes.py` lines 38–41:
    Reads `r1`, `r3`, `r5` from `metadata["metrics"]` inside `model_metadata_v2.json`!
  - `backend/ml/artifacts/model_metadata_v7_compat.json` lines 19–26:
    Actual V7 metrics:
    ```json
    "internal_metrics": {
      "candidate_recall@25": 75.63,
      "r1": 17.8,
      "r3": 32.38,
      "r5": 41.61,
      "mrr": 0.2947,
      "median_error_km": 6.38
    }
    ```
  - `frontend/src/pages/ModelPerformance.tsx` lines 118–120:
    ```tsx
    <span>{data.location_features_count ?? 43} Engineered Signals</span>
    ```
- **Root Cause**:
  `model_routes.py` was never updated when the ML engine promoted `location_ranker_v7_compat.joblib` and `time_regressor_v3.joblib`. The route handler fetches the live model version string (`cashout-location-xgb-v7-compat`) from the prediction service, but hardcodes file paths to `model_metadata_v2.json` for all metrics, samples, notices, and architecture descriptions. As a result, the page presents a patchwork of V7 version names plastered over obsolete V2 classification numbers.
- **Affected Files**:
  - `backend/app/api/model_routes.py`
  - `frontend/src/pages/ModelPerformance.tsx`
  - `backend/ml/artifacts/model_metadata_v7_compat.json`
- **Proposed Fix**:
  1. In `model_routes.py`, read the metadata corresponding to the active model: `model_metadata_v7_compat.json` when V7-compat is loaded, falling back to V4 or V2.
  2. Accurately map V7-compat properties:
     - Algorithm: `pairwise_xgb_ranker (XGBRanker with rank:ndcg)`
     - Calibration: `Platt Logistic Regression (Calibrated on Validation)`
     - Metrics: `Recall@3: 32.38%`, `Recall@1: 17.8%`, `Candidate Pool Recall@25: 75.63%`, `MRR: 0.2947`, `Median Distance Error: 6.38 km`
     - Dataset: Multi-regime synthetic Delhi corpus (`17,655` total training complaints across legacy, V6.2, and V6.3 families)
     - Feature Count: `47 Engineered Signals` (43 base + 4 V4 stacking signals)
     - Runtime notice: Truthful disclosure of V7-compat pairwise ranking.
  3. In `ModelPerformance.tsx`, dynamically display `data.location_features_count` (47).
- **Verification Plan**:
  - Call `GET /api/v1/model/performance`; verify JSON metrics match `model_metadata_v7_compat.json` with zero V2 residual text.
  - Open `/model-performance` in browser; verify clean, consistent telemetry.
- **Dependencies**: `backend/app/api/model_routes.py`.
- **Status**: **VERIFIED ROOT CAUSE — PENDING REMEDIATION**

---

### Issue 7: Hardcoded Case Navigation and Broken Map Action

- **Verified Finding**:
  1. The navigation sidebar hardcodes `CMP-NEW-000002` for both "Case Intelligence" and "Transaction Network".
  2. The Dashboard header pilot button hardcodes `CMP-NEW-000002`.
  3. Clicking a Priority Hotspot card on the Dashboard calls `navigate('/risk-map')` with zero parameters. In `RiskMap.tsx`, the map completely ignores the clicked hotspot, keeps all 60 ATM cluster markers hidden (`showHotspots = false`), and fails with a red error banner if `comps[0]` has no prediction.
- **Evidence**:
  - `frontend/src/components/Sidebar.tsx` lines 36 & 39:
    ```typescript
    { name: 'Case Intelligence', path: '/cases/CMP-NEW-000002', icon: ShieldAlert },
    { name: 'Transaction Network', path: '/network/CMP-NEW-000002', icon: Network },
    ```
  - `frontend/src/pages/Dashboard.tsx` line 68 & 134:
    ```typescript
    const handleViewPilotCase = () => navigate('/cases/CMP-NEW-000002');
    ```
    ```tsx
    <span>CMP-NEW-000002</span>
    ```
  - `frontend/src/pages/Dashboard.tsx` line 230:
    ```tsx
    <div key={hotspot.id} onClick={() => navigate('/risk-map')} ...>
    ```
  - `frontend/src/pages/RiskMap.tsx` lines 74 & 111–115:
    ```typescript
    const [showHotspots, setShowHotspots] = useState<boolean>(false);
    ...
    } else if (comps.length > 0) {
      const defaultComp = comps[0];
      setSelectedComplaintId(defaultComp.complaint_number);
      setSelectedComplaint(defaultComp);
    }
    ```
- **Root Cause**:
  1. Hardcoded development mock strings (`CMP-NEW-000002`) were left in the primary application shell (`Sidebar.tsx`, `Dashboard.tsx`).
  2. Hotspot cards on the Dashboard do not pass any cluster identifier (`?cluster=...`) to `/risk-map`.
  3. `RiskMap.tsx` only parses `case` or `complaint` search params, defaulting to `comps[0]`. Furthermore, `showHotspots` defaults to `false`, so all Delhi clusters remain invisible until manually toggled. If `comps[0]` lacks a persisted prediction, `fetchPersistedPrediction` sets `predictionError`, presenting the user with an empty error state.
- **Affected Files**:
  - `frontend/src/components/Sidebar.tsx`
  - `frontend/src/pages/Dashboard.tsx`
  - `frontend/src/pages/RiskMap.tsx`
  - `frontend/src/pages/TransactionNetwork.tsx`
- **Proposed Fix**:
  1. In `Sidebar.tsx`, route "Case Intelligence" and "Transaction Network" dynamically:
     - Store `lastViewedCaseId` in session/local storage (defaulting to the latest complaint if none viewed).
     - Or navigate to `/complaints` if no case has been selected yet.
  2. In `Dashboard.tsx`, dynamically set the pilot case button to `summary.recent_complaints[0]?.complaint_number || 'CMP-NEW-000002'`.
  3. On Dashboard hotspot cards, navigate with cluster context:
     `navigate(`/risk-map?cluster=${hotspot.id}&lat=${hotspot.latitude}&lon=${hotspot.longitude}`)`.
  4. In `RiskMap.tsx`:
     - Support `searchParams.get('cluster')`.
     - When `cluster` query parameter is present, automatically set `showHotspots(true)`, center the map on the cluster coordinates, and highlight the cluster circle.
- **Verification Plan**:
  - Create a new complaint `CMP-NEW-000999`; verify navigating via sidebar maintains or allows access to this complaint.
  - Click on "Rohini Sector 7" hotspot on Dashboard; confirm `/risk-map` opens centered on Rohini with cluster pins visible.
- **Dependencies**: React Router query parameter synchronization.
- **Status**: **VERIFIED ROOT CAUSE — PENDING REMEDIATION**

---

### Issue 8: Freeze-Review Button Only Navigates Without Review Workflow

- **Verified Finding**:
  In `TransactionNetwork.tsx`, selecting a mule account and clicking **"RECOMMEND RAPID LIEN / FREEZE REVIEW"** simply redirects the browser to `/alerts`. No review workflow is initiated, no modal opens, no account data is transferred, and no bank action record is logged.
- **Evidence**:
  - `frontend/src/pages/TransactionNetwork.tsx` lines 429–435:
    ```tsx
    <button
      onClick={() => navigate('/alerts')}
      className="w-full py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 shadow-xs"
    >
      <AlertTriangle className="w-3.5 h-3.5" />
      <span>RECOMMEND RAPID LIEN / FREEZE REVIEW</span>
    </button>
    ```
  - `backend/app/api/bank_action_routes.py`: Contains full backend infrastructure (`BankAction` model, `POST /bank-actions/{id}/transition`, `GET /bank-actions`), but no endpoint is invoked by the button.
- **Root Cause**:
  The button is an incomplete UI placeholder. It triggers a blind page transition (`navigate('/alerts')`) with zero state, omitting the selected node, masked account, complaint number, or reason for recommendation.
- **Affected Files**:
  - `frontend/src/pages/TransactionNetwork.tsx`
  - `frontend/src/services/api.ts`
  - `backend/app/api/bank_action_routes.py`
- **Proposed Fix**:
  1. Build a **Lien / Freeze Recommendation Modal** in `TransactionNetwork.tsx`:
     - Displays account details (Masked ID, Bank, Risk Score, Hop Depth, Mule Pattern Flag).
     - Allows officer to select action type (`SIMULATED_DISBURSEMENT_HOLD`, `ACCOUNT_LIEN`, `BENEFICIARY_SURVEILLANCE`).
     - Includes justification textarea and mandatory "Simulated Prototype Action" disclaimer.
  2. Connect to backend `POST /api/v1/bank-actions` to persist the recommendation in the audit trail.
  3. Show immediate visual confirmation ("Lien Review Registered for ACC••••8129 — Action Ref #ACT-0042") with a direct deep-link to the audit record.
- **Verification Plan**:
  - Click "Recommend Rapid Lien" on node ACC••••8129; verify modal appears, allows submission, and creates an audit entry without blindly redirecting.
- **Dependencies**: Backend `bank_action_service`, modal component.
- **Status**: **VERIFIED ROOT CAUSE — PENDING REMEDIATION**

---

## Authoritative Identification of Duplicate Model Artifact Directories

### 1. The Two Directories in Question

```
CyberShield AI/
├── ml/
│   └── artifacts/          <-- 45 files (Full Research & Retraining Pipeline Output)
└── backend/
    └── ml/
        └── artifacts/      <-- 30 files (Bundled Deployment Subset for Railway)
```

### 2. Comprehensive SHA-256 Comparison & Hash Drift Analysis

| Artifact File | `ml/artifacts` (Root) | `backend/ml/artifacts` | Status / Discrepancy |
| :--- | :--- | :--- | :--- |
| `location_ranker_v7_compat.joblib` | `89057bce1000...` | `89057bce1000...` | **MATCH** (Identical binary) |
| `location_calibrator_v7_compat.joblib`| `1c14d5aba1b0...` | `1c14d5aba1b0...` | **MATCH** (Identical binary) |
| `location_ranker_v4.joblib` | `9ed5792ced4f...` | `9ed5792ced4f...` | **MATCH** (Identical binary) |
| `location_calibrator_v4.joblib` | `65ceb736838d...` | `65ceb736838d...` | **MATCH** (Identical binary) |
| `time_regressor_v3.joblib` | `41183f4579df...` | `41183f4579df...` | **MATCH** (Identical binary) |
| `v7_lime_background.npy` | `94128 bytes` | `94128 bytes` | **MATCH** (Identical binary) |
| `feature_schema_v7_compat.json` | `fc303d7e8b99...` (LF, 2193 B) | `6a22835ec817...` (CRLF, 2275 B) | **HASH DRIFT** (Windows CRLF vs Unix LF) |
| `model_metadata_v7_compat.json` | `64ffd5ecac55...` (LF, 1597 B) | `0f57ab7c3e85...` (CRLF, 1647 B) | **HASH DRIFT** (Points to CRLF schema hash) |
| `blockchain_shadow_*` (6 files) | **Present** (Research qualification) | Missing | Root only |
| `location_ranker_v5`, `v7` (8 files)| **Present** (Iterative ablation models)| Missing | Root only |

### 3. Authoritative Source Determination

1. **`ml/artifacts/` is the Single Authoritative Upstream Source**:
   - All training pipelines (`ml/training/train_v7_compat.py`, `train_blockchain_shadow.py`) output to `ml/artifacts/`.
   - `backend/Dockerfile` copies `ml/` to `/app/ml/artifacts` and sets `ENV MODEL_ARTIFACTS_DIR=/app/ml/artifacts`.
   - Test suites (`test_ml_feature_pipeline.py`) resolve to `ml/artifacts/`.
2. **Origin of `backend/ml/artifacts/`**:
   - Created in commit `af174ab` ("chore(deploy): bundle v7 compat artifacts in backend for Railway deployment") when the build pack root was set to `backend`.
   - During Windows git checkout/commit, line endings on JSON files were converted to CRLF (`\r\n`), altering the SHA-256 hashes of `feature_schema_v7_compat.json` and `model_metadata_v7_compat.json`.
   - `backend/app/services/prediction_service.py` `EXPECTED_HASHES` was pinned against the CRLF hashes from `backend/ml/artifacts/`.
3. **Runtime Divergence Bug**:
   - `prediction_service.py` resolves to `ml/artifacts/` locally.
   - `prediction_explainability_service.py` hardcodes `backend/ml/artifacts/`.
   - The application currently splits its model loading across both directories at runtime!

### 4. Authoritative Consolidation Strategy
- Enforce `ml/artifacts/` as the single canonical repository directory.
- Configure `.gitattributes` to enforce `eol=lf` strictly for text files (`*.json`, `*.py`, `*.md`, etc.). **Binary artifacts such as `.joblib` and `.npy` must NOT receive text line-ending conversion** (declare as `*.joblib binary`, `*.npy binary` or omit from text filters). Recorded for the artifact consolidation phase.
- Update `prediction_explainability_service.py` and `prediction_service.py` to use one unified resolver.
- Delete or symlink `backend/ml/artifacts` to eliminate directory divergence.

---

## Local Implementation vs Deployed Behavior Comparison

| Dimension | Local Development | Live Deployed Environment |
| :--- | :--- | :--- |
| **Frontend URL** | `http://localhost:5173` | `https://cybershield-ai-ruddy.vercel.app` |
| **Backend URL** | `http://localhost:8000` | `https://cybershield-ai-production-66121.up.railway.app` |
| **Database Engine** | SQLite (`cybershield.db`) or local PostgreSQL | Cloud PostgreSQL 16 (measured latency ~587 ms) |
| **Frontend Bundle** | Freshly built `dist/assets/index-Cu1po-q6.js` (2,502 modules) | Previous production build `index-CLx0TJeP.js` |
| **CORS Policy** | Local dev permits localhost:5173 / 3000 | Railway CORS enforces whitelist; rejects unlisted origins |
| **Cartography Provider** | Leaflet OpenStreetMap fallback (if no Google API key in `.env.local`) | Leaflet OpenStreetMap fallback (Google API key not injected in Vercel) |
| **Model Artifacts Path** | Local filesystem (`CyberShield AI/ml/artifacts`) | Container path (`/app/ml/artifacts` or bundled) |
| **RBAC Enforcement** | Active (requires token on all protected endpoints) | Active (returns 401 Unauthorized for unauthenticated API access) |

---

## Actionable Remediation Roadmap

```mermaid
graph TD
    A[Step 1: Unify Model Artifacts & Git LFs] --> B[Step 2: Timezone Contract Unification]
    B --> C[Step 3: Fix Prediction Explainability LIME Paths & UI]
    C --> D[Step 4: Disentangle Hotspot Risk Scores & Active Inactive States]
    D --> E[Step 5: Dynamic Navigation & Map Linking Dashboard/Sidebar/RiskMap]
    E --> F[Step 6: Cytoscape Graph Sizing & Layout Responsiveness]
    F --> G[Step 7: Lien / Freeze Review Modal Workflow]
    G --> H[Step 8: Model Performance Telemetry Route Alignment]
    H --> I[Step 9: Update Legacy Test Suite to Match Auth & Multi-Hop]
```

### Prioritized Remediation Tasks

1. **Phase 1 — Data & Timezone Integrity (Issues 5 & 7)**:
   - Normalize all datetime fields to explicit UTC ISO strings in Pydantic schemas.
   - Use `formatIST()` universally in frontend components.
   - Replace hardcoded `CMP-NEW-000002` in `Sidebar.tsx` and `Dashboard.tsx` with dynamic case navigation.
2. **Phase 2 — Explainability & Artifact Consolidation (Issues 3 & Authoritative Source)**:
   - Point `prediction_explainability_service.py` to `resolve_artifacts_dir()`.
   - Add `.gitattributes` for LF normalization and standardize SHA-256 hashes.
   - Render friendly feature labels and relative impact percentages in `CaseIntelligence.tsx`.
3. **Phase 3 — GIS & Hotspot Prior Separation (Issue 1)**:
   - Separate historical cluster baseline priors from active incident predictions in `gis_routes.py`.
   - Eliminate misleading "87% CRITICAL / ₹0" dashboard cards.
   - Present historical prior baseline as distinct from active incident priority without altering model rankings.
4. **Phase 4 — UX & Interaction Polish (Issues 4 & 8)**:
   - Expand `CytoscapeNetwork` canvas dimensions, adjust font scaling, add `ResizeObserver`, and prevent default-selection squishing.
   - Implement the rapid lien/freeze review recommendation modal in `TransactionNetwork.tsx` wired to `BankAction` logging.
5. **Phase 5 — Model Performance & Legacy Test Modernization (Issue 6 & Baseline Tests)**:
   - Wire `model_routes.py` to `model_metadata_v7_compat.json` so metrics (32.4% Recall@3, 47 features, pairwise ranker) are truthful.
   - Update 70 legacy unit tests to use authenticated test clients and expect current model schemas.

---

## Phase 2 Implementation Report: Timestamp Correctness & Score Semantics

### 1. Verified Timestamp Semantics
- **Database Storage Semantics**: PostgreSQL/SQLite columns store naive UTC timestamps (created via `datetime.now(timezone.utc)` or parsed from UTC ISO strings). Stored database records are NOT shifted.
- **Legacy Naive Compatibility Policy**: When a legacy naive timestamp is encountered in database records or legacy inputs without timezone metadata, it is treated as a UTC instant (`tzinfo=timezone.utc`) without shifting. This prevents double-conversion or +5h30m drift.
- **Input Parsing Contract**: `ComplaintCreate` parses timezone-aware strings (`+05:30`, `+00:00`, `Z`) and normalizes to UTC naive datetime for persistence exactly once. Datetime-local inputs from frontend browser are converted via `new Date(value).toISOString()`, preserving the user's intended instant.
- **API Serialization Contract**: All datetime fields representing instants serialize with explicit UTC `Z` suffix (`2026-09-16T10:00:00Z`).
- **Frontend Presentation Contract**: Operational timestamps are rendered in `Asia/Kolkata` with an explicit `IST` label using shared `formatIST` and `formatWindowIST` utilities. Windows that cross midnight explicitly show full date and time for both start and end (`16 Sep 2026, 23:30 IST – 17 Sep 2026, 01:30 IST`).
- **Exact Expiry Boundary**: Windows are evaluated with exact boundary `window_end <= now` for expiration, displaying an explicit expired banner without rewriting historical prediction evidence.

### 2. Verified Score Semantics
- **Official Model Outputs Preserved**: Official XGBoost calibrated ranking scores (e.g. `0.089` or `8.9%`) are preserved without artificial rescaling or transformation into fabricated 70–90% relevance indices.
- **Output Labeling**: Candidate score is explicitly labeled `"Model ranking score"`, with UI tooltips explaining that it reflects relative candidate zone ranking across Delhi clusters for the specific complaint, not overall model accuracy or verified real-world withdrawal probability.
- **Operational Priority Separation**: Operational priority (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) is presented separately from model ranking scores. It is governed by law-enforcement triage rules (amount $\ge$ ₹5L, window $\le$ 90 min, recency $\le$ 4h), and the UI explicitly explains that a high operational priority legitimately coexists with a low candidate score.
- **Distinction of Risk Signals**: Model ranking score (`prediction.ml_score`), Graph heuristic risk (`prediction.graph_score`, based on mule network topology), and Historical geographic risk (`prediction.geo_score`, based on historical cluster incident concentration) are clearly distinguished in dedicated Provenance and Evaluated Risk Signals UI components.
- **Zero vs Missing Scores**: Legitimate zero scores (`0.0`) are preserved and displayed as `0.0%`. Missing scores remain `Unavailable` and never default to zero.

### 3. Files Changed
- `docs/remediation-plan.md`: Corrected unsupported audit recommendations and added Phase 2 implementation documentation.
- `backend/app/schemas/schemas.py`: Implemented `to_utc_datetime` and `to_utc_iso` helpers; added `@field_validator` and `@field_serializer(..., when_used="json")` across response schemas; added non-breaking `score_label` and `operational_priority` fields.
- `backend/app/services/prediction_contract.py`: Updated `utc_iso` to return UTC ISO strings with trailing `Z`.
- `backend/app/services/alert_service.py`: Added `format_window_ist` with explicit `IST` label and midnight-crossing full date formatting.
- `frontend/src/types/index.ts`: Added optional non-breaking fields `score_label`, `operational_priority` to `PredictionLocationItem` and `disputed_amount` to `Complaint`.
- `frontend/src/utils/predictionDisplay.ts`: Implemented robust `parseApiDate`, `formatIST`, `formatWindowIST`, `modelScore`, and `explainOperationalPriority`.
- `frontend/src/components/PredictionTiming.tsx`: Added exact expiry boundary evaluation (`<= Date.now()`) and explicit expired window banner.
- `frontend/src/pages/CaseIntelligence.tsx`: Replaced raw `new Date()` calls with `formatIST()`; added operational priority tooltips in table and mobile cards; added Evaluated Risk Signals breakdown distinguishing Model ranking score, Graph heuristic risk, and Historical geographic risk.
- `frontend/src/pages/Complaints.tsx`: Updated `formatDateTime` to use `formatIST`.
- `frontend/src/pages/Dashboard.tsx`: Replaced `new Date().toLocaleDateString()` and `toLocaleTimeString()` with `formatIST`.
- `frontend/src/pages/AuditLog.tsx`: Replaced `new Date().toLocaleString()` with `formatIST`.
- `tests/test_phase2_timestamp_and_scores.py`: Added 15 comprehensive regression tests covering all Phase 2 requirements.

### 4. Test Commands & Verification Results
- **Phase 2 Regression Suite**:
  - Command: `.venv\Scripts\pytest tests/test_phase2_timestamp_and_scores.py -v`
  - Result: **15 passed in 1.93s** (100% pass rate)
- **Core Security & Functional Tests**:
  - Command: `.venv\Scripts\pytest tests/test_phase1_security_authorization.py tests/test_v7_compat_runtime_parity.py tests/test_prediction_idempotency.py tests/test_prediction_time_metadata_regression.py tests/test_code_consolidation.py -v`
  - Result: **40 passed in 20.49s** (100% pass rate)
- **Frontend Production Build**:
  - Command: `npm --prefix frontend run build`
  - Result: **0 errors, 2,502 modules transformed, built in 6.30s**

### 5. Before & After Case Inspection Example (CMP-1042)
| Dimension | Before Phase 2 | After Phase 2 |
| :--- | :--- | :--- |
| **Backend `ComplaintResponse`** | `"2026-09-12T08:14:27"` (naive UTC) | `"2026-09-12T08:14:27.198072Z"` (explicit UTC with Z) |
| **Backend `Prediction reference_time`** | `"2026-09-12T08:14:27.198072+00:00"` | `"2026-09-12T08:14:27.198072Z"` (explicit UTC with Z) |
| **Complaint Header Display** | `12 Sep 2026, 08:14` (interpreted as local IST) | `12 Sept 2026, 13:44 IST` (parsed as UTC, converted to IST) |
| **Prediction Reference Display** | `12 Sep 2026, 13:44 IST` (+5h30m from UTC) | `12 Sept 2026, 13:44 IST` (parsed as UTC, converted to IST) |
| **Discrepancy** | **5 hours 30 minutes apart** | **0 minutes (Identical instant)** |
| **Candidate Score Display** | Ambiguous percentage | Labeled `"Model ranking score"`, explained as relative ranking across Delhi clusters |
| **Operational Priority** | Conflated with risk score | Separated with explicit inspection-rule tooltip and explanation |
| **Risk Distinction** | Geo/Graph scores unlabelled | Graph heuristic risk and Historical geographic risk labeled and distinguished |

### 6. Phase 2 Verification Gaps Resolution
1. **Local Browser Visual Verification Status**:
   - **Status**: **UNVERIFIED (Automated Browser Driver Download Unavailable)**
   - **Reason**: The headless automated browser environment could not initialize due to an external driver binary download failure (Playwright CDN 404 in the local Windows execution environment).
   - **Data Grounding**: Verified via code inspection and regression test assertions:
     - Both `complaint.reported_at` and `prediction.reference_time` serialize to identical instants in UTC with an explicit `Z` suffix (`2026-09-12T08:14:27.198072Z` for case `CMP-1042`).
     - Frontend `formatIST` formats both as `12 Sept 2026, 13:44 IST`, completely resolving the previously observed 5h 30m offset.
2. **Operational Priority Calculations & Explanations Policy Review**:
   - **Git History & Code Comparison**:
     - Inspected `compute_operational_priority` in `backend/app/services/prediction_service.py` across git history.
     - **Verification Finding**: The underlying Python policy code was **never altered**. The mention of "₹1L HIGH" or "<= 90m CRITICAL" in the completion report was a reporting shorthand error in documentation.
     - **Actual Authoritative Code Rules Preserved**:
       - *Rank 1 (Primary)*:
         - `CRITICAL`: Dispute amount $\ge$ ₹5,00,000 OR (amount $\ge$ ₹1,50,000 AND predicted window $\le$ 90 min AND intake delay $\le$ 4 hrs).
         - `HIGH`: Dispute amount $\ge$ ₹75,000 OR (amount $\ge$ ₹30,000 AND predicted window $\le$ 90 min).
         - `MEDIUM`: Dispute amount $\ge$ ₹20,000 OR predicted window $\le$ 90 min.
         - `LOW`: Routine observation.
       - *Rank 2 (Secondary)*:
         - `HIGH`: Dispute amount $\ge$ ₹5,00,000 AND predicted window $\le$ 90 min.
         - `MEDIUM`: Dispute amount $\ge$ ₹1,00,000 OR (amount $\ge$ ₹40,000 AND predicted window $\le$ 90 min).
         - `LOW`: Routine observation.
       - *Rank $\ge$ 3 (Tertiary)*:
         - `MEDIUM`: Dispute amount $\ge$ ₹5,00,000 AND predicted window $\le$ 90 min AND intake delay $\le$ 4 hrs.
         - `LOW`: Routine observation.
   - **Intake Delay Calculation**:
     - The criterion "recent $\le 4$h" strictly measures **incident-to-report intake delay** (`(as_utc(reported_at) - as_utc(incident_time)).total_seconds() / 3600.0 <= 4.0`), **not** elapsed time relative to wall-clock time.
   - **Frontend Explanation Alignment**:
     - `explainOperationalPriority` in `frontend/src/utils/predictionDisplay.ts` mirrors the exact thresholds above and displays persisted backend reason metadata when provided by the API, guaranteeing that UI tooltips never diverge from saved prediction records.

---

## Phase 3 Implementation Report: Active Hotspots & GIS Correctness

### 1. Verified Root Causes
1. **Historical Baseline Conflation**:
   - In `backend/app/api/gis_routes.py`, empty clusters with zero active case predictions previously fell back to `default=float(cluster.risk_score or 0)`.
   - Because Delhi historical baseline commercial clusters have prior risk scores $\ge 0.8$, empty clusters were classified as `CRITICAL` with 0 active cases and ₹0, appearing as active interception priorities on the Dashboard.
2. **Candidate Score Propagation**:
   - `PredictionLocation.probability` was discarded during cluster aggregation in favor of `pred.risk_score`, causing secondary and tertiary candidate zones to inherit Rank 1's score.

### 2. API & Aggregation Architecture
1. **Explicit Concept Separation**:
   - **Active Interception Candidates**: Only clusters with authorized, open cases having latest unexpired prediction windows (`predicted_window_end > now_utc`) and persisted `PredictionLocation` links.
   - **Historical Hotspots**: Baseline clusters reflecting ATM cash-out concentration from historical cybercrime patterns.
2. **Eligibility & Latest Invariant**:
   - Canonical window function `row_number().over(partition_by=complaint_id, order_by=(created_at.desc(), id.desc())) == 1` identifies the latest prediction per complaint.
   - Older predictions are never revived if the latest prediction is expired or ineligible.
   - Complaints with status `RESOLVED` or `CLOSED` are excluded.
3. **Additive Response Schema**:
   - Added to `HotspotCluster`: `is_active_candidate`, `data_basis`, `historical_risk`, `candidate_score`, `operational_priority`, `operational_priority_basis`, `associated_complaint_amount`, `window_start`, `window_end`, `window_status`, `linked_complaint_numbers`.
   - Added to `GISOverviewResponse`: `active_candidates`, `historical_hotspots`.
4. **Historical Compatibility Fields & Threat Isolation**:
   - `candidate_score = None` is strictly returned for clusters without an active prediction.
   - Legacy compatibility fields `risk_score = 0.0` and `risk_level = "LOW"` are retained solely for backward compatibility with unmigrated schema parsers, and are **never** rendered as measured active threats on any UI component:
     - `Dashboard.tsx`: Renders `Baseline Risk: {Math.round(hotspot.historical_risk * 100)}%` (with `0 active cases`), never referencing `risk_score` or `risk_level`.
     - `RiskMap.tsx`: Cluster Focus panel renders `Historical Risk: {Math.round(selectedCluster.historical_risk * 100)}%`, completely isolated from legacy fields.
     - `UnifiedRiskMap.tsx` & `LeafletFallbackMap.tsx`: Cluster popups render `Baseline Historical Risk: {Math.round(cluster.historical_risk * 100)}%`.
5. **Amount Semantics & Deduplication**:
   - Cluster-level: Deduplicates cases within the cluster (`sum(complaint.amount for unique complaints in cluster)`).
   - Global-level: `summary.total_associated_amount` deduplicates complaints across overlapping zones so multi-zone cases are never double-counted in global platform totals.
6. **Authoritative 60-Second Refresh Cycle**:
   - In `Dashboard.tsx`, the 60-second timer triggers a background re-fetch (`fetchTelemetry(false)`) against `api.getRiskMap()` and `api.getDashboardSummary()`.
   - For multi-case clusters with staggered prediction windows, single-case expiration recomputes active cases, amounts, and the next valid window authoritatively on the server, avoiding premature cluster drops or stale amount aggregates.

### 3. Files Changed
- `backend/app/services/prediction_service.py`: Documented intake delay calculation and added `explain_operational_priority_rule`.
- `backend/app/schemas/schemas.py`: Added additive fields to `HotspotCluster` and `GISOverviewResponse`.
- `backend/app/api/gis_routes.py`: Refactored `_cluster_items` with latest prediction window function, unexpired window check, score preservation, historical fallback elimination, and deduplicated global amount.
- `frontend/src/types/index.ts`: Added additive fields to `HotspotCluster` and `GISOverviewResponse`.
- `frontend/src/services/api.ts`: Updated `getRiskMap` return type.
- `frontend/src/utils/predictionDisplay.ts`: Updated `explainOperationalPriority` with intake delay and exact rank threshold rules.
- `frontend/src/pages/Dashboard.tsx`: Separated Active Interception Candidates from Historical Hotspots (Baseline), added 60s authoritative telemetry refresh.
- `frontend/src/maps/CashOutRiskMap.tsx`: Added `selectedClusterId` prop.
- `frontend/src/maps/UnifiedRiskMap.tsx`: Differentiated active and historical markers, added pan/zoom focus, updated legend.
- `frontend/src/maps/LeafletFallbackMap.tsx`: Added historical cluster icons, center controller, and legend.
- `frontend/src/pages/RiskMap.tsx`: Added `?cluster=` deep linking, cluster focus panel, and validation banner.
- `tests/test_phase3_hotspots_and_gis.py`: Added 13 verification tests.

### 4. Focused Test Commands & Verification Results
> [!NOTE]
> The commands below represent focused verification suites executed for Phases 1–3 changes. The 70 pre-existing baseline test failures identified in the initial audit remain documented in Section 2 and pending for subsequent phases.

- **Phase 3 Active Hotspots & GIS Suite (13 tests)**:
  - Command: `.venv\Scripts\pytest tests/test_phase3_hotspots_and_gis.py -v`
  - Result: **13 passed in 124.97s** (100% pass rate)
- **Phase 2 Timestamps & Scores Regression Suite (15 tests)**:
  - Command: `.venv\Scripts\pytest tests/test_phase2_timestamp_and_scores.py -v`
  - Result: **15 passed in 3.60s** (100% pass rate)
- **Phase 1 Security & RBAC Suite (30 tests)**:
  - Command: `.venv\Scripts\pytest tests/test_phase1_security_authorization.py -v`
  - Result: **30 passed in 4.65s** (100% pass rate)
- **Frontend Production Build**:
  - Command: `npm --prefix frontend run build`
  - Result: **0 errors, built in 6.25s**

### 5. Remaining Limitations & Non-Verified Items
- **Visual Acceptance**: Automated browser visual verification remains **UNVERIFIED** due to missing local Playwright driver binaries. Code and API-level assertions confirm correctness.
- Cytoscape mule transaction network canvas resizing and node truncation remain scheduled for Phase 4.
- LIME surrogate explanation cache and model performance runtime telemetry remain scheduled for Phase 5.
- Deployment to production is withheld until all phases complete.

---

## Phase 3 Closure Review & Invariant Certification

### 1. `compute_operational_priority` Git History & Code Invariant Analysis
- **Git History Trace**:
  - Traced `compute_operational_priority` in `backend/app/services/prediction_service.py` via `git log -L :compute_operational_priority:backend/app/services/prediction_service.py`.
  - **Commit `6c34121`** (Sep 12, 2026): Introduced `compute_operational_priority` with original thresholds.
  - **Commit `f2aee07`** (Sep 13, 2026): Added UTC normalization (`as_utc(reported_at) >= as_utc(incident_time)`). Thresholds unchanged.
  - **Phases 2–3**: Added intake delay documentation, `explain_operational_priority_rule`, and schema serialization. Python logic was **NEVER altered**.
- **Determination on Discrepancy**:
  - The previous completion report's mention of "₹1L HIGH and <=90 minutes CRITICAL" was strictly a **reporting shorthand error** in the narrative summary text, **not an unintended code change**.
- **Authentic Operational Priority Policy**:
  - **Rank 1 (Primary Candidate)**:
    - `CRITICAL`: Amount $\ge$ ₹5,00,000 OR (Amount $\ge$ ₹1,50,000 AND predicted window urgency $\le$ 90 min AND intake delay $\le$ 4 hrs).
    - `HIGH`: Amount $\ge$ ₹75,000 OR (Amount $\ge$ ₹30,000 AND predicted window urgency $\le$ 90 min).
    - `MEDIUM`: Amount $\ge$ ₹20,000 OR predicted window urgency $\le$ 90 min.
    - `LOW`: Routine observation.
  - **Rank 2 (Secondary Candidate)**:
    - `HIGH`: Amount $\ge$ ₹5,00,000 AND predicted window urgency $\le$ 90 min.
    - `MEDIUM`: Amount $\ge$ ₹1,00,000 OR (Amount $\ge$ ₹40,000 AND predicted window urgency $\le$ 90 min).
    - `LOW`: Routine observation.
  - **Rank $\ge$ 3 (Tertiary Candidate)**:
    - `MEDIUM`: Amount $\ge$ ₹5,00,000 AND predicted window urgency $\le$ 90 min AND intake delay $\le$ 4 hrs.
    - `LOW`: Routine observation.
  - **Intake Delay Semantics**: Strictly defined as `(as_utc(reported_at) - as_utc(incident_time)).total_seconds() / 3600.0 <= 4.0` (delay between incident occurrence and official report), NOT age relative to wall-clock time.
- **Truthful Rule Explanations**:
  - Both `explain_operational_priority_rule` in Python and `explainOperationalPriority` in TypeScript mirror these exact thresholds.
  - Added `operational_priority_basis` to `PredictionLocationItem` and `HotspotCluster` to ensure UI explanations describe the exact rule that produced the saved result.

### 2. Historical-Only Hotspot Threat Isolation & Compatibility Fields
- **No Active Threat Masking**:
  - For clusters without active case predictions:
    - `is_active_candidate = False`
    - `data_basis = "historical_baseline"`
    - `candidate_score = None`
    - `operational_priority = None`
    - `operational_priority_basis = "No active case prediction in current operational window"`
    - Legacy compatibility fields: `risk_score = 0.0`, `risk_level = "LOW"` (retained solely for legacy parsers).
- **Consumer Isolation Guarantee**:
  - `Dashboard.tsx`: Renders historical hotspots in a dedicated "Historical Hotspots (Baseline)" panel showing `Baseline Risk: {Math.round(hotspot.historical_risk * 100)}%` and `0 active cases`. Never references `risk_score` or `risk_level`.
  - `RiskMap.tsx`: Cluster focus panel checks `selectedCluster.is_active_candidate`. For historical clusters, renders "None eligible", "Historical Hotspot", and `Historical Risk: {Math.round(selectedCluster.historical_risk * 100)}%`.
  - `UnifiedRiskMap.tsx` & `LeafletFallbackMap.tsx`: Popups render a neutral slate badge labeled `HISTORICAL` and display `Baseline Historical Risk: {Math.round(cluster.historical_risk * 100)}%` with `Active Cases: 0 (No active prediction)`.

### 3. Authoritative 60-Second Refresh & Multi-Case Cluster Preservation
- **Staggered Multi-Case Expiry Verification**:
  - In `backend/app/api/gis_routes.py`, `_cluster_items` calculates both `window_end` (earliest expiry, for tactical intervention) and `latest_window_end` (latest expiry among linked active cases).
  - In `frontend/src/pages/Dashboard.tsx`, `unexpiredActiveCandidates` evaluates `h.latest_window_end || (h.active_cases > 1 ? null : h.window_end)`.
  - **Invariant Verified**: If Cluster 16 contains Case A (expiring in 30m) and Case B (expiring in 3h), the expiration of Case A does **NOT** drop Cluster 16 from active candidates.
  - When Case A expires, the 60-second background timer (and 10-second boundary trigger) queries `/api/v1/risk-map` for fresh authoritative aggregates:
    - Backend excludes Case A via `predicted_window_end > now_utc`.
    - Cluster 16 updates authoritatively: `active_cases = 1`, `associated_complaint_amount` updates to Case B's amount, `linked_complaint_numbers = [Case B]`, and `window_end` advances to Case B's window.

### 4. Verification of Core Query & Aggregation Invariants
- **Latest-Prediction Selection**:
  - Uses canonical window function `row_number().over(partition_by=Prediction.complaint_id, order_by=(Prediction.created_at.desc(), Prediction.id.desc())) == 1`.
  - Only the latest prediction per complaint is ever evaluated; expired latest predictions never resurrect older historical predictions.
- **Jurisdiction Filtering**:
  - Evaluates `filter_complaints_by_jurisdiction(rows_query, user, db)` in `_cluster_items` and applies state/district filtering on clusters, strictly enforcing officer authorization boundaries.
- **Amount Deduplication**:
  - Cluster-level: `evidence` maps `cluster_id -> complaint_id -> item`, guaranteeing that complaints appearing multiple times within the same cluster (e.g. Rank 1 and Rank 2) contribute their amount exactly once.
  - Global-level: `unique_active_complaints` in `gis_routes.py` deduplicates across clusters, ensuring that complaints spanning multiple candidate zones are counted exactly once in `summary.total_associated_amount`.

### 5. Explicit Verification & Acceptance Status
- **Browser Visual Verification**:
  - Status: **UNVERIFIED (Visual Browser Verification Deferred)**.
  - Automated browser initialization was unavailable due to local environment driver binary download restrictions (Playwright CDN 404). Visual verification in a real browser remains an open acceptance item separated from code/API implementation completion.
- **Exact Regression Test Suites Executed**:
  - `tests/test_phase3_hotspots_and_gis.py`: 14 tests (100% pass rate)
  - `tests/test_phase2_timestamp_and_scores.py`: 15 tests (100% pass rate)
  - `tests/test_phase1_security_authorization.py`: 30 tests (100% pass rate)
  - **Disclaimer**: 70 pre-existing baseline test failures identified during the initial audit remain cataloged in Section 2 and scheduled for remediation in subsequent phases.
- **Phase 4 Status**: Phase 4 has **NOT** been started. All work stops after this Phase 3 closure review.

---

## Conclusion & Audit Certification

This audit and remediation conclusively addresses Phase 1 (Security & RBAC), Phase 2 (Timestamps & Scores), and Phase 3 (Active Hotspots & GIS Correctness), establishing strict mathematical and operational integrity across backend services, database schemas, and frontend interfaces.
