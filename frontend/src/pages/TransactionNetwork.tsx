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
  ExternalLink,
  MapPin,
  Camera,
  CheckCircle2
} from 'lucide-react';
import { api } from '../services/api';
import { GraphData, CytoscapeNodeData } from '../types';
import { CytoscapeNetwork, formatSafeDisplayLabel } from '../graphs/CytoscapeNetwork';

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
        // Default select first available beneficiary / account under review or high-risk node
        const preferredNode =
          data.nodes.find(n => n.data.masked_id === 'ACC••••8129') ||
          data.nodes.find(n => !n.data.is_source && n.data.node_type !== 'victim' && n.data.node_type !== 'atm') ||
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

  // Defensible counts strictly computed from DB-backed graph
  const flaggedPatternCount = graphData
    ? graphData.nodes.filter(n =>
        !n.data.is_source &&
        n.data.node_type !== 'victim' &&
        n.data.node_type !== 'atm' && (
          n.data.node_type === 'mule' ||
          n.data.pattern_flags?.rapid_pass_through ||
          n.data.pattern_flags?.rapid_fan_out ||
          n.data.pattern_flags?.central_intermediary ||
          (n.data.risk_score || 0) >= 0.7
        )
      ).length
    : 0;

  const accountsUnderReviewCount = graphData
    ? graphData.nodes.filter(n =>
        !n.data.is_source &&
        n.data.node_type !== 'victim' &&
        n.data.node_type !== 'atm'
      ).length
    : 0;

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

        {/* Graph Quick Metrics — 100% DB-derived */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs">
          <div className="px-3 py-1.5 rounded-md bg-[#F6F8FC] border border-[#DCE5F0]">
            <span className="text-slate-500 block text-[10px] uppercase font-semibold">TOTAL NODES</span>
            <span className="text-blue-700 font-bold">{graphData.metrics.node_count} Entities</span>
          </div>
          <div className="px-3 py-1.5 rounded-md bg-[#F6F8FC] border border-[#DCE5F0]">
            <span className="text-slate-500 block text-[10px] uppercase font-semibold">HOP DEPTH</span>
            <span className="text-amber-700 font-bold">
              {graphData.metrics.max_hop} {graphData.metrics.max_hop === 1 ? 'Hop' : 'Hops'}
            </span>
          </div>
          <div className="px-3 py-1.5 rounded-md bg-[#F6F8FC] border border-[#DCE5F0]">
            <span className="text-slate-500 block text-[10px] uppercase font-semibold">POTENTIAL MULE INDICATORS</span>
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-800 font-bold">{flaggedPatternCount} Flagged Patterns</span>
              {accountsUnderReviewCount > 0 && (
                <span className="text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded text-[10px] font-semibold">
                  {accountsUnderReviewCount} Under Review
                </span>
              )}
            </div>
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

        {/* Node Details Side Panel */}
        {selectedNode && (() => {
          const isATM = selectedNode.node_type === 'atm';

          if (isATM) {
            // Privacy-Safe ATM Cash-Out Endpoint Details
            const atmLocality = selectedNode.pattern_flags?.atm_locality || selectedNode.bank;
            const atmAddress = selectedNode.pattern_flags?.atm_address || 'Delhi Region';
            const wdlTime = selectedNode.pattern_flags?.withdrawal_timestamp || 'Recent';
            const cameraFlagged = Boolean(selectedNode.pattern_flags?.camera_flagged);
            const wdlRef = selectedNode.pattern_flags?.withdrawal_ref || `ATM-${selectedNode.id}`;

            return (
              <div className="lg:col-span-4 bg-white rounded-lg border border-[#DCE5F0] p-5 shadow-xs space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#DCE5F0]">
                  <div className="flex items-center space-x-2 min-w-0">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-emerald-500"></span>
                    <h3 className="text-sm font-bold text-[#173A63] truncate" title={selectedNode.label}>
                      {selectedNode.label}
                    </h3>
                  </div>
                  <button
                    onClick={() => setSelectedNode(null)}
                    className="text-slate-400 hover:text-slate-600 p-1 rounded transition-colors shrink-0"
                    title="Close Side Panel"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* ATM Terminal Stats */}
                <div className="space-y-2.5 text-xs">
                  <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                    <span className="text-slate-500 shrink-0">Terminal Type:</span>
                    <span className="text-emerald-700 font-semibold text-right">
                      ATM Cash-Out Endpoint
                    </span>
                  </div>

                  <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                    <span className="text-slate-500 shrink-0">ATM Terminal ID:</span>
                    <span className="text-blue-700 font-semibold font-mono">{selectedNode.masked_id}</span>
                  </div>

                  <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                    <span className="text-slate-500 shrink-0">Bank Operator:</span>
                    <span className="text-slate-800 font-medium text-right truncate" title={selectedNode.bank}>
                      {selectedNode.bank}
                    </span>
                  </div>

                  <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                    <span className="text-slate-500 shrink-0">Locality / Cluster:</span>
                    <span className="text-slate-800 font-medium text-right">
                      {atmLocality}
                    </span>
                  </div>

                  <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                    <span className="text-slate-500 shrink-0">Address:</span>
                    <span className="text-slate-700 text-[11px] text-right truncate max-w-[200px]" title={atmAddress}>
                      {atmAddress}
                    </span>
                  </div>

                  <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                    <span className="text-slate-500">Withdrawal Amount:</span>
                    <span className="text-emerald-700 font-bold font-mono text-sm">
                      ₹{selectedNode.amount_received.toLocaleString('en-IN')}
                    </span>
                  </div>

                  <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                    <span className="text-slate-500">Timestamp:</span>
                    <span className="text-slate-800 font-mono text-[11px]">
                      {wdlTime}
                    </span>
                  </div>

                  <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                    <span className="text-slate-500">CCTV Telemetry:</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        cameraFlagged
                          ? 'bg-red-50 text-red-700 border border-red-200'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}
                    >
                      {cameraFlagged ? 'FLAGGED BY CCTV AUDIT' : 'STANDARD RECORD'}
                    </span>
                  </div>

                  {/* Privacy-Safe Notice */}
                  <p className="text-[10px] text-slate-500 leading-tight px-1">
                    Privacy-safe terminal endpoint. Physical cash withdrawal telemetry rendered without exposing personal account information.
                  </p>
                </div>

                {/* Quick Actions for ATM Terminal */}
                <div className="pt-3 border-t border-[#DCE5F0] flex flex-col space-y-2">
                  <button
                    onClick={() => navigate('/map')}
                    className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 shadow-xs"
                  >
                    <MapPin className="w-3.5 h-3.5" />
                    <span>VIEW ATM LOCALITY ON RISK MAP</span>
                  </button>
                  <button
                    onClick={() => navigate(`/cases/${activeId}`)}
                    className="w-full py-2 bg-white hover:bg-blue-50 border border-[#DCE5F0] text-blue-700 rounded-md text-xs font-semibold transition-colors shadow-xs"
                  >
                    RETURN TO CASE INTELLIGENCE
                  </button>
                </div>
              </div>
            );
          }

          // Normal Bank Account Node Details
          const safeName = formatSafeDisplayLabel(selectedNode.label, selectedNode.node_type, selectedNode.is_source);
          const rawRiskPercent = Math.round(selectedNode.risk_score * 100);
          const riskBand = (selectedNode as any).risk_band ||
            (selectedNode.risk_score >= 0.7 ? 'HIGH' : selectedNode.risk_score >= 0.3 ? 'MODERATE' : 'LOW');
          const isVictim = selectedNode.is_source || selectedNode.node_type === 'victim';
          const isIntermediary = selectedNode.is_intermediary || selectedNode.node_type === 'intermediary';
          const accountRole = isVictim
            ? 'Victim / Reporting Account'
            : isIntermediary
            ? 'Intermediary / Under Review'
            : 'Beneficiary / Under Review';

          return (
            <div className="lg:col-span-4 bg-white rounded-lg border border-[#DCE5F0] p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#DCE5F0]">
                <div className="flex items-center space-x-2 min-w-0">
                  <span
                    className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                      riskBand === 'HIGH'
                        ? 'bg-red-600'
                        : riskBand === 'MODERATE'
                        ? 'bg-amber-500'
                        : 'bg-emerald-500'
                    }`}
                  ></span>
                  <h3 className="text-sm font-bold text-[#173A63] truncate" title={safeName}>
                    {safeName}
                  </h3>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="text-slate-400 hover:text-slate-600 p-1 rounded transition-colors shrink-0"
                  title="Close Side Panel"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Entity Stats */}
              <div className="space-y-2.5 text-xs">
                <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                  <span className="text-slate-500 shrink-0">Account / Entity:</span>
                  <span className="text-[#173A63] font-semibold text-right truncate font-sans" title={safeName}>
                    {safeName}
                  </span>
                </div>

                <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                  <span className="text-slate-500 shrink-0">Masked Account ID:</span>
                  <span className="text-blue-700 font-semibold font-mono">{selectedNode.masked_id}</span>
                </div>

                <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                  <span className="text-slate-500 shrink-0">Bank & Branch:</span>
                  <span className="text-slate-800 font-medium text-right truncate" title={selectedNode.bank}>
                    {selectedNode.bank}
                  </span>
                </div>

                <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                  <span className="text-slate-500 shrink-0">Account Role:</span>
                  <span className="text-slate-800 font-medium text-right">
                    {accountRole}
                  </span>
                </div>

                <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                  <span className="text-slate-500">Graph Risk Score:</span>
                  <span className="text-slate-900 font-bold font-mono">
                    {rawRiskPercent} / 100
                  </span>
                </div>

                <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                  <span className="text-slate-500">Risk Band:</span>
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                      riskBand === 'HIGH'
                        ? 'bg-red-50 text-red-700 border border-red-200'
                        : riskBand === 'MODERATE'
                        ? 'bg-amber-50 text-amber-700 border border-amber-200'
                        : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    }`}
                  >
                    {riskBand}
                  </span>
                </div>

                <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                  <span className="text-slate-500">Hop Level:</span>
                  <span className="text-blue-700 font-semibold font-mono">
                    {selectedNode.hop_level === 0 ? 'Root (0)' : `Layer ${selectedNode.hop_level}`}
                  </span>
                </div>

                <p className="text-[10px] text-slate-500 leading-tight px-1">
                  Relative network risk indicator used for operational prioritization; not a probability of guilt or criminal involvement.
                </p>

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
                  <span className="text-slate-500">Graph Connections:</span>
                  <span className="text-blue-700 font-semibold">{selectedNode.connections_count} edges</span>
                </div>

                <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                  <span className="text-slate-500">Previous Complaint Links:</span>
                  <span className="text-slate-800 font-semibold">
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
                  <span>RECOMMEND RAPID LIEN / FREEZE REVIEW</span>
                </button>
                <button
                  onClick={() => navigate(`/cases/${activeId}`)}
                  className="w-full py-2 bg-white hover:bg-blue-50 border border-[#DCE5F0] text-blue-700 rounded-md text-xs font-semibold transition-colors shadow-xs"
                >
                  RETURN TO CASE INTELLIGENCE
                </button>

                {/* Human-in-the-loop disclaimer per Section 5 */}
                <p className="text-[10px] text-slate-500 text-center leading-normal pt-1">
                  CyberShield AI provides decision support only. Any lien, freeze, investigation, or enforcement action requires authorized human review.
                </p>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
};
