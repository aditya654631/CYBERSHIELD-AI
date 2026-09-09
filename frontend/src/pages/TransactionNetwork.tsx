import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Network as NetworkIcon,
  ShieldAlert,
  ArrowLeft,
  X,
  Building2,
  DollarSign,
  Share2,
  AlertTriangle,
  Layers,
  Sparkles,
  Search,
  ExternalLink
} from 'lucide-react';
import { api } from '../services/api';
import { GraphData, CytoscapeNodeData } from '../types';
import { CytoscapeNetwork } from '../graphs/CytoscapeNetwork';

export const TransactionNetwork: React.FC = () => {
  const { complaintId } = useParams<{ complaintId: string }>();
  const activeId = complaintId || 'CMP-1042';
  const navigate = useNavigate();

  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedNode, setSelectedNode] = useState<CytoscapeNodeData | null>(null);
  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchGraph = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getGraph(activeId);
        setGraphData(data);
        // Default select high-risk mule node or cashier if exists
        const preferredNode =
          data.nodes.find(n => n.data.masked_id === 'ACC••••8129') ||
          data.nodes.find(n => n.data.node_type === 'mule') ||
          data.nodes.find(n => n.data.risk_score >= 0.7) ||
          data.nodes[0];
        if (preferredNode) {
          setSelectedNode(preferredNode.data);
        }
      } catch (err) {
        console.error('Failed to load transaction network graph', err);
        setError('Transaction network graph data unavailable for this complaint.');
      } finally {
        setLoading(false);
      }
    };
    fetchGraph();
  }, [activeId]);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-16 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
        <div className="h-[520px] bg-[#0c1428] rounded-xl border border-[#162544]"></div>
      </div>
    );
  }

  if (error || !graphData) {
    return (
      <div className="p-8 bg-[#0a1020] rounded-2xl border border-[#162544] text-center space-y-4 font-mono">
        <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Network Telemetry Unavailable</h2>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          {error || 'No transaction layering data registered for this complaint.'}
        </p>
        <button
          onClick={() => navigate(`/cases/${activeId}`)}
          className="px-4 py-2 bg-[#0e1933] border border-cyan-500/40 text-cyan-300 rounded-lg text-xs font-bold"
        >
          Return to Case Intelligence
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Network Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl gap-4">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate(`/cases/${activeId}`)}
            className="p-2 rounded-lg bg-[#070c18] border border-[#162544] text-slate-300 hover:text-cyan-400 hover:border-cyan-500/40 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2.5">
              <h1 className="text-lg font-bold text-white font-['JetBrains_Mono',monospace]">
                Financial Transaction & Mule Network Graph
              </h1>
              <span className="text-xs px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono font-bold">
                {activeId}
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              NetworkX Graph Centrality & Directed Flow Layering
            </p>
          </div>
        </div>

        {/* Graph Quick Metrics */}
        <div className="flex items-center space-x-4 text-xs font-mono">
          <div className="px-3 py-1.5 rounded-lg bg-[#070c18] border border-[#162544]">
            <span className="text-slate-400 block text-[10px]">TOTAL NODES</span>
            <span className="text-cyan-300 font-bold">{graphData.metrics.node_count} Entities</span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-[#070c18] border border-[#162544]">
            <span className="text-slate-400 block text-[10px]">HOP DEPTH</span>
            <span className="text-amber-400 font-bold">{graphData.metrics.max_hop} Hops</span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-[#070c18] border border-red-500/30">
            <span className="text-slate-400 block text-[10px]">SUSPECTED MULES</span>
            <span className="text-red-400 font-bold">{graphData.metrics.high_risk_mule_nodes} Identified</span>
          </div>
        </div>
      </div>

      {/* Main Graph Area with Side Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Cytoscape Canvas */}
        <div className={selectedNode ? 'lg:col-span-8' : 'lg:col-span-12'}>
          <CytoscapeNetwork
            graphData={graphData}
            onSelectNode={(node) => setSelectedNode(node)}
            selectedNodeId={selectedNode?.id}
          />
        </div>

        {/* Step 10: Node Details Side Panel */}
        {selectedNode && (
          <div className="lg:col-span-4 bg-[#0a1020] rounded-2xl border border-cyan-500/50 p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#162544]">
              <div className="flex items-center space-x-2">
                <span
                  className={`w-3 h-3 rounded-full ${
                    selectedNode.risk_score > 0.8
                      ? 'bg-red-500 animate-ping'
                      : selectedNode.risk_score > 0.6
                      ? 'bg-amber-500'
                      : 'bg-blue-500'
                  }`}
                ></span>
                <h3 className="text-sm font-bold text-white font-mono">{selectedNode.label}</h3>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-white p-1 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Entity Stats */}
            <div className="space-y-3 text-xs font-mono">
              <div className="p-3 bg-[#070d1a] rounded-lg border border-[#162544] flex items-center justify-between">
                <span className="text-slate-400">Masked Account ID:</span>
                <span className="text-cyan-300 font-bold">{selectedNode.masked_id}</span>
              </div>

              <div className="p-3 bg-[#070d1a] rounded-lg border border-[#162544] flex items-center justify-between">
                <span className="text-slate-400">Bank & Branch:</span>
                <span className="text-slate-200 font-bold">{selectedNode.bank}</span>
              </div>

              <div className="p-3 bg-[#070d1a] rounded-lg border border-[#162544] flex items-center justify-between">
                <span className="text-slate-400">Graph Risk Score:</span>
                <span
                  className={`font-bold ${
                    selectedNode.risk_score > 0.8
                      ? 'text-red-400'
                      : selectedNode.risk_score > 0.6
                      ? 'text-amber-400'
                      : 'text-blue-400'
                  }`}
                >
                  {Math.round(selectedNode.risk_score * 100)}% (
                  {selectedNode.risk_score > 0.8 ? 'CRITICAL' : 'HIGH'})
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div className="p-3 bg-[#070d1a] rounded-lg border border-[#162544]">
                  <span className="text-slate-400 text-[10px] block">RECEIVED AMOUNT</span>
                  <span className="text-emerald-400 font-bold">
                    ₹{selectedNode.amount_received.toLocaleString('en-IN')}
                  </span>
                </div>
                <div className="p-3 bg-[#070d1a] rounded-lg border border-[#162544]">
                  <span className="text-slate-400 text-[10px] block">SENT AMOUNT</span>
                  <span className="text-slate-200 font-bold">
                    ₹{selectedNode.amount_sent.toLocaleString('en-IN')}
                  </span>
                </div>
              </div>

              <div className="p-3 bg-[#070d1a] rounded-lg border border-[#162544] flex items-center justify-between">
                <span className="text-slate-400">Total Graph Connections:</span>
                <span className="text-cyan-400 font-bold">{selectedNode.connections_count} edges</span>
              </div>

              <div className="p-3 bg-[#070d1a] rounded-lg border border-[#162544] flex items-center justify-between">
                <span className="text-slate-400">Previous Complaint Links:</span>
                <span className="text-red-400 font-bold">
                  {selectedNode.previous_complaints} incidents
                </span>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="pt-3 border-t border-[#162544] flex flex-col space-y-2">
              <button
                onClick={() => navigate('/alerts')}
                className="w-full py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-mono font-bold transition-all flex items-center justify-center space-x-1.5"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>ISSUE RAPID ATM LIEN / FREEZE</span>
              </button>
              <button
                onClick={() => navigate('/cases/CMP-1042')}
                className="w-full py-2 bg-[#101a33] hover:bg-[#18284e] border border-cyan-500/40 text-cyan-300 rounded-lg text-xs font-mono font-semibold transition-all"
              >
                RETURN TO CASE INTELLIGENCE
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
