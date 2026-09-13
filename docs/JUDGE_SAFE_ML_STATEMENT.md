# JUDGE-SAFE ML STATEMENT — CYBERSHIELD AI (SIH 26184)

## 1. Executive Prototype Disclosure

CyberShield AI currently uses an actually trained XGBoost-based location prediction pipeline for the Delhi prototype. The current active location model is `cashout-location-xgb-v4` and the current active time model is `cashout-time-xgb-v3`. These prototype models were trained and evaluated using controlled synthetic Delhi cybercrime scenarios because real NCRP and banking outcome datasets are not publicly available.

Multiple experimental challenger models and dataset-generation strategies were evaluated under pre-defined promotion gates. Challengers that did not satisfy those gates were not promoted. The production prototype therefore continues to use the last validated baseline while future retraining is deferred until higher-fidelity verified data is available.

---

## 2. Boundaries of Truth & Claims

To maintain absolute scientific and ethical integrity during judging and operational demonstrations, the following operational boundaries are explicitly affirmed:

| Attribute | Legitimate Prototype Reality | Disallowed / False Claim |
| :--- | :--- | :--- |
| **Data Provenance** | Controlled synthetic Delhi cybercrime scenario simulation. | Real national NCRP database records or live law enforcement feeds. |
| **Banking Integration** | Simulated multi-hop transaction topologies with realistic IFSC / branch data. | Live integration with RBI, NPCI, or production core banking systems. |
| **Prediction Scope** | Macro spatial clustering (Delhi 11 police districts, 41 hot-zones). | Pinpoint GPS or real-time surveillance certainty of a single ATM machine. |
| **Evaluation Scope** | Synthetic benchmark evaluation against held-out scenario seeds. | Validated national production accuracy across Indian states. |
| **Prediction Role** | Decision-support intelligence to prioritize investigation vectors. | Automated criminal conviction, automated asset freezing, or guilt determination. |

---

## 3. Human-in-the-Loop (HITL) Decision Governance

CyberShield AI predictions are designed strictly as **actionable intelligence support** for authorized nodal officers, cybercrime investigators, and banking security desks:

1. **No Automated Coercive Actions**: Predictive rankings do not trigger automated account freezes, automated FIR registrations, or automated suspect detentions.
2. **Investigative Triangulation**: The Top-3 predicted hot-zones and estimated cash-out windows provide investigative leads to dispatch field units or request CCTV preservation from nodal bank branches.
3. **Auditability & Provenance**: Every prediction emitted by the system records its model version (`cashout-location-xgb-v4`), timestamp, feature count, calibrated confidence scores, and runtime mode (`trained_ml`).
4. **Human Discretion**: The law enforcement investigator remains the sole authoritative decision-maker at all stages of the case lifecycle.
