import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Network as NetworkIcon,
  ShieldAlert,
  ArrowLeft,
  X,
  Building2,
  AlertTriangle,
  Info,
  Maximize2,
  Minimize2,
  MapPin,
  CheckCircle2,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Table as TableIcon
} from 'lucide-react';
import { api } from '../services/api';
import { GraphData, CytoscapeNodeData } from '../types';
import { CytoscapeNetwork, formatSafeDisplayLabel } from '../graphs/CytoscapeNetwork';

export const TransactionNetwork: React.FC = () => {
  const { complaintId } = useParams<{ complaintId: string }>();
  const activeId = complaintId || sessionStorage.getItem('cybershield_last_case_id') || 'CMP-NEW-000154';
  const navigate = useNavigate();

  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedNode, setSelectedNode] = useState<CytoscapeNodeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showEntityTable, setShowEntityTable] = useState(false);
  const graphContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchGraph = async () => {
      setLoading(true);
      setError(null);
      setSelectedNode(null); // Clear selection when active case changes
      try {
        const data = await api.getGraph(activeId);
        setGraphData(data);
        // PART B requirement: Open with the graph using available content width.
        // Do NOT auto-select an arbitrary or hardcoded beneficiary on initial load!
      } catch (err) {
        console.error('Failed to load transaction network graph', err);
        setError('Transaction network graph data unavailable for this complaint.');
      } finally {
        setLoading(false);
      }
    };
    fetchGraph();
  }, [activeId]);

  const handleSelectNodeFromTable = (nodeData: CytoscapeNodeData) => {
    setSelectedNode(nodeData);
    if (graphContainerRef.current) {
      graphContainerRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  };

  // Honest Loading State — Preserves Case Identity
  if (loading) {
    return (
      <div className="space-y-4 pb-12" role="status" aria-live="polite">
        <div className="flex items-center justify-between p-4 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <div className="flex items-center space-x-3">
            <button
              onClick={() => navigate(`/cases/${activeId}`)}
              className="p-1.5 rounded-md bg-white border border-[#DCE5F0] text-slate-600 hover:text-blue-600 hover:bg-blue-50 transition-colors"
              aria-label="Back to case overview"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-base font-bold text-[#173A63] font-sans">
                  Financial Transaction & Mule Network Graph
                </h1>
                <span className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold font-mono">
                  {activeId}
                </span>
              </div>
              <p className="text-xs text-slate-500 font-sans mt-0.5">
                Loading banking telemetry and constructing directed layered layout...
              </p>
            </div>
          </div>
        </div>

        <div className="h-[520px] bg-white rounded-lg border border-[#DCE5F0] flex flex-col items-center justify-center p-8 space-y-3">
          <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-xs font-semibold text-slate-700">Loading Network Telemetry for {activeId}</p>
          <p className="text-[11px] text-slate-400">Computing deterministic multi-hop layout...</p>
        </div>
      </div>
    );
  }

  // Honest Error State — Preserves Case Identity
  if (error || !graphData) {
    return (
      <div className="space-y-4 pb-12">
        <div className="flex items-center justify-between p-4 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <div className="flex items-center space-x-3">
            <button
              onClick={() => navigate(`/cases/${activeId}`)}
              className="p-1.5 rounded-md bg-white border border-[#DCE5F0] text-slate-600 hover:text-blue-600 hover:bg-blue-50 transition-colors"
              aria-label="Back to case overview"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-bold text-[#173A63] font-sans">
                Financial Transaction & Mule Network Graph
              </h1>
              <span className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold font-mono">
                {activeId}
              </span>
            </div>
          </div>
        </div>

        <div className="p-8 bg-white rounded-lg border border-red-200 text-center space-y-4 max-w-xl mx-auto shadow-xs">
          <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto" />
          <h2 className="text-lg font-bold text-slate-900">Network Telemetry Unavailable</h2>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            {error || `No transaction layering data registered for complaint ${activeId}.`}
          </p>
          <div className="flex items-center justify-center gap-2.5 pt-2">
            <button
              onClick={() => navigate(`/cases/${activeId}`)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-semibold transition-colors shadow-xs"
            >
              Return to Case Intelligence
            </button>
            <button
              onClick={() => navigate('/complaints')}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-semibold transition-colors"
            >
              Back to Complaints
            </button>
            <button
              onClick={() => navigate('/dashboard')}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-semibold transition-colors"
            >
              Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Honest Empty State — Preserves Case Identity
  if (graphData.nodes.length === 0) {
    return (
      <div className="space-y-4 pb-12">
        <div className="flex items-center justify-between p-4 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <div className="flex items-center space-x-3">
            <button
              onClick={() => navigate(`/cases/${activeId}`)}
              className="p-1.5 rounded-md bg-white border border-[#DCE5F0] text-slate-600 hover:text-blue-600 hover:bg-blue-50 transition-colors"
              aria-label="Back to case overview"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-bold text-[#173A63] font-sans">
                Financial Transaction & Mule Network Graph
              </h1>
              <span className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold font-mono">
                {activeId}
              </span>
            </div>
          </div>
        </div>

        <div className="p-8 bg-white rounded-lg border border-slate-200 text-center space-y-4 max-w-xl mx-auto shadow-xs">
          <NetworkIcon className="w-8 h-8 text-slate-400 mx-auto" />
          <h2 className="text-lg font-bold text-slate-900">No Entities Recorded in Graph</h2>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Case <span className="font-mono font-semibold text-slate-700">{activeId}</span> does not currently have any associated banking accounts or transaction telemetry.
          </p>
          <button
            onClick={() => navigate(`/cases/${activeId}`)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-semibold transition-colors shadow-xs"
          >
            Return to Case Intelligence
          </button>
        </div>
      </div>
    );
  }

  // Defensible counts strictly computed from DB-backed graph
  const flaggedPatternCount = graphData.nodes.filter(n =>
    !n.data.is_source &&
    n.data.node_type !== 'victim' &&
    n.data.node_type !== 'atm' && (
      n.data.node_type === 'mule' ||
      n.data.pattern_flags?.rapid_pass_through ||
      n.data.pattern_flags?.rapid_fan_out ||
      n.data.pattern_flags?.central_intermediary ||
      (n.data.risk_score || 0) >= 0.7
    )
  ).length;

  const accountsUnderReviewCount = graphData.nodes.filter(n =>
    !n.data.is_source &&
    n.data.node_type !== 'victim' &&
    n.data.node_type !== 'atm'
  ).length;

  const isPartialData = graphData.nodes.length > 0 && graphData.edges.length === 0;

  return (
    <div className="space-y-4 pb-12" ref={graphContainerRef}>
      {/* Compact Header: Case identity + essential metrics */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between p-4 bg-white rounded-lg border border-[#DCE5F0] shadow-xs gap-3">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate(`/cases/${activeId}`)}
            className="p-1.5 rounded-md bg-white border border-[#DCE5F0] text-slate-600 hover:text-blue-600 hover:bg-blue-50 transition-colors shrink-0"
            aria-label="Back to case overview"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="min-w-0">
            <div className="flex items-center space-x-2 flex-wrap gap-y-1">
              <h1 className="text-base font-bold text-[#173A63] font-sans truncate">
                Financial Transaction & Mule Network Graph
              </h1>
              <span className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold font-mono">
                {activeId}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-sans mt-0.5 truncate">
              Directed Layered Layout • Left-to-right flow from victim account to observed cash-out endpoints
            </p>
          </div>
        </div>

        {/* Compact Quick Metrics — 100% DB-derived */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="px-2.5 py-1 rounded bg-[#F6F8FC] border border-[#DCE5F0]">
            <span className="text-slate-500 block text-[9px] uppercase font-semibold">Entities</span>
            <span className="text-blue-700 font-bold">{graphData.metrics.node_count} Nodes</span>
          </div>
          <div className="px-2.5 py-1 rounded bg-[#F6F8FC] border border-[#DCE5F0]">
            <span className="text-slate-500 block text-[9px] uppercase font-semibold">Hop Depth</span>
            <span className="text-amber-700 font-bold">
              {graphData.metrics.max_hop} {graphData.metrics.max_hop === 1 ? 'Hop' : 'Hops'}
            </span>
          </div>
          <div className="px-2.5 py-1 rounded bg-[#F6F8FC] border border-[#DCE5F0]">
            <span className="text-slate-500 block text-[9px] uppercase font-semibold">Mule Indicators</span>
            <div className="flex items-center space-x-1">
              <span className="text-red-700 font-bold">{graphData.metrics.high_risk_mule_nodes ?? flaggedPatternCount} Flagged</span>
              {accountsUnderReviewCount > 0 && (
                <span className="text-amber-700 bg-amber-50 border border-amber-200 px-1 py-0.2 rounded text-[9px] font-semibold">
                  ({accountsUnderReviewCount} Review)
                </span>
              )}
            </div>
          </div>
          <div className="px-2.5 py-1 rounded bg-[#F6F8FC] border border-[#DCE5F0]">
            <span className="text-slate-500 block text-[9px] uppercase font-semibold">Cash-Out Endpoints</span>
            <span className="text-emerald-700 font-bold">
              {graphData.metrics.withdrawal_count ?? 0} {(graphData.metrics.withdrawal_count ?? 0) === 1 ? 'Terminal' : 'Terminals'}
            </span>
          </div>
        </div>
      </div>

      {/* Partial Data Notice if edges are missing */}
      {isPartialData && (
        <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 flex items-start space-x-2 text-xs text-amber-800">
          <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Partial Telemetry:</span> Recorded entities without observed inter-account transaction edges. Graph representation shows isolated registered accounts; this does not imply a complete transaction trail.
          </div>
        </div>
      )}

      {/* Main Graph Area: Graph-First Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* Cytoscape Canvas Container — Takes 100% width on load, collapses to 8 cols when node selected */}
        <div className={selectedNode ? 'lg:col-span-8 w-full' : 'col-span-12 w-full'}>
          <CytoscapeNetwork
            graphData={graphData}
            onSelectNode={(node) => setSelectedNode(node)}
            selectedNodeId={selectedNode?.id}
          />
        </div>

        {/* Collapsible Details Panel — Rendered after user selection */}
        {selectedNode && (
          <aside
            className="lg:col-span-4 w-full bg-white rounded-lg border border-[#DCE5F0] p-4 sm:p-5 shadow-xs space-y-4"
            aria-label={`Details for selected entity ${selectedNode.masked_id}`}
          >
            {(() => {
              const isATM = selectedNode.node_type === 'atm';

              if (isATM) {
                // ATM Cash-Out Endpoint Details
                const atmLocality = selectedNode.pattern_flags?.atm_locality || selectedNode.bank;
                const atmAddress = selectedNode.pattern_flags?.atm_address || 'Delhi Region';
                const wdlTime = selectedNode.pattern_flags?.withdrawal_timestamp || 'Recent';
                const cameraFlagged = Boolean(selectedNode.pattern_flags?.camera_flagged);

                return (
                  <>
                    <div className="flex items-center justify-between pb-3 border-b border-[#DCE5F0]">
                      <div className="flex items-center space-x-2 min-w-0">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-emerald-500"></span>
                        <h3 className="text-sm font-bold text-[#173A63] truncate" title={selectedNode.label}>
                          {selectedNode.label}
                        </h3>
                      </div>
                      <button
                        onClick={() => setSelectedNode(null)}
                        className="text-slate-400 hover:text-slate-600 p-1.5 rounded-md hover:bg-slate-100 transition-colors shrink-0 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                        title="Close details panel and clear selection"
                        aria-label="Close details panel and clear selection"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    {/* ATM Terminal Stats */}
                    <div className="space-y-2 text-xs">
                      <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                        <span className="text-slate-500 shrink-0">Terminal Type:</span>
                        <span className="text-emerald-700 font-semibold text-right">
                          ATM Cash-Out Endpoint
                        </span>
                      </div>

                      <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                        <span className="text-slate-500 shrink-0">Terminal ID:</span>
                        <span className="text-blue-700 font-semibold font-mono">{selectedNode.masked_id}</span>
                      </div>

                      <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                        <span className="text-slate-500 shrink-0">Bank Operator:</span>
                        <span className="text-slate-800 font-medium text-right truncate" title={selectedNode.bank}>
                          {selectedNode.bank}
                        </span>
                      </div>

                      <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                        <span className="text-slate-500 shrink-0">Locality:</span>
                        <span className="text-slate-800 font-medium text-right">
                          {atmLocality}
                        </span>
                      </div>

                      <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between gap-2">
                        <span className="text-slate-500 shrink-0">Address:</span>
                        <span className="text-slate-700 text-[11px] text-right truncate max-w-[180px]" title={atmAddress}>
                          {atmAddress}
                        </span>
                      </div>

                      <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                        <span className="text-slate-500">Withdrawal:</span>
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

                      <p className="text-[10px] text-slate-500 leading-tight px-1 pt-1">
                        Physical cash withdrawal endpoint. Telemetry displayed with privacy protection; does not establish identity of person at terminal.
                      </p>
                    </div>

                    {/* Quick Actions */}
                    <div className="pt-2 border-t border-[#DCE5F0] flex flex-col space-y-2">
                      <button
                        onClick={() => navigate('/map')}
                        className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 shadow-xs"
                      >
                        <MapPin className="w-3.5 h-3.5" />
                        <span>VIEW ATM ON RISK MAP</span>
                      </button>
                      <button
                        onClick={() => setSelectedNode(null)}
                        className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-semibold transition-colors"
                      >
                        CLOSE DETAILS PANEL
                      </button>
                    </div>
                  </>
                );
              }

              // Normal Account / Entity Details
              const isMuleIndicator = Boolean(selectedNode.is_potential_mule_indicator || selectedNode.node_type === 'mule');
              const safeName = formatSafeDisplayLabel(
                selectedNode.label,
                selectedNode.node_type,
                selectedNode.is_source,
                selectedNode.masked_id,
                isMuleIndicator
              );
              const rawRiskPercent = Math.round(selectedNode.risk_score * 100);
              const riskBand = selectedNode.risk_band ||
                (selectedNode.risk_score >= 0.7 ? 'HIGH' : selectedNode.risk_score >= 0.3 ? 'MODERATE' : 'LOW');
              const isVictim = selectedNode.is_source || selectedNode.node_type === 'victim';
              const isIntermediary = selectedNode.is_intermediary || selectedNode.node_type === 'intermediary';
              const accountRole = isVictim
                ? 'Victim / Reporting Account'
                : isMuleIndicator
                ? 'Potential Mule Indicator / Under Review'
                : isIntermediary
                ? 'Intermediary / Under Review'
                : selectedNode.node_type === 'sink'
                ? 'Observed Endpoint / Under Review'
                : 'Beneficiary / Under Review';

              return (
                <>
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
                      className="text-slate-400 hover:text-slate-600 p-1.5 rounded-md hover:bg-slate-100 transition-colors shrink-0 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                      title="Close details panel and clear selection"
                      aria-label="Close details panel and clear selection"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Entity Stats */}
                  <div className="space-y-2 text-xs">
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
                      <span className="text-slate-500 shrink-0">Role Classification:</span>
                      <span className="text-slate-800 font-medium text-right">
                        {accountRole}
                      </span>
                    </div>

                    <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                      <span className="text-slate-500">Network Risk Indicator:</span>
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
                      <span className="text-slate-500">Layer (Hop Depth):</span>
                      <span className="text-blue-700 font-semibold font-mono">
                        {selectedNode.hop_level === 0 ? 'Layer 0 (Victim Source)' : `Layer ${selectedNode.hop_level}`}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div className="p-2 bg-[#F6F8FC] rounded-md border border-[#DCE5F0]">
                        <span className="text-slate-500 text-[9px] block uppercase font-medium">RECEIVED</span>
                        <span className="text-emerald-700 font-bold">
                          ₹{selectedNode.amount_received.toLocaleString('en-IN')}
                        </span>
                      </div>
                      <div className="p-2 bg-[#F6F8FC] rounded-md border border-[#DCE5F0]">
                        <span className="text-slate-500 text-[9px] block uppercase font-medium">FORWARDED</span>
                        <span className="text-slate-800 font-bold">
                          ₹{selectedNode.amount_sent.toLocaleString('en-IN')}
                        </span>
                      </div>
                    </div>

                    <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
                      <span className="text-slate-500">Observed Connections:</span>
                      <span className="text-blue-700 font-semibold">{selectedNode.connections_count} edges</span>
                    </div>

                    {/* Neutral language disclaimer */}
                    <p className="text-[10px] text-slate-500 leading-tight px-1 pt-1">
                      Relative network risk indicator used for operational triage only; does not establish guilt or unlawful conduct.
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="pt-2 border-t border-[#DCE5F0] flex flex-col space-y-2">
                    <button
                      onClick={() => navigate('/alerts')}
                      className="w-full py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 shadow-xs"
                    >
                      <AlertTriangle className="w-3.5 h-3.5" />
                      <span>RECOMMEND RAPID LIEN / FREEZE REVIEW</span>
                    </button>
                    <button
                      onClick={() => setSelectedNode(null)}
                      className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-semibold transition-colors"
                    >
                      CLOSE DETAILS PANEL
                    </button>

                    {/* Human-in-the-loop notice */}
                    <p className="text-[10px] text-slate-400 text-center leading-normal pt-1">
                      CyberShield AI provides investigative decision support. Enforcement requires authorized human approval.
                    </p>
                  </div>
                </>
              );
            })()}
          </aside>
        )}
      </div>

      {/* Accessible Entity Directory & Tabular View */}
      <section
        className="bg-white rounded-lg border border-[#DCE5F0] shadow-xs overflow-hidden"
        aria-label="Accessible Entity Directory"
      >
        <button
          onClick={() => setShowEntityTable(!showEntityTable)}
          className="w-full px-4 py-3 bg-[#F6F8FC] hover:bg-[#EEF2F8] border-b border-[#DCE5F0] flex items-center justify-between transition-colors text-left"
          aria-expanded={showEntityTable}
          aria-controls="accessible-entity-table"
        >
          <div className="flex items-center space-x-2">
            <TableIcon className="w-4 h-4 text-blue-600" />
            <h2 className="text-xs font-bold text-[#173A63] uppercase tracking-wide">
              Accessible Entity Directory ({graphData.nodes.length} Accounts & Terminals)
            </h2>
          </div>
          <div className="flex items-center space-x-2 text-xs text-slate-500 font-medium">
            <span>{showEntityTable ? 'Hide Table' : 'Show Keyboard/Screen-Reader Table'}</span>
            {showEntityTable ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {showEntityTable && (
          <div id="accessible-entity-table" className="overflow-x-auto p-2 sm:p-4">
            <table className="w-full text-left text-xs border-collapse" aria-label="Transaction network entities">
              <thead>
                <tr className="border-b border-[#DCE5F0] text-[11px] font-semibold text-slate-600 bg-slate-50">
                  <th scope="col" className="p-2.5">Masked Account / Terminal</th>
                  <th scope="col" className="p-2.5">Role Classification</th>
                  <th scope="col" className="p-2.5">Bank / Operator</th>
                  <th scope="col" className="p-2.5 text-center">Layer</th>
                  <th scope="col" className="p-2.5 text-right">Inflow (₹)</th>
                  <th scope="col" className="p-2.5 text-right">Outflow (₹)</th>
                  <th scope="col" className="p-2.5 text-center">Risk Score</th>
                  <th scope="col" className="p-2.5 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#DCE5F0]">
                {graphData.nodes.map((node) => {
                  const d = node.data;
                  const isSelected = selectedNode?.id === d.id;
                  const isNodeMuleIndicator = Boolean(d.is_potential_mule_indicator || d.node_type === 'mule');
                  const roleLabel = d.is_source || d.node_type === 'victim'
                    ? 'Victim Source'
                    : d.node_type === 'atm'
                    ? 'ATM Cash-Out'
                    : isNodeMuleIndicator
                    ? 'Potential Mule Indicator / Under Review'
                    : d.is_intermediary || d.node_type === 'intermediary'
                    ? 'Intermediary'
                    : d.node_type === 'sink'
                    ? 'Endpoint'
                    : 'Beneficiary';

                  return (
                    <tr
                      key={d.id}
                      className={`hover:bg-blue-50/50 transition-colors ${
                        isSelected ? 'bg-blue-50 font-semibold' : ''
                      }`}
                    >
                      <td className="p-2.5 font-mono text-slate-800">
                        {d.masked_id || d.id}
                      </td>
                      <td className="p-2.5">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            roleLabel === 'Victim Source'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : roleLabel === 'ATM Cash-Out'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : isNodeMuleIndicator
                              ? 'bg-red-50 text-red-700 border border-red-200'
                              : roleLabel === 'Intermediary'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                        >
                          {roleLabel}
                        </span>
                      </td>
                      <td className="p-2.5 text-slate-700">{d.bank || '—'}</td>
                      <td className="p-2.5 text-center font-mono text-slate-600">
                        {d.hop_level ?? '—'}
                      </td>
                      <td className="p-2.5 text-right font-mono text-emerald-700">
                        ₹{(d.amount_received || 0).toLocaleString('en-IN')}
                      </td>
                      <td className="p-2.5 text-right font-mono text-slate-700">
                        ₹{(d.amount_sent || 0).toLocaleString('en-IN')}
                      </td>
                      <td className="p-2.5 text-center font-mono">
                        <span
                          className={
                            d.risk_score >= 0.7
                              ? 'text-red-700 font-bold'
                              : d.risk_score >= 0.3
                              ? 'text-amber-700 font-semibold'
                              : 'text-emerald-700'
                          }
                        >
                          {Math.round((d.risk_score || 0) * 100)}%
                        </span>
                      </td>
                      <td className="p-2.5 text-center">
                        <button
                          onClick={() => handleSelectNodeFromTable(d)}
                          className={`px-2.5 py-1 rounded text-[11px] transition-colors focus:outline-hidden focus:ring-2 focus:ring-blue-500 ${
                            isSelected
                              ? 'bg-blue-600 text-white font-semibold'
                              : 'bg-slate-100 hover:bg-blue-600 hover:text-white text-slate-700'
                          }`}
                          aria-label={`Select ${d.masked_id || d.id} in graph`}
                        >
                          {isSelected ? 'Selected' : 'Inspect'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
