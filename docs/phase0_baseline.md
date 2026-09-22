# CyberShield AI — Phase 0 Baseline System State

This document records the exact frozen baseline of the CyberShield AI system prior to initiating the SIH26184 operational upgrade work.

---

## 1. GIT STATE
- **Branch**: `main`
- **Commit**: `e74306f0203c5ed08294a76bd9821b5d4600f0b8`
- **Origin/Main**: `e74306f0203c5ed08294a76bd9821b5d4600f0b8`
- **Baseline Tag**: `v1.0.0-pre-operational-upgrade`
- **Head Match**: `YES`
- **Working Tree**: `Clean`

---

## 2. DEPLOYMENT TARGETS
- **Frontend URL**: `https://cybershield-ai-ruddy.vercel.app`
- **Backend URL**: `https://cybershield-ai-production-66121.up.railway.app`
- **Vercel Commit**: `e74306f0203c5ed08294a76bd9821b5d4600f0b8`
- **Railway Commit**: `e74306f0203c5ed08294a76bd9821b5d4600f0b8`

---

## 3. DATABASE MIGRATION STATE
- **Current Revision**: `0020_withdrawal_attribution_and_region_fix`
- **Head Revision**: `0020_withdrawal_attribution_and_region_fix`
- **Up to date**: `YES` (head match verified via Alembic)

---

## 4. MODEL ARTIFACT VERIFICATION & CHECKSUMS (V8)
- **Active Model Version**: `cashout-location-xgb-v8-debiased`
- **Feature Count**: `49`
- **Candidate Universe**: `60 Delhi clusters`

### SHA-256 Checksums
| Artifact | SHA-256 Checksum |
| :--- | :--- |
| `ml/artifacts/location_ranker_v8_debiased.joblib` | `69f300b4b208f2c3a606f54d84f992b665f30602de0ebe8f77f6561d625bfd71` |
| `ml/artifacts/location_calibrator_v8_debiased.joblib` | `e2ec24047c42b98a4aefd8c0951f125adf2947a5c1c198136dde9c77c4cb8dd1` |
| `ml/artifacts/feature_schema_v8_debiased.json` | `68c9643cea2c3f2480ca085e5da37299568cf72fef98e3f2c7f39b840c514b4b` |
| `ml/artifacts/model_metadata_v8_debiased.json` | `cf5b76ac27686dd4ccae238cc7a7b6af1c583af8cbcce2bbb369fe2293362050` |
| `ml/artifacts/v8_lime_background.npy` | `dab72448527c140d969e650048d0dc3c3515dbeb034effece3fdd2ca5d047f14` |

---

## 5. PRODUCTION HEALTH CHECK
- **GET /health/live**: `200 OK` (`status: alive`)
- **GET /health/ready**: `200 OK` (`status: ready`)
- **Database Connected**: `true`
- **Model Available**: `true`
- **Model Verified**: `true`
- **Active Model Version**: `cashout-location-xgb-v8-debiased`
- **Artifact Verification Status**: `COMPATIBLE`
- **Scikit-Learn Version Match**: `EXACT_MATCH`

---

## 6. BASELINE TEST SUITE RESULTS
- **Backend Compileall**: `PASS` (0 syntax errors)
- **Backend Regression Suite**:
  - **Passed**: `101`
  - **Failed**: `17` (legacy/strict auth & synthetic test expectations documented as baseline, unmodified in Phase 0)
  - **Skipped**: `1`
- **Frontend Build (`npm run build`)**: `PASS`
  - **TypeScript**: `0 errors`
  - **Vite Build**: `PASS`

---

## 7. BASELINE CASE RECORD (Delhi Pilot)
- **Complaint Number**: `CMP-NEW-000192`
- **Prediction ID**: `221`
- **Model Version**: `cashout-location-xgb-v8-debiased`
- **Top-3 Locations**:
  1. Connaught Place, Delhi (`0.0833`)
  2. Karol Bagh, Delhi (`0.0747`)
  3. Rajendra Place, Delhi (`0.0664`)
- **Top-3 Probabilities**: `[0.0833, 0.0747, 0.0664]`
- **LIME Explainability Status**: `surrogate_verified_compatible` (49 debiased features)
- **Prediction Fingerprint**: `c2d1d4d4754e6e36b1cb493a65ea754c9da46e5c5132fb6fd3479c322655b9cc`
