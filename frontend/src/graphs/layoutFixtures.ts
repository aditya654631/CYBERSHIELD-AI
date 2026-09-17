/**
 * Phase 6 Verification Fixtures
 * 
 * 10 clearly labeled local fixtures covering all graph topology edge cases:
 * 1. Single direct transfer
 * 2. Branched multi-hop flow
 * 3. Merging paths
 * 4. A cycle
 * 5. Disconnected components
 * 6. ATM cash-out endpoint
 * 7. Predicted zone (optional contract-supported zone)
 * 8. Sparse/missing labels
 * 9. Empty graph
 * 10. Moderately large graph (20+ entities)
 */

import type { GraphData } from '../types';

export const FIXTURE_SINGLE_DIRECT: GraphData = {
  nodes: [
    {
      data: {
        id: 'vic-1',
        label: 'Victim Account',
        node_type: 'victim',
        masked_id: 'ACC••••1001',
        bank: 'HDFC Bank',
        risk_score: 0.05,
        amount_received: 0,
        amount_sent: 50000,
        connections_count: 1,
        previous_complaints: 0,
        is_hotspot: false,
        is_source: true,
        hop_level: 0,
      },
    },
    {
      data: {
        id: 'ben-1',
        label: 'Primary Beneficiary',
        node_type: 'mule',
        masked_id: 'ACC••••2001',
        bank: 'State Bank of India',
        risk_score: 0.85,
        amount_received: 50000,
        amount_sent: 0,
        connections_count: 1,
        previous_complaints: 2,
        is_hotspot: false,
        hop_level: 1,
      },
    },
  ],
  edges: [
    {
      data: {
        id: 'e-1',
        source: 'vic-1',
        target: 'ben-1',
        amount: 50000,
        channel: 'IMPS',
        hop: 1,
        is_suspicious: true,
      },
    },
  ],
  metrics: {
    node_count: 2,
    edge_count: 1,
    max_hop: 1,
    branching_factor: 1.0,
    connected_components: 1,
    high_risk_mule_nodes: 1,
    withdrawal_count: 0,
  },
};

export const FIXTURE_BRANCHED_MULTI_HOP: GraphData = {
  nodes: [
    {
      data: {
        id: 'vic-branch',
        label: 'Complainant Primary',
        node_type: 'victim',
        masked_id: 'ACC••••1100',
        bank: 'ICICI Bank',
        risk_score: 0.02,
        amount_received: 0,
        amount_sent: 200000,
        connections_count: 2,
        previous_complaints: 0,
        is_source: true,
        hop_level: 0,
      },
    },
    {
      data: {
        id: 'layer1-a',
        label: 'Intermediary Alpha',
        node_type: 'intermediary',
        masked_id: 'ACC••••2101',
        bank: 'Axis Bank',
        risk_score: 0.55,
        amount_received: 120000,
        amount_sent: 120000,
        connections_count: 3,
        previous_complaints: 1,
        is_intermediary: true,
        hop_level: 1,
      },
    },
    {
      data: {
        id: 'layer1-b',
        label: 'Intermediary Beta',
        node_type: 'intermediary',
        masked_id: 'ACC••••2102',
        bank: 'Kotak Mahindra',
        risk_score: 0.50,
        amount_received: 80000,
        amount_sent: 80000,
        connections_count: 3,
        previous_complaints: 0,
        is_intermediary: true,
        hop_level: 1,
      },
    },
    {
      data: {
        id: 'layer2-m1',
        label: 'Layer 2 Mule 1',
        node_type: 'mule',
        masked_id: 'ACC••••3101',
        bank: 'Yes Bank',
        risk_score: 0.88,
        amount_received: 60000,
        amount_sent: 0,
        connections_count: 1,
        previous_complaints: 3,
        hop_level: 2,
      },
    },
    {
      data: {
        id: 'layer2-m2',
        label: 'Layer 2 Mule 2',
        node_type: 'mule',
        masked_id: 'ACC••••3102',
        bank: 'Punjab National Bank',
        risk_score: 0.79,
        amount_received: 60000,
        amount_sent: 0,
        connections_count: 1,
        previous_complaints: 1,
        hop_level: 2,
      },
    },
    {
      data: {
        id: 'layer2-m3',
        label: 'Layer 2 Mule 3',
        node_type: 'mule',
        masked_id: 'ACC••••3103',
        bank: 'Bank of Baroda',
        risk_score: 0.82,
        amount_received: 40000,
        amount_sent: 0,
        connections_count: 1,
        previous_complaints: 2,
        hop_level: 2,
      },
    },
    {
      data: {
        id: 'layer2-m4',
        label: 'Layer 2 Mule 4',
        node_type: 'mule',
        masked_id: 'ACC••••3104',
        bank: 'Canara Bank',
        risk_score: 0.75,
        amount_received: 40000,
        amount_sent: 0,
        connections_count: 1,
        previous_complaints: 1,
        hop_level: 2,
      },
    },
  ],
  edges: [
    { data: { id: 'e-br-1', source: 'vic-branch', target: 'layer1-a', amount: 120000, channel: 'NEFT', hop: 1, is_suspicious: false } },
    { data: { id: 'e-br-2', source: 'vic-branch', target: 'layer1-b', amount: 80000, channel: 'RTGS', hop: 1, is_suspicious: false } },
    { data: { id: 'e-br-3', source: 'layer1-a', target: 'layer2-m1', amount: 60000, channel: 'IMPS', hop: 2, is_suspicious: true } },
    { data: { id: 'e-br-4', source: 'layer1-a', target: 'layer2-m2', amount: 60000, channel: 'IMPS', hop: 2, is_suspicious: true } },
    { data: { id: 'e-br-5', source: 'layer1-b', target: 'layer2-m3', amount: 40000, channel: 'UPI', hop: 2, is_suspicious: true } },
    { data: { id: 'e-br-6', source: 'layer1-b', target: 'layer2-m4', amount: 40000, channel: 'UPI', hop: 2, is_suspicious: true } },
  ],
  metrics: {
    node_count: 7,
    edge_count: 6,
    max_hop: 2,
    branching_factor: 2.0,
    connected_components: 1,
    high_risk_mule_nodes: 4,
    withdrawal_count: 0,
  },
};

export const FIXTURE_MERGING_PATHS: GraphData = {
  nodes: [
    {
      data: {
        id: 'source-alpha',
        label: 'Source Alpha',
        node_type: 'victim',
        masked_id: 'ACC••••0001',
        bank: 'HDFC Bank',
        risk_score: 0.05,
        amount_received: 0,
        amount_sent: 50000,
        connections_count: 1,
        previous_complaints: 0,
        is_source: true,
        hop_level: 0,
      },
    },
    {
      data: {
        id: 'source-beta',
        label: 'Source Beta',
        node_type: 'account',
        masked_id: 'ACC••••0002',
        bank: 'ICICI Bank',
        risk_score: 0.15,
        amount_received: 0,
        amount_sent: 75000,
        connections_count: 1,
        previous_complaints: 0,
        is_source: true,
        hop_level: 0,
      },
    },
    {
      data: {
        id: 'aggregator-sink',
        label: 'Funnel Collector',
        node_type: 'sink',
        masked_id: 'ACC••••9999',
        bank: 'Axis Bank',
        risk_score: 0.92,
        amount_received: 125000,
        amount_sent: 0,
        connections_count: 2,
        previous_complaints: 4,
        is_sink: true,
        hop_level: 1,
      },
    },
  ],
  edges: [
    { data: { id: 'e-m-1', source: 'source-alpha', target: 'aggregator-sink', amount: 50000, channel: 'UPI', hop: 1, is_suspicious: true } },
    { data: { id: 'e-m-2', source: 'source-beta', target: 'aggregator-sink', amount: 75000, channel: 'IMPS', hop: 1, is_suspicious: true } },
  ],
  metrics: {
    node_count: 3,
    edge_count: 2,
    max_hop: 1,
    branching_factor: 0.5,
    connected_components: 1,
    high_risk_mule_nodes: 1,
    withdrawal_count: 0,
  },
};

export const FIXTURE_CYCLE: GraphData = {
  nodes: [
    {
      data: {
        id: 'cyc-a',
        label: 'Node Alpha',
        node_type: 'victim',
        masked_id: 'ACC••••8001',
        bank: 'SBI',
        risk_score: 0.1,
        amount_received: 10000,
        amount_sent: 10000,
        connections_count: 2,
        previous_complaints: 0,
        is_source: true,
        hop_level: 0,
      },
    },
    {
      data: {
        id: 'cyc-b',
        label: 'Node Bravo',
        node_type: 'account',
        masked_id: 'ACC••••8002',
        bank: 'HDFC',
        risk_score: 0.6,
        amount_received: 10000,
        amount_sent: 10000,
        connections_count: 2,
        previous_complaints: 1,
        hop_level: 1,
      },
    },
    {
      data: {
        id: 'cyc-c',
        label: 'Node Charlie',
        node_type: 'mule',
        masked_id: 'ACC••••8003',
        bank: 'ICICI',
        risk_score: 0.8,
        amount_received: 10000,
        amount_sent: 10000,
        connections_count: 2,
        previous_complaints: 2,
        hop_level: 2,
      },
    },
  ],
  edges: [
    { data: { id: 'e-cyc-1', source: 'cyc-a', target: 'cyc-b', amount: 10000, channel: 'UPI', hop: 1, is_suspicious: true } },
    { data: { id: 'e-cyc-2', source: 'cyc-b', target: 'cyc-c', amount: 10000, channel: 'IMPS', hop: 2, is_suspicious: true } },
    { data: { id: 'e-cyc-3', source: 'cyc-c', target: 'cyc-a', amount: 10000, channel: 'RTGS', hop: 3, is_suspicious: true } },
  ],
  metrics: {
    node_count: 3,
    edge_count: 3,
    max_hop: 3,
    branching_factor: 1.0,
    connected_components: 1,
    high_risk_mule_nodes: 1,
    withdrawal_count: 0,
  },
};

export const FIXTURE_DISCONNECTED: GraphData = {
  nodes: [
    {
      data: {
        id: 'comp1-src',
        label: 'Component 1 Source',
        node_type: 'victim',
        masked_id: 'ACC••••5001',
        bank: 'Bank A',
        risk_score: 0.05,
        amount_received: 0,
        amount_sent: 30000,
        connections_count: 1,
        previous_complaints: 0,
        is_source: true,
        hop_level: 0,
      },
    },
    {
      data: {
        id: 'comp1-dst',
        label: 'Component 1 Beneficiary',
        node_type: 'account',
        masked_id: 'ACC••••5002',
        bank: 'Bank B',
        risk_score: 0.45,
        amount_received: 30000,
        amount_sent: 0,
        connections_count: 1,
        previous_complaints: 0,
        hop_level: 1,
      },
    },
    {
      data: {
        id: 'comp2-src',
        label: 'Component 2 Source',
        node_type: 'victim',
        masked_id: 'ACC••••6001',
        bank: 'Bank C',
        risk_score: 0.05,
        amount_received: 0,
        amount_sent: 70000,
        connections_count: 1,
        previous_complaints: 0,
        is_source: true,
        hop_level: 0,
      },
    },
    {
      data: {
        id: 'comp2-dst',
        label: 'Component 2 Beneficiary',
        node_type: 'mule',
        masked_id: 'ACC••••6002',
        bank: 'Bank D',
        risk_score: 0.85,
        amount_received: 70000,
        amount_sent: 0,
        connections_count: 1,
        previous_complaints: 1,
        hop_level: 1,
      },
    },
  ],
  edges: [
    { data: { id: 'e-d1', source: 'comp1-src', target: 'comp1-dst', amount: 30000, channel: 'UPI', hop: 1, is_suspicious: false } },
    { data: { id: 'e-d2', source: 'comp2-src', target: 'comp2-dst', amount: 70000, channel: 'IMPS', hop: 1, is_suspicious: true } },
  ],
  metrics: {
    node_count: 4,
    edge_count: 2,
    max_hop: 1,
    branching_factor: 1.0,
    connected_components: 2,
    high_risk_mule_nodes: 1,
    withdrawal_count: 0,
  },
};

export const FIXTURE_ATM_CASHOUT: GraphData = {
  nodes: [
    {
      data: {
        id: 'vic-atm',
        label: 'Reporting Victim',
        node_type: 'victim',
        masked_id: 'ACC••••7001',
        bank: 'HDFC Bank',
        risk_score: 0.05,
        amount_received: 0,
        amount_sent: 45000,
        connections_count: 1,
        previous_complaints: 0,
        is_source: true,
        hop_level: 0,
      },
    },
    {
      data: {
        id: 'mule-atm',
        label: 'Mule Intermediary',
        node_type: 'mule',
        masked_id: 'ACC••••7002',
        bank: 'SBI',
        risk_score: 0.90,
        amount_received: 45000,
        amount_sent: 40000,
        connections_count: 2,
        previous_complaints: 3,
        hop_level: 1,
      },
    },
    {
      data: {
        id: 'atm-term-1',
        label: 'Connaught Place ATM 04',
        node_type: 'atm',
        masked_id: 'ATM••••9912',
        bank: 'SBI ATM Network',
        risk_score: 0.95,
        amount_received: 40000,
        amount_sent: 0,
        connections_count: 1,
        previous_complaints: 1,
        is_sink: true,
        hop_level: 2,
        pattern_flags: {
          atm_locality: 'Connaught Place',
          atm_address: 'Block B, Radial 3, Connaught Place, New Delhi',
          withdrawal_timestamp: '2026-09-15 14:22:10 IST',
          camera_flagged: true,
        },
      },
    },
  ],
  edges: [
    { data: { id: 'e-atm-1', source: 'vic-atm', target: 'mule-atm', amount: 45000, channel: 'IMPS', hop: 1, is_suspicious: true } },
    { data: { id: 'e-atm-2', source: 'mule-atm', target: 'atm-term-1', amount: 40000, channel: 'ATM_WITHDRAWAL', hop: 2, is_suspicious: true } },
  ],
  metrics: {
    node_count: 3,
    edge_count: 2,
    max_hop: 2,
    branching_factor: 1.0,
    connected_components: 1,
    high_risk_mule_nodes: 1,
    withdrawal_count: 1,
  },
};

export const FIXTURE_PREDICTED_ZONE: GraphData = {
  nodes: [
    {
      data: {
        id: 'src-pz',
        label: 'Victim Account',
        node_type: 'victim',
        masked_id: 'ACC••••4001',
        bank: 'Canara Bank',
        risk_score: 0.05,
        amount_received: 0,
        amount_sent: 100000,
        connections_count: 1,
        previous_complaints: 0,
        is_source: true,
        hop_level: 0,
      },
    },
    {
      data: {
        id: 'mule-pz',
        label: 'Rapid Mule Layer',
        node_type: 'mule',
        masked_id: 'ACC••••4002',
        bank: 'Axis Bank',
        risk_score: 0.85,
        amount_received: 100000,
        amount_sent: 80000,
        connections_count: 2,
        previous_complaints: 2,
        hop_level: 1,
      },
    },
    {
      data: {
        id: 'zone-rohire',
        label: 'Predicted Rohini Hotspot Cluster',
        node_type: 'cluster',
        masked_id: 'CLUSTER••••ROHINI',
        bank: 'Predicted Zone',
        risk_score: 0.78,
        amount_received: 80000,
        amount_sent: 0,
        connections_count: 1,
        previous_complaints: 0,
        is_sink: true,
        hop_level: 2,
        pattern_flags: {
          is_predicted_zone: true,
          predicted_locality: 'Rohini Sector 18',
        },
      },
    },
  ],
  edges: [
    { data: { id: 'e-pz-1', source: 'src-pz', target: 'mule-pz', amount: 100000, channel: 'NEFT', hop: 1, is_suspicious: true } },
    { data: { id: 'e-pz-2', source: 'mule-pz', target: 'zone-rohire', amount: 80000, channel: 'GEO_PROJECTION', hop: 2, is_suspicious: true } },
  ],
  metrics: {
    node_count: 3,
    edge_count: 2,
    max_hop: 2,
    branching_factor: 1.0,
    connected_components: 1,
    high_risk_mule_nodes: 1,
    withdrawal_count: 0,
    target_cashout_cluster: 'Rohini Sector 18',
  },
};

export const FIXTURE_SPARSE_LABELS: GraphData = {
  nodes: [
    {
      data: {
        id: 'sp-1',
        label: '', // Empty label
        node_type: 'account',
        masked_id: 'ACC••••0011',
        bank: '', // Empty bank
        risk_score: 0.2,
        amount_received: 0,
        amount_sent: 25000,
        connections_count: 1,
        previous_complaints: 0,
        is_source: true,
        hop_level: 0,
      },
    },
    {
      data: {
        id: 'sp-2',
        label: '   ', // Whitespace-only label
        node_type: 'account',
        masked_id: 'ACC••••0022',
        bank: 'Bank Of India',
        risk_score: 0.6,
        amount_received: 25000,
        amount_sent: 0,
        connections_count: 1,
        previous_complaints: 0,
        hop_level: 1,
      },
    },
  ],
  edges: [
    { data: { id: 'e-sp-1', source: 'sp-1', target: 'sp-2', amount: 25000, channel: 'UPI', hop: 1, is_suspicious: false } },
  ],
  metrics: {
    node_count: 2,
    edge_count: 1,
    max_hop: 1,
    branching_factor: 1.0,
    connected_components: 1,
    high_risk_mule_nodes: 0,
    withdrawal_count: 0,
  },
};

export const FIXTURE_EMPTY_GRAPH: GraphData = {
  nodes: [],
  edges: [],
  metrics: {
    node_count: 0,
    edge_count: 0,
    max_hop: 0,
    branching_factor: 0,
    connected_components: 0,
    high_risk_mule_nodes: 0,
    withdrawal_count: 0,
  },
};

export const FIXTURE_MODERATELY_LARGE: GraphData = (() => {
  const nodes: GraphData['nodes'] = [];
  const edges: GraphData['edges'] = [];

  // Root Victim
  nodes.push({
    data: {
      id: 'large-root',
      label: 'Victim Root',
      node_type: 'victim',
      masked_id: 'ACC••••9000',
      bank: 'HDFC Bank',
      risk_score: 0.05,
      amount_received: 0,
      amount_sent: 500000,
      connections_count: 4,
      previous_complaints: 0,
      is_source: true,
      hop_level: 0,
    },
  });

  // Layer 1: 4 Intermediaries
  for (let i = 1; i <= 4; i++) {
    const id = `large-l1-${i}`;
    nodes.push({
      data: {
        id,
        label: `Intermediary Layer 1-${i}`,
        node_type: 'intermediary',
        masked_id: `ACC••••910${i}`,
        bank: `Bank ${i}`,
        risk_score: 0.4 + i * 0.08,
        amount_received: 125000,
        amount_sent: 125000,
        connections_count: 4,
        previous_complaints: i,
        is_intermediary: true,
        hop_level: 1,
      },
    });
    edges.push({
      data: {
        id: `e-large-r-${i}`,
        source: 'large-root',
        target: id,
        amount: 125000,
        channel: 'NEFT',
        hop: 1,
        is_suspicious: false,
      },
    });
  }

  // Layer 2: 12 Mules (3 per Layer 1 node)
  let muleIndex = 1;
  for (let i = 1; i <= 4; i++) {
    const parentId = `large-l1-${i}`;
    for (let j = 1; j <= 3; j++) {
      const id = `large-l2-${muleIndex}`;
      nodes.push({
        data: {
          id,
          label: `Mule Account L2-${muleIndex}`,
          node_type: 'mule',
          masked_id: `ACC••••92${muleIndex.toString().padStart(2, '0')}`,
          bank: `Mule Bank ${j}`,
          risk_score: 0.75 + (muleIndex % 3) * 0.08,
          amount_received: 41666,
          amount_sent: 35000,
          connections_count: 2,
          previous_complaints: 2,
          hop_level: 2,
        },
      });
      edges.push({
        data: {
          id: `e-large-l1-l2-${muleIndex}`,
          source: parentId,
          target: id,
          amount: 41666,
          channel: 'IMPS',
          hop: 2,
          is_suspicious: true,
        },
      });
      muleIndex++;
    }
  }

  // Layer 3: 4 ATM Cash-Out Terminals (merging some Layer 2 mules)
  for (let k = 1; k <= 4; k++) {
    const id = `large-atm-${k}`;
    nodes.push({
      data: {
        id,
        label: `ATM Terminal ${k}`,
        node_type: 'atm',
        masked_id: `ATM••••880${k}`,
        bank: `ATM Network ${k}`,
        risk_score: 0.95,
        amount_received: 105000,
        amount_sent: 0,
        connections_count: 3,
        previous_complaints: 1,
        is_sink: true,
        hop_level: 3,
        pattern_flags: {
          atm_locality: `District ${k}`,
          withdrawal_timestamp: `2026-09-15 15:0${k}:00 IST`,
        },
      },
    });

    // Connect 3 Layer 2 mules to this ATM
    for (let m = (k - 1) * 3 + 1; m <= k * 3; m++) {
      edges.push({
        data: {
          id: `e-large-l2-atm-${m}`,
          source: `large-l2-${m}`,
          target: id,
          amount: 35000,
          channel: 'ATM_WITHDRAWAL',
          hop: 3,
          is_suspicious: true,
        },
      });
    }
  }

  return {
    nodes,
    edges,
    metrics: {
      node_count: nodes.length, // 1 + 4 + 12 + 4 = 21 nodes
      edge_count: edges.length, // 4 + 12 + 12 = 28 edges
      max_hop: 3,
      branching_factor: 2.5,
      connected_components: 1,
      high_risk_mule_nodes: 12,
      withdrawal_count: 4,
    },
  };
})();

export const ALL_VERIFICATION_FIXTURES: Record<string, GraphData> = {
  'Single Direct Transfer': FIXTURE_SINGLE_DIRECT,
  'Branched Multi-Hop Flow': FIXTURE_BRANCHED_MULTI_HOP,
  'Merging Paths': FIXTURE_MERGING_PATHS,
  'A Cycle': FIXTURE_CYCLE,
  'Disconnected Components': FIXTURE_DISCONNECTED,
  'ATM Cash-Out Endpoint': FIXTURE_ATM_CASHOUT,
  'Predicted Zone (Contract-Supported)': FIXTURE_PREDICTED_ZONE,
  'Sparse / Missing Labels': FIXTURE_SPARSE_LABELS,
  'Empty Graph': FIXTURE_EMPTY_GRAPH,
  'Moderately Large Graph': FIXTURE_MODERATELY_LARGE,
};
