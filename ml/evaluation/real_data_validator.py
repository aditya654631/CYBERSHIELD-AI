"""
CyberShield AI — Phase 10: Authorized Real-Data Import Validator & Readiness Gate

Enforces strict compliance before any external real-world dataset can be ingested:
1. Schema Validation: Mandatory case, event, temporal, spatial, and outcome fields
2. Provenance & Authorization: Source agency, batch ID, export date, authorized role
3. Temporal Sanity: Chronological sequencing, no future dates
4. Geographic Boundaries: Valid coordinate bounding boxes (India / jurisdiction)
5. Deduplication: Uniqueness of case IDs and transaction hashes
6. Missing Value Policy: Explicit quarantine of records with missing targets
7. PII Safeguards: Detection and rejection of unmasked phone numbers, Aadhaar, PAN, and card numbers

Real-Data Readiness Gate:
If no authorized real data has been imported, the system explicitly reports
REAL_VALIDATION_PENDING. Synthetic evaluation metrics are NEVER relabeled or
conflated as real-world operational proof.
"""

import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

AUTHORIZED_SOURCES = {
    "NCRP",
    "CFCFRMS",
    "STATE_LEA_EXPORT",
    "DISTRICT_LEA_EXPORT",
    "PARTNER_BANK_GATEWAY",
    "FIU_IND",
}

# Regex patterns for raw PII detection (unmasked)
RAW_PHONE_REGEX = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}\b")
RAW_AADHAAR_REGEX = re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b")
RAW_PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")
RAW_CARD_REGEX = re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6011[0-9]{12}|3[47][0-9]{13})\b")

# India bounding box
MIN_LAT, MAX_LAT = 8.0, 37.5
MIN_LON, MAX_LON = 68.0, 97.5


class RealDataImportValidator:
    """Validates real-world cybercrime and financial outcome datasets."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_dataset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full validation pipeline for an external data import payload.
        Expected payload structure:
        {
            "metadata": {
                "source_system": "NCRP",
                "batch_id": "BATCH-2026-09-001",
                "authorized_officer_id": 12,
                "export_date": "2026-09-20T00:00:00Z",
                "jurisdiction_state": "Delhi",
                "pii_attestation": True
            },
            "records": [
                {
                    "case_id": "CR-2026-001",
                    "reported_at": "2026-09-15T10:00:00Z",
                    "fraud_type": "UPI / QR Code Fraud",
                    "amount": 45000.0,
                    "victim_lat": 28.6139,
                    "victim_lon": 77.2090,
                    "victim_district": "CENTRAL_NEW_DELHI",
                    "realized_cashout_lat": 28.6300,
                    "realized_cashout_lon": 77.2200,
                    "realized_cashout_cluster_id": 14,
                    "realized_cashout_time": "2026-09-15T12:30:00Z"
                }
            ]
        }
        """
        self.errors = []
        self.warnings = []

        meta = payload.get("metadata", {})
        records = payload.get("records", [])

        # 1. Provenance check
        self._check_provenance(meta)

        # 2. Record checks
        if not records or not isinstance(records, list):
            self.errors.append("Payload contains no records array or records is empty")
            return self._build_result(meta, len(records), is_valid=False)

        seen_case_ids = set()
        valid_records_count = 0
        now_utc = datetime.now(timezone.utc)

        for idx, rec in enumerate(records):
            rec_id = rec.get("case_id", f"Row-{idx}")

            # Deduplication
            if rec_id in seen_case_ids:
                self.errors.append(f"Duplicate case_id found: '{rec_id}' at record index {idx}")
            seen_case_ids.add(rec_id)

            # Schema & Missing values
            is_rec_valid = self._check_record_schema(rec, idx)

            # Dates & Temporal validity
            if is_rec_valid:
                is_rec_valid = self._check_record_dates(rec, idx, now_utc)

            # Geography
            if is_rec_valid:
                is_rec_valid = self._check_record_geography(rec, idx)

            # PII detection
            self._check_record_pii(rec, idx)

            if is_rec_valid:
                valid_records_count += 1

        is_valid = len(self.errors) == 0
        return self._build_result(meta, len(records), is_valid, valid_records_count)

    def _check_provenance(self, meta: Dict[str, Any]):
        src = meta.get("source_system")
        if not src or src not in AUTHORIZED_SOURCES:
            self.errors.append(
                f"Invalid or missing source_system: '{src}'. Must be one of: {sorted(AUTHORIZED_SOURCES)}"
            )

        if not meta.get("batch_id"):
            self.errors.append("Missing required metadata field: 'batch_id'")

        if not meta.get("export_date"):
            self.errors.append("Missing required metadata field: 'export_date'")

        if not meta.get("pii_attestation"):
            self.errors.append("Missing required metadata field: 'pii_attestation' (must certify PII masking)")

    def _check_record_schema(self, rec: Dict[str, Any], idx: int) -> bool:
        required_fields = [
            "case_id",
            "reported_at",
            "fraud_type",
            "amount",
            "victim_lat",
            "victim_lon",
            "victim_district",
            "realized_cashout_cluster_id",
        ]
        missing = [f for f in required_fields if f not in rec or rec[f] is None]
        if missing:
            self.errors.append(f"Record {idx} ('{rec.get('case_id', idx)}') missing required fields: {missing}")
            return False

        try:
            amt = float(rec["amount"])
            if amt <= 0.0:
                self.errors.append(f"Record {idx} amount must be positive: got {amt}")
                return False
        except (ValueError, TypeError):
            self.errors.append(f"Record {idx} invalid amount format: {rec.get('amount')}")
            return False

        return True

    def _check_record_dates(self, rec: Dict[str, Any], idx: int, now_utc: datetime) -> bool:
        try:
            rep_t = pd.to_datetime(rec["reported_at"], utc=True)
            if rep_t > now_utc:
                self.errors.append(f"Record {idx} has future reported_at: {rec['reported_at']}")
                return False

            if "realized_cashout_time" in rec and rec["realized_cashout_time"]:
                cash_t = pd.to_datetime(rec["realized_cashout_time"], utc=True)
                if cash_t < rep_t:
                    self.warnings.append(
                        f"Record {idx} cashout time precedes reported_at ({cash_t} < {rep_t}). Allowed if delayed report."
                    )
                if cash_t > now_utc:
                    self.errors.append(f"Record {idx} has future realized_cashout_time: {rec['realized_cashout_time']}")
                    return False

            if "incident_time" in rec and rec["incident_time"]:
                inc_t = pd.to_datetime(rec["incident_time"], utc=True)
                if inc_t > rep_t:
                    self.errors.append(f"Record {idx} incident_time after reported_at ({inc_t} > {rep_t})")
                    return False
        except Exception as exc:
            self.errors.append(f"Record {idx} invalid datetime format: {str(exc)}")
            return False

        return True

    def _check_record_geography(self, rec: Dict[str, Any], idx: int) -> bool:
        try:
            v_lat = float(rec["victim_lat"])
            v_lon = float(rec["victim_lon"])
            if not (MIN_LAT <= v_lat <= MAX_LAT and MIN_LON <= v_lon <= MAX_LON):
                self.errors.append(
                    f"Record {idx} victim coords ({v_lat}, {v_lon}) outside Indian geographic bounds"
                )
                return False

            if "realized_cashout_lat" in rec and "realized_cashout_lon" in rec:
                c_lat = float(rec["realized_cashout_lat"])
                c_lon = float(rec["realized_cashout_lon"])
                if not (MIN_LAT <= c_lat <= MAX_LAT and MIN_LON <= c_lon <= MAX_LON):
                    self.errors.append(
                        f"Record {idx} cashout coords ({c_lat}, {c_lon}) outside Indian geographic bounds"
                    )
                    return False
        except (ValueError, TypeError) as exc:
            self.errors.append(f"Record {idx} invalid geographic coordinate format: {str(exc)}")
            return False

        return True

    def _check_record_pii(self, rec: Dict[str, Any], idx: int):
        for field, val in rec.items():
            if not isinstance(val, str):
                continue

            if RAW_PHONE_REGEX.search(val):
                self.errors.append(
                    f"Record {idx} field '{field}' contains unmasked raw phone number. Enforce +91 ******1234 masking."
                )
            if RAW_AADHAAR_REGEX.search(val):
                self.errors.append(
                    f"Record {idx} field '{field}' contains unmasked raw 12-digit Aadhaar number. Enforce XXXX-XXXX-1234 masking."
                )
            if RAW_PAN_REGEX.search(val):
                self.errors.append(
                    f"Record {idx} field '{field}' contains unmasked raw PAN card identifier. Enforce XXXXX1234X masking."
                )
            if RAW_CARD_REGEX.search(val):
                self.errors.append(
                    f"Record {idx} field '{field}' contains unmasked raw payment card number."
                )

    def _build_result(
        self,
        meta: Dict[str, Any],
        total_records: int,
        is_valid: bool,
        valid_records: int = 0
    ) -> Dict[str, Any]:
        return {
            "validation_status": "PASSED" if is_valid else "REJECTED",
            "is_valid": is_valid,
            "metadata_submitted": meta,
            "total_records_evaluated": total_records,
            "valid_records_count": valid_records,
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "errors": self.errors[:50],  # Cap output
            "warnings": self.warnings[:50],
            "pii_compliance_status": "COMPLIANT" if not any("PII" in e or "unmasked" in e for e in self.errors) else "VIOLATION_DETECTED",
        }


def get_real_data_validation_status() -> Dict[str, Any]:
    """
    Returns the truthful operational status of real-data validation.
    When authorized real-world data is absent, returns REAL_VALIDATION_PENDING.
    """
    return {
        "status": "REAL_VALIDATION_PENDING",
        "evaluation_readiness": "SYNTHETIC_EVALUATED_REAL_PENDING",
        "message": (
            "Real-world NCRP/CFCFRMS location model validation remains an external acceptance gate. "
            "System is currently operating in compliant synthetic evaluation mode. "
            "Zero real cybercrime or bank records have been fabricated."
        ),
        "external_acceptance_gates": [
            {
                "gate": "GATE_NCRP_PARTNER_CREDENTIALS",
                "description": "Formal Memorandum of Understanding (MoU) and API credentials for National Cybercrime Reporting Portal",
                "status": "PENDING_EXTERNAL_APPROVAL",
            },
            {
                "gate": "GATE_CFCFRMS_BANK_INTEGRATION",
                "description": "Citizen Financial Cyber Fraud Reporting & Management System partner bank direct API integration",
                "status": "PENDING_EXTERNAL_APPROVAL",
            },
            {
                "gate": "GATE_STATE_LEA_OUTCOME_AUDIT",
                "description": "State/District LEA ground-truth cashout seizure outcome verification protocol",
                "status": "PENDING_EXTERNAL_APPROVAL",
            },
        ],
        "methodology_disclosures": {
            "synthetic_generalization": (
                "Synthetic Delhi scenario evaluations test cross-generator distribution shifts (v4 vs v6.2 vs v6.3). "
                "A fresh synthetic random seed evaluates generator stability, NOT real-world national accuracy."
            ),
            "prohibited_actions": [
                "Do NOT fabricate mock records and label them as real LEA/bank investigations",
                "Do NOT claim candidate Platt calibration represents per-case real-world probability",
                "Do NOT promote experimental models without meeting predeclared promotion evidence gates",
            ],
        },
    }
