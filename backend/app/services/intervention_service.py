import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.models.models import (
    Complaint,
    Prediction,
    PredictionLocation,
    LocationCluster,
    Alert,
    BankAction,
    CaseHandoff,
    EvidenceFile,
    InterventionPlan,
    InterventionPlanAction,
    User,
    Organization,
)
from backend.app.services.audit_service import log_audit
from backend.app.auth.rbac import verify_complaint_access, verify_alert_access

logger = logging.getLogger(__name__)


class InterventionOrchestratorService:
    """
    Phase 3: Decision-Support Intervention Orchestrator Service.
    Converts persisted V8 predictions and existing case context into a structured, reviewable,
    role-aware decision-support action plan.

    Guardrails:
    - Zero ML model inference / reruns.
    - Zero autonomous real-world enforcement (no auto bank freeze, police dispatch, live notices).
    - Idempotent generation: returns existing active plan unless underlying operational state changed or refresh requested.
    - Deterministic action recommendation.
    """

    def generate_plan_for_complaint(
        self,
        db: Session,
        complaint_id_or_num: str,
        user: User,
        force_refresh: bool = False
    ) -> InterventionPlan:
        """
        Generates or retrieves the active Intervention Plan for a complaint strictly derived
        from existing persisted intelligence.
        """
        # 1. Resolve Complaint & verify RBAC access
        if complaint_id_or_num.isdigit():
            complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id_or_num)).first()
        else:
            complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id_or_num).first()

        if not complaint or not verify_complaint_access(complaint, user, db):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Complaint not found or insufficient jurisdiction access."
            )

        # 2. Fetch latest persisted Prediction
        prediction = (
            db.query(Prediction)
            .filter(Prediction.complaint_id == complaint.id)
            .order_by(Prediction.version_number.desc(), Prediction.id.desc())
            .first()
        )
        if not prediction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No persisted prediction available for complaint {complaint.complaint_number}."
            )

        pred_version = prediction.version_number or 1

        # 3. Check for existing ACTIVE plan (Idempotency)
        existing_plan = (
            db.query(InterventionPlan)
            .filter(
                InterventionPlan.complaint_id == complaint.id,
                InterventionPlan.prediction_id == prediction.id,
                InterventionPlan.status == "ACTIVE"
            )
            .order_by(InterventionPlan.plan_version.desc())
            .first()
        )

        if existing_plan and not force_refresh:
            logger.info(
                f"[InterventionService] Returning existing active InterventionPlan #{existing_plan.id} "
                f"(v{existing_plan.plan_version}) for complaint {complaint.complaint_number}."
            )
            return existing_plan

        # If force_refresh and an existing plan exists, mark old plan SUPERSEDED
        if existing_plan and force_refresh:
            existing_plan.status = "SUPERSEDED"
            db.flush()
            next_version = existing_plan.plan_version + 1
        else:
            next_version = 1

        # 4. Fetch Rank-1 Location
        locations = (
            db.query(PredictionLocation)
            .filter(PredictionLocation.prediction_id == prediction.id)
            .order_by(PredictionLocation.rank.asc())
            .all()
        )

        rank1_loc = locations[0] if locations else None
        primary_cluster_id = rank1_loc.cluster_id if rank1_loc else prediction.primary_cluster_id
        primary_cluster_name = rank1_loc.location_name if rank1_loc else "Unknown Zone"

        if rank1_loc and rank1_loc.cluster_id:
            cluster_obj = db.query(LocationCluster).filter(LocationCluster.id == rank1_loc.cluster_id).first()
            if cluster_obj:
                primary_cluster_name = cluster_obj.cluster_name

        # Operational window
        win_start = prediction.predicted_window_start
        win_end = prediction.predicted_window_end

        # 5. Inspect existing case objects
        existing_alert = (
            db.query(Alert)
            .filter(Alert.complaint_id == complaint.id)
            .order_by(Alert.id.desc())
            .first()
        )

        existing_bank_action = (
            db.query(BankAction)
            .filter(BankAction.complaint_id == complaint.id)
            .order_by(BankAction.id.desc())
            .first()
        )

        existing_handoff = (
            db.query(CaseHandoff)
            .filter(CaseHandoff.complaint_id == complaint.id)
            .order_by(CaseHandoff.id.desc())
            .first()
        )

        existing_evidence = (
            db.query(EvidenceFile)
            .filter(EvidenceFile.complaint_id == complaint.id)
            .all()
        )

        # 6. Build Plan Summary JSON
        top3_summary = [
            {
                "rank": loc.rank,
                "location_name": loc.location_name,
                "probability": float(loc.probability or 0.0),
                "risk_level": loc.risk_level or "MEDIUM"
            }
            for loc in locations[:3]
        ]

        summary_json = {
            "title": f"Decision-Support Action Plan: {complaint.complaint_number}",
            "model_version": prediction.model_version or "cashout-location-xgb-v8-debiased",
            "primary_zone": primary_cluster_name,
            "risk_score": float(prediction.risk_score or 0.0),
            "top3_candidates": top3_summary,
            "amount_at_risk": float(complaint.amount or 0.0),
            "fraud_type": complaint.fraud_type,
            "jurisdiction": f"{complaint.district}, {complaint.state}",
            "disclaimer": (
                "CyberShield's Intervention Plan converts persisted prediction and case intelligence into recommended "
                "operational steps. It does not automatically execute law-enforcement or banking actions."
            )
        }

        # Try capturing ATM/CSP Context snapshot for primary candidate cluster
        try:
            from backend.app.services.atm_context_service import ATMContextService
            atm_svc = ATMContextService()
            ctx_res = atm_svc.get_atm_context_for_prediction(db, prediction.id, rank=1, user=user)
            summary_json["atm_context_snapshot"] = {
                "candidate_zone": ctx_res.get("candidate_zone"),
                "items_count": len(ctx_res.get("items", [])),
                "high_priority_count": sum(1 for item in ctx_res.get("items", []) if item.get("priority_band") == "HIGH"),
                "context_method": ctx_res.get("context_method"),
                "items_sample": [
                    {
                        "name": item.get("name"),
                        "type": item.get("type"),
                        "score": item.get("context_priority_score"),
                        "priority_band": item.get("priority_band"),
                        "distance_km": item.get("distance_km"),
                        "bank_match": item.get("bank_match")
                    }
                    for item in ctx_res.get("items", [])[:5]
                ]
            }
        except Exception as e:
            logger.warning(f"[InterventionService] Could not capture ATM context snapshot: {e}")

        # Try capturing Golden-Hour snapshot
        try:
            from backend.app.services.golden_hour_service import golden_hour_service
            gh_res = golden_hour_service.get_golden_hour_for_prediction(db, prediction.id, user=user)
            summary_json["golden_hour_snapshot"] = {
                "status": gh_res.get("status"),
                "status_display": gh_res.get("status_display"),
                "window_start": gh_res.get("window", {}).get("start"),
                "window_end": gh_res.get("window", {}).get("end"),
                "window_start_ist": gh_res.get("window", {}).get("start_ist"),
                "window_end_ist": gh_res.get("window", {}).get("end_ist"),
                "minutes_until_start": gh_res.get("minutes_until_start"),
                "minutes_until_end": gh_res.get("minutes_until_end"),
            }
        except Exception as e:
            logger.warning(f"[InterventionService] Could not capture Golden-Hour snapshot: {e}")

        # 7. Create Plan
        new_plan = InterventionPlan(
            plan_uuid=str(uuid.uuid4()),
            complaint_id=complaint.id,
            prediction_id=prediction.id,
            prediction_version=pred_version,
            generated_by_user_id=user.id,
            generated_at=datetime.utcnow(),
            status="ACTIVE",
            plan_version=next_version,
            primary_candidate_cluster_id=primary_cluster_id,
            operational_window_start=win_start,
            operational_window_end=win_end,
            summary_json=summary_json,
            created_at=datetime.utcnow()
        )
        db.add(new_plan)
        db.flush()

        # 8. Construct Deterministic Action Cards
        actions_to_add: List[InterventionPlanAction] = []

        # Category 1: LEA Response Actions
        actions_to_add.append(
            InterventionPlanAction(
                plan_id=new_plan.id,
                category="LEA",
                action_type="REVIEW_PRIMARY_ZONE",
                title=f"Prepare Field Coordination — {primary_cluster_name}",
                description=f"Review primary predicted cashout cluster '{primary_cluster_name}' for operational field awareness.",
                priority="HIGH",
                status="RECOMMENDED",
                recommended_reason="Top-ranked location candidate from persisted V8 prediction model.",
                assigned_role="DISTRICT_LEA",
                created_at=datetime.utcnow()
            )
        )

        if len(locations) > 1:
            sec_names = ", ".join([loc.location_name for loc in locations[1:3]])
            actions_to_add.append(
                InterventionPlanAction(
                    plan_id=new_plan.id,
                    category="LEA",
                    action_type="REVIEW_SECONDARY_ZONES",
                    title=f"Review Secondary Candidates ({sec_names})",
                    description="Evaluate secondary candidate clusters in the district if primary cluster activity is negative.",
                    priority="MEDIUM",
                    status="AVAILABLE",
                    recommended_reason="Alternative candidate clusters ranked by V8 multi-cluster model.",
                    assigned_role="DISTRICT_LEA",
                    created_at=datetime.utcnow()
                )
            )

        actions_to_add.append(
            InterventionPlanAction(
                plan_id=new_plan.id,
                category="LEA",
                action_type="REVIEW_WINDOW",
                title="Review Cash-Out Operational Estimate Window",
                description=f"Align field response within predicted time window: {prediction.window_label or '2–4 Hours'}.",
                priority="HIGH",
                status="RECOMMENDED",
                recommended_reason="Time-decay estimation window derived from complaint timestamp and transaction velocity.",
                assigned_role="DISTRICT_LEA",
                created_at=datetime.utcnow()
            )
        )

        # Category 2: Bank Response Actions
        bank_status = "RECOMMENDED" if complaint.amount and complaint.amount >= 50000 else "AVAILABLE"
        linked_ba_id = existing_bank_action.id if existing_bank_action else None
        ba_card_status = "STARTED" if existing_bank_action and existing_bank_action.status in ("REQUESTED", "APPROVED", "SENT") else ("COMPLETED" if existing_bank_action and existing_bank_action.status in ("CONFIRMED_HOLD", "COMPLETED") else bank_status)

        actions_to_add.append(
            InterventionPlanAction(
                plan_id=new_plan.id,
                category="BANK",
                action_type="PREPARE_BANK_ACTION",
                title="Prepare Sandbox Bank Disbursement Hold Request",
                description="Review terminal beneficiary financial context and prepare a bank disbursement hold through the Bank Action workflow.",
                priority="HIGH" if complaint.amount and complaint.amount >= 100000 else "MEDIUM",
                status=ba_card_status,
                recommended_reason="Beneficiary account and financial velocity indicate potential cash-out risk.",
                linked_bank_action_id=linked_ba_id,
                assigned_role="BANK_OFFICER",
                created_at=datetime.utcnow()
            )
        )

        # Category 3: Jurisdiction / Handoff Actions
        linked_ho_id = existing_handoff.id if existing_handoff else None
        ho_card_status = "STARTED" if existing_handoff and existing_handoff.status in ("REQUESTED", "IN_PROGRESS") else ("COMPLETED" if existing_handoff and existing_handoff.status == "ACCEPTED" else "AVAILABLE")

        actions_to_add.append(
            InterventionPlanAction(
                plan_id=new_plan.id,
                category="JURISDICTION",
                action_type="REVIEW_CROSS_STATE_HANDOFF",
                title="Review Cross-Jurisdiction Handoff Requirement",
                description="Check if victim location or mule account origin requires coordination with neighboring Cyber Cells.",
                priority="MEDIUM",
                status=ho_card_status,
                recommended_reason="Cross-district transaction flow or multi-state victim provenance detected.",
                linked_handoff_id=linked_ho_id,
                assigned_role="STATE_LEA",
                created_at=datetime.utcnow()
            )
        )

        # Category 4: GIS Actions
        actions_to_add.append(
            InterventionPlanAction(
                plan_id=new_plan.id,
                category="GIS",
                action_type="OPEN_RISK_MAP",
                title=f"Open Live Risk Map Focused on {primary_cluster_name}",
                description="Visualize spatial ATM density, cluster radius, and nearby cyber crime hotspots.",
                priority="HIGH",
                status="RECOMMENDED",
                recommended_reason="Spatial intelligence mapping available for primary candidate cluster.",
                assigned_role="ANALYST",
                created_at=datetime.utcnow()
            )
        )

        actions_to_add.append(
            InterventionPlanAction(
                plan_id=new_plan.id,
                category="GIS",
                action_type="REVIEW_ATM_CSP_CONTEXT",
                title=f"Review High-Priority Cash-Out Points Within {primary_cluster_name}",
                description=f"Inspect high-priority ATM/CSP contextual shortlist within primary candidate zone '{primary_cluster_name}' for operational surveillance.",
                priority="HIGH",
                status="RECOMMENDED",
                recommended_reason="Secondary contextual operational prioritization layer computed for primary candidate zone.",
                assigned_role="DISTRICT_LEA",
                created_at=datetime.utcnow()
            )
        )

        actions_to_add.append(
            InterventionPlanAction(
                plan_id=new_plan.id,
                category="GIS",
                action_type="REVIEW_GOLDEN_HOUR_WINDOW",
                title="Prioritize Response for Golden-Hour Operational Window",
                description="Monitor real-time Golden-Hour countdown and operational urgency window derived from time-decay prediction.",
                priority="HIGH",
                status="RECOMMENDED",
                recommended_reason="Operational time window derived from cashout-time-xgb-v3 prediction model.",
                assigned_role="DISTRICT_LEA",
                created_at=datetime.utcnow()
            )
        )

        # Category 5: Alert Actions
        linked_alert_id = existing_alert.id if existing_alert else None
        alert_card_status = "COMPLETED" if existing_alert and existing_alert.status in ("ACKNOWLEDGED", "ACTION_INITIATED") else ("STARTED" if existing_alert else "RECOMMENDED")

        actions_to_add.append(
            InterventionPlanAction(
                plan_id=new_plan.id,
                category="ALERT",
                action_type="ACKNOWLEDGE_OR_CREATE_ALERT",
                title="Acknowledge or Dispatch Multi-Channel Alert",
                description="Broadcast or acknowledge high-risk tactical alert via Dashboard WebSocket, Email, SMS, or Partner Webhook.",
                priority="CRITICAL" if prediction.risk_score and prediction.risk_score > 0.8 else "HIGH",
                status=alert_card_status,
                recommended_reason="Multi-channel notification outbox ready for operational dispatch.",
                linked_alert_id=linked_alert_id,
                assigned_role="DISTRICT_LEA",
                created_at=datetime.utcnow()
            )
        )

        # Category 6: Evidence / Dossier Actions
        dossier_status = "COMPLETED" if existing_evidence else "RECOMMENDED"
        actions_to_add.append(
            InterventionPlanAction(
                plan_id=new_plan.id,
                category="EVIDENCE",
                action_type="GENERATE_DOSSIER",
                title="Generate & Verify Case Investigation Dossier",
                description="Compile tamper-evident investigation package containing prediction snapshot, transaction graph, and evidence hashes.",
                priority="MEDIUM",
                status=dossier_status,
                recommended_reason="Tamper-evident evidence documentation required for court admissible case file.",
                assigned_role="ANALYST",
                created_at=datetime.utcnow()
            )
        )

        db.add_all(actions_to_add)
        db.commit()
        db.refresh(new_plan)

        # Log Audit
        log_audit(
            db=db,
            user_id=user.id,
            officer_name=user.full_name or "Officer",
            role=user.role,
            action="INTERVENTION_PLAN_CREATED",
            case_number=complaint.complaint_number,
            details=f"Generated Decision-Support InterventionPlan #{new_plan.id} (v{new_plan.plan_version}) referencing Prediction #{prediction.id}."
        )

        logger.info(
            f"[InterventionService] Created InterventionPlan #{new_plan.id} for complaint {complaint.complaint_number} "
            f"with {len(actions_to_add)} actions."
        )

        return new_plan

    def get_plan(self, db: Session, plan_id: int, user: User) -> InterventionPlan:
        """Retrieves an InterventionPlan by ID enforcing RBAC."""
        plan = db.query(InterventionPlan).filter(InterventionPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Intervention plan #{plan_id} not found."
            )

        complaint = db.query(Complaint).filter(Complaint.id == plan.complaint_id).first()
        if not complaint or not verify_complaint_access(complaint, user, db):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intervention plan not found or access denied."
            )

        return plan

    def transition_action_status(
        self,
        db: Session,
        plan_id: int,
        action_id: int,
        new_status: str,
        user: User,
        notes: Optional[str] = None
    ) -> InterventionPlanAction:
        """
        Transitions the status of a specific InterventionPlanAction (e.g. RECOMMENDED -> STARTED -> COMPLETED).
        Enforces role permissions and logs audit entries without bypassing subsystem rules.
        """
        valid_statuses = {"RECOMMENDED", "AVAILABLE", "STARTED", "COMPLETED", "NOT_APPLICABLE", "CANCELLED"}
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action status '{new_status}'. Allowed: {sorted(valid_statuses)}"
            )

        plan = self.get_plan(db, plan_id, user)
        action = db.query(InterventionPlanAction).filter(
            InterventionPlanAction.id == action_id,
            InterventionPlanAction.plan_id == plan.id
        ).first()

        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Intervention action #{action_id} not found in plan #{plan_id}."
            )

        # Role restriction checks
        if user.role == "AUDITOR":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AUDITOR role has read-only visibility for intervention plans."
            )

        if user.role == "BANK_OFFICER" and action.category != "BANK":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="BANK_OFFICER users may only update BANK category intervention actions."
            )

        old_status = action.status
        action.status = new_status
        action.updated_at = datetime.utcnow()

        if new_status == "STARTED" and not action.started_at:
            action.started_at = datetime.utcnow()
        elif new_status in ("COMPLETED", "CANCELLED", "NOT_APPLICABLE") and not action.completed_at:
            action.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(action)

        # Audit log
        complaint = db.query(Complaint).filter(Complaint.id == plan.complaint_id).first()
        log_audit(
            db=db,
            user_id=user.id,
            officer_name=user.full_name or "Officer",
            role=user.role,
            action=f"INTERVENTION_ACTION_{new_status}",
            case_number=complaint.complaint_number if complaint else f"CMP-{plan.complaint_id}",
            details=f"Updated action #{action.id} ('{action.title}') status from {old_status} to {new_status}."
        )

        return action

    def get_plan_for_complaint(self, db: Session, complaint_id_or_num: str, user: User) -> InterventionPlan:
        return self.generate_plan_for_complaint(db, complaint_id_or_num, user, force_refresh=False)

    def generate_intervention_plan(self, db: Session, complaint_id: str, user: User, force_new_revision: bool = False) -> InterventionPlan:
        return self.generate_plan_for_complaint(db, complaint_id, user, force_refresh=force_new_revision)

    def get_intervention_plan(self, db: Session, complaint_id: str, user: User) -> InterventionPlan:
        return self.generate_plan_for_complaint(db, complaint_id, user, force_refresh=False)

    def update_action_status(self, db: Session, plan_id: int, action_id: int, new_status: str, user: User, notes: Optional[str] = None) -> InterventionPlanAction:
        return self.transition_action_status(db, plan_id, action_id, new_status, user, notes=notes)


intervention_service = InterventionOrchestratorService()
