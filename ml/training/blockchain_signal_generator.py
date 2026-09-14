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

# Bank name normalization helper
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
        noise_level: float = 0.20
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

        amount = float(complaint.get("amount", 25000.0))
        c_num = complaint.get("complaint_number", "CMP-UNKNOWN")

        # Deterministic PRNG seeded by complaint attributes (excluding target!)
        # Use complaint number, amount, payment channel, victim district
        seed_str = f"{c_num}_{amount}_{complaint.get('payment_channel')}_{complaint.get('victim_district')}"
        case_seed = hash(seed_str) & 0xFFFFFFFF
        c_rng = random.Random(case_seed)

        # Opaque subject token (e.g. SHA-256 hash of terminal mule account if available)
        opaque_subject_ref = None
        mule_bank_msp = c_rng.choice(CONSORTIUM_BANKS)
        if transactions and len(transactions) > 0:
            terminal_tx = max(transactions, key=lambda x: x.get("hop_number", 0))
            mule_acc = terminal_tx.get("receiver_account_number", "MULE_UNKNOWN")
            mule_bank = terminal_tx.get("receiver_bank")
            mule_bank_msp = get_bank_msp(mule_bank, c_rng)
            # Opaque hash
            opaque_subject_ref = f"MULE_SUBJ_{hash(mule_acc) & 0xFFFFFF:06x}"
        else:
            opaque_subject_ref = f"MULE_SUBJ_{case_seed & 0xFFFFFF:06x}"

        cluster_signals = []
        subject_signals = []

        active_zones = set()
        if terminal_zone:
            active_zones.add(terminal_zone)
        if all_tx_zones:
            active_zones.update(all_tx_zones)
        if not active_zones and complaint.get("victim_district"):
            active_zones.add(str(complaint.get("victim_district")))

        # Iterate over all candidate clusters and generate causal signals
        # Probability of signals depends on:
        # 1. Zone proximity to terminal/active mule zones (observable)
        # 2. Historical cluster risk score and historical fraud rate (observable)
        # 3. Transaction velocity / amount (observable)
        for cluster in candidate_clusters:
            cid = cluster["id"]
            c_zone = cluster.get("zone") or cluster.get("district")
            c_risk = float(cluster.get("risk", 0.50))
            c_density = float(cluster.get("atm_density", 15.0))
            c_hist_count = float(cluster.get("historical_cashout_count", 200.0))

            in_active_zone = c_zone in active_zones

            # Base signal emission probability:
            # - Clusters in the terminal mule district have higher pre-cashout observation rates
            # - Clusters with high historical risk have background signals
            base_prob = 0.15
            if in_active_zone:
                base_prob += 0.35
            base_prob += min(0.30, c_risk * 0.30)

            # Roll for signals in this cluster
            if c_rng.random() < base_prob:
                num_signals = c_rng.choices([1, 2, 3, 4], weights=[0.50, 0.30, 0.15, 0.05])[0]

                for s_idx in range(num_signals):
                    # Signal age relative to T: strictly in the past!
                    # Mix of very recent (15-60 min ago), medium (1-6h), and historical (1-7d)
                    age_category = c_rng.choices(
                        ["1h", "6h", "24h", "7d", "30d"],
                        weights=[0.30, 0.35, 0.20, 0.10, 0.05]
                    )[0]

                    if age_category == "1h":
                        age_minutes = c_rng.uniform(5.0, 55.0)
                    elif age_category == "6h":
                        age_minutes = c_rng.uniform(65.0, 350.0)
                    elif age_category == "24h":
                        age_minutes = c_rng.uniform(370.0, 1400.0)
                    elif age_category == "7d":
                        age_minutes = c_rng.uniform(1500.0, 9500.0)
                    else:
                        age_minutes = c_rng.uniform(10000.0, 40000.0)

                    evt_time = t_ref - timedelta(minutes=age_minutes)
                    sub_time = evt_time + timedelta(seconds=c_rng.uniform(10.0, 120.0))
                    # Guarantee anti-leakage: submitted_at <= t_ref
                    if sub_time > t_ref:
                        sub_time = t_ref

                    # Select causal event type
                    # In active mule zone: high mule activity, attempt, or confirmation
                    if in_active_zone:
                        etype = c_rng.choices(
                            [
                                "MULE_ACCOUNT_ACTIVITY",
                                "ATM_WITHDRAWAL_ATTEMPT",
                                "ATM_WITHDRAWAL_CONFIRMED",
                                "BRANCH_CASHOUT_CONFIRMED",
                                "LEA_CONFIRMED_CLUSTER"
                            ],
                            weights=[0.35, 0.30, 0.20, 0.05, 0.10]
                        )[0]
                    else:
                        etype = c_rng.choices(
                            [
                                "ATM_WITHDRAWAL_ATTEMPT",
                                "ATM_WITHDRAWAL_CONFIRMED",
                                "MULE_ACCOUNT_ACTIVITY",
                                "LEA_CONFIRMED_CLUSTER"
                            ],
                            weights=[0.40, 0.35, 0.15, 0.10]
                        )[0]

                    # Organization
                    if etype == "LEA_CONFIRMED_CLUSTER":
                        org_msp = c_rng.choice(AUTHORITIES)
                    elif etype == "MULE_ACCOUNT_ACTIVITY":
                        org_msp = mule_bank_msp if c_rng.random() < 0.70 else c_rng.choice(CONSORTIUM_BANKS)
                    else:
                        org_msp = c_rng.choice(CONSORTIUM_BANKS)

                    conf = round(c_rng.uniform(0.70, 0.98), 2)
                    if etype == "LEA_CONFIRMED_CLUSTER":
                        conf = 1.0

                    sig_id = f"SIG-CAUSAL-{cid}-{case_seed & 0xFFFF}-{s_idx}"
                    sig = {
                        "event_id": sig_id,
                        "event_type": etype,
                        "cluster_id": cid,
                        "organization_msp": org_msp,
                        "district": c_zone,
                        "event_timestamp": evt_time.isoformat(),
                        "submitted_at": sub_time.isoformat(),
                        "confidence": conf,
                        "status": "ACTIVE"
                    }
                    cluster_signals.append(sig)

                    # Link to subject if mule activity in active zone
                    if in_active_zone and etype == "MULE_ACCOUNT_ACTIVITY" and c_rng.random() < 0.60:
                        subj_sig = dict(sig)
                        subj_sig["opaque_subject_ref"] = opaque_subject_ref
                        subject_signals.append(subj_sig)

        return cluster_signals, subject_signals
