"""
CyberShield AI — Synthetic Dataset Generator (V2)
Phase 1 Step 8B: Controlled Probabilistic Cybercrime Cash-Out Corridor Generator.

Causal generation order:
1. Generate complaint.
2. Generate/select origin geography.
3. Generate fraud/channel/amount/time profile.
4. Generate mule/account network.
5. Assign legitimate pre-withdrawal account geography (zone, branch).
6. Generate multi-hop branching transaction trail.
7. Derive pre-withdrawal corridor context (terminal account geography).
8. Sample target cash-out cluster probabilistically:
   - LOCAL (35%): origin cluster (60%) or another cluster in same origin zone (40%)
   - MULE_CORRIDOR (35%): terminal account zone (70%), adjacent zone (20%), or hotspot (10%)
   - HISTORICAL_HOTSPOT (18%): top Delhi cybercrime hotspots weighted by fraud-type affinity
   - CROSS_ZONE (12%): distant operational zones across Delhi
9. Generate Withdrawal / ATM outcome from chosen target.
10. Store target only as outcome / label.
"""

import random
import datetime
import collections
from collections import Counter
from decimal import Decimal
from typing import List, Dict, Any, Set, Optional

from database.seed.seed_config import (
    SYNTHETIC_RANDOM_SEED,
    COMPLAINT_PREFIX, ACCOUNT_PREFIX, TRANSACTION_PREFIX,
    NUM_COMPLAINTS, NUM_ACCOUNTS, WITHDRAWAL_RATIO,
    FRAUD_TYPES, PAYMENT_CHANNELS, BANK_NAMES, AMOUNT_BANDS,
    REPORTING_DELAYS
)

# Geographic adjacency across the 9 Delhi Operational Zones
ZONE_ADJACENCY: Dict[str, List[str]] = {
    "CENTRAL_NEW_DELHI": ["NORTH", "WEST", "SOUTH", "SOUTH_EAST", "EAST"],
    "SOUTH": ["CENTRAL_NEW_DELHI", "SOUTH_EAST", "SOUTH_WEST_DWARKA"],
    "SOUTH_EAST": ["SOUTH", "CENTRAL_NEW_DELHI", "EAST"],
    "WEST": ["CENTRAL_NEW_DELHI", "NORTH_WEST", "SOUTH_WEST_DWARKA"],
    "SOUTH_WEST_DWARKA": ["WEST", "SOUTH"],
    "NORTH": ["CENTRAL_NEW_DELHI", "NORTH_WEST", "NORTH_EAST_SHAHDARA"],
    "NORTH_WEST": ["NORTH", "WEST"],
    "EAST": ["CENTRAL_NEW_DELHI", "SOUTH_EAST", "NORTH_EAST_SHAHDARA"],
    "NORTH_EAST_SHAHDARA": ["EAST", "NORTH"]
}

# Probabilistic fraud-type corridor affinity (weak/moderate priors, not deterministic)
FRAUD_TYPE_ZONE_AFFINITY: Dict[str, List[str]] = {
    "investment scam": ["CENTRAL_NEW_DELHI", "SOUTH_EAST", "SOUTH"],
    "phishing": ["NORTH_WEST", "WEST", "EAST"],
    "loan-app scam": ["WEST", "NORTH_WEST", "SOUTH_EAST"],
    "fake customer-care scam": ["EAST", "NORTH_EAST_SHAHDARA", "NORTH"],
    "job scam": ["SOUTH_WEST_DWARKA", "WEST", "NORTH_WEST"],
    "impersonation scam": ["CENTRAL_NEW_DELHI", "SOUTH", "NORTH"],
    "UPI fraud": ["SOUTH", "WEST", "EAST"],
    "QR-code scam": ["CENTRAL_NEW_DELHI", "SOUTH_EAST", "NORTH"],
    "remote-access scam": ["WEST", "SOUTH_WEST_DWARKA", "SOUTH_EAST"],
    "account takeover": ["CENTRAL_NEW_DELHI", "NORTH_WEST", "SOUTH"],
    "marketplace scam": ["NORTH", "EAST", "WEST"],
    "e-commerce scam": ["SOUTH_EAST", "EAST", "SOUTH_WEST_DWARKA"]
}


class DelhiSyntheticDataGenerator:
    """
    Synthetic Dataset Generator V2 for CyberShield AI.
    Implements realistic, learnable, prediction-time-safe cash-out corridor patterns.
    """

    def __init__(self, seed: int = SYNTHETIC_RANDOM_SEED):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_accounts(
        self,
        clusters: Optional[Any] = None,
        num_accounts: int = NUM_ACCOUNTS
    ) -> List[Dict[str, Any]]:
        """
        Generates deterministic synthetic accounts with distinct roles and coherent
        Delhi operational geography (zone, commercial branch).
        - 0 to 2999: Victim Accounts (is_mule=False)
        - 3000 to 5199: Dedicated Mule / Intermediary Accounts (is_mule=True)
        - 5200 to 5999: Shared High-Frequency Mule Accounts (is_mule=True)
        """
        if isinstance(clusters, int):
            num_accounts = clusters
            clusters = None

        accounts = []
        base_date = datetime.datetime(2026, 1, 1, 10, 0, 0)

        # Map clusters by zone to generate coherent branch names
        clusters_by_zone = collections.defaultdict(list)
        if clusters:
            for c in clusters:
                clusters_by_zone[c.get("zone", c.get("district", "CENTRAL_NEW_DELHI"))].append(c)

        zones = list(clusters_by_zone.keys()) if clusters_by_zone else [
            "CENTRAL_NEW_DELHI", "SOUTH", "SOUTH_EAST", "WEST",
            "SOUTH_WEST_DWARKA", "NORTH", "NORTH_WEST", "EAST", "NORTH_EAST_SHAHDARA"
        ]

        for i in range(1, num_accounts + 1):
            acc_num = f"{ACCOUNT_PREFIX}{i:06d}"
            masked = f"ACC••••{i:04d}"
            bank = BANK_NAMES[(i - 1) % len(BANK_NAMES)]

            # Cyclically distribute accounts across the 9 Delhi zones
            zone = zones[(i - 1) % len(zones)]
            zone_clusters = clusters_by_zone.get(zone, [])
            if zone_clusters:
                rep_cluster = zone_clusters[((i - 1) // len(zones)) % len(zone_clusters)]
                area_name = rep_cluster.get("name", "").replace(", Delhi", "").strip()
                branch = f"{area_name} Commercial Branch"
            else:
                branch = f"Delhi Zone {((i - 1) % 9) + 1} Hub {((i - 1) % 50) + 1}"

            if i <= 3000:
                is_mule = False
                holder = f"Citizen Cardholder DL-{i}"
                acc_type = "SAVINGS"
                risk_score = round(self.rng.uniform(0.02, 0.20), 2)
                flag_reason = None
            elif i <= 5200:
                is_mule = True
                holder = f"Commercial Node DL-{i}"
                acc_type = "CURRENT" if (i % 3 == 0) else "SAVINGS"
                risk_score = round(self.rng.uniform(0.65, 0.88), 2)
                flag_reason = "Layering node with rapid fund dispersion"
            else:
                is_mule = True
                holder = f"Shared Syndicate Mule DL-{i}"
                acc_type = "CURRENT" if (i % 2 == 0) else "SAVINGS"
                risk_score = round(self.rng.uniform(0.85, 0.98), 2)
                flag_reason = "Repeated terminal recipient across multiple cybercrime cases"

            ifsc = f"{bank.replace(' ', '')[:4].upper()}000{((i - 1) % 900) + 100}"
            created_at = base_date + datetime.timedelta(days=(i % 60))

            accounts.append({
                "account_number": acc_num,
                "masked_account": masked,
                "bank_name": bank,
                "branch": branch,
                "ifsc": ifsc,
                "holder_name": holder,
                "account_type": acc_type,
                "state": "Delhi",
                "district": zone,
                "risk_score": risk_score,
                "is_mule": is_mule,
                "flag_reason": flag_reason,
                "created_at": created_at
            })

        return accounts

    def sample_amount(self) -> Decimal:
        """Samples heterogeneous realistic amounts across 4 amount bands."""
        r = self.rng.random()
        cumulative = 0.0
        for name, low, high, weight in AMOUNT_BANDS:
            cumulative += weight
            if r <= cumulative:
                amt = self.rng.uniform(low, high)
                amt_rounded = round(amt / 50.0) * 50.0
                return Decimal(f"{amt_rounded:.2f}")
        return Decimal("25000.00")

    def sample_reporting_delay_hours(self) -> float:
        """Samples realistic reporting delays."""
        r = self.rng.random()
        cumulative = 0.0
        for name, low, high, weight in REPORTING_DELAYS:
            cumulative += weight
            if r <= cumulative:
                return self.rng.uniform(low, high)
        return 2.5

    def sample_hop_count(self) -> int:
        """Samples hop depth according to target distribution."""
        r = self.rng.random()
        if r < 0.12:
            return 1
        elif r < 0.40:
            return 2
        elif r < 0.72:
            return 3
        else:
            return 4

    def sample_cluster_weighted(self, cluster_candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Samples a cluster from candidates weighted by risk and ATM density."""
        if not cluster_candidates:
            return None
        weights = [
            float(c.get("risk", c.get("base_risk", 0.5))) * float(c.get("atm_density", 15.0))
            for c in cluster_candidates
        ]
        total_w = sum(weights)
        if total_w <= 0:
            return self.rng.choice(cluster_candidates)
        probs = [w / total_w for w in weights]
        return self.rng.choices(cluster_candidates, weights=probs, k=1)[0]

    def generate_dataset(
        self,
        clusters: List[Dict[str, Any]],
        atms: List[Dict[str, Any]],
        num_complaints: int = NUM_COMPLAINTS,
        num_accounts: int = NUM_ACCOUNTS
    ) -> Dict[str, Any]:
        """
        Generates the full relational synthetic dataset V2 with realistic cash-out corridors:
        - accounts
        - complaints
        - complaint_accounts
        - multi-hop branching transactions (~48,000)
        - withdrawals (~2,100)
        - debug_metadata (scenario explainability)
        """
        accounts = self.generate_accounts(clusters, num_accounts)

        atms_by_cluster = collections.defaultdict(list)
        for a in atms:
            atms_by_cluster[a["cluster_name"]].append(a)

        clusters_by_zone = collections.defaultdict(list)
        for c in clusters:
            clusters_by_zone[c.get("zone", c.get("district"))].append(c)

        top_hotspots = sorted(
            clusters,
            key=lambda c: (float(c.get("risk", c.get("base_risk", 0.5))), float(c.get("atm_density", 15.0))),
            reverse=True
        )[:15]

        complaints = []
        complaint_accounts = []
        transactions = []
        withdrawals = []
        debug_metadata = []

        end_date = datetime.datetime(2026, 9, 10, 18, 0, 0)

        n_acc = len(accounts)
        victim_cutoff = min(num_complaints, int(n_acc * 0.5))
        dedicated_end = victim_cutoff + int((n_acc - victim_cutoff) * 0.50)

        dedicated_mules = list(range(victim_cutoff, dedicated_end))
        shared_mules = list(range(dedicated_end, n_acc))

        mule_capacities = {}
        for m in shared_mules:
            r_cap = self.rng.random()
            if r_cap < 0.65:
                mule_capacities[m] = self.rng.randint(2, 4)
            elif r_cap < 0.88:
                mule_capacities[m] = self.rng.randint(5, 8)
            elif r_cap < 0.97:
                mule_capacities[m] = self.rng.randint(9, 13)
            else:
                mule_capacities[m] = self.rng.randint(14, 18)

        mule_usage = Counter()
        txn_counter = 1
        withdrawal_counter = 1
        scenario_counts = Counter()

        for c_idx in range(num_complaints):
            complaint_num = f"{COMPLAINT_PREFIX}{c_idx + 1:04d}"
            fraud_type = FRAUD_TYPES[c_idx % len(FRAUD_TYPES)]
            payment_channel = PAYMENT_CHANNELS[c_idx % len(PAYMENT_CHANNELS)]
            total_amount = self.sample_amount()

            # 1. Origin Geography
            origin_cluster = clusters[c_idx % len(clusters)]
            origin_zone = origin_cluster.get("zone", origin_cluster.get("district"))
            victim_location = f"{origin_cluster['name']}, {origin_zone}"
            district = origin_zone

            # Coordinates: 80% populated with realistic jitter, 20% nullable
            if self.rng.random() < 0.80:
                victim_lat = round(origin_cluster["lat"] + self.rng.uniform(-0.008, 0.008), 6)
                victim_lon = round(origin_cluster["lon"] + self.rng.uniform(-0.008, 0.008), 6)
            else:
                victim_lat = None
                victim_lon = None

            days_ago = self.rng.uniform(1.0, 35.0)
            incident_time = end_date - datetime.timedelta(days=days_ago, hours=self.rng.uniform(0, 12))
            delay_hours = self.sample_reporting_delay_hours()
            reported_at = incident_time + datetime.timedelta(hours=delay_hours)
            created_at = reported_at + datetime.timedelta(minutes=self.rng.uniform(5, 15))

            risk_score = round(self.rng.uniform(0.40, 0.96), 2)
            risk_level = "CRITICAL" if risk_score >= 0.80 else ("HIGH" if risk_score >= 0.60 else "MEDIUM")
            prediction_status = "COMPLETED" if risk_score >= 0.60 else "PENDING"

            status_roll = self.rng.random()
            if status_roll < 0.60:
                case_status = "ACTIVE"
            elif status_roll < 0.85:
                case_status = "UNDER_INVESTIGATION"
            elif status_roll < 0.95:
                case_status = "ALERTED"
            else:
                case_status = "RESOLVED"

            description = (
                f"Synthetic operational complaint: unauthorized {fraud_type} debit of ₹{total_amount} "
                f"via {payment_channel} in {origin_cluster['name']}."
            )

            complaint_record = {
                "complaint_number": complaint_num,
                "fraud_type": fraud_type,
                "amount": total_amount,
                "victim_name": f"Citizen DL-{c_idx + 1}",
                "victim_phone": f"+91 9{self.rng.randint(100000000, 999999999)}",
                "victim_location": victim_location,
                "state": "Delhi",
                "district": district,
                "payment_channel": payment_channel,
                "reported_at": reported_at,
                "incident_time": incident_time,
                "victim_lat": victim_lat,
                "victim_lon": victim_lon,
                "description": description,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "prediction_status": prediction_status,
                "case_status": case_status,
                "created_at": created_at
            }
            complaints.append(complaint_record)

            # 2. Multi-Hop Branching Transaction Graph
            victim_acc_idx = c_idx
            victim_acc = accounts[victim_acc_idx]
            linked_account_numbers = {victim_acc["account_number"]}

            complaint_accounts.append({
                "complaint_number": complaint_num,
                "account_number": victim_acc["account_number"],
                "association_type": "VICTIM"
            })

            hop_depth = self.sample_hop_count()
            is_delayed_movement = (self.rng.random() < 0.08)
            delayed_hop = self.rng.choice([1, 2]) if hop_depth >= 2 else 1

            if hop_depth == 1:
                layer_widths = [self.rng.choice([1, 2, 2])]
            elif hop_depth == 2:
                layer_widths = [2, self.rng.choice([3, 4, 4])]
            elif hop_depth == 3:
                layer_widths = [2, self.rng.choice([4, 5, 5]), self.rng.choice([4, 5, 6])]
            else:
                layer_widths = [3, self.rng.choice([4, 5, 6]), self.rng.choice([5, 6, 7]), self.rng.choice([5, 6, 6])]

            layers_nodes = []
            used_in_this_complaint = {victim_acc_idx}

            for width in layer_widths:
                layer = []
                for _ in range(width):
                    candidate = None
                    if self.rng.random() < 0.35 and shared_mules:
                        sample_size = min(25, len(shared_mules))
                        cand_list = [
                            m for m in self.rng.sample(shared_mules, sample_size)
                            if m not in used_in_this_complaint and mule_usage[m] < mule_capacities.get(m, 4)
                        ]
                        if cand_list:
                            candidate = cand_list[0]
                            mule_usage[candidate] += 1

                    if candidate is None:
                        candidate = self.rng.choice(dedicated_mules)
                        attempts = 0
                        while candidate in used_in_this_complaint and attempts < 10:
                            candidate = self.rng.choice(dedicated_mules)
                            attempts += 1

                    used_in_this_complaint.add(candidate)
                    layer.append(candidate)
                layers_nodes.append(layer)

            # Record associations
            for layer_idx, layer in enumerate(layers_nodes):
                is_terminal = (layer_idx == len(layers_nodes) - 1)
                assoc_role = "BENEFICIARY" if is_terminal else "INTERMEDIARY"
                for m_idx in layer:
                    m_acc = accounts[m_idx]
                    if m_acc["account_number"] not in linked_account_numbers:
                        linked_account_numbers.add(m_acc["account_number"])
                        complaint_accounts.append({
                            "complaint_number": complaint_num,
                            "account_number": m_acc["account_number"],
                            "association_type": assoc_role
                        })

            # Initial victim outflow allocations
            current_time = incident_time + datetime.timedelta(minutes=self.rng.uniform(2, 20))
            if self.rng.random() < 0.40 and float(total_amount) > 15000:
                split_val = self.rng.uniform(0.40, 0.60)
                a1 = Decimal(f"{round(float(total_amount) * split_val, 2):.2f}")
                a2 = total_amount - a1
                active_allocations = [
                    (victim_acc["account_number"], a1, current_time),
                    (victim_acc["account_number"], a2, current_time + datetime.timedelta(minutes=self.rng.uniform(1, 5)))
                ]
            else:
                active_allocations = [(victim_acc["account_number"], total_amount, current_time)]

            comp_tx_records = []
            terminal_transactions = []
            for hop_idx, layer in enumerate(layers_nodes):
                hop_num = hop_idx + 1
                next_allocations = []

                for sender_acc_num, in_amt, in_time in active_allocations:
                    n_recvs = min(len(layer), 2 if len(layer) > 1 and self.rng.random() < 0.90 else 1)
                    receivers_idx = self.rng.sample(layer, n_recvs)

                    split_weights = [self.rng.uniform(0.7, 1.3) for _ in receivers_idx]
                    weight_sum = sum(split_weights)
                    net_amt = Decimal(f"{round(float(in_amt) * 0.985, 2):.2f}")

                    allocated_so_far = Decimal("0.00")
                    for r_i, r_idx in enumerate(receivers_idx):
                        r_acc = accounts[r_idx]
                        if r_acc["account_number"] == sender_acc_num:
                            continue

                        if r_i == len(receivers_idx) - 1:
                            tx_amt = max(net_amt - allocated_so_far, Decimal("50.00"))
                        else:
                            share = (split_weights[r_i] / weight_sum)
                            tx_amt = Decimal(f"{round(float(net_amt) * share, 2):.2f}")
                            allocated_so_far += tx_amt

                        if tx_amt <= 0:
                            tx_amt = Decimal("50.00")

                        if is_delayed_movement and hop_num == delayed_hop:
                            delay_h = self.rng.uniform(6.0, 24.0) if self.rng.random() < 0.65 else self.rng.uniform(24.0, 48.0)
                            t_gap_minutes = delay_h * 60.0
                        elif self.rng.random() < 0.20:
                            t_gap_minutes = self.rng.uniform(0.5, 2.0)
                        else:
                            t_gap_minutes = self.rng.uniform(3, 30) if hop_num < 3 else self.rng.uniform(15, 60)

                        tx_time = in_time + datetime.timedelta(minutes=t_gap_minutes)
                        ch = payment_channel if hop_num == 1 else self.rng.choice(["UPI", "IMPS", "NEFT", "RTGS"])

                        tx_record = {
                            "transaction_ref": f"{TRANSACTION_PREFIX}{txn_counter:06d}",
                            "complaint_number": complaint_num,
                            "sender_account_number": sender_acc_num,
                            "receiver_account_number": r_acc["account_number"],
                            "amount": tx_amt,
                            "payment_channel": ch,
                            "timestamp": tx_time,
                            "hop_number": hop_num,
                            "status": "COMPLETED",
                            "suspicious_flag": True
                        }
                        transactions.append(tx_record)
                        comp_tx_records.append(tx_record)
                        txn_counter += 1

                        next_allocations.append((r_acc["account_number"], tx_amt, tx_time))

                        if hop_idx == len(layers_nodes) - 1:
                            terminal_transactions.append((tx_record, r_acc))

                if len(next_allocations) > 10:
                    active_allocations = self.rng.sample(next_allocations, 10)
                else:
                    active_allocations = next_allocations

            # Chronological Cutoff Alignment:
            # Ensure prediction reference cutoff (reported_at) occurs strictly AFTER
            # all transactions in the multi-hop network have completed.
            if comp_tx_records:
                max_tx_time = max(t["timestamp"] for t in comp_tx_records)
                if reported_at < max_tx_time:
                    reported_at = max_tx_time + datetime.timedelta(minutes=self.rng.uniform(5, 25))
                    created_at = reported_at + datetime.timedelta(minutes=self.rng.uniform(5, 15))
                    complaint_record["reported_at"] = reported_at
                    complaint_record["created_at"] = created_at
            else:
                max_tx_time = incident_time

            # 3. Pre-Withdrawal Corridor Context & Probabilistic Target Sampling
            # Target cash-out cluster emerges causally from the money network (mules, layering, hotspots)
            # ZERO direct shortcuts based on victim origin geography.
            if terminal_transactions:
                chosen_term_tx, term_account = max(terminal_transactions, key=lambda pair: pair[0]["amount"])
            else:
                chosen_term_tx = None
                term_account = victim_acc

            term_zone = term_account.get("district", origin_zone)

            # Collect intermediate layering account zones across the multi-hop network
            int_zones = []
            for layer_idx, layer in enumerate(layers_nodes[:-1]):
                for m_idx in layer:
                    m_z = accounts[m_idx].get("district")
                    if m_z:
                        int_zones.append(m_z)

            # Causal Cash-Out Corridor Mixture:
            # 1. TERMINAL_MULE_CORRIDOR (50%): cash-out occurs near terminal recipient mule node
            # 2. INTERMEDIARY_CORRIDOR (25%): cash-out occurs at intermediary layering node
            # 3. FRAUD_HOTSPOT (15%): cash-out occurs at top Delhi cybercrime commercial hotspots
            # 4. CROSS_ZONE_EVASION (10%): deliberate evasive cash-out across distant Delhi zones
            r_scen = self.rng.random()
            if r_scen < 0.50:
                scen_pattern = "TERMINAL_MULE_CORRIDOR"
                r_sub = self.rng.random()
                if r_sub < 0.70:
                    target_cluster = self.sample_cluster_weighted(clusters_by_zone.get(term_zone, []))
                elif r_sub < 0.90:
                    adj_zones = ZONE_ADJACENCY.get(term_zone, [term_zone])
                    chosen_adj = self.rng.choice(adj_zones)
                    target_cluster = self.sample_cluster_weighted(clusters_by_zone.get(chosen_adj, []))
                else:
                    target_cluster = self.sample_cluster_weighted(top_hotspots)
            elif r_scen < 0.75:
                scen_pattern = "INTERMEDIARY_CORRIDOR"
                if int_zones:
                    chosen_int_zone = self.rng.choice(int_zones)
                    r_sub = self.rng.random()
                    if r_sub < 0.75:
                        target_cluster = self.sample_cluster_weighted(clusters_by_zone.get(chosen_int_zone, []))
                    else:
                        adj_zones = ZONE_ADJACENCY.get(chosen_int_zone, [chosen_int_zone])
                        chosen_adj = self.rng.choice(adj_zones)
                        target_cluster = self.sample_cluster_weighted(clusters_by_zone.get(chosen_adj, []))
                else:
                    target_cluster = self.sample_cluster_weighted(clusters_by_zone.get(term_zone, []))
            elif r_scen < 0.90:
                scen_pattern = "FRAUD_HOTSPOT"
                favored_zones = FRAUD_TYPE_ZONE_AFFINITY.get(fraud_type, [])
                favored_clusters = [c for c in top_hotspots if c.get("zone", c.get("district")) in favored_zones]
                if favored_clusters and self.rng.random() < 0.75:
                    target_cluster = self.sample_cluster_weighted(favored_clusters)
                else:
                    target_cluster = self.sample_cluster_weighted(top_hotspots)
            else:
                scen_pattern = "CROSS_ZONE_EVASION"
                distant_zones = [z for z in clusters_by_zone.keys() if z != term_zone and z != origin_zone]
                if distant_zones:
                    chosen_d_zone = self.rng.choice(distant_zones)
                    target_cluster = self.sample_cluster_weighted(clusters_by_zone.get(chosen_d_zone, []))
                else:
                    target_cluster = self.sample_cluster_weighted(top_hotspots)

            if target_cluster is None:
                target_cluster = self.sample_cluster_weighted(clusters)

            scenario_counts[scen_pattern] += 1

            debug_metadata.append({
                "complaint_number": complaint_num,
                "scenario_pattern": scen_pattern,
                "origin_zone": origin_zone,
                "terminal_zone": term_zone,
                "target_cluster_name": target_cluster["name"],
                "target_zone": target_cluster.get("zone", target_cluster.get("district")),
                "is_same_origin": (target_cluster["name"] == origin_cluster["name"]),
                "is_same_origin_zone": (target_cluster.get("zone", target_cluster.get("district")) == origin_zone),
                "is_same_terminal_zone": (target_cluster.get("zone", target_cluster.get("district")) == term_zone)
            })

            # 4. Cash-Out / Withdrawal Outcome Generation
            if self.rng.random() < WITHDRAWAL_RATIO and chosen_term_tx:
                c_atms = atms_by_cluster.get(target_cluster["name"], atms[:4])
                target_atm = self.rng.choice(c_atms)
                ref_time = max(reported_at, max_tx_time, chosen_term_tx["timestamp"] if chosen_term_tx else reported_at)
                withdrawal_time = ref_time + datetime.timedelta(minutes=self.rng.uniform(15, 60))
                w_amt = Decimal(f"{min(float(chosen_term_tx['amount']), 50000.0):.2f}")

                withdrawals.append({
                    "withdrawal_ref": f"WDL-DL-{withdrawal_counter:06d}",
                    "atm_code": target_atm["atm_code"],
                    "account_number": term_account["account_number"],
                    "amount": w_amt,
                    "timestamp": withdrawal_time,
                    "success": True,
                    "camera_flagged": (self.rng.random() < 0.15),
                    "target_cluster_name": target_cluster["name"],
                    "target_zone": target_cluster.get("zone", target_cluster.get("district")),
                    "complaint_number": complaint_num
                })
                withdrawal_counter += 1

        return {
            "accounts": accounts,
            "complaints": complaints,
            "complaint_accounts": complaint_accounts,
            "transactions": transactions,
            "withdrawals": withdrawals,
            "debug_metadata": debug_metadata,
            "scenario_counts": dict(scenario_counts)
        }
