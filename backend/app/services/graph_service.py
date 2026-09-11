"""
CyberShield AI — Dynamic NetworkX Transaction Graph Service
Phase 1 Step 7: Fully Dynamic NetworkX Transaction Graph

Computes data-driven topological, flow, branching, centrality, and pattern metrics
directly from the Step-6 Transaction Context Resolver without hardcoded values,
without database writes, and with zero target-label leakage.

Thresholds:
- Centralized prototype-configurable analytical heuristic thresholds (NOT learned/guilt-determining).
"""

import collections
import statistics
from typing import Dict, Any, List, Optional
import networkx as nx
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.app.models.models import Complaint, Transaction, Account, ComplaintAccount
from backend.app.services.transaction_context_service import resolve_transaction_context

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


def build_complaint_graph(db: Session, complaint_id: int) -> Dict[str, Any]:
    """
    Builds a fully data-driven NetworkX directed transaction graph from Step-6 context.

    Returns Cytoscape-compatible structure:
        - nodes: List[CytoscapeNode]
        - edges: List[CytoscapeEdge]
        - metrics: Dict[str, Any]
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        return _empty_graph_response()

    context = resolve_transaction_context(db, complaint)
    transactions: List[Transaction] = context["transactions"]

    if not transactions:
        return _empty_graph_response()

    # Total amount = sum of unique constituent transactions in context (no double counting)
    total_amount = float(sum(tx.amount for tx in transactions))

    # Pre-fetch accounts for all senders and receivers
    account_ids = set()
    for tx in transactions:
        account_ids.add(tx.sender_account_id)
        account_ids.add(tx.receiver_account_id)

    accounts = {acc.id: acc for acc in db.query(Account).filter(Account.id.in_(account_ids)).all()} if account_ids else {}

    # Build NetworkX directed graph: one account = one node
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

    # 1. Source / Root Identification
    # First prefer ComplaintAccount role indicating VICTIM or SOURCE
    cas = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == complaint.id).all()
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

    # 2. Structural Hop Distance (Shortest path from all valid source roots)
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

    # 3. Flow and Transaction Grouping per Node
    node_incoming_amount = collections.defaultdict(float)
    node_outgoing_amount = collections.defaultdict(float)
    node_incoming_txs = collections.defaultdict(list)
    node_outgoing_txs = collections.defaultdict(list)

    for tx in transactions:
        node_incoming_amount[str(tx.receiver_account_id)] += float(tx.amount)
        node_outgoing_amount[str(tx.sender_account_id)] += float(tx.amount)
        node_incoming_txs[str(tx.receiver_account_id)].append(tx)
        node_outgoing_txs[str(tx.sender_account_id)].append(tx)

    # 4. Centrality Metrics (Computed genuine NetworkX metrics)
    degree_centrality = nx.degree_centrality(G) if len(G) > 0 else {}
    betweenness_centrality = nx.betweenness_centrality(G) if len(G) > 0 else {}
    try:
        pagerank = nx.pagerank(G, max_iter=200) if len(G) > 0 else {}
    except Exception:
        pagerank = {n: 0.0 for n in G.nodes()}

    # 5. Temporal-Safe Previous Complaints Calculation
    # Strictly count only complaints reported BEFORE current complaint cutoff
    cutoff_time = complaint.reported_at or complaint.incident_time
    prev_complaints_map = collections.defaultdict(int)
    if cutoff_time and account_ids:
        rows = db.query(ComplaintAccount.account_id, func.count(Complaint.id)).join(
            Complaint, ComplaintAccount.complaint_id == Complaint.id
        ).filter(
            ComplaintAccount.account_id.in_(account_ids),
            Complaint.id != complaint.id,
            Complaint.reported_at < cutoff_time
        ).group_by(ComplaintAccount.account_id).all()
        for aid, cnt in rows:
            prev_complaints_map[str(aid)] = cnt

    # 6. Node-Level and Graph-Level Pattern Analysis
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
        median_pass_through_sec = statistics.median(pass_through_delays) if pass_through_delays else None
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

        nodes_list.append({
            "data": {
                "id": str(node_id),
                "label": acc.holder_name if acc else f"Account {node_id}",
                "node_type": node_type,
                "masked_id": acc.masked_account if acc else f"ACC••••{str(node_id)[-4:]}",
                "bank": acc.bank_name if acc else "Unknown Bank",
                # account.risk_score exposed strictly for stored UI display, NOT used for graph intelligence
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

    # 7. Edge List (Deterministic sorting by first_timestamp asc then id asc)
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
                "pattern_flags": edge_flags
            },
            "_sort_key": (sorted_txs[0].timestamp, sorted_txs[0].id)
        })

    edges_list.sort(key=lambda e: e["_sort_key"])
    for e in edges_list:
        e.pop("_sort_key", None)

    # 8. Graph-Level Metrics
    out_degrees = [G.out_degree(n) for n in G.nodes()]
    branching_nodes = [n for n in G.nodes() if G.out_degree(n) > 1]
    active_out_degrees = [d for d in out_degrees if d > 0]
    branching_factor = round(sum(active_out_degrees) / len(active_out_degrees), 2) if active_out_degrees else 0.0

    non_source_hops = [h for n, h in node_hop.items() if n not in sources]
    min_hop = min(non_source_hops) if non_source_hops else (min(node_hop.values()) if node_hop else 0)
    max_hop = max(node_hop.values()) if node_hop else 0
    hop_distribution = dict(collections.Counter(node_hop.values()))

    graph_pattern_flags = {
        "rapid_pass_through": bool(graph_has_rapid_pass_through),
        "rapid_fan_out": bool(graph_has_rapid_fan_out),
        "high_branching": bool(any(d >= HIGH_BRANCHING_OUT_DEGREE for d in out_degrees)),
        "high_value_flow": bool(any(float(t.amount) >= HIGH_VALUE_FLOW_THRESHOLD for t in transactions)),
        "multi_hop_flow": bool(max_hop >= MULTI_HOP_THRESHOLD),
        "high_centrality_intermediary": bool(any(betweenness_centrality.get(n, 0.0) >= HIGH_CENTRALITY_THRESHOLD for n in G.nodes() if G.in_degree(n) > 0 and G.out_degree(n) > 0))
    }

    # Count high-flow intermediary accounts (structural analytical metric, NOT account.risk_score)
    high_flow_intermediary_nodes = sum(
        1 for n in nodes_list
        if n["data"]["is_intermediary"] and (n["data"]["amount_sent"] >= HIGH_VALUE_FLOW_THRESHOLD or n["data"]["betweenness_centrality"] >= HIGH_CENTRALITY_THRESHOLD)
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
        "hop_distribution": hop_distribution,
        "density": round(nx.density(G), 4) if len(G) > 0 else 0.0,
        "connected_components": nx.number_weakly_connected_components(G) if len(G) > 0 else 0,
        "weakly_connected_components": nx.number_weakly_connected_components(G) if len(G) > 0 else 0,
        "strongly_connected_components": nx.number_strongly_connected_components(G) if len(G) > 0 else 0,
        "high_risk_mule_nodes": high_flow_intermediary_nodes,
        "degree_centrality": {k: round(v, 4) for k, v in degree_centrality.items()},
        "betweenness": {k: round(v, 4) for k, v in betweenness_centrality.items()},
        "pagerank": {k: round(v, 4) for k, v in pagerank.items()},
        "pattern_flags": graph_pattern_flags,
        "source_identification_method": source_id_method,
        "hop_mismatches": hop_mismatches
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
            "hop_mismatches": 0
        }
    }
