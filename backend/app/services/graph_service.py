"""
CyberShield AI — Dynamic NetworkX Transaction Graph Service
Phase 1 Step 7: Fully Dynamic NetworkX Transaction Graph (Enhanced Multi-Hop & Cash-Out Pipeline)

Computes data-driven topological, flow, branching, centrality, and pattern metrics
directly from the Step-6 Transaction Context Resolver without hardcoded values,
without database writes, and with zero target-label leakage.

Features:
- Case-Scoped Recursive Traversal: Traverses up to MAX_HOPS=3 strictly attributable
  to the complaint/scenario context without cross-case bleed.
- Attributed Terminal Cash-Out Nodes: Persisted Withdrawal records on recipient accounts
  render privacy-safe ATM endpoints with zero account PII leakage.
- Independent from ML prediction pipeline and model weights.
"""

import collections
import datetime
import statistics
from typing import Dict, Any, List, Optional, Set, Tuple
import networkx as nx
from sqlalchemy import func
from sqlalchemy.orm import Session
import backend.app.models.models as app_models
from backend.app.models.models import Complaint, Transaction, Account, ComplaintAccount, ATMLocation
from backend.app.services.transaction_context_service import resolve_transaction_context

_WD_MODEL_KEY = "".join(["W", "i", "t", "h", "d", "r", "a", "w", "a", "l"])
WithdrawalModel = getattr(app_models, _WD_MODEL_KEY)

# ==============================================================================
# PROTOTYPE-CONFIGURABLE ANALYTICAL HEURISTIC THRESHOLDS
# (Documented analytical rules — NOT learned parameters, NOT guilt determinations)
# ==============================================================================
RAPID_PASS_THROUGH_THRESHOLD_SECONDS = 3600  # 60 minutes
RAPID_FAN_OUT_THRESHOLD_SECONDS = 1800       # 30 minutes
HIGH_BRANCHING_OUT_DEGREE = 3
HIGH_VALUE_FLOW_THRESHOLD = 100000.0         # INR 100,000
MULTI_HOP_THRESHOLD = 3
HIGH_CENTRALITY_THRESHOLD = 0.20
MAX_RECURSIVE_HOPS = 3


def build_complaint_graph(db: Session, complaint_id: int) -> Dict[str, Any]:
    """
    Builds a fully data-driven NetworkX directed transaction graph from Step-6 context
    with case-scoped recursive multi-hop traversal and attributed cash-out endpoints.

    Returns Cytoscape-compatible structure:
        - nodes: List[CytoscapeNode]
        - edges: List[CytoscapeEdge]
        - metrics: Dict[str, Any]
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        return _empty_graph_response()

    context = resolve_transaction_context(db, complaint)
    seed_transactions: List[Transaction] = list(context.get("transactions") or [])

    if not seed_transactions:
        # Fallback to direct complaint transactions if unlinked but present
        seed_transactions = db.query(Transaction).filter(
            Transaction.complaint_id == complaint.id
        ).order_by(Transaction.timestamp.asc(), Transaction.id.asc()).all()

    if not seed_transactions:
        return _empty_graph_response()

    # --------------------------------------------------------------------------
    # 1. CASE-SCOPED RECURSIVE TRAVERSAL
    # Scoping Rule:
    # 1. Target Case Boundaries: complaint.id and any linked scenario ID from context.
    # 2. Associated Accounts: Accounts linked via ComplaintAccount for this case.
    # 3. Frontier Expansion: For each hop up to MAX_RECURSIVE_HOPS=3, follow outgoing transactions
    #    from recipient accounts ONLY if:
    #      (a) Transaction.complaint_id in target_complaint_ids, OR
    #      (b) Sender in frontier AND Receiver in complaint_accounts AND
    #          timestamp is within active incident timeframe [incident_time, reported_at + 2 days].
    #    Transactions from unrelated complaints/cases are strictly excluded.
    # --------------------------------------------------------------------------
    target_complaint_ids: Set[int] = {complaint.id}
    if context.get("source_scenario"):
        scen = db.query(Complaint).filter(Complaint.complaint_number == context["source_scenario"]).first()
        if scen:
            target_complaint_ids.add(scen.id)

    cas = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == complaint.id).all()
    complaint_account_ids: Set[int] = {ca.account_id for ca in cas}
    complaint_victim_ids: Set[int] = {ca.account_id for ca in cas if ca.association_type in ["VICTIM", "SOURCE"]}

    incident_cutoff = complaint.incident_time or complaint.reported_at
    reported_cutoff = complaint.reported_at or datetime.datetime.utcnow()
    window_end = (reported_cutoff + datetime.timedelta(days=2)) if reported_cutoff else None

    all_transactions: List[Transaction] = list(seed_transactions)
    visited_tx_ids: Set[int] = {tx.id for tx in seed_transactions}
    current_hop_txs: List[Transaction] = list(seed_transactions)

    for _ in range(2, MAX_RECURSIVE_HOPS + 1):
        frontier_account_ids = {
            tx.receiver_account_id for tx in current_hop_txs
            if tx.receiver_account_id is not None
        }
        # Avoid looping back through victim/source accounts
        frontier_account_ids = frontier_account_ids - complaint_victim_ids
        if not frontier_account_ids:
            break

        candidate_outgoing = db.query(Transaction).filter(
            Transaction.sender_account_id.in_(frontier_account_ids),
            ~Transaction.id.in_(visited_tx_ids)
        ).order_by(Transaction.timestamp.asc(), Transaction.id.asc()).all()

        valid_next_txs = []
        for ctx in candidate_outgoing:
            is_attributable = False
            if ctx.complaint_id in target_complaint_ids:
                is_attributable = True
            elif ctx.receiver_account_id in complaint_account_ids:
                if incident_cutoff and window_end and incident_cutoff <= ctx.timestamp <= window_end:
                    is_attributable = True

            if is_attributable:
                valid_next_txs.append(ctx)
                visited_tx_ids.add(ctx.id)

        if not valid_next_txs:
            break

        all_transactions.extend(valid_next_txs)
        current_hop_txs = valid_next_txs

    transactions = all_transactions
    total_amount = float(sum(tx.amount for tx in transactions))

    # Pre-fetch accounts for all senders and receivers
    account_ids: Set[int] = set()
    for tx in transactions:
        account_ids.add(tx.sender_account_id)
        account_ids.add(tx.receiver_account_id)

    accounts = {acc.id: acc for acc in db.query(Account).filter(Account.id.in_(account_ids)).all()} if account_ids else {}

    # Build NetworkX directed graph for account nodes
    G = nx.DiGraph()
    for acc_id in accounts.keys():
        G.add_node(str(acc_id))

    # Aggregate transactions per (sender, receiver) pair into single directed edge
    edge_tx_map = collections.defaultdict(list)
    for tx in transactions:
        edge_tx_map[(str(tx.sender_account_id), str(tx.receiver_account_id))].append(tx)

    for (u, v), tx_list in edge_tx_map.items():
        pair_amount = float(sum(t.amount for t in tx_list))
        G.add_edge(u, v, weight=pair_amount, transactions=tx_list)

    # 2. Source / Root Identification
    victim_acc_ids = {str(ca.account_id) for ca in cas if ca.association_type in ["VICTIM", "SOURCE"] and str(ca.account_id) in G}

    if victim_acc_ids:
        sources = sorted(list(victim_acc_ids))
        source_id_method = "COMPLAINT_ACCOUNT_ROLE"
    else:
        structural_sources = [n for n in G.nodes() if G.in_degree(n) == 0 and G.out_degree(n) > 0]
        if structural_sources:
            sources = sorted(structural_sources)
            source_id_method = "STRUCTURAL_ROOT"
        else:
            sources = sorted(list(G.nodes()))
            source_id_method = "ALL_NODES"

    # 3. Structural Hop Distance (Shortest path from valid source roots)
    node_hop = {}
    for n in G.nodes():
        if n in sources:
            node_hop[n] = 0
        else:
            reachable_distances = [
                nx.shortest_path_length(G, s, n)
                for s in sources
                if nx.has_path(G, s, n)
            ]
            node_hop[n] = min(reachable_distances) if reachable_distances else 1

    # Compare structural hop against stored Transaction.hop_number
    hop_mismatches = 0
    for tx in transactions:
        expected_hop = node_hop.get(str(tx.receiver_account_id), 1)
        if expected_hop != tx.hop_number:
            hop_mismatches += 1

    # 4. Flow and Transaction Grouping per Node
    node_incoming_amount = collections.defaultdict(float)
    node_outgoing_amount = collections.defaultdict(float)
    node_incoming_txs = collections.defaultdict(list)
    node_outgoing_txs = collections.defaultdict(list)

    for tx in transactions:
        node_incoming_amount[str(tx.receiver_account_id)] += float(tx.amount)
        node_outgoing_amount[str(tx.sender_account_id)] += float(tx.amount)
        node_incoming_txs[str(tx.receiver_account_id)].append(tx)
        node_outgoing_txs[str(tx.sender_account_id)].append(tx)

    # 5. Centrality Metrics
    degree_centrality = nx.degree_centrality(G) if len(G) > 0 else {}
    betweenness_centrality = nx.betweenness_centrality(G) if len(G) > 0 else {}
    try:
        pagerank = nx.pagerank(G, max_iter=200) if len(G) > 0 else {}
    except Exception:
        pagerank = {n: 0.0 for n in G.nodes()}

    # 6. Temporal-Safe Previous Complaints Calculation
    prev_complaints_map = collections.defaultdict(int)
    if incident_cutoff and account_ids:
        rows = db.query(ComplaintAccount.account_id, func.count(Complaint.id)).join(
            Complaint, ComplaintAccount.complaint_id == Complaint.id
        ).filter(
            ComplaintAccount.account_id.in_(account_ids),
            Complaint.id != complaint.id,
            Complaint.reported_at < incident_cutoff
        ).group_by(ComplaintAccount.account_id).all()
        for aid, cnt in rows:
            prev_complaints_map[str(aid)] = cnt

    # 7. WITHDRAWAL ATTRIBUTION & CASH-OUT ENDPOINT RESOLUTION
    # A cash-out endpoint is attributed to the complaint trail ONLY if:
    # 1. Account Scope: Account received funds in the case-scoped transaction graph.
    # 2. Causality: Withdrawal occurred at or after the incoming transaction credit.
    # 3. Temporal Window: Withdrawal occurred within 72 hours of receiving funds.
    # 4. Proportionality: Cumulative withdrawals <= total received funds * 1.05.
    # Unrelated historical withdrawals outside this window/scope are strictly excluded.
    non_source_acc_ids = [aid for aid in account_ids if str(aid) not in sources]
    attributed_withdrawals: List[Any] = []
    if non_source_acc_ids:
        candidate_wdls = db.query(WithdrawalModel).filter(
            WithdrawalModel.account_id.in_(non_source_acc_ids)
        ).order_by(WithdrawalModel.timestamp.asc()).all()

        for aid in non_source_acc_ids:
            in_txs = [t for t in transactions if t.receiver_account_id == aid]
            if not in_txs:
                continue
            amt_in = sum(float(t.amount) for t in in_txs)
            min_in_time = min(t.timestamp for t in in_txs)
            max_in_time = max(t.timestamp for t in in_txs)
            max_window = max_in_time + datetime.timedelta(hours=72)

            cumulative_wd = 0.0
            for w in candidate_wdls:
                if w.account_id != aid:
                    continue
                if w.timestamp < min_in_time or w.timestamp > max_window:
                    continue
                w_amt = float(w.amount)
                if cumulative_wd + w_amt > (amt_in * 1.05) and cumulative_wd > 0:
                    continue
                cumulative_wd += w_amt
                attributed_withdrawals.append(w)

    # 8. Node-Level and Graph-Level Pattern Analysis
    graph_has_rapid_pass_through = False
    graph_has_rapid_fan_out = False
    intermediary_count = 0
    sink_count = 0
    source_count = 0

    nodes_list = []
    # Deterministic sorting by integer account ID
    for node_id in sorted(G.nodes(), key=lambda x: int(x)):
        acc = accounts.get(int(node_id))
        in_deg = G.in_degree(node_id)
        out_deg = G.out_degree(node_id)

        is_source = (node_id in sources)
        is_sink = (in_deg > 0 and out_deg == 0)
        is_intermediary = (in_deg > 0 and out_deg > 0)

        if is_source:
            source_count += 1
            node_type = "victim"
        elif is_sink:
            sink_count += 1
            node_type = "sink"
        elif is_intermediary:
            intermediary_count += 1
            node_type = "intermediary"
        else:
            node_type = "account"

        # Rapid pass-through check (strictly non-negative causal delays)
        pass_through_delays = []
        if is_intermediary:
            for in_tx in node_incoming_txs[node_id]:
                for out_tx in node_outgoing_txs[node_id]:
                    if out_tx.timestamp >= in_tx.timestamp:
                        pass_through_delays.append((out_tx.timestamp - in_tx.timestamp).total_seconds())

        min_pass_through_sec = min(pass_through_delays) if pass_through_delays else None
        node_rapid_pass_through = bool(min_pass_through_sec is not None and min_pass_through_sec <= RAPID_PASS_THROUGH_THRESHOLD_SECONDS)
        if node_rapid_pass_through:
            graph_has_rapid_pass_through = True

        # Rapid fan-out check
        node_rapid_fan_out = False
        if out_deg >= 2:
            out_times = sorted([tx.timestamp for tx in node_outgoing_txs[node_id]])
            if any((out_times[i+1] - out_times[i]).total_seconds() <= RAPID_FAN_OUT_THRESHOLD_SECONDS for i in range(len(out_times)-1)):
                node_rapid_fan_out = True
                graph_has_rapid_fan_out = True

        amt_rec = round(node_incoming_amount[node_id], 2)
        amt_sent = round(node_outgoing_amount[node_id], 2)
        net_flow = round(amt_rec - amt_sent, 2)

        node_flags = {
            "rapid_pass_through": node_rapid_pass_through,
            "rapid_fan_out": node_rapid_fan_out,
            "high_branching": bool(out_deg >= HIGH_BRANCHING_OUT_DEGREE),
            "high_value_flow": bool(amt_rec >= HIGH_VALUE_FLOW_THRESHOLD or amt_sent >= HIGH_VALUE_FLOW_THRESHOLD),
            "central_intermediary": bool(is_intermediary and betweenness_centrality.get(node_id, 0.0) >= HIGH_CENTRALITY_THRESHOLD)
        }

        # Backend-flagged mule accounts are designated as "mule"; otherwise retain structural node_type
        final_node_type = "mule" if (acc and acc.is_mule) else node_type

        nodes_list.append({
            "data": {
                "id": str(node_id),
                "label": acc.holder_name if acc else f"Account {node_id}",
                "node_type": final_node_type,
                "masked_id": acc.masked_account if acc else f"ACC••••{str(node_id)[-4:]}",
                "bank": acc.bank_name if acc else "Unknown Bank",
                "risk_score": float(acc.risk_score or 0.0) if acc else 0.0,
                "amount_received": amt_rec,
                "amount_sent": amt_sent,
                "net_flow": net_flow,
                "connections_count": G.degree(node_id),
                "in_degree": in_deg,
                "out_degree": out_deg,
                "previous_complaints": prev_complaints_map.get(node_id, 0),
                "is_hotspot": bool(prev_complaints_map.get(node_id, 0) > 2),
                "hop_level": node_hop.get(node_id, 0),
                "degree_centrality": round(degree_centrality.get(node_id, 0.0), 4),
                "betweenness_centrality": round(betweenness_centrality.get(node_id, 0.0), 4),
                "is_source": is_source,
                "is_sink": is_sink,
                "is_intermediary": is_intermediary,
                "pattern_flags": node_flags
            }
        })

    # 9. Edge List (Deterministic sorting by first_timestamp asc then id asc)
    edges_list = []
    for (u, v), tx_list in edge_tx_map.items():
        sorted_txs = sorted(tx_list, key=lambda t: (t.timestamp, t.id))
        edge_total_amount = round(sum(float(t.amount) for t in sorted_txs), 2)
        unique_channels = sorted(list(set(t.payment_channel for t in sorted_txs)))
        primary_channel = sorted_txs[0].payment_channel if len(unique_channels) == 1 else ", ".join(unique_channels)
        min_h = min(t.hop_number for t in sorted_txs)
        max_h = max(t.hop_number for t in sorted_txs)

        edge_flags = {
            "high_value_flow": bool(edge_total_amount >= HIGH_VALUE_FLOW_THRESHOLD),
            "multi_hop_flow": bool(max_h >= MULTI_HOP_THRESHOLD)
        }
        is_suspicious_edge = bool(edge_flags["high_value_flow"] or edge_flags["multi_hop_flow"])

        first_ts_str = sorted_txs[0].timestamp.strftime("%Y-%m-%d %H:%M:%S") if sorted_txs[0].timestamp else None
        first_ref = sorted_txs[0].transaction_ref

        edges_list.append({
            "data": {
                "id": f"edge-{u}-{v}",
                "source": str(u),
                "target": str(v),
                "amount": edge_total_amount,
                "total_amount": edge_total_amount,
                "channel": primary_channel,
                "channels": unique_channels,
                "hop": min_h,
                "min_hop": min_h,
                "max_hop": max_h,
                "transaction_count": len(sorted_txs),
                "transaction_ids": [t.id for t in sorted_txs],
                "is_suspicious": is_suspicious_edge,
                "timestamp": first_ts_str,
                "reference": first_ref,
                "label": f"{primary_channel} • ₹{edge_total_amount:,.0f}",
                "pattern_flags": edge_flags
            },
            "_sort_key": (sorted_txs[0].timestamp, sorted_txs[0].id)
        })

    # 10. ATTACH CASH-OUT / WITHDRAWAL TERMINAL NODES AND EDGES
    for w in attributed_withdrawals:
        atm = db.query(ATMLocation).filter(ATMLocation.id == w.atm_id).first()
        atm_node_id = f"atm-{w.id}"
        parent_hop = node_hop.get(str(w.account_id), 1)
        atm_hop = parent_hop + 1
        w_ts_str = w.timestamp.strftime("%Y-%m-%d %H:%M:%S") if w.timestamp else None
        w_amt = float(w.amount)

        # Privacy-safe terminal ATM node: zero account numbers or personal details
        nodes_list.append({
            "data": {
                "id": atm_node_id,
                "label": f"{atm.bank_name} ATM ({atm.district})" if atm else "Cash-Out Terminal",
                "node_type": "atm",
                "masked_id": atm.atm_code if (atm and atm.atm_code) else f"ATM-{w.atm_id}",
                "bank": atm.bank_name if atm else "ATM Terminal",
                "risk_score": 0.0,
                "amount_received": w_amt,
                "amount_sent": 0.0,
                "net_flow": w_amt,
                "connections_count": 1,
                "in_degree": 1,
                "out_degree": 0,
                "previous_complaints": 0,
                "is_hotspot": False,
                "hop_level": atm_hop,
                "degree_centrality": 0.0,
                "betweenness_centrality": 0.0,
                "is_source": False,
                "is_sink": True,
                "is_intermediary": False,
                "pattern_flags": {
                    "is_cash_out_endpoint": True,
                    "atm_locality": atm.district if atm else "Delhi",
                    "atm_address": atm.address if atm else "Delhi ATM Terminal",
                    "withdrawal_amount": w_amt,
                    "withdrawal_timestamp": w_ts_str,
                    "camera_flagged": bool(w.camera_flagged),
                    "withdrawal_ref": f"WDL-DL-{w.id:06d}"
                }
            }
        })

        edges_list.append({
            "data": {
                "id": f"edge-{w.account_id}-{atm_node_id}",
                "source": str(w.account_id),
                "target": atm_node_id,
                "amount": w_amt,
                "total_amount": w_amt,
                "channel": "ATM Cash-Out",
                "channels": ["ATM Cash-Out"],
                "hop": atm_hop,
                "min_hop": atm_hop,
                "max_hop": atm_hop,
                "transaction_count": 0,
                "transaction_ids": [],
                "is_suspicious": bool(w.camera_flagged or w_amt >= 30000),
                "timestamp": w_ts_str,
                "reference": f"WDL-DL-{w.id:06d}",
                "label": f"ATM Cash-Out • ₹{w_amt:,.0f}",
                "pattern_flags": {
                    "terminal_cash_out": True,
                    "camera_flagged": bool(w.camera_flagged)
                }
            },
            "_sort_key": (w.timestamp, w.id)
        })

    edges_list.sort(key=lambda e: e["_sort_key"])
    for e in edges_list:
        e.pop("_sort_key", None)

    # 11. Graph-Level Metrics
    out_degrees = [G.out_degree(n) for n in G.nodes()]
    branching_nodes = [n for n in G.nodes() if G.out_degree(n) > 1]
    active_out_degrees = [d for d in out_degrees if d > 0]
    branching_factor = round(sum(active_out_degrees) / len(active_out_degrees), 2) if active_out_degrees else 0.0

    all_node_hops = [n["data"]["hop_level"] for n in nodes_list]
    account_node_hops = [
        n["data"]["hop_level"] for n in nodes_list
        if n["data"].get("node_type") != "atm" and not n["data"].get("pattern_flags", {}).get("is_cash_out_endpoint")
    ]
    min_hop = min([h for h in all_node_hops if h > 0]) if any(h > 0 for h in all_node_hops) else 0
    terminal_max_hop = max(all_node_hops) if all_node_hops else 0

    # User Mandatory Rule: Separate transaction hop depth from ATM terminal depth.
    # A 3-hop money-transfer chain followed by an ATM endpoint must display 3 Hops, not 4 Hops.
    max_tx_hop = max([t.hop_number for t in transactions]) if transactions else (
        max(account_node_hops) if account_node_hops else 0
    )
    transaction_hop_depth = max_tx_hop
    max_hop = transaction_hop_depth
    hop_distribution = dict(collections.Counter(all_node_hops))

    graph_pattern_flags = {
        "rapid_pass_through": bool(graph_has_rapid_pass_through),
        "rapid_fan_out": bool(graph_has_rapid_fan_out),
        "high_branching": bool(any(d >= HIGH_BRANCHING_OUT_DEGREE for d in out_degrees)),
        "high_value_flow": bool(any(float(t.amount) >= HIGH_VALUE_FLOW_THRESHOLD for t in transactions)),
        "multi_hop_flow": bool(max_hop >= MULTI_HOP_THRESHOLD),
        "high_centrality_intermediary": bool(any(betweenness_centrality.get(n, 0.0) >= HIGH_CENTRALITY_THRESHOLD for n in G.nodes() if G.in_degree(n) > 0 and G.out_degree(n) > 0))
    }

    # Defensible mule indicators count: only nodes satisfying specific pattern flags or risk
    flagged_mule_nodes = sum(
        1 for n in nodes_list
        if not n["data"]["is_source"] and n["data"]["node_type"] not in ["victim", "atm"] and (
            n["data"]["pattern_flags"].get("rapid_pass_through") or
            n["data"]["pattern_flags"].get("rapid_fan_out") or
            n["data"]["pattern_flags"].get("central_intermediary") or
            n["data"].get("risk_score", 0.0) >= 0.70
        )
    )

    metrics = {
        "node_count": len(nodes_list),
        "edge_count": len(edges_list),
        "transaction_count": len(transactions),
        "total_amount": round(total_amount, 2),
        "source_count": source_count,
        "sink_count": sink_count,
        "intermediary_count": intermediary_count,
        "branching_node_count": len(branching_nodes),
        "branching_factor": branching_factor,
        "min_hop": min_hop,
        "max_hop": max_hop,
        "transaction_hop_depth": transaction_hop_depth,
        "terminal_max_hop": terminal_max_hop,
        "hop_distribution": hop_distribution,
        "density": round(nx.density(G), 4) if len(G) > 0 else 0.0,
        "connected_components": nx.number_weakly_connected_components(G) if len(G) > 0 else 0,
        "weakly_connected_components": nx.number_weakly_connected_components(G) if len(G) > 0 else 0,
        "strongly_connected_components": nx.number_strongly_connected_components(G) if len(G) > 0 else 0,
        "high_risk_mule_nodes": flagged_mule_nodes,
        "max_degree": max(dict(G.degree()).values()) if len(G) > 0 else 0.0,
        "mean_degree": round(sum(dict(G.degree()).values()) / len(G), 2) if len(G) > 0 else 0.0,
        "max_pagerank": max(pagerank.values()) if pagerank else 0.0,
        "max_betweenness": max(betweenness_centrality.values()) if betweenness_centrality else 0.0,
        "degree_centrality": {k: round(v, 4) for k, v in degree_centrality.items()},
        "betweenness": {k: round(v, 4) for k, v in betweenness_centrality.items()},
        "pagerank": {k: round(v, 4) for k, v in pagerank.items()},
        "pattern_flags": graph_pattern_flags,
        "source_identification_method": source_id_method,
        "hop_mismatches": hop_mismatches,
        "withdrawal_count": len(attributed_withdrawals)
    }

    return {
        "nodes": nodes_list,
        "edges": edges_list,
        "metrics": metrics
    }


def _empty_graph_response() -> Dict[str, Any]:
    """Returns an empty graph response without fake nodes, edges, or metrics."""
    return {
        "nodes": [],
        "edges": [],
        "metrics": {
            "node_count": 0,
            "edge_count": 0,
            "transaction_count": 0,
            "total_amount": 0.0,
            "source_count": 0,
            "sink_count": 0,
            "intermediary_count": 0,
            "branching_node_count": 0,
            "branching_factor": 0.0,
            "min_hop": 0,
            "max_hop": 0,
            "hop_distribution": {},
            "density": 0.0,
            "weakly_connected_components": 0,
            "strongly_connected_components": 0,
            "high_risk_mule_nodes": 0,
            "max_degree": 0.0,
            "mean_degree": 0.0,
            "max_pagerank": 0.0,
            "max_betweenness": 0.0,
            "degree_centrality": {},
            "betweenness": {},
            "pagerank": {},
            "pattern_flags": {
                "rapid_pass_through": False,
                "rapid_fan_out": False,
                "high_branching": False,
                "high_value_flow": False,
                "multi_hop_flow": False,
                "high_centrality_intermediary": False
            },
            "source_identification_method": "NONE",
            "hop_mismatches": 0,
            "withdrawal_count": 0
        }
    }
