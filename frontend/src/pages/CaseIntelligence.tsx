import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  ShieldAlert,
  MapPin,
  Clock,
  Network,
  BellRing,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Info,
  Layers,
  Map as MapIcon,
  RefreshCw,
  Gauge,
  FileText,
  CreditCard,
  Building2,
  User,
  ArrowUpRight,
  Cpu,
  ChevronRight,
  ExternalLink,
  ShieldCheck,
  HelpCircle,
  Sparkles,
  Lock,
} from 'lucide-react';
import { api } from '../services/api';
import { Complaint, Prediction, Explanation, HotspotCluster, GraphData, AlertItem } from '../types';
import { CashOutRiskMap } from '../maps/CashOutRiskMap';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { LoadingState } from '../components/common/LoadingState';
import { PredictionTiming } from '../components/PredictionTiming';
import { apiErrorMessage, modelScore, predictionScoreNote } from '../utils/predictionDisplay';

export const CaseIntelligence: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const caseId = id || '';
  const navigate = useNavigate();
  const location = useLocation();
  const loadVersion = useRef(0);

  const [complaint, setComplaint] = useState<Complaint | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [explanationError, setExplanationError] = useState<string | null>(null);
  const [auditVerification, setAuditVerification] = useState<any | null>(null);
  const [verifyingAudit, setVerifyingAudit] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [clusters, setClusters] = useState<HotspotCluster[]>([]);
  const [existingAlert, setExistingAlert] = useState<AlertItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningPrediction, setRunningPrediction] = useState(false);
  const [predictionError, setPredictionError] = useState<string | null>(null);
  const [caseError, setCaseError] = useState<string | null>(null);
  const [alertSuccess, setAlertSuccess] = useState<string | null>(null);

  const fetchCaseDetails = async () => {
    const version = ++loadVersion.current;
    setLoading(true);
    setCaseError(null);
    setPredictionError(location.state?.analysisError || null);
    setComplaint(null);
    setPrediction(null);
    setExplanation(null);
    setAuditVerification(null);
    setGraphData(null);
    setExistingAlert(null);
    try {
      const [compResult, predResult, mapResult, alertsResult, graphResult] = await Promise.allSettled([
        api.getComplaint(caseId),
        api.getPrediction(caseId),
        api.getRiskMap(),
        api.getAlerts(),
        api.getGraph(caseId),
      ]);
      if (version !== loadVersion.current) return;
      if (compResult.status === 'rejected') throw compResult.reason;
      const compData = compResult.value;
      const predData = predResult.status === 'fulfilled' ? predResult.value : null;
      if (predResult.status === 'rejected') setPredictionError(apiErrorMessage(predResult.reason, 'Could not load analysis. Retry below.'));
      setComplaint(compData);
      setPrediction(predData);
      setClusters(mapResult.status === 'fulfilled' ? mapResult.value.hotspots || [] : []);
      setGraphData(graphResult.status === 'fulfilled' ? graphResult.value : null);

      const matchedAlert = (alertsResult.status === 'fulfilled' ? alertsResult.value : []).find(
        (a) => a.complaint_number === caseId || a.complaint_id === compData.id
      );
      setExistingAlert(matchedAlert || null);

      // On-demand LIME: Do NOT block initial case page loading on LIME inference

    } catch (err: any) {
      console.error('Failed to load case intelligence', err);
      if (version === loadVersion.current) setCaseError(apiErrorMessage(err, 'Could not load this complaint. Check the case number and retry.'));
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  };

  useEffect(() => {
    fetchCaseDetails();
    return () => { loadVersion.current += 1; };
  }, [caseId]);

  // Operational Action: Run Predictive Analysis
  const handleRunPrediction = async () => {
    setRunningPrediction(true);
    setPredictionError(null);
    setExplanation(null);
    setAuditVerification(null);
    try {
      const newPred = await api.runPrediction(caseId);
      setPrediction(newPred);
      // Non-blocking: Prediction response completes immediately without waiting on LIME
    } catch (err: any) {
      console.error('Error running predictive analysis', err);
      setPredictionError(apiErrorMessage(err, 'Predictive analysis could not be completed. Check case context or backend service.'));
    } finally {
      setRunningPrediction(false);
    }
  };

  // On-demand LIME Explanation handler
  const handleExplainPrediction = async () => {
    const predId = prediction?.prediction_id || (prediction as any)?.id;
    if (!predId) return;
    setLoadingExplanation(true);
    setExplanationError(null);
    try {
      const explData = await api.getExplanation(predId);
      setExplanation(explData);
    } catch (err: any) {
      console.error('Failed to generate LIME explanation', err);
      setExplanationError('LIME explanation service is currently unavailable.');
    } finally {
      setLoadingExplanation(false);
    }
  };

  // On-demand Fabric Prediction Audit Verification handler
  const handleVerifyAudit = async () => {
    const predId = prediction?.prediction_id || (prediction as any)?.id;
    if (!predId) return;
    setVerifyingAudit(true);
    setAuditError(null);
    try {
      const auditData = await api.verifyPredictionAudit(predId);
      setAuditVerification(auditData);
    } catch (err: any) {
      console.error('Failed to verify prediction audit', err);
      setAuditError('Ledger verification gateway unreachable.');
    } finally {
      setVerifyingAudit(false);
    }
  };

  // Operational Action: Generate or View Alert
  const handleGenerateAlert = async () => {
    if (!complaint || !prediction) return;
    try {
      const predId = prediction.prediction_id || prediction.id;
      if (!predId) return;

      const created = await api.createAlertForPrediction(predId);
      setExistingAlert(created);
      const targetLoc = created.location_name || prediction.where_location || 'hotspot';
      setAlertSuccess(`Alert #${created.id} generated for ${targetLoc}`);
      setTimeout(() => setAlertSuccess(null), 5000);
    } catch (err: any) {
      console.error('Error creating alert', err);
      setAlertSuccess(err.response?.data?.detail || 'Alert creation failed');
      setTimeout(() => setAlertSuccess(null), 5000);
    }
  };

  if (loading) {
    return (
      <div className="py-24">
        <LoadingState message="Loading case intelligence dossier and evidence records..." />
      </div>
    );
  }

  if (!complaint) return (
    <div className="p-6 bg-white rounded-lg border border-red-200 space-y-3">
      <p className="text-sm text-red-700">{caseError || 'Complaint unavailable.'}</p>
      <Button onClick={fetchCaseDetails}>Retry loading case</Button>
    </div>
  );

  const isTrained = prediction?.prediction_mode === 'trained_ml';
  const isDemo = prediction?.prediction_mode === 'deterministic_demo';
  const topLocations = [...(prediction?.top_locations || [])].sort((a, b) => a.rank - b.rank).slice(0, 3);
  const rank1Location = topLocations[0] || null;

  // Context provenance mapping
  const provenanceLabel =
    complaint.provenance_mode === 'DIRECT_OFFICER_INPUT'
      ? 'Direct Officer-Reported Transaction'
      : complaint.provenance_mode === 'LINKED_SYNTHETIC_SCENARIO'
      ? 'Linked Investigation Scenario'
      : complaint.provenance_mode === 'HYBRID_CONTEXT'
      ? 'Hybrid Context'
      : 'Direct Officer-Reported Transaction';

  const nodeCount = graphData?.metrics?.node_count ?? (complaint.linked_account_count || 2);
  const transferCount = graphData?.metrics?.edge_count ?? (complaint.available_transaction_count || 1);

  return (
    <div className="space-y-5 pb-12 font-sans">
      {/* ==================================================================== */}
      {/* B2: COMPACT PROFESSIONAL CASE HEADER */}
      {/* ==================================================================== */}
      <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Case Intelligence
              </span>
              <span className="text-slate-300">•</span>
              <span className="text-lg font-bold font-mono text-slate-900">
                {complaint.complaint_number}
              </span>
              <Badge
                variant={
                  complaint.case_status === 'ALERTED'
                    ? 'critical'
                    : complaint.case_status === 'ACTIVE'
                    ? 'info'
                    : 'neutral'
                }
              >
                {complaint.case_status}
              </Badge>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Cybercrime complaint investigation and predictive cash-out analysis
            </p>
          </div>

          {/* Primary Operational Actions */}
          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            {prediction ? (
              <Button
                onClick={handleRunPrediction}
                disabled={runningPrediction}
                variant="secondary"
                size="sm"
                icon={<RefreshCw className={`w-3.5 h-3.5 ${runningPrediction ? 'animate-spin' : ''}`} />}
              >
                {runningPrediction ? 'Evaluating...' : 'Rerun Analysis'}
              </Button>
            ) : (
              <Button
                onClick={handleRunPrediction}
                disabled={runningPrediction}
                variant="primary"
                size="sm"
                icon={<Cpu className={`w-3.5 h-3.5 ${runningPrediction ? 'animate-spin' : ''}`} />}
              >
                {runningPrediction ? 'Evaluating...' : 'Run Predictive Analysis'}
              </Button>
            )}

            {prediction ? (
              <Button
                onClick={() => navigate(`/risk-map?case=${caseId}`)}
                variant="outline"
                size="sm"
                icon={<MapIcon className="w-3.5 h-3.5" />}
              >
                Show on Map
              </Button>
            ) : null}

            {existingAlert ? (
              <Button
                onClick={() => navigate('/alerts')}
                variant="secondary"
                size="sm"
                icon={<BellRing className="w-3.5 h-3.5 text-amber-600" />}
              >
                <span>Alert #{existingAlert.id} ({existingAlert.status})</span>
              </Button>
            ) : prediction ? (
              <Button
                onClick={handleGenerateAlert}
                variant="danger"
                size="sm"
                icon={<BellRing className="w-3.5 h-3.5" />}
              >
                Generate Alert
              </Button>
            ) : null}
          </div>
        </div>

        {alertSuccess && (
          <div className="mt-3.5 p-3 rounded-md bg-green-50 border border-green-200 text-green-800 text-xs flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0" />
            <span className="font-medium">{alertSuccess}</span>
          </div>
        )}
      </div>

      {/* ==================================================================== */}
      {/* B3: COMPACT CASE SUMMARY STRIP (6 Information Cells) */}
      {/* ==================================================================== */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Amount Lost
          </span>
          <div className="text-base font-bold text-slate-900 mt-0.5">
            ₹{Number(complaint.amount).toLocaleString('en-IN')}
          </div>
          <span className="text-[10px] text-slate-400">Total reported loss</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Fraud Type
          </span>
          <div className="text-sm font-semibold text-slate-800 mt-0.5 truncate" title={complaint.fraud_type}>
            {complaint.fraud_type}
          </div>
          <span className="text-[10px] text-slate-400">Classification</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Incident Time
          </span>
          <div className="text-xs font-semibold text-slate-800 mt-0.5">
            {complaint.incident_time
              ? new Date(complaint.incident_time).toLocaleString('en-IN', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                })
              : 'Not available'}
          </div>
          <span className="text-[10px] text-slate-400">Complainant timestamp</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Reported Time
          </span>
          <div className="text-xs font-semibold text-slate-800 mt-0.5">
            {complaint.reported_at
              ? new Date(complaint.reported_at).toLocaleString('en-IN', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                })
              : 'Not available'}
          </div>
          <span className="text-[10px] text-slate-400">Portal intake timestamp</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Payment Channel
          </span>
          <div className="text-sm font-semibold text-slate-800 mt-0.5">
            {complaint.payment_channel || 'Not available'}
          </div>
          <span className="text-[10px] text-slate-400">Initial remittance rail</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Jurisdiction
          </span>
          <div className="text-xs font-semibold text-slate-800 mt-0.5 truncate" title={`${complaint.district || ''}, ${complaint.state || 'Delhi'}`}>
            {complaint.district ? `${complaint.district}, ${complaint.state || 'Delhi'}` : complaint.state || 'Delhi'}
          </div>
          <span className="text-[10px] text-slate-400">Police jurisdiction</span>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* B4 & B6: INVESTIGATION DETAILS & CONTEXT PROVENANCE */}
      {/* ==================================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Victim / Complaint Context */}
        <div className="lg:col-span-6 bg-white border border-slate-200 rounded-lg p-5 shadow-sm">
          <div className="flex items-center space-x-2 pb-3 border-b border-slate-100 mb-3.5">
            <User className="w-4 h-4 text-slate-600" />
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Victim & Complaint Context
            </h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs">
            <div>
              <span className="text-slate-500 text-[11px] block">Victim Name</span>
              <span className="font-semibold text-slate-800">
                {complaint.victim_name || 'Not available'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 text-[11px] block">Locality / Origin</span>
              <span className="text-slate-800">
                {complaint.locality || complaint.victim_location || 'Not available'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 text-[11px] block">Victim Bank</span>
              <span className="font-semibold text-slate-800">
                {complaint.victim_bank || 'Not available'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 text-[11px] block">Reported Phone</span>
              <span className="text-slate-800 font-mono">
                {complaint.victim_phone || 'Not available'}
              </span>
            </div>
          </div>

          {/* Narrative description */}
          <div className="mt-4 pt-3.5 border-t border-slate-100 text-xs">
            <span className="text-slate-500 text-[11px] block mb-1">
              Officer Complaint Description / Modus Operandi
            </span>
            <p className="text-slate-700 leading-relaxed bg-slate-50 p-2.5 rounded border border-slate-100">
              {complaint.description || 'No complaint narrative description entered at registration.'}
            </p>
          </div>
        </div>

        {/* Right Column: Transaction Evidence */}
        <div className="lg:col-span-6 bg-white border border-slate-200 rounded-lg p-5 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3.5">
            <div className="flex items-center space-x-2">
              <CreditCard className="w-4 h-4 text-slate-600" />
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Transaction Evidence
              </h3>
            </div>
            <span
              className="text-[11px] px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 font-medium"
              title="Prediction inputs derived from transaction information registered with this complaint."
            >
              {provenanceLabel}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs">
            <div>
              <span className="text-slate-500 text-[11px] block">Beneficiary Bank</span>
              <span className="font-semibold text-slate-800">
                {complaint.beneficiary_bank || 'Not available'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 text-[11px] block">Beneficiary Account</span>
              <span className="font-mono text-slate-800 font-semibold break-all">
                {complaint.beneficiary_id || 'Not available'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 text-[11px] block">UTR / Transaction Ref</span>
              <span className="font-mono text-slate-900 font-bold break-all">
                {complaint.transaction_ref || 'Not available'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 text-[11px] block">Transaction Timestamp</span>
              <span className="text-slate-800">
                {complaint.transaction_time
                  ? new Date(complaint.transaction_time).toLocaleString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : 'Not available'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 text-[11px] block">IFSC / Branch Code</span>
              <span className="font-mono text-slate-800">
                {complaint.ifsc_code || 'Not available'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 text-[11px] block">Evidence Source Status</span>
              <span className="text-slate-700">
                {complaint.scenario_link_status || 'Verified Ledger'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* B5 & B19: TRANSACTION TRAIL (Accurate Hop Presentation) */}
      {/* ==================================================================== */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-100 mb-4 gap-2">
          <div className="flex items-center space-x-2">
            <Network className="w-4 h-4 text-slate-600" />
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Transaction Trail
            </h3>
          </div>
          <div className="flex items-center space-x-3 text-xs text-slate-500">
            <span>Nodes: <strong className="text-slate-800 font-mono">{nodeCount}</strong></span>
            <span>•</span>
            <span>Transfers: <strong className="text-slate-800 font-mono">{transferCount}</strong></span>
            <span>•</span>
            <span>Amount: <strong className="text-slate-800 font-mono">₹{Number(complaint.amount).toLocaleString('en-IN')}</strong></span>
            <button
              onClick={() => navigate(`/network/${complaint.complaint_number}`)}
              className="text-blue-700 hover:underline font-medium text-xs flex items-center space-x-1 ml-2"
            >
              <span>Full Graph</span>
              <ArrowUpRight className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* Honest Step Flow Diagram */}
        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            {/* Step 1: Victim Account */}
            <div className="flex-1 bg-white p-3.5 rounded-md border border-slate-200 shadow-sm">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-semibold uppercase text-slate-500 tracking-wider">
                  Victim Account
                </span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 font-medium">
                  Source Hop
                </span>
              </div>
              <div className="font-semibold text-xs text-slate-900">
                {complaint.victim_bank || 'Source Bank'}
              </div>
              <div className="text-xs text-slate-600 mt-0.5 font-mono">
                {complaint.victim_name || 'Complainant Account'}
              </div>
            </div>

            {/* Transfer Connector */}
            <div className="flex flex-col items-center justify-center px-4 py-1 text-center shrink-0 space-y-0.5">
              <div className="text-xs font-bold text-slate-900 font-mono">
                ₹{Number(complaint.amount).toLocaleString('en-IN')} • {complaint.payment_channel || 'UPI'}
              </div>
              <div className="text-[11px] text-slate-600 font-mono">
                {complaint.transaction_ref || 'Direct Remittance'}
              </div>
              <div className="text-[10px] text-slate-500">
                {complaint.transaction_time
                  ? new Date(complaint.transaction_time).toLocaleString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : complaint.incident_time
                  ? new Date(complaint.incident_time).toLocaleString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : 'Timestamp Recorded'}
              </div>
              <div className="w-full flex items-center justify-center text-slate-400 pt-0.5">
                <span className="hidden md:inline text-slate-400 font-bold">────────►</span>
                <span className="md:hidden text-slate-400 font-bold">▼</span>
              </div>
            </div>

            {/* Step 2: Beneficiary Account */}
            <div className="flex-1 bg-white p-3.5 rounded-md border border-slate-200 shadow-sm">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-semibold uppercase text-slate-500 tracking-wider">
                  Beneficiary Account
                </span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-50 text-amber-700 border border-amber-200 font-medium">
                  Destination Hop
                </span>
              </div>
              <div className="font-semibold text-xs text-slate-900">
                {complaint.beneficiary_bank || 'Destination Bank'}
              </div>
              <div className="text-xs text-slate-600 mt-0.5 font-mono truncate" title={complaint.beneficiary_id || ''}>
                {complaint.beneficiary_id || 'Beneficiary Account Recorded'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* B7 - B14: PREDICTIVE CASH-OUT ASSESSMENT */}
      {/* ==================================================================== */}
      {predictionError ? (
        <div className="bg-white border border-red-200 rounded-lg p-6 shadow-sm text-center space-y-3">
          <AlertTriangle className="w-8 h-8 text-red-600 mx-auto" />
          <h3 className="text-sm font-bold text-slate-900">Predictive Analysis Error</h3>
          <p className="text-xs text-slate-600 max-w-md mx-auto">{predictionError}</p>
          <Button onClick={handleRunPrediction} variant="secondary" size="sm">
            Retry Analysis
          </Button>
        </div>
      ) : !prediction ? (
        /* B15: TRUTHFUL PRE-PREDICTION STATE DERIVED FROM DB (Section 22) */
        <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                Case Intake & Operational Readiness
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Current case state verified directly from PostgreSQL evidence records.
              </p>
            </div>
            <Button
              onClick={handleRunPrediction}
              disabled={runningPrediction}
              variant="primary"
              size="md"
              icon={<Cpu className={`w-4 h-4 ${runningPrediction ? 'animate-spin' : ''}`} />}
            >
              {runningPrediction ? 'Running Predictive Analysis...' : 'Run Predictive Analysis'}
            </Button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <div className="p-3 rounded-lg border border-green-200 bg-green-50/50">
              <div className="flex items-center justify-between text-xs text-green-700 font-semibold mb-1">
                <span>Complaint Intake</span>
                <CheckCircle2 className="w-4 h-4 text-green-600" />
              </div>
              <div className="text-sm font-bold text-slate-900">Registered</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Stored in PostgreSQL</div>
            </div>

            <div className="p-3 rounded-lg border border-green-200 bg-green-50/50">
              <div className="flex items-center justify-between text-xs text-green-700 font-semibold mb-1">
                <span>Transaction Evidence</span>
                <CheckCircle2 className="w-4 h-4 text-green-600" />
              </div>
              <div className="text-sm font-bold text-slate-900">Available</div>
              <div className="text-[11px] text-slate-500 mt-0.5 font-mono">{complaint.transaction_ref || 'Direct Record'}</div>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 bg-slate-50">
              <div className="flex items-center justify-between text-xs text-slate-600 font-semibold mb-1">
                <span>Predictive Analysis</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-200 text-slate-700 font-bold">AWAITING</span>
              </div>
              <div className="text-sm font-bold text-slate-700">NOT RUN</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Requires execution</div>
            </div>

            <div className="p-3 rounded-lg border border-amber-200 bg-amber-50/50">
              <div className="flex items-center justify-between text-xs text-amber-700 font-semibold mb-1">
                <span>Operational Assessment</span>
                <Clock className="w-4 h-4 text-amber-600" />
              </div>
              <div className="text-sm font-bold text-slate-900">PENDING</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Awaiting ML scoring</div>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 bg-slate-50">
              <div className="flex items-center justify-between text-xs text-slate-600 font-semibold mb-1">
                <span>Alert Status</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-200 text-slate-700 font-bold">HOLD</span>
              </div>
              <div className="text-sm font-bold text-slate-700">NOT GENERATED</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Post-inference only</div>
            </div>
          </div>

          <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-slate-700 uppercase text-[11px]">Model Provenance:</span>
              <span>Prediction Mode: <strong className="text-slate-800 font-mono">unavailable</strong></span>
              <span>•</span>
              <span>Location Model: <strong className="text-slate-800 font-mono">unavailable</strong></span>
              <span>•</span>
              <span>Time Model: <strong className="text-slate-800 font-mono">unavailable</strong></span>
            </div>
            <span className="text-[11px] text-slate-500">Run predictive analysis above to compute live Top-3 candidate clusters</span>
          </div>
        </div>
      ) : (
        /* ACTIVE PREDICTION WORKSPACE */
        <div className="space-y-5">
          <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div className="flex items-center space-x-2">
                <ShieldAlert className="w-4 h-4 text-slate-600" />
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Predictive Cash-Out Assessment
                </h3>
              </div>
              <span className="text-xs text-slate-500">
                Prediction #{prediction.prediction_id || prediction.id} • {isTrained ? 'Trained ML' : isDemo ? 'Deterministic Demo' : 'Operational'}
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left 2/3: Top Predicted Cash-Out Zones */}
              <div className="lg:col-span-8 space-y-4">
                {/* Primary Predicted Zone Banner (B9 & Section 21) */}
                {rank1Location && (
                  <div className="p-4 rounded-lg bg-[#EFF6FF]/70 border border-[#DCE5F0]">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="text-[11px] font-semibold uppercase text-blue-700 tracking-wider">
                        #1 PRIMARY PREDICTED ZONE
                      </span>
                      <span className={`text-[10px] px-2 py-0.5 rounded font-medium border ${
                        rank1Location.risk_level === 'CRITICAL'
                          ? 'bg-red-50 text-red-700 border-red-200'
                          : rank1Location.risk_level === 'HIGH'
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : 'bg-blue-50 text-blue-700 border-blue-200'
                      }`}>
                        {rank1Location.risk_level} Operational Priority
                      </span>
                    </div>

                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div>
                        <div className="text-base font-bold text-[#173A63]">
                          {rank1Location.cluster_name || rank1Location.location_name}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                          Distance from complaint origin: {rank1Location.distance_km} km
                        </div>
                      </div>

                      <div className="text-left sm:text-right">
                        <div className="text-[11px] text-slate-500">Operational Priority</div>
                        <div className="text-sm font-bold text-slate-900">
                          Rank #1 Candidate Cash-Out Zone
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Top-3 Location Table (Section 21) */}
                <div>
                  <div className="text-xs font-semibold text-[#173A63] uppercase tracking-wider mb-2">
                    Ranked Cash-Out Candidate Zones (Delhi Pilot)
                  </div>

                  {/* Desktop Table View (>= md) */}
                  <div className="hidden md:block overflow-x-auto border border-[#DCE5F0] rounded-md">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-[#F8FAFC] border-b border-[#DCE5F0] text-slate-700 font-semibold">
                          <th className="py-2.5 px-3">Rank</th>
                          <th className="py-2.5 px-3">Candidate Zone</th>
                          <th className="py-2.5 px-3">{prediction.score_label || 'Model score'}</th>
                          <th className="py-2.5 px-3 text-center">Operational Priority</th>
                          <th className="py-2.5 px-3">Distance</th>
                          <th className="py-2.5 px-3">Intervention Reasoning</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#DCE5F0]">
                        {topLocations.slice(0, 3).map((loc) => (
                          <tr
                            key={loc.rank}
                            className={`hover:bg-blue-50/30 transition-colors ${
                              loc.rank === 1 ? 'bg-blue-50/40 font-medium' : ''
                            }`}
                          >
                            <td className="py-2.5 px-3 font-bold font-mono text-blue-700">
                              #{loc.rank === 1 ? '1 PRIMARY' : loc.rank === 2 ? '2 SECONDARY' : '3 TERTIARY'}
                            </td>
                            <td className="py-2.5 px-3 font-semibold text-slate-900">
                              {loc.cluster_name || loc.location_name}
                            </td>
                            <td className="py-2.5 px-3 font-semibold text-blue-700">{modelScore(loc)}</td>
                            <td className="py-2.5 px-3 text-center">
                              <span className={`inline-block text-[10px] px-2 py-0.5 rounded font-medium border ${
                                loc.risk_level === 'CRITICAL'
                                  ? 'bg-red-50 text-red-700 border-red-200'
                                  : loc.risk_level === 'HIGH'
                                  ? 'bg-amber-50 text-amber-700 border-amber-200'
                                  : 'bg-blue-50 text-blue-700 border-blue-200'
                              }`}>
                                {loc.risk_level}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-slate-600 font-mono">
                              {loc.distance_km} km
                            </td>
                            <td className="py-2.5 px-3 text-slate-600 max-w-xs truncate" title={loc.reasoning}>
                              {loc.reasoning}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Mobile Top-3 Cards (< md) */}
                  <div className="md:hidden space-y-2.5">
                    {topLocations.slice(0, 3).map((loc) => (
                      <div
                        key={`m-ci-${loc.rank}`}
                        className={`p-3 rounded-lg border text-xs space-y-2 ${
                          loc.rank === 1 ? 'bg-blue-50/50 border-blue-200 border-l-4 border-l-blue-600' : 'bg-white border-[#DCE5F0]'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold font-mono text-blue-700">
                            #{loc.rank === 1 ? '1 PRIMARY' : loc.rank === 2 ? '2 SECONDARY' : '3 TERTIARY'}
                          </span>
                          <span className={`text-[10px] px-2 py-0.5 rounded font-medium border ${
                            loc.risk_level === 'CRITICAL'
                              ? 'bg-red-50 text-red-700 border-red-200'
                              : loc.risk_level === 'HIGH'
                              ? 'bg-amber-50 text-amber-700 border-amber-200'
                              : 'bg-blue-50 text-blue-700 border-blue-200'
                          }`}>
                            {loc.risk_level}
                          </span>
                        </div>
                        <div className="font-semibold text-slate-900 text-sm">
                          {loc.cluster_name || loc.location_name}
                        </div>
                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span>Distance: <strong className="text-slate-700 font-mono">{loc.distance_km} km</strong></span>
                          <span>{prediction.score_label || 'Model score'}: <strong className="text-blue-700">{modelScore(loc)}</strong></span>
                        </div>
                        {loc.reasoning && (
                          <div className="text-[11px] text-slate-600 bg-slate-50 p-2 rounded border border-slate-100 leading-relaxed">
                            {loc.reasoning}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* On-Demand LIME Explainability Card */}
                <div className="p-4 bg-white rounded-lg border border-[#DCE5F0] space-y-3 shadow-xs">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-[#DCE5F0]">
                    <div className="flex items-center space-x-2">
                      <Sparkles className="w-4 h-4 text-blue-600 shrink-0" />
                      <div>
                        <h4 className="text-xs font-bold text-[#173A63] uppercase">
                          Model Attribution & Local Explainability (LIME)
                        </h4>
                        <p className="text-[11px] text-slate-500">
                          Explains why the trained model prioritized Top-3 candidates without altering rankings.
                        </p>
                      </div>
                    </div>
                    <Button
                      onClick={handleExplainPrediction}
                      disabled={loadingExplanation}
                      variant="outline"
                      size="sm"
                      className="shrink-0 text-xs"
                      icon={<Cpu className="w-3.5 h-3.5 text-blue-600" />}
                    >
                      {loadingExplanation ? 'Computing LIME...' : explanation ? 'Re-explain (LIME)' : 'Explain Prediction'}
                    </Button>
                  </div>

                  {explanationError && (
                    <div className="p-2.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
                      {explanationError}
                    </div>
                  )}

                  {explanation && explanation.top3_explanations && explanation.top3_explanations.length > 0 ? (
                    <div className="space-y-3 pt-1">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 text-xs p-2.5 bg-slate-50 rounded border border-slate-200">
                        <div className="flex items-center space-x-2">
                          <span className="text-slate-600 font-medium">Surrogate Linear Fidelity:</span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            explanation.overall_fidelity_status === 'HIGH_FIDELITY'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : explanation.overall_fidelity_status === 'MODERATE_FIDELITY'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}>
                            {explanation.overall_fidelity_status?.replace('_', ' ')} (Mean R² = {explanation.mean_local_fidelity_r2 !== undefined ? explanation.mean_local_fidelity_r2.toFixed(4) : '0.2252'})
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-500 font-mono">
                          Method: {explanation.explanation_method || 'LIME'} Tabular
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                        {explanation.top3_explanations.map((cand) => (
                          <div
                            key={`lime-card-${cand.rank}`}
                            className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-2"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-blue-700 font-mono">Rank #{cand.rank}</span>
                              <span className={`text-[10px] px-1.5 py-0.2 rounded font-semibold ${
                                cand.fidelity_status === 'HIGH_FIDELITY'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : cand.fidelity_status === 'MODERATE_FIDELITY'
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}>
                                {cand.fidelity_status?.replace('_', ' ')}
                              </span>
                            </div>
                            <div className="font-semibold text-slate-900 truncate" title={cand.location_name}>
                              {cand.location_name}
                            </div>
                            <div className="text-[11px] text-slate-500 flex justify-between font-mono">
                              <span>Official: <strong>{(cand.official_score * 100).toFixed(1)}%</strong></span>
                              <span>LIME: <strong>{(cand.lime_local_prediction * 100).toFixed(1)}%</strong></span>
                              <span>R²: <strong>{cand.local_fidelity_r2 !== undefined ? cand.local_fidelity_r2.toFixed(2) : 'N/A'}</strong></span>
                            </div>

                            {/* Top Positive Contributions */}
                            {cand.positive_contributions && cand.positive_contributions.length > 0 && (
                              <div className="space-y-1 pt-1 border-t border-slate-200">
                                <span className="text-[10px] font-bold text-emerald-700 uppercase block">
                                  Contributing Signals:
                                </span>
                                {cand.positive_contributions.slice(0, 2).map((c, i) => (
                                  <div key={i} className="flex justify-between text-[10px] text-slate-700">
                                    <span className="truncate pr-1" title={c.feature_name}>{c.feature_name}</span>
                                    <span className="font-mono text-emerald-700 font-bold shrink-0">+{c.weight.toFixed(4)}</span>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Top Negative Contributions */}
                            {cand.negative_contributions && cand.negative_contributions.length > 0 && (
                              <div className="space-y-1 pt-1 border-t border-slate-200">
                                <span className="text-[10px] font-bold text-slate-500 uppercase block">
                                  Down-weighting Signals:
                                </span>
                                {cand.negative_contributions.slice(0, 2).map((c, i) => (
                                  <div key={i} className="flex justify-between text-[10px] text-slate-700">
                                    <span className="truncate pr-1" title={c.feature_name}>{c.feature_name}</span>
                                    <span className="font-mono text-slate-600 font-bold shrink-0">{c.weight.toFixed(4)}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>

                      <div className="p-2.5 bg-blue-50/60 rounded border border-blue-100 text-[11px] text-slate-600 flex items-start space-x-2">
                        <Info className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                        <p className="leading-relaxed">
                          {explanation.disclaimer || 'LIME provides a local approximation of model behavior and does not prove causality or criminal activity.'}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-[11px] text-slate-500 italic">
                      Click &quot;Explain Prediction&quot; to compute feature attributions on demand without blocking standard workflow.
                    </p>
                  )}
                </div>

                {/* Explanatory Disclaimer Note (Section 21) */}
                <CashOutRiskMap
                  topLocations={topLocations}
                  complaint={complaint}
                  prediction={prediction}
                  height="340px"
                  showControls={false}
                />
                <div className="p-3 bg-[#F8FAFC] rounded-md border border-[#DCE5F0] text-xs text-slate-500 flex items-start space-x-2">
                  <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                  <p className="leading-relaxed">
                    {predictionScoreNote(prediction)} Rankings do not guarantee that activity will occur at a particular location.
                  </p>
                </div>
              </div>

              {/* Right 1/3: Timing + Model Provenance + Action Panel */}
              <div className="lg:col-span-4 space-y-4">
                {/* Time Prediction Card (B11) */}
                <div className="p-4 bg-[#F8FAFC] rounded-lg border border-[#DCE5F0] space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span className="font-semibold uppercase text-slate-700 flex items-center space-x-1.5">
                      <Clock className="w-3.5 h-3.5 text-blue-600" />
                      <span>Predicted Cash-out Window</span>
                    </span>
                    <span className="text-[10px] font-medium bg-blue-50 text-blue-700 px-1.5 py-0.2 rounded border border-blue-200">
                      Operational Estimate
                    </span>
                  </div>

                  <PredictionTiming prediction={prediction} />

                  <p className="text-[11px] text-slate-500">
                    Estimated intervention window generated by {prediction.time_prediction?.model_version || (prediction as any).time_model_version || 'predictive time model'}.
                  </p>
                </div>

                {/* Model Provenance Card (B12 & Final Integration) */}
                <div className="p-4 bg-white rounded-lg border border-[#DCE5F0] space-y-2.5 shadow-xs text-xs">
                  <div className="flex items-center justify-between pb-2 border-b border-[#DCE5F0]">
                    <span className="font-bold text-[#173A63] uppercase text-[11px]">
                      Model & Provenance
                    </span>
                    <span className="font-mono text-blue-700 font-semibold">
                      #{prediction.prediction_id || prediction.id}
                    </span>
                  </div>

                  <div className="space-y-1.5 text-slate-600">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Prediction Mode:</span>
                      <strong className="text-slate-800">{isTrained ? 'Trained ML' : isDemo ? 'Deterministic Demo' : (prediction.prediction_mode || 'unavailable')}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Location Model:</span>
                      <span className="font-mono text-slate-800 font-semibold">{prediction.model_version || 'cashout-location-xgb-v7-compat'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Time Model:</span>
                      <span className="font-mono text-slate-800">{prediction.time_prediction?.model_version || (prediction as any).time_model_version || 'cashout-time-xgb-v3'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Consortium Ledger:</span>
                      <span className="text-slate-800 font-medium">Hyperledger Fabric</span>
                    </div>
                    <div className="flex justify-between items-center pt-0.5">
                      <span className="text-slate-500">Blockchain Audit:</span>
                      {auditVerification ? (
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          auditVerification.status === 'VERIFIED'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : auditVerification.status === 'HASH_MISMATCH'
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}>
                          {auditVerification.status}
                        </span>
                      ) : (
                        <button
                          onClick={handleVerifyAudit}
                          disabled={verifyingAudit}
                          className="text-[10px] font-semibold text-blue-700 hover:underline flex items-center space-x-1"
                        >
                          {verifyingAudit ? (
                            <span>Verifying...</span>
                          ) : (
                            <>
                              <ShieldCheck className="w-3 h-3 text-blue-600" />
                              <span>Verify on Ledger</span>
                            </>
                          )}
                        </button>
                      )}
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-500">Explainability:</span>
                      <span className="text-slate-800 font-medium">LIME Tabular</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-500">LIME Fidelity:</span>
                      {explanation ? (
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          explanation.overall_fidelity_status === 'HIGH_FIDELITY'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : explanation.overall_fidelity_status === 'MODERATE_FIDELITY'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}>
                          {explanation.overall_fidelity_status?.replace('_', ' ') || 'LOW FIDELITY'}
                        </span>
                      ) : (
                        <span className="text-[10px] text-slate-400">On Demand</span>
                      )}
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Candidate Scope:</span>
                      <span className="text-slate-800">{prediction.operational_scope || 'Delhi Pilot • 60 Clusters'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Context:</span>
                      <span className="text-slate-800">{provenanceLabel}</span>
                    </div>
                    {prediction.analysis_basis && <div className="pt-2 text-slate-600">
                      {prediction.analysis_basis === 'complaint_only' ? 'Limited evidence: complaint details only. Add verified transfer evidence to improve analysis.' : prediction.analysis_basis === 'linked_synthetic_scenario' ? 'Evidence includes a synthetic investigation scenario.' : 'Analysis includes recorded transaction evidence.'}
                    </div>}
                  </div>
                </div>

                {/* Operational Actions Card (B14) */}
                <div className="p-4 bg-[#F8FAFC] rounded-lg border border-[#DCE5F0] space-y-2.5">
                  <span className="text-xs font-bold text-[#173A63] uppercase block">
                    Operational Actions
                  </span>

                  {existingAlert ? (
                    <div className="p-2.5 bg-white rounded border border-slate-200 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900">Alert #{existingAlert.id} Active</span>
                        <Badge variant={existingAlert.status === 'ACKNOWLEDGED' ? 'success' : 'critical'}>
                          {existingAlert.status}
                        </Badge>
                      </div>
                      <div className="text-[11px] text-slate-600 truncate">
                        Location: {existingAlert.location_name}
                      </div>
                      {existingAlert.acknowledged_by && (
                        <div className="text-[10px] text-slate-400 truncate">
                          Officer: {existingAlert.acknowledged_by}
                        </div>
                      )}
                      <div className="pt-1.5">
                        <Button
                          onClick={() => navigate('/alerts')}
                          variant="secondary"
                          size="sm"
                          className="w-full"
                        >
                          View in Alert Center
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button
                      onClick={handleGenerateAlert}
                      variant="danger"
                      size="sm"
                      className="w-full"
                      icon={<BellRing className="w-3.5 h-3.5" />}
                    >
                      Generate Alert for Prediction
                    </Button>
                  )}

                  <Button
                    onClick={() => navigate(`/risk-map?case=${caseId}`)}
                    variant="outline"
                    size="sm"
                    className="w-full"
                    icon={<MapIcon className="w-3.5 h-3.5" />}
                  >
                    View Geographic Context on Map
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
