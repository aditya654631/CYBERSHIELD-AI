"""
Causal Synthetic Blockchain Signal Generator
Phase B.6 — Strict Anti-Leakage & Observable-State Causality

RULES:
1. STRICT CAUSALITY: All signals are generated exclusively from observable pre-outcome state
   available at or before complaint reporting time T (reported_at).
2. NO TARGET LEAKAGE: Signals are NEVER derived from the winning cluster, future cashout location,
   actual withdrawal timestamp, or target label.
3. REALISTIC CONSORTIUM BEHAVIOR:
   - Signals reflect prior transaction trajectory (mule bank, terminal mule district, transaction velocity).
   - Signals reflect prior historical cluster activity (baseline risk score, historical fraud rate, ATM density).
   - Signals reflect multi-bank alerts (BankA, BankB, BankC observing mule activity).
   - Signals reflect LEA district-level bulletins on high-risk clusters.
   - Background signals exist across Delhi clusters regardless of the specific complaint.
"""

import math
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple

CONSORTIUM_BANKS = ["BankAMSP", "BankBMSP", "BankCMSP"]
AUTHORITIES = ["I4CMSP", "LEAMSP"]

BANK_TO_MSP = {
    "state bank of india": "BankAMSP",
    "sbi": "BankAMSP",
    "hdfc": "BankBMSP",
    "hdfc bank": "BankBMSP",
    "icici": "BankCMSP",
    "icici bank": "BankCMSP",
    "punjab national bank": "BankAMSP",
    "axis bank": "BankBMSP",
    "kotak mahindra bank": "BankCMSP"
}


def normalize_zone(z: Optional[str]) -> Optional[str]:
    if not z:
        return None
    clean = str(z).strip().upper().replace("-", "_").replace(" ", "_")
    if clean in ("CENTRAL", "NEW_DELHI", "NEWDELHI", "CENTRAL_DELHI", "CENTRAL_NEW_DELHI"):
        return "CENTRAL_NEW_DELHI"
    if clean in ("NORTH_EAST", "NORTHEAST", "SHAHDARA", "NORTH_EAST_SHAHDARA"):
        return "NORTH_EAST_SHAHDARA"
    if clean in ("SOUTH_WEST", "SOUTHWEST", "DWARKA", "SOUTH_WEST_DWARKA"):
        return "SOUTH_WEST_DWARKA"
    if clean in ("SOUTH_EAST", "SOUTHEAST"):
        return "SOUTH_EAST"
    if clean in ("NORTH_WEST", "NORTHWEST"):
        return "NORTH_WEST"
    return clean


def get_bank_msp(bank_name: Optional[str], rng: random.Random) -> str:
    if not bank_name:
        return rng.choice(CONSORTIUM_BANKS)
    clean = bank_name.strip().lower()
    return BANK_TO_MSP.get(clean, rng.choice(CONSORTIUM_BANKS))


class CausalBlockchainSignalGenerator:
    """
    Generates causal pre-outcome Hyperledger Fabric signals for a complaint
    based strictly on observable state at prediction time T.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate_pre_outcome_signals(
        self,
        complaint: Dict[str, Any],
        candidate_clusters: List[Dict[str, Any]],
        all_delhi_clusters: List[Dict[str, Any]],
        terminal_zone: Optional[str] = None,
        all_tx_zones: Optional[Set[str]] = None,
        transactions: Optional[List[Dict[str, Any]]] = None,
        noise_level: float = 0.15
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Generates causal pre-outcome signals for candidate clusters and subject mule.

        Returns:
            (cluster_signals, subject_signals)
        """
        # Reference timestamp T
        rep_at = complaint.get("reported_at")
        if isinstance(rep_at, str):
            if rep_at.endswith("Z"):
                rep_clean = rep_at[:-1] + "+00:00"
            else:
                rep_clean = rep_at
            t_ref = datetime.fromisoformat(rep_clean)
            if t_ref.tzinfo is None:
                t_ref = t_ref.replace(tzinfo=timezone.utc)
        elif isinstance(rep_at, datetime):
            t_ref = rep_at if rep_at.tzinfo else rep_at.replace(tzinfo=timezone.utc)
        else:
            t_ref = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)

        amount_raw = complaint.get("amount")
        amount = float(amount_raw) if amount_raw is not None else 25000.0
        c_num = complaint.get("complaint_number") or "CMP-UNKNOWN"

        # Deterministic PRNG seeded by observable complaint attributes (NO target label!)
        seed_str = f"{c_num}_{amount}_{complaint.get('payment_channel')}_{complaint.get('victim_district')}_{terminal_zone}"
        case_seed = hash(seed_str) & 0xFFFFFFFF
        c_rng = random.Random(case_seed)

        # Opaque subject token from observable mule account / transaction
        opaque_subject_ref = None
        mule_bank_msp = c_rng.choice(CONSORTIUM_BANKS)
        if transactions and len(transactions) > 0:
            terminal_tx = max(transactions, key=lambda x: x.get("hop_number", 0))
            mule_acc = terminal_tx.get("receiver_account_number", "MULE_UNKNOWN")
            mule_bank = terminal_tx.get("receiver_bank")
            mule_bank_msp = get_bank_msp(mule_bank, c_rng)
            opaque_subject_ref = f"MULE_SUBJ_{hash(mule_acc) & 0xFFFFFF:06x}"
        else:
            opaque_subject_ref = f"MULE_SUBJ_{case_seed & 0xFFFFFF:06x}"

        cluster_signals = []
        subject_signals = []

        active_zones = set()
        if terminal_zone:
            norm_tz = normalize_zone(terminal_zone)
            if norm_tz:
                active_zones.add(norm_tz)
        if all_tx_zones:
            for z in all_tx_zones:
                norm_z = normalize_zone(z)
                if norm_z:
                    active_zones.add(norm_z)
        if complaint.get("victim_district"):
            norm_vd = normalize_zone(complaint.get("victim_district"))
            if norm_vd:
                active_zones.add(norm_vd)

        # Observable trajectory analysis:
        v_lat = float(complaint.get("victim_lat") or 28.6315)
        v_lon = float(complaint.get("victim_lon") or 77.2167)
        origin_cands = sorted(
            candidate_clusters,
            key=lambda c: (float(c.get("lat", 28.6315)) - v_lat) ** 2 + (float(c.get("lon", 77.2167)) - v_lon) ** 2
        )
        origin_cand = origin_cands[0] if origin_cands else None

        norm_tz = normalize_zone(terminal_zone)
        norm_vd = normalize_zone(complaint.get("victim_district"))
        term_cands = [
            c for c in candidate_clusters
            if normalize_zone(c.get("zone") or c.get("district")) == norm_tz
        ] if norm_tz else []

        if term_cands:
            term_hub = max(
                term_cands,
                key=lambda x: ((min(45.0, float(x.get("atm_density") or 15.0)) / 45.0) * 0.50 + float(x.get("risk") or x.get("base_risk") or 0.50) * 0.50)
            )
        else:
            term_hub = None

        # Causal syndicate pre-cashout hub assignment:
        # - Local trajectory (terminal == origin or no terminal zone): local origin commercial hub
        # - Cross-zone trajectory: terminal corridor commercial hub
        op_cluster_ids = set()
        r_choice = c_rng.random()
        if (norm_tz == norm_vd or not norm_tz) and origin_cand:
            if r_choice < 0.70:
                op_cluster_ids.add(origin_cand["id"])
            elif term_hub:
                op_cluster_ids.add(term_hub["id"])
        else:
            if r_choice < 0.65 and term_hub:
                op_cluster_ids.add(term_hub["id"])
            elif origin_cand:
                op_cluster_ids.add(origin_cand["id"])

        for cluster in candidate_clusters:
            cid = cluster["id"]
            c_raw_zone = cluster.get("zone") or cluster.get("district")
            c_norm_zone = normalize_zone(c_raw_zone)
            c_risk = float(cluster.get("risk") or cluster.get("base_risk") or 0.50)

            is_op_hub = cid in op_cluster_ids
            in_active_corridor = (c_norm_zone in active_zones) if c_norm_zone else False

            if is_op_hub:
                # Strong pre-outcome activity at the operational hub
                p_emit = 0.95
                num_sigs = c_rng.choices([2, 3, 4], weights=[0.30, 0.50, 0.20])[0]
            elif in_active_corridor:
                # Sparse background in corridor: 10%
                p_emit = 0.10
                num_sigs = 1
            else:
                # Low diffuse background across city: 5%
                p_emit = 0.04 + 0.05 * c_risk
                num_sigs = 1

            if c_rng.random() < p_emit:
                for s_idx in range(num_sigs):
                    if is_op_hub:
                        # Recent pre-cashout window: 15 min to 2.5 hours before T_ref
                        age_min = c_rng.uniform(15.0, 150.0)
                        etype = c_rng.choices(
                            [
                                "ATM_WITHDRAWAL_ATTEMPT",
                                "MULE_ACCOUNT_ACTIVITY",
                                "ATM_WITHDRAWAL_CONFIRMED",
                                "LEA_CONFIRMED_CLUSTER"
                            ],
                            weights=[0.45, 0.35, 0.15, 0.05]
                        )[0]
                    elif in_active_corridor:
                        # Older corridor traffic: 3 hours to 24 hours
                        age_min = c_rng.uniform(180.0, 1440.0)
                        etype = c_rng.choice(["ATM_WITHDRAWAL_ATTEMPT", "ATM_WITHDRAWAL_CONFIRMED"])
                    else:
                        # City background: 12 hours to 7 days before T_ref
                        age_min = c_rng.uniform(720.0, 10000.0)
                        etype = c_rng.choice(["ATM_WITHDRAWAL_CONFIRMED", "ATM_WITHDRAWAL_ATTEMPT"])

                    evt_time = t_ref - timedelta(minutes=age_min)
                    sub_time = evt_time + timedelta(seconds=c_rng.uniform(10.0, 60.0))
                    if sub_time > t_ref:
                        sub_time = t_ref

                    if etype == "LEA_CONFIRMED_CLUSTER":
                        org = c_rng.choice(AUTHORITIES)
                        conf = 1.0
                    elif etype == "MULE_ACCOUNT_ACTIVITY":
                        org = mule_bank_msp if s_idx == 0 else c_rng.choice(CONSORTIUM_BANKS)
                        conf = round(c_rng.uniform(0.85, 0.98), 2)
                    else:
                        org = c_rng.choice(CONSORTIUM_BANKS)
                        conf = round(c_rng.uniform(0.78, 0.94), 2)

                    sig = {
                        "event_id": f"SIG-CAUSAL-{cid}-{case_seed & 0xFFFF}-{s_idx}",
                        "event_type": etype,
                        "cluster_id": cid,
                        "organization_msp": org,
                        "district": c_raw_zone,
                        "event_timestamp": evt_time.isoformat(),
                        "submitted_at": sub_time.isoformat(),
                        "confidence": conf,
                        "status": "ACTIVE"
                    }
                    cluster_signals.append(sig)

                    if etype == "MULE_ACCOUNT_ACTIVITY":
                        subj_sig = dict(sig)
                        subj_sig["opaque_subject_ref"] = opaque_subject_ref
                        subject_signals.append(subj_sig)

        return cluster_signals, subject_signals
