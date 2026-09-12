import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Network as NetworkIcon,
  ShieldAlert,
  ArrowLeft,
  X,
  Building2,
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
  const activeId = complaintId || 'CMP-NEW-000002';
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
        <div className="h-16 bg-white rounded-lg border border-[#DCE5F0]"></div>
        <div className="h-[520px] bg-white rounded-lg border border-[#DCE5F0]"></div>
      </div>
    );
  }

  if (error || !graphData) {
    return (
      <div className="p-8 bg-white rounded-lg border border-red-200 text-center space-y-4 max-w-xl mx-auto shadow-xs">
        <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto" />
        <h2 className="text-lg font-bold text-slate-900">Network Telemetry Unavailable</h2>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          {error || 'No transaction layering data registered for this complaint.'}
        </p>
        <button
          onClick={() => navigate(`/cases/${activeId}`)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-semibold transition-colors shadow-xs"
        >
          Return to Case Intelligence
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Network Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs gap-4">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate(`/cases/${activeId}`)}
            className="p-2 rounded-md bg-white border border-[#DCE5F0] text-slate-600 hover:text-blue-600 hover:bg-blue-50 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2.5">
              <h1 className="text-lg font-bold text-[#173A63] font-sans">
                Financial Transaction & Mule Network Graph
              </h1>
              <span className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold font-mono">
                {activeId}
              </span>
            </div>
            <p className="text-xs text-slate-500 font-sans mt-0.5">
              NetworkX Graph Centrality & Directed Flow Layering
            </p>
          </div>
        </div>

        {/* Graph Quick Metrics */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs">
          <div className="px-3 py-1.5 rounded-md bg-[#F6F8FC] border border-[#DCE5F0]">
            <span className="text-slate-500 block text-[10px] uppercase font-semibold">TOTAL NODES</span>
            <span className="text-blue-700 font-bold">{graphData.metrics.node_count} Entities</span>
          </div>
          <div className="px-3 py-1.5 rounded-md bg-[#F6F8FC] border border-[#DCE5F0]">
            <span className="text-slate-500 block text-[10px] uppercase font-semibold">HOP DEPTH</span>
            <span className="text-amber-700 font-bold">{graphData.metrics.max_hop} Hops</span>
          </div>
          <div className="px-3 py-1.5 rounded-md bg-red-50 border border-red-200">
            <span className="text-red-700 block text-[10px] uppercase font-semibold">SUSPECTED MULES</span>
            <span className="text-red-700 font-bold">{graphData.metrics.high_risk_mule_nodes} Identified</span>
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
          <div className="lg:col-span-4 bg-white rounded-lg border border-[#DCE5F0] p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#DCE5F0]">
              <div className="flex items-center space-x-2">
                <span
                  className={`w-2.5 h-2.5 rounded-full ${
                    selectedNode.risk_score > 0.8
                      ? 'bg-red-600'
                      : selectedNode.risk_score > 0.6
                      ? 'bg-amber-500'
                      : 'bg-blue-500'
                  }`}
                ></span>
                <h3 className="text-sm font-bold text-[#173A63]">{selectedNode.label}</h3>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Entity Stats */}
            <div className="space-y-2.5 text-xs">
              <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                <span className="text-slate-500">Masked Account ID:</span>
                <span className="text-blue-700 font-semibold font-mono">{selectedNode.masked_id}</span>
              </div>

              <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                <span className="text-slate-500">Bank & Branch:</span>
                <span className="text-slate-800 font-medium">{selectedNode.bank}</span>
              </div>

              <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                <span className="text-slate-500">Graph Risk Score:</span>
                <span
                  className={`font-bold ${
                    selectedNode.risk_score > 0.8
                      ? 'text-red-700'
                      : selectedNode.risk_score > 0.6
                      ? 'text-amber-700'
                      : 'text-blue-700'
                  }`}
                >
                  {Math.round(selectedNode.risk_score * 100)}% (
                  {selectedNode.risk_score > 0.8 ? 'CRITICAL' : 'HIGH'})
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0]">
                  <span className="text-slate-500 text-[10px] block uppercase font-medium">RECEIVED AMOUNT</span>
                  <span className="text-emerald-700 font-bold">
                    ₹{selectedNode.amount_received.toLocaleString('en-IN')}
                  </span>
                </div>
                <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0]">
                  <span className="text-slate-500 text-[10px] block uppercase font-medium">SENT AMOUNT</span>
                  <span className="text-slate-800 font-bold">
                    ₹{selectedNode.amount_sent.toLocaleString('en-IN')}
                  </span>
                </div>
              </div>

              <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                <span className="text-slate-500">Total Graph Connections:</span>
                <span className="text-blue-700 font-semibold">{selectedNode.connections_count} edges</span>
              </div>

              <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                <span className="text-slate-500">Previous Complaint Links:</span>
                <span className="text-red-700 font-bold">
                  {selectedNode.previous_complaints} incidents
                </span>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="pt-3 border-t border-[#DCE5F0] flex flex-col space-y-2">
              <button
                onClick={() => navigate('/alerts')}
                className="w-full py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 shadow-xs"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>ISSUE RAPID ATM LIEN / FREEZE</span>
              </button>
              <button
                onClick={() => navigate(`/cases/${activeId}`)}
                className="w-full py-2 bg-white hover:bg-blue-50 border border-[#DCE5F0] text-blue-700 rounded-md text-xs font-semibold transition-colors shadow-xs"
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
