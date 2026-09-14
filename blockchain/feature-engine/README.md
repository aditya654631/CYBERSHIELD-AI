# CyberShield AI — Blockchain Feature Engine (Phase B.4)

> **CRITICAL ARCHITECTURE NOTICE:**
> **VERIFIED FABRIC SIGNALS -> LEAKAGE-SAFE GEO-RISK FEATURES**
> All features are deterministically derived from cryptographically endorsed, committed consortium signals on the `cyber-intelligence` channel via the B.3 Fabric Gateway layer. No predictions are re-ranked yet, and current ML runtimes remain untouched.

---

## 1. Overview & Architecture

The Blockchain Feature Engine translates verified, immutable consortium intelligence into candidate-cluster spatial risk signals.

```
  +-----------------------------------------------------------+
  |              Blockchain Feature Engine                    |
  |                                                           |
  |  Candidate Cluster + Reference Timestamp (ISO-8601)       |
  |                            |                              |
  |                            v                              |
  |  +-----------------------------------------------------+  |
  |  |           Input & Anti-PII Validation               |  |
  |  +-------------------------+---------------------------+  |
  |                            |                              |
  |                            v                              |
  |  +-----------------------------------------------------+  |
  |  |           Fabric Gateway Layer (I4CMSP)             |  |
  |  |          QuerySignalsByCluster(includeInactive=true) |  |
  |  +-------------------------+---------------------------+  |
  |                            |                              |
  |                            v                              |
  |  +-----------------------------------------------------+  |
  |  |     Signal Normalizer (Anti-Leakage & As-Of Filter) |  |
  |  |   - Excludes events where event_timestamp > T_ref   |  |
  |  |   - Reconstructs point-in-time status               |  |
  |  +-------------------------+---------------------------+  |
  |                            |                              |
  |                            v                              |
  |  +-----------------------------------------------------+  |
  |  |             Cluster Feature Builder                 |  |
  |  |   - Temporal Windows: 1h, 6h, 24h, 7d, 30d          |  |
  |  |   - Multi-Org Attestation & Diversity               |  |
  |  |   - Confidence, Recency (sentinel -1), Recurrence   |  |
  |  +-------------------------+---------------------------+  |
  |                            |                              |
  |                            v                              |
  |     Deterministic Candidate Cluster Feature Vector        |
  |           (blockchain-feature-schema-v1)                  |
  +-----------------------------------------------------------+
```

---

## 2. Anti-Leakage & Historical As-Of Invariants

1. **Temporal Safety:**
   - Any signal with `event_timestamp > reference_timestamp` or `submitted_at > reference_timestamp` is strictly excluded.
   - Future signals contribute `0` to features as-of `reference_timestamp`.

2. **Historical Status Resolution:**
   - If a signal was revoked *after* `reference_timestamp`, it is considered `ACTIVE` as-of `reference_timestamp`.
   - If a signal was revoked *before* `reference_timestamp`, it is excluded from active intelligence features.
   - If a signal was corrected *before* `reference_timestamp`, the active correction record supersedes the original.

3. **No Fake Fallback:**
   - If Fabric is unavailable, the engine fails explicitly with `503 FABRIC_UNAVAILABLE`. No synthetic zeros or mocked features are returned.

---

## 3. Feature Contract & Categories

All features adhere to the frozen specification in `blockchain_feature_contract.json`:

- **Core Temporal:** `verified_cashouts_1h`, `verified_cashouts_6h`, `verified_cashouts_24h`, `withdrawal_attempts_1h`, `withdrawal_attempts_6h`, `withdrawal_attempts_24h`, `branch_cashouts_6h`, `branch_cashouts_24h`, `mule_activity_6h`, `mule_activity_24h`, `lea_confirmations_6h`, `lea_confirmations_24h`.
- **Diversity & Attestation:** `distinct_orgs_1h`, `distinct_orgs_6h`, `distinct_orgs_24h`, `distinct_banks_1h`, `distinct_banks_6h`, `distinct_banks_24h`, `multi_org_attestation_1h/6h/24h`, `has_multi_org_attestation_1h/6h/24h` (>= 2 orgs).
- **Confidence:** `mean_signal_confidence_1h/6h/24h`, `max_signal_confidence_1h/6h/24h`.
- **Recency:** `latest_signal_age_minutes`, `latest_verified_cashout_age_minutes`, `latest_attempt_age_minutes`, `latest_lea_confirmation_age_minutes` (sentinel `-1` if no events).
- **Recurrence:** `cluster_signal_count_7d/30d`, `cluster_active_days_7d/30d`, `cluster_recurrence_rate_7d/30d`.
- **Governance & Audit:** `correction_count_24h`, `revocation_count_24h`, `active_signal_ratio_24h`.
- **Subject-Linked:** `subject_features_available`, `subject_signal_count_1h/6h/24h`, `subject_distinct_clusters_24h`, `subject_distinct_orgs_24h`.

---

## 4. Usage & Commands

### Running Unit Tests
```bash
cd blockchain/feature-engine
npm test
```

### Running Live Acceptance Smoke Test
```bash
node scripts/feature-engine-smoke-test.js
```

### Running Feature Extraction Demo
```bash
node scripts/demo-features.js
```
