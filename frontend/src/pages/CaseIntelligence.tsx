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
  ArrowLeft,
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
  Upload,
  Download,
  FileCheck,
  FileSpreadsheet,
  FilePlus,
  Eye,
  Share2,
  Send,
  Check,
  XCircle,
  PlayCircle,
  Clock4,
  CheckCircle,
  ClipboardList,
} from 'lucide-react';
import { api } from '../services/api';
import {
  Complaint,
  Prediction,
  PredictionVersionSummary,
  Explanation,
  HotspotCluster,
  GraphData,
  AlertItem,
  EvidenceFileItem,
  EvidenceIntegrityResult,
  CaseHandoffItem,
  CreateHandoffPayload,
  InterventionPlanItem,
  InterventionPlanActionItem,
  ATMContextResponse,
  ATMContextItem,
} from '../types';
import { CashOutRiskMap } from '../maps/CashOutRiskMap';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { LoadingState } from '../components/common/LoadingState';
import { PredictionTiming } from '../components/PredictionTiming';
import { apiErrorMessage, formatIST, explainOperationalPriority, modelScore, predictionScoreNote } from '../utils/predictionDisplay';

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

  // Info popover state for contextual ⓘ buttons
  const [activeInfoPopover, setActiveInfoPopover] = useState<string | null>(null);
  const toggleInfoPopover = (key: string) => setActiveInfoPopover(prev => prev === key ? null : key);

  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [clusters, setClusters] = useState<HotspotCluster[]>([]);
  const [existingAlert, setExistingAlert] = useState<AlertItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningPrediction, setRunningPrediction] = useState(false);
  const [predictionError, setPredictionError] = useState<string | null>(null);
  const [caseError, setCaseError] = useState<string | null>(null);
  const [alertSuccess, setAlertSuccess] = useState<string | null>(null);
  const [predictionVersions, setPredictionVersions] = useState<PredictionVersionSummary[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [loadingVersion, setLoadingVersion] = useState(false);
  const [asOfInput, setAsOfInput] = useState<string>('');

  // Evidence & Report state (Phase 6)
  const [evidenceList, setEvidenceList] = useState<EvidenceFileItem[]>([]);
  const [loadingEvidence, setLoadingEvidence] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [replaceTarget, setReplaceTarget] = useState<EvidenceFileItem | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [evidenceSource, setEvidenceSource] = useState('OFFICER_UPLOAD');
  const [evidenceDesc, setEvidenceDesc] = useState('');
  const [uploadingEvidence, setUploadingEvidence] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [integrityResults, setIntegrityResults] = useState<Record<number, EvidenceIntegrityResult>>({});
  const [checkingIntegrityId, setCheckingIntegrityId] = useState<number | null>(null);
  const [exportingDossier, setExportingDossier] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // Cross-Jurisdiction Handoffs state (Phase 7)
  const [handoffsList, setHandoffsList] = useState<CaseHandoffItem[]>([]);
  const [createHandoffModalOpen, setCreateHandoffModalOpen] = useState(false);
  const [handoffActionModalOpen, setHandoffActionModalOpen] = useState(false);
  const [activeHandoffForAction, setActiveHandoffForAction] = useState<CaseHandoffItem | null>(null);
  const [handoffActionType, setHandoffActionType] = useState<'accept' | 'reject' | 'start' | 'complete' | 'cancel' | null>(null);
  const [actionReasonOrNotes, setActionReasonOrNotes] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [targetStateInput, setTargetStateInput] = useState('Maharashtra');
  const [targetDistrictInput, setTargetDistrictInput] = useState('MUMBAI');
  const [handoffPurposeInput, setHandoffPurposeInput] = useState('PHYSICAL_SURVEILLANCE');
  const [handoffScopeInput, setHandoffScopeInput] = useState<'METADATA_ONLY' | 'SPECIFIC_EVIDENCE' | 'ALL_EVIDENCE'>('METADATA_ONLY');
  const [selectedEvidenceIdsForHandoff, setSelectedEvidenceIdsForHandoff] = useState<number[]>([]);
  const [createHandoffLoading, setCreateHandoffLoading] = useState(false);
  const [createHandoffError, setCreateHandoffError] = useState<string | null>(null);

  // Phase 3: Intervention Orchestrator state
  const [interventionPlan, setInterventionPlan] = useState<InterventionPlanItem | null>(null);
  const [loadingInterventionPlan, setLoadingInterventionPlan] = useState(false);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [interventionError, setInterventionError] = useState<string | null>(null);
  const [updatingActionId, setUpdatingActionId] = useState<number | null>(null);

  // Phase 4: ATM / CSP Context state
  const [atmContext, setAtmContext] = useState<ATMContextResponse | null>(null);
  const [selectedAtmRank, setSelectedAtmRank] = useState<number>(1);
  const [loadingAtmContext, setLoadingAtmContext] = useState(false);
  const [atmContextError, setAtmContextError] = useState<string | null>(null);
  const [expandedAtmItemId, setExpandedAtmItemId] = useState<number | null>(null);

  const fetchATMContext = async (predId: number, rank: number) => {
    setLoadingAtmContext(true);
    setAtmContextError(null);
    try {
      const res = await api.getATMContext(predId, rank);
      setAtmContext(res);
    } catch (err: any) {
      console.error('Failed to load ATM/CSP context', err);
      setAtmContextError(apiErrorMessage(err, 'ATM/CSP context unavailable'));
      setAtmContext(null);
    } finally {
      setLoadingAtmContext(false);
    }
  };

  useEffect(() => {
    const predId = prediction?.prediction_id || (prediction as any)?.id;
    if (predId) {
      fetchATMContext(predId, selectedAtmRank);
    } else {
      setAtmContext(null);
    }
  }, [prediction?.prediction_id, (prediction as any)?.id, selectedAtmRank]);

  const handleGenerateInterventionPlan = async () => {
    if (!caseId) return;
    setGeneratingPlan(true);
    setInterventionError(null);
    try {
      const plan = await api.generateInterventionPlan(caseId);
      setInterventionPlan(plan);
    } catch (err: any) {
      setInterventionError(apiErrorMessage(err, 'Failed to generate intervention plan.'));
    } finally {
      setGeneratingPlan(false);
    }
  };

  const handleRefreshInterventionPlan = async () => {
    if (!interventionPlan) return;
    setGeneratingPlan(true);
    setInterventionError(null);
    try {
      const plan = await api.refreshInterventionPlan(interventionPlan.id);
      setInterventionPlan(plan);
    } catch (err: any) {
      setInterventionError(apiErrorMessage(err, 'Failed to refresh intervention plan.'));
    } finally {
      setGeneratingPlan(false);
    }
  };

  const handleUpdateActionStatus = async (actionId: number, newStatus: string) => {
    if (!interventionPlan) return;
    setUpdatingActionId(actionId);
    try {
      const updatedAction = await api.updateInterventionActionStatus(interventionPlan.id, actionId, newStatus);
      setInterventionPlan(prev => {
        if (!prev) return null;
        return {
          ...prev,
          actions: prev.actions.map(a => a.id === actionId ? updatedAction : a)
        };
      });
    } catch (err: any) {
      setInterventionError(apiErrorMessage(err, 'Failed to update action status.'));
    } finally {
      setUpdatingActionId(null);
    }
  };

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
    setSelectedVersionId(null);
    setInterventionPlan(null);
    setInterventionError(null);
    try {
      const [compResult, predResult, mapResult, alertsResult, graphResult, versionsResult, evidenceResult, handoffsResult, planResult] = await Promise.allSettled([
        api.getComplaint(caseId),
        api.getPrediction(caseId),
        api.getRiskMap(),
        api.getAlerts(),
        api.getGraph(caseId),
        api.getPredictionVersions(caseId),
        api.getComplaintEvidence(caseId),
        api.getComplaintHandoffs(caseId),
        api.getInterventionPlan(caseId),
      ]);
      if (version !== loadVersion.current) return;
      if (compResult.status === 'rejected') throw compResult.reason;
      const compData = compResult.value;
      const predData = predResult.status === 'fulfilled' ? predResult.value : null;
      if (predResult.status === 'rejected') setPredictionError(apiErrorMessage(predResult.reason, 'Could not load analysis. Retry below.'));
      setComplaint(compData);
      setPrediction(predData);
      if (alertsResult.status === 'fulfilled') {
        const found = (alertsResult.value || []).find((a: any) => a.complaint_id === caseId);
        setExistingAlert(found || null);
      }
      if (graphResult.status === 'fulfilled') setGraphData(graphResult.value);
      if (versionsResult.status === 'fulfilled') {
        const vList = Array.isArray(versionsResult.value) ? versionsResult.value : (versionsResult.value as any)?.versions || [];
        setPredictionVersions(vList);
        if (vList.length > 0) {
          setSelectedVersionId(vList[0].prediction_id);
        }
      }
      if (evidenceResult.status === 'fulfilled') setEvidenceList(evidenceResult.value);
      if (handoffsResult.status === 'fulfilled') setHandoffsList(handoffsResult.value);
      if (planResult.status === 'fulfilled') setInterventionPlan(planResult.value);
    } catch (err: any) {
      if (version === loadVersion.current) {
        setCaseError(apiErrorMessage(err, `Case ${caseId} not found.`));
      }
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
      const newPred = await api.runPrediction(caseId, asOfInput || undefined);
      setPrediction(newPred);
      const [newGraph, versionsRes] = await Promise.all([
        api.getGraph(caseId, asOfInput || undefined),
        api.getPredictionVersions(caseId),
      ]);
      setGraphData(newGraph);
      const vList = Array.isArray(versionsRes)
        ? versionsRes
        : (versionsRes as any)?.versions || [];
      setPredictionVersions(vList);
      setSelectedVersionId(null);
    } catch (err: any) {
      console.error('Error running predictive analysis', err);
      setPredictionError(apiErrorMessage(err, 'Predictive analysis could not be completed. Check case context or backend service.'));
    } finally {
      setRunningPrediction(false);
    }
  };

  const handleSelectVersion = async (v: PredictionVersionSummary) => {
    if (loadingVersion || !complaint) return;
    setLoadingVersion(true);
    setPredictionError(null);
    setExplanation(null);
    setAuditVerification(null);
    try {
      const pred = await api.getPredictionVersion(v.prediction_id);
      if (pred) {
        setPrediction(pred);
        setSelectedVersionId(v.prediction_id);
        const newGraph = await api.getGraph(caseId, v.analysis_as_of || undefined);
        setGraphData(newGraph);
      }
    } catch (err: any) {
      console.error('Failed to load historical prediction version', err);
      setPredictionError(apiErrorMessage(err, 'Failed to load selected prediction version.'));
    } finally {
      setLoadingVersion(false);
    }
  };

  const handleReturnToOperational = async () => {
    setSelectedVersionId(null);
    fetchCaseDetails();
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

  const handleUploadEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadError('Please select a valid file.');
      return;
    }
    setUploadingEvidence(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('source', evidenceSource);
      if (evidenceDesc) formData.append('description', evidenceDesc);

      if (replaceTarget) {
        await api.replaceComplaintEvidence(caseId, replaceTarget.id, formData);
      } else {
        await api.uploadComplaintEvidence(caseId, formData);
      }
      const updated = await api.getComplaintEvidence(caseId);
      setEvidenceList(updated);
      setUploadModalOpen(false);
      setSelectedFile(null);
      setReplaceTarget(null);
      setEvidenceDesc('');
    } catch (err: any) {
      setUploadError(apiErrorMessage(err, 'Failed to upload evidence.'));
    } finally {
      setUploadingEvidence(false);
    }
  };

  const handleCheckIntegrity = async (evId: number) => {
    setCheckingIntegrityId(evId);
    try {
      const res = await api.checkEvidenceIntegrity(evId, caseId);
      setIntegrityResults((prev) => ({ ...prev, [evId]: res }));
    } catch (err: any) {
      console.error('Integrity check failed', err);
    } finally {
      setCheckingIntegrityId(null);
    }
  };

  const handleExportReport = async () => {
    if (exportingDossier) return;
    setExportingDossier(true);
    setExportError(null);
    try {
      const response = await api.exportComplaintDossier(caseId);

      let filename = `dossier_${complaint?.complaint_number || caseId}.html`;
      const disposition =
        response.headers?.['content-disposition'] ||
        (response.headers as any)?.get?.('content-disposition');
      if (disposition && typeof disposition === 'string') {
        const match = disposition.match(/filename=["']?([^"';]+)["']?/i);
        if (match && match[1]) {
          filename = match[1].trim();
        }
      }

      const blob = new Blob(
        [response.data],
        { type: (response.headers?.['content-type'] as string) || 'text/html;charset=utf-8' }
      );

      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('Failed to export dossier', err);
      setExportError(
        apiErrorMessage(
          err,
          'Failed to export dossier report. Please ensure you have permission for this case.'
        )
      );
    } finally {
      setExportingDossier(false);
    }
  };

  const handleCreateHandoff = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateHandoffLoading(true);
    setCreateHandoffError(null);
    try {
      const predId = prediction?.prediction_id || (prediction as any)?.id;
      const predVer = (prediction as any)?.version_number || (prediction as any)?.version;
      const payload: CreateHandoffPayload = {
        target_state: targetStateInput,
        target_district: targetDistrictInput,
        purpose: handoffPurposeInput,
        evidence_scope: handoffScopeInput,
        shared_evidence_ids: handoffScopeInput === 'SPECIFIC_EVIDENCE' ? selectedEvidenceIdsForHandoff : undefined,
        prediction_id: predId,
        prediction_version: predVer,
        acknowledgement_hours: 24,
      };
      const created = await api.createComplaintHandoff(caseId, payload);
      setHandoffsList((prev) => [created, ...prev]);
      setCreateHandoffModalOpen(false);
    } catch (err: any) {
      console.error('Failed to create handoff', err);
      setCreateHandoffError(apiErrorMessage(err, 'Failed to initiate cross-jurisdiction handoff.'));
    } finally {
      setCreateHandoffLoading(false);
    }
  };

  const handleOpenActionModal = (handoff: CaseHandoffItem, action: 'accept' | 'reject' | 'start' | 'complete' | 'cancel') => {
    setActiveHandoffForAction(handoff);
    setHandoffActionType(action);
    setActionReasonOrNotes('');
    setActionError(null);
    setHandoffActionModalOpen(true);
  };

  const handleExecuteHandoffAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeHandoffForAction || !handoffActionType) return;
    setActionLoading(true);
    setActionError(null);
    try {
      let updated: CaseHandoffItem;
      if (handoffActionType === 'accept') {
        updated = await api.acceptHandoff(activeHandoffForAction.id);
      } else if (handoffActionType === 'reject') {
        if (!actionReasonOrNotes.trim()) {
          setActionError('Rejection reason is required.');
          setActionLoading(false);
          return;
        }
        updated = await api.rejectHandoff(activeHandoffForAction.id, actionReasonOrNotes);
      } else if (handoffActionType === 'start') {
        updated = await api.startHandoff(activeHandoffForAction.id);
      } else if (handoffActionType === 'complete') {
        updated = await api.completeHandoff(activeHandoffForAction.id, actionReasonOrNotes);
      } else if (handoffActionType === 'cancel') {
        if (!actionReasonOrNotes.trim()) {
          setActionError('Cancellation reason is required.');
          setActionLoading(false);
          return;
        }
        updated = await api.cancelHandoff(activeHandoffForAction.id, actionReasonOrNotes);
      } else {
        return;
      }
      setHandoffsList((prev) => prev.map((h) => (h.id === updated.id ? updated : h)));
      setHandoffActionModalOpen(false);
    } catch (err: any) {
      console.error('Handoff action failed', err);
      setActionError(apiErrorMessage(err, 'Handoff action failed.'));
    } finally {
      setActionLoading(false);
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
    <div className="p-8 max-w-xl mx-auto my-12 bg-white rounded-xl border border-slate-200 shadow-sm text-center space-y-4">
      <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-500">
        <ShieldAlert className="w-6 h-6" />
      </div>
      <div>
        <h3 className="text-base font-bold text-slate-800">Complaint Not Found or Inaccessible</h3>
        <p className="text-xs text-slate-500 mt-1">
          {caseError || 'The requested case is unavailable, out of jurisdiction, or does not exist.'}
        </p>
      </div>
      <div className="flex items-center justify-center gap-3 pt-2">
        <button
          onClick={() => navigate('/complaints')}
          className="px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs shadow-sm transition-colors"
        >
          Back to Complaints
        </button>
        <button
          onClick={() => navigate('/dashboard')}
          className="px-4 py-2 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs transition-colors"
        >
          Dashboard
        </button>
        <Button onClick={fetchCaseDetails} variant="secondary" size="sm">
          Retry
        </Button>
      </div>
    </div>
  );

  const isTrained = prediction?.prediction_mode === 'trained_ml';
  const isDemo = prediction?.prediction_mode === 'deterministic_demo';
  const topLocations = [...(prediction?.top_locations || [])].sort((a, b) => a.rank - b.rank).slice(0, 3);
  const rank1Location = topLocations[0] || null;

  // Context provenance mapping
  const provenanceLabel =
    complaint.provenance_mode === 'CONTROLLED_SYNTHETIC_DEMO'
      ? 'Controlled Synthetic Transaction Trail'
      : complaint.provenance_mode === 'LINKED_SYNTHETIC_SCENARIO'
      ? 'Linked Investigation Scenario'
      : complaint.provenance_mode === 'HYBRID_CONTEXT'
      ? 'Hybrid Context'
      : complaint.provenance_mode === 'DIRECT_OFFICER_INPUT'
      ? 'Direct Officer-Reported Transaction'
      : 'Controlled Synthetic Transaction Trail';

  const nodeCount = graphData?.metrics?.node_count ?? (complaint.linked_account_count || 2);
  const transferCount = graphData?.metrics?.edge_count ?? (complaint.available_transaction_count || 1);

  // Close any open popover when clicking outside
  const handlePageClick = () => { if (activeInfoPopover) setActiveInfoPopover(null); };

  return (
    <div className="space-y-5 pb-12 font-sans" onClick={handlePageClick}>
      {/* ===================================================================== */}
      {/* BACK TO COMPLAINTS NAVIGATION */}
      {/* ===================================================================== */}
      <div className="flex items-center">
        <button
          id="btn-back-to-complaints"
          onClick={(e) => { e.stopPropagation(); navigate('/complaints'); }}
          className="flex items-center space-x-1.5 text-xs text-slate-500 hover:text-slate-800 transition-colors group py-1 pr-2"
        >
          <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
          <span className="font-medium">Back to Complaints</span>
        </button>
      </div>

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

            <Button
              onClick={handleExportReport}
              disabled={exportingDossier}
              variant="outline"
              size="sm"
              icon={<FileText className={`w-3.5 h-3.5 text-blue-600 ${exportingDossier ? 'animate-spin' : ''}`} />}
            >
              {exportingDossier ? 'Exporting...' : 'Export Dossier'}
            </Button>
          </div>
        </div>

        {exportError && (
          <div className="mt-3.5 p-3 rounded-md bg-red-50 border border-red-200 text-red-800 text-xs flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            <span className="font-medium">{exportError}</span>
          </div>
        )}

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
            {complaint.incident_time ? formatIST(complaint.incident_time) : 'Not available'}
          </div>
          <span className="text-[10px] text-slate-400">Complainant timestamp</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Reported Time
          </span>
          <div className="text-xs font-semibold text-slate-800 mt-0.5">
            {complaint.reported_at ? formatIST(complaint.reported_at) : 'Not available'}
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
                {complaint.transaction_time ? formatIST(complaint.transaction_time) : 'Not available'}
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
                  ? formatIST(complaint.transaction_time)
                  : complaint.incident_time
                  ? formatIST(complaint.incident_time)
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
          {/* HISTORICAL INTELLIGENCE REPLAY WARNING BANNER */}
          {(prediction?.analysis_purpose === 'HISTORICAL_REPLAY' || (selectedVersionId && selectedVersionId !== predictionVersions[predictionVersions.length - 1]?.prediction_id)) && (
            <div className="p-4 rounded-lg bg-amber-50 border border-amber-300 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-amber-900 shadow-sm">
              <div className="flex items-start sm:items-center space-x-3">
                <Clock className="w-5 h-5 text-amber-600 shrink-0 mt-0.5 sm:mt-0" />
                <div>
                  <div className="text-xs font-bold uppercase tracking-wider text-amber-800 flex items-center space-x-2">
                    <span>Viewing Historical Intelligence Replay</span>
                    <Badge variant="warning">Version {prediction?.version_number || 'Historical'}</Badge>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-200 text-amber-800 font-semibold">HISTORICAL_REPLAY</span>
                  </div>
                  <p className="text-xs text-amber-700 mt-0.5">
                    Point-in-time snapshot evaluated as of{' '}
                    <strong>{prediction?.analysis_as_of ? formatIST(prediction.analysis_as_of) : 'Historical Cutoff'}</strong>.
                    This is an immutable audit replay and does not represent live operational posture.
                  </p>
                </div>
              </div>
              <Button
                onClick={handleReturnToOperational}
                variant="outline"
                size="sm"
                icon={<ArrowRight className="w-3.5 h-3.5" />}
              >
                Return to Operational Latest
              </Button>
            </div>
          )}

          {/* PREDICTION VERSION HISTORY SELECTOR */}
          {predictionVersions.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-slate-100">
                <div className="flex items-center space-x-2">
                  <Layers className="w-4 h-4 text-indigo-600" />
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Prediction Version History ({predictionVersions.length})
                  </h3>
                </div>
                <span className="text-[11px] text-slate-500">
                  Chronological immutable prediction audit trail
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5">
                {predictionVersions.map((v) => {
                  const isSelected = (selectedVersionId === v.prediction_id) || (!selectedVersionId && v.prediction_id === (prediction?.prediction_id || (prediction as any)?.id));
                  const isOp = (v.analysis_purpose || (v.analysis_as_of ? 'HISTORICAL_REPLAY' : 'OPERATIONAL')) === 'OPERATIONAL';

                  return (
                    <button
                      key={v.prediction_id}
                      type="button"
                      onClick={() => handleSelectVersion(v)}
                      disabled={loadingVersion}
                      className={`p-3 rounded-lg border text-left transition-all relative ${
                        isSelected
                          ? 'border-indigo-600 bg-indigo-50/60 shadow-sm ring-1 ring-indigo-600'
                          : 'border-slate-200 hover:border-slate-300 bg-white'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono text-xs font-bold text-slate-900">
                          Version {v.version_number}
                        </span>
                        <span
                          className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                            isOp
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                              : 'bg-purple-100 text-purple-800 border border-purple-200'
                          }`}
                        >
                          {isOp ? 'OPERATIONAL' : 'HISTORICAL_REPLAY'}
                        </span>
                      </div>

                      <div className="text-xs font-medium text-slate-800 truncate" title={v.primary_location_name || 'Primary Cluster'}>
                        {v.primary_location_name || 'Cash-Out Location'}
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-slate-500 mt-1.5 pt-1.5 border-t border-slate-100">
                        <span>Risk: <strong className="text-slate-700">{v.risk_level}</strong></span>
                        <span>{v.created_at ? formatIST(v.created_at) : ''}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div className="flex items-center space-x-2">
                <ShieldAlert className="w-4 h-4 text-slate-600" />
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Predictive Cash-Out Assessment
                </h3>
              </div>
              <div className="flex items-center space-x-2 text-xs text-slate-500">
                <span className="font-semibold text-slate-700">v{prediction.version_number || 1}</span>
                <span>•</span>
                <span
                  className={`text-[10px] font-semibold px-1.5 py-0.2 rounded ${
                    (prediction.analysis_purpose || (prediction.analysis_as_of ? 'HISTORICAL_REPLAY' : 'OPERATIONAL')) === 'OPERATIONAL'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-purple-100 text-purple-800'
                  }`}
                >
                  {prediction.analysis_purpose || (prediction.analysis_as_of ? 'HISTORICAL_REPLAY' : 'OPERATIONAL')}
                </span>
                <span>•</span>
                <span>Prediction #{prediction.prediction_id || prediction.id}</span>
                <span>•</span>
                <span>{isTrained ? 'Trained ML' : isDemo ? 'Deterministic Demo' : 'Operational'}</span>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left 2/3: Top Predicted Cash-Out Zones */}
              <div className="lg:col-span-8 space-y-4">
                {/* Primary Predicted Zone Banner (B9 & Section 21) */}
                {rank1Location && (
                  <div className="p-4 rounded-lg bg-[#F0F6F6] border border-[#9DBEBB]/60">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="text-[11px] font-semibold uppercase text-[#468189] tracking-wider">
                        #1 PRIMARY PREDICTED ZONE
                      </span>
                      <span className={`text-[10px] px-2 py-0.5 rounded font-medium border ${
                        rank1Location.risk_level === 'CRITICAL'
                          ? 'bg-red-50 text-red-700 border-red-200'
                          : rank1Location.risk_level === 'HIGH'
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : 'bg-[#F0F6F6] text-[#468189] border-[#9DBEBB]'
                      }`}>
                        {rank1Location.risk_level} Operational Priority
                      </span>
                    </div>

                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div>
                        <div className="text-base font-bold text-[#031926]">
                          {rank1Location.cluster_name || rank1Location.location_name}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                          Distance from complaint origin: {rank1Location.distance_km} km
                        </div>
                      </div>

                      <div className="text-left sm:text-right">
                        <div className="text-[11px] text-slate-500">Operational Priority</div>
                        <div className="text-sm font-bold text-[#031926]">
                          Rank #1 Candidate Cash-Out Zone
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Top-3 Location Table (Section 21) */}
                <div>
                  <div className="flex items-center space-x-1.5">
                    <div className="text-xs font-semibold text-[#031926] uppercase tracking-wider">
                      Ranked Cash-Out Candidate Zones (Delhi Pilot)
                    </div>
                    <div className="relative" onClick={(e) => e.stopPropagation()}>
                      <button
                        id="info-btn-top3"
                        onClick={() => toggleInfoPopover('top3')}
                        className="text-slate-400 hover:text-blue-600 transition-colors"
                        title="About candidate zones"
                      >
                        <Info className="w-3.5 h-3.5" />
                      </button>
                      {activeInfoPopover === 'top3' && (
                        <div className="absolute left-0 top-5 z-30 w-64 p-3 bg-white border border-slate-200 rounded-lg shadow-lg text-[11px] text-slate-600 leading-relaxed">
                          <p className="font-semibold text-slate-800 mb-1">Top-3 Candidate Cash-Out Zones</p>
                          <p>These are ranked predictive candidate locations, not confirmed withdrawal locations. Scores are relative ranking metrics used to compare candidate zones for this complaint — they are not verified real-world probabilities.</p>
                        </div>
                      )}
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-500 leading-relaxed mt-1 mb-2">
                    Scores are relative model ranking scores used to compare candidate cash-out zones. They are not literal probabilities of withdrawal and do not need to sum to 100%.
                  </p>

                  {/* Desktop Table View (>= md) */}
                  <div className="hidden md:block overflow-x-auto border border-[#DCE5F0] rounded-md">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-[#F8FAFC] border-b border-[#DCE5F0] text-slate-700 font-semibold">
                          <th className="py-2.5 px-3">Rank</th>
                          <th className="py-2.5 px-3">Candidate Zone</th>
                          <th
                            className="py-2.5 px-3 cursor-help"
                            title="Relative ranking score generated by the trained ML model. Higher values indicate stronger ranking compared with other candidate zones for this complaint."
                          >
                            <div className="flex items-center space-x-1">
                              <span>Model ranking score</span>
                              <Info className="w-3 h-3 text-slate-400" />
                            </div>
                          </th>
                          <th
                            className="py-2.5 px-3 text-center cursor-help"
                            title="Action urgency derived from disputed amount bands, window urgency, and incident recency. High priority can legitimately coexist with low candidate ranking scores."
                          >
                            <div className="flex items-center justify-center space-x-1">
                              <span>Operational Priority</span>
                              <Info className="w-3 h-3 text-slate-400" />
                            </div>
                          </th>
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
                            <td
                              className="py-2.5 px-3 font-semibold text-blue-700 font-mono cursor-help"
                              title="Relative ranking score generated by the trained ML model. Higher values indicate stronger ranking compared with other candidate zones for this complaint."
                            >
                              {modelScore(loc)}
                            </td>
                            <td className="py-2.5 px-3 text-center">
                              <span
                                className={`inline-block text-[10px] px-2 py-0.5 rounded font-medium border cursor-help ${
                                  loc.risk_level === 'CRITICAL'
                                    ? 'bg-red-50 text-red-700 border-red-200'
                                    : loc.risk_level === 'HIGH'
                                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                                    : 'bg-blue-50 text-blue-700 border-blue-200'
                                }`}
                                title={explainOperationalPriority(loc.operational_priority || loc.risk_level, complaint.disputed_amount ?? complaint.amount)}
                              >
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
                        {loc.zone && (
                          <div className="flex justify-between items-center text-slate-500 text-[11px]">
                            <span>Zone / District:</span>
                            <span className="text-slate-800 font-medium">{loc.zone}</span>
                          </div>
                        )}
                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span>Distance: <strong className="text-slate-700 font-mono">{loc.distance_km} km</strong></span>
                          <span
                            className="flex items-center space-x-1 cursor-help"
                            title="Relative ranking score generated by the trained ML model. Higher values indicate stronger ranking compared with other candidate zones for this complaint."
                          >
                            <span>Model ranking score:</span>
                            <strong className="text-blue-700 font-mono">{modelScore(loc)}</strong>
                            <Info className="w-3 h-3 text-slate-400" />
                          </span>
                        </div>
                        <div className="flex justify-between items-center text-slate-500 text-[11px]">
                          <span>Operational Priority:</span>
                          <span
                            className="text-slate-700 font-semibold cursor-help"
                            title={explainOperationalPriority(loc.operational_priority || loc.risk_level, complaint.disputed_amount ?? complaint.amount)}
                          >
                            {loc.risk_level || (loc.rank === 1 ? 'HIGH' : loc.rank === 2 ? 'MEDIUM' : 'LOW')}
                          </span>
                        </div>
                        <div className="text-[10px] text-slate-500 italic pt-1 border-t border-slate-200/60">
                          Ranked #{loc.rank} by {prediction.model_version || 'Location V7-compat'} for the current complaint context.
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

                {/* ==================================================================== */}
                {/* PHASE 4: ATM / CSP CONTEXTUAL OPERATIONAL PRIORITIZATION */}
                {/* ==================================================================== */}
                <div className="p-4 bg-white rounded-lg border border-[#DCE5F0] space-y-3.5 shadow-xs">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-[#DCE5F0]">
                    <div className="flex items-center space-x-2">
                      <Building2 className="w-4 h-4 text-[#468189] shrink-0" />
                      <div>
                        <div className="flex items-center space-x-1.5">
                          <h4 className="text-xs font-bold text-[#031926] uppercase">
                            ATM / CSP CONTEXT
                          </h4>
                          <div className="relative" onClick={(e) => e.stopPropagation()}>
                            <button
                              id="info-btn-atm-context"
                              onClick={() => toggleInfoPopover('atm_context')}
                              className="text-slate-400 hover:text-blue-600 transition-colors"
                            >
                              <Info className="w-3.5 h-3.5" />
                            </button>
                            {activeInfoPopover === 'atm_context' && (
                              <div className="absolute left-0 top-5 z-30 w-72 p-3 bg-white border border-slate-200 rounded-lg shadow-lg text-[11px] text-slate-600 leading-relaxed">
                                <p className="font-semibold text-slate-800 mb-1">ATM/CSP Operational Context</p>
                                <p>ATM/CSP prioritization is an operational context layer inside the model-predicted zone. It does not represent a confirmed withdrawal location.</p>
                              </div>
                            )}
                          </div>
                        </div>
                        <p className="text-[11px] text-slate-500">
                          Secondary contextual operational shortlist for predicted candidate cash-out zone.
                        </p>
                      </div>
                    </div>

                    {/* Candidate Zone Rank Selector (#1, #2, #3) */}
                    {topLocations.length > 0 && (
                      <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
                        <span className="text-[10px] font-bold text-slate-500 uppercase px-1.5">Candidate Rank:</span>
                        {topLocations.map((loc) => {
                          const isSelected = selectedAtmRank === loc.rank;
                          return (
                            <button
                              key={`atm-rank-btn-${loc.rank}`}
                              type="button"
                              onClick={() => setSelectedAtmRank(loc.rank)}
                              className={`px-2.5 py-1 rounded-md text-xs font-bold transition-all ${
                                isSelected
                                  ? 'bg-blue-600 text-white shadow-xs'
                                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/70'
                              }`}
                            >
                              #{loc.rank} {loc.cluster_name || loc.location_name}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Active Candidate Zone Summary Header */}
                  {atmContext && (
                    <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-slate-900">
                            Candidate: #{atmContext.candidate_rank} {atmContext.candidate_zone}
                          </span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-blue-100 text-blue-800 border border-blue-200">
                            Model Prob: {(atmContext.candidate_probability * 100).toFixed(2)}%
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          {atmContext.items.length} contextual cash-out points evaluated via {atmContext.context_method}
                        </p>
                      </div>
                      <Button
                        onClick={() => navigate(`/risk-map?case=${caseId}&rank=${selectedAtmRank}`)}
                        variant="outline"
                        size="sm"
                        icon={<MapIcon className="w-3.5 h-3.5 text-blue-600" />}
                      >
                        View on Risk Map
                      </Button>
                    </div>
                  )}

                  {/* Disclaimer Banner */}
                  <div className="p-2.5 bg-amber-50/70 rounded-md border border-amber-200 text-[11px] text-amber-900 flex items-start space-x-2">
                    <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <span className="leading-relaxed">
                      ATM/CSP prioritization is an operational context layer inside the model-predicted zone. It does not represent a confirmed withdrawal location.
                    </span>
                  </div>

                  {/* Content / Loading / Error States */}
                  {loadingAtmContext ? (
                    <div className="py-6 text-center text-xs text-slate-500">
                      <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-1 text-slate-400" />
                      Loading contextual cash-out points...
                    </div>
                  ) : atmContextError ? (
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs text-slate-600 text-center">
                      {atmContextError}
                    </div>
                  ) : atmContext && atmContext.items.length > 0 ? (
                    <div className="space-y-2">
                      {atmContext.items.map((item) => {
                        const isExpanded = expandedAtmItemId === item.id;
                        const isHigh = item.priority_band === 'HIGH';
                        const isMedium = item.priority_band === 'MEDIUM';

                        return (
                          <div
                            key={item.id}
                            className="p-3 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-all text-xs space-y-2"
                          >
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                              <div className="space-y-0.5">
                                <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                                  <span className="font-bold text-slate-900 text-sm">{item.name}</span>
                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200 font-mono">
                                    {item.type}
                                  </span>
                                  <span
                                    className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                                      isHigh
                                        ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                        : isMedium
                                        ? 'bg-amber-100 text-amber-800 border border-amber-300'
                                        : 'bg-slate-100 text-slate-700 border border-slate-300'
                                    }`}
                                  >
                                    {item.priority_band} PRIORITY
                                  </span>
                                  {item.bank_match && (
                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-800 border border-indigo-200">
                                      Bank Context Match
                                    </span>
                                  )}
                                </div>
                                <div className="text-slate-500 text-[11px] flex items-center space-x-2 flex-wrap">
                                  <span>Bank: <strong className="text-slate-700">{item.bank_name}</strong></span>
                                  <span>•</span>
                                  <span>Distance: <strong className="text-slate-700 font-mono">{item.distance_km} km</strong></span>
                                  <span>•</span>
                                  <span>Score: <strong className="text-blue-700 font-mono">{item.context_priority_score} / 100</strong></span>
                                </div>
                              </div>

                              <div className="flex items-center space-x-2 self-start sm:self-auto">
                                <span className="text-[10px] font-mono text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200">
                                  {item.source}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => setExpandedAtmItemId(isExpanded ? null : item.id)}
                                  className="text-xs text-blue-600 hover:text-blue-800 font-semibold flex items-center space-x-1"
                                >
                                  <span>{isExpanded ? 'Hide Details' : 'Why Prioritized?'}</span>
                                </button>
                              </div>
                            </div>

                            {/* Expandable Reasoning & Breakdown */}
                            {isExpanded && (
                              <div className="pt-2 border-t border-slate-100 space-y-1.5 text-[11px] text-slate-600 bg-slate-50/70 p-2.5 rounded-md">
                                <div className="font-bold text-slate-700 text-[10px] uppercase tracking-wider">
                                  Operational Context Justification:
                                </div>
                                {item.reasons && item.reasons.length > 0 ? (
                                  <ul className="space-y-1 pl-1">
                                    {item.reasons.map((r, ri) => (
                                      <li key={ri} className="flex items-start space-x-1.5">
                                        <span className="text-blue-500 font-bold">•</span>
                                        <span>{r}</span>
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  <p className="italic text-slate-500">Located within candidate zone operational perimeter.</p>
                                )}
                                {item.address && (
                                  <div className="pt-1 text-[10px] text-slate-500 font-mono border-t border-slate-200/60">
                                    Address: {item.address}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs text-slate-500 italic text-center">
                      ATM/CSP context unavailable for this candidate zone.
                    </div>
                  )}
                </div>

                {/* On-Demand LIME Explainability Card */}
                <div className="p-4 bg-white rounded-lg border border-[#DCE5F0] space-y-3 shadow-xs">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-[#DCE5F0]">
                    <div className="flex items-center space-x-2">
                      <Sparkles className="w-4 h-4 text-[#468189] shrink-0" />
                      <div>
                        <div className="flex items-center space-x-1.5">
                          <h4 className="text-xs font-bold text-[#031926] uppercase">
                            Model Attribution & Local Explainability (LIME)
                          </h4>
                          <div className="relative" onClick={(e) => e.stopPropagation()}>
                            <button
                              id="info-btn-lime"
                              onClick={() => toggleInfoPopover('lime')}
                              className="text-slate-400 hover:text-blue-600 transition-colors"
                            >
                              <Info className="w-3 h-3" />
                            </button>
                            {activeInfoPopover === 'lime' && (
                              <div className="absolute left-0 top-4 z-30 w-72 p-3 bg-white border border-slate-200 rounded-lg shadow-lg text-[11px] text-slate-600 leading-relaxed">
                                <p className="font-semibold text-slate-800 mb-1">About LIME Explainability</p>
                                <p>LIME is a local surrogate explanation showing which features locally influenced this specific candidate ranking. It does not establish causation and does not modify the official prediction or probabilities.</p>
                              </div>
                            )}
                          </div>
                        </div>
                        <p className="text-[11px] text-slate-500">
                          Local factors influencing this prediction without altering candidate ranking.
                        </p>
                      </div>
                    </div>
                    <Button
                      onClick={handleExplainPrediction}
                      disabled={
                        loadingExplanation ||
                        (explanation?.explanation_status === 'UNAVAILABLE' && !!explanation.is_legacy_prediction) ||
                        (explanation?.explanation_status === 'UNAVAILABLE' && explanation.reason === 'CALIBRATOR_HASH_MISMATCH')
                      }
                      variant="outline"
                      size="sm"
                      className="shrink-0 text-xs"
                      icon={<Cpu className="w-3.5 h-3.5 text-blue-600" />}
                    >
                      {loadingExplanation
                        ? 'Computing LIME...'
                        : explanation?.explanation_status === 'UNAVAILABLE' && explanation.reason === 'CALIBRATOR_HASH_MISMATCH'
                        ? 'Unavailable (Historical Artifact)'
                        : explanation?.explanation_status === 'UNAVAILABLE' && explanation.is_legacy_prediction
                        ? 'Unavailable (Legacy Prediction)'
                        : explanation
                        ? 'Re-explain (LIME)'
                        : 'Explain Prediction'}
                    </Button>
                  </div>

                  {explanationError && (
                    <div className="p-2.5 bg-rose-50 border border-rose-200 rounded text-xs text-rose-800 flex items-center space-x-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
                      <span>{explanationError}</span>
                    </div>
                  )}

                  {/* Unavailable Explanation Banner — CALIBRATOR_HASH_MISMATCH */}
                  {explanation && explanation.explanation_status === 'UNAVAILABLE' && explanation.reason === 'CALIBRATOR_HASH_MISMATCH' && (
                    <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg text-xs space-y-3">
                      <div className="flex items-center space-x-2">
                        <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                        <span className="font-bold text-amber-900">Historical Prediction</span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-200/70 text-amber-900">V7 Artifact</span>
                      </div>
                      <p className="text-amber-800 leading-relaxed">
                        This prediction was generated using an earlier verified model/calibrator artifact.
                        CyberShield will not generate a LIME explanation using different runtime artifacts
                        because that could produce a misleading explanation.
                      </p>
                      <Button
                        onClick={handleRunPrediction}
                        disabled={runningPrediction}
                        variant="primary"
                        size="sm"
                        icon={<Cpu className={`w-3.5 h-3.5 ${runningPrediction ? 'animate-spin' : ''}`} />}
                      >
                        {runningPrediction ? 'Running V8 Analysis...' : 'Run Current V8 Analysis'}
                      </Button>
                      <details className="text-[10px] text-amber-700 cursor-pointer">
                        <summary className="font-semibold hover:text-amber-900 select-none">ⓘ Technical Details</summary>
                        <div className="mt-2 p-2 bg-amber-100/60 rounded border border-amber-200/80 space-y-1 font-mono">
                          <div>Historical model: <span className="font-semibold">{explanation.model_version || explanation.location_model_version || 'cashout-location-xgb-v7-compat'}</span></div>
                          {explanation.snapshot_calibrator_hash_prefix && (
                            <div>Snapshot calibrator: <span className="font-semibold">{explanation.snapshot_calibrator_hash_prefix}</span></div>
                          )}
                          {explanation.runtime_calibrator_hash_prefix && (
                            <div>Runtime calibrator: <span className="font-semibold">{explanation.runtime_calibrator_hash_prefix}</span></div>
                          )}
                          <div className="pt-1 text-[9px] text-amber-600">Explanation refused to prevent misaligned probability scaling. Historical predictions remain tied to the exact artifacts used at prediction time.</div>
                        </div>
                      </details>
                    </div>
                  )}

                  {/* Unavailable Explanation Banner — Legacy (no snapshot) */}
                  {explanation && explanation.explanation_status === 'UNAVAILABLE' && explanation.is_legacy_prediction && (
                    <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg text-xs space-y-3">
                      <div className="flex items-center space-x-2">
                        <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                        <span className="font-bold text-amber-900">Historical Snapshot Unavailable</span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-200/70 text-amber-900">No Snapshot</span>
                      </div>
                      <p className="text-amber-800 leading-relaxed">
                        This historical prediction does not have an immutable feature snapshot attached.
                        CyberShield does not reconstruct feature inputs from current database state to prevent evidence drift.
                      </p>
                      <Button
                        onClick={handleRunPrediction}
                        disabled={runningPrediction}
                        variant="primary"
                        size="sm"
                        icon={<Cpu className={`w-3.5 h-3.5 ${runningPrediction ? 'animate-spin' : ''}`} />}
                      >
                        {runningPrediction ? 'Running V8 Analysis...' : 'Run Current V8 Analysis'}
                      </Button>
                    </div>
                  )}

                  {/* Unavailable Explanation Banner — Other/Generic */}
                  {explanation && explanation.explanation_status === 'UNAVAILABLE' && !explanation.is_legacy_prediction && explanation.reason !== 'CALIBRATOR_HASH_MISMATCH' && (
                    <div className="p-3 bg-amber-50/80 border border-amber-200 rounded-lg text-xs space-y-2">
                      <div className="flex items-center space-x-2 font-semibold text-amber-900">
                        <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                        <span>LIME Explanation Unavailable</span>
                      </div>
                      <p className="text-amber-800 leading-relaxed">
                        {explanation.message || 'LIME explanation could not be generated for this prediction.'}
                      </p>
                      {explanation.actionable_next_step && (
                        <div className="pt-1 border-t border-amber-200/60 text-[11px] text-amber-900 flex items-start space-x-1.5">
                          <span className="font-semibold">Next Step:</span>
                          <span>{explanation.actionable_next_step}</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Render Available or Low-Fidelity Explanations */}
                  {explanation && explanation.top3_explanations && explanation.top3_explanations.length > 0 ? (
                    <div className="space-y-3 pt-1">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 text-xs p-2.5 bg-slate-50 rounded border border-slate-200">
                        <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                          <span className="text-slate-600 font-medium">Surrogate Linear Fidelity:</span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            explanation.overall_fidelity_status === 'HIGH_FIDELITY'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : explanation.overall_fidelity_status === 'MODERATE_FIDELITY'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}>
                            {explanation.overall_fidelity_status?.replace('_', ' ')} (Mean R² = {explanation.mean_local_fidelity_r2 !== undefined && explanation.mean_local_fidelity_r2 !== null ? explanation.mean_local_fidelity_r2.toFixed(4) : 'N/A'})
                          </span>
                          {explanation.snapshot_provenance && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
                              Immutable Snapshot
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] text-slate-500 font-mono">
                          Method: {explanation.explanation_method || 'LIME'} Tabular
                        </span>
                      </div>

                      {explanation.overall_fidelity_status === 'LOW_FIDELITY' && (
                        <div className="p-2 bg-amber-50/70 border border-amber-200 rounded text-[11px] text-amber-800 flex items-start space-x-1.5">
                          <Info className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
                          <span>
                            <strong>Low Surrogate Fidelity:</strong> The local surrogate R² indicates non-linear decision boundaries around this candidate. Signals reflect local linear trends rather than global exact rules.
                          </span>
                        </div>
                      )}

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                        {explanation.top3_explanations.map((cand) => (
                          <div
                            key={`lime-card-${cand.rank}`}
                            className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-2 flex flex-col justify-between"
                          >
                            <div className="space-y-1.5">
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
                              <div className="text-[11px] text-slate-500 flex justify-between font-mono bg-white p-1.5 rounded border border-slate-100">
                                <span>Official: <strong>{(cand.official_score * 100).toFixed(1)}%</strong></span>
                                <span>LIME: <strong>{(cand.lime_local_prediction * 100).toFixed(1)}%</strong></span>
                                <span>R²: <strong>{cand.local_fidelity_r2 !== undefined ? cand.local_fidelity_r2.toFixed(2) : 'N/A'}</strong></span>
                              </div>

                              {cand.summary_statement && (
                                <p className="text-[11px] text-slate-600 italic bg-blue-50/50 p-1.5 rounded">
                                  {cand.summary_statement}
                                </p>
                              )}

                              {/* Top Supporting Factors (Positive) */}
                              {cand.positive_contributions && cand.positive_contributions.length > 0 && (
                                <div className="space-y-1.5 pt-1 border-t border-slate-200">
                                  <span className="text-[10px] font-bold text-emerald-700 uppercase block tracking-wider">
                                    Top Supporting Factors:
                                  </span>
                                  {cand.positive_contributions.slice(0, 3).map((c, i) => (
                                    <div key={i} className="text-[10px] bg-white p-1.5 rounded border border-emerald-100 space-y-0.5">
                                      <div className="flex justify-between items-baseline">
                                        <span className="font-semibold text-slate-800 truncate pr-1" title={c.friendly_label || c.feature_name}>
                                          {c.friendly_label || c.feature_name}
                                        </span>
                                        <span className="font-mono text-emerald-700 font-bold shrink-0">
                                          {c.contribution_share !== undefined ? `+${c.contribution_share}%` : `+${c.weight.toFixed(4)}`}
                                        </span>
                                      </div>
                                      {c.formatted_value && (
                                        <div className="text-[10px] text-slate-600 font-mono">
                                          Observed: {c.formatted_value}
                                        </div>
                                      )}
                                      {c.honest_explanation && (
                                        <div className="text-[9px] text-slate-500 leading-tight">
                                          {c.honest_explanation}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}

                              {/* Top Down-weighting Factors (Negative) */}
                              {cand.negative_contributions && cand.negative_contributions.length > 0 && (
                                <div className="space-y-1.5 pt-1 border-t border-slate-200">
                                  <span className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">
                                    Top Down-weighting Factors:
                                  </span>
                                  {cand.negative_contributions.slice(0, 2).map((c, i) => (
                                    <div key={i} className="text-[10px] bg-white p-1.5 rounded border border-slate-200 space-y-0.5">
                                      <div className="flex justify-between items-baseline">
                                        <span className="font-semibold text-slate-700 truncate pr-1" title={c.friendly_label || c.feature_name}>
                                          {c.friendly_label || c.feature_name}
                                        </span>
                                        <span className="font-mono text-slate-600 font-bold shrink-0">
                                          {c.contribution_share !== undefined ? `-${c.contribution_share}%` : `${c.weight.toFixed(4)}`}
                                        </span>
                                      </div>
                                      {c.formatted_value && (
                                        <div className="text-[10px] text-slate-500 font-mono">
                                          Observed: {c.formatted_value}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>

                            {/* Expandable Technical Surrogate Details */}
                            <details className="mt-2 pt-2 border-t border-slate-200 text-[10px] text-slate-500 cursor-pointer">
                              <summary className="font-medium text-blue-600 hover:text-blue-800">
                                Technical Surrogate Details
                              </summary>
                              <div className="mt-1.5 space-y-1 bg-white p-2 rounded border border-slate-100 font-mono text-[9px]">
                                <div>Cluster ID: {cand.cluster_id}</div>
                                <div>Abs Error: {cand.absolute_approximation_error.toFixed(4)}</div>
                                <div className="pt-1 text-slate-400">Rules & Raw Weights:</div>
                                {[...cand.positive_contributions, ...cand.negative_contributions].slice(0, 5).map((ct, idx) => (
                                  <div key={idx} className="truncate" title={ct.rule}>
                                    • {ct.feature_name}: {ct.weight > 0 ? '+' : ''}{ct.weight.toFixed(4)} ({ct.rule})
                                  </div>
                                ))}
                              </div>
                            </details>
                          </div>
                        ))}
                      </div>

                      <div className="p-2.5 bg-blue-50/60 rounded border border-blue-100 text-[11px] text-slate-600 flex items-start space-x-2">
                        <Info className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                        <div className="space-y-1">
                          {explanation.narrative && (
                            <p className="font-medium text-slate-700">
                              {explanation.narrative}
                            </p>
                          )}
                          <p className="leading-relaxed">
                            {explanation.disclaimer || 'LIME provides a local approximation of model behavior and does not prove causality or criminal activity.'}
                          </p>
                        </div>
                      </div>
                    </div>
                  ) : !explanation || explanation.explanation_status !== 'UNAVAILABLE' ? (
                    <p className="text-[11px] text-slate-500 italic">
                      Click &quot;Explain Prediction&quot; to compute feature attributions on demand without blocking standard workflow.
                    </p>
                  ) : null}
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
                    {predictionScoreNote(prediction)} These scores rank candidate locations and are not verified real-world probabilities. Rankings do not guarantee that activity will occur at a particular location.
                  </p>
                </div>
              </div>

              {/* Right 1/3: Timing + Model Provenance + Action Panel */}
              <div className="lg:col-span-4 space-y-4">
                {/* Time Prediction Card (B11) */}
                <div className="p-4 bg-[#FDFBF7] rounded-lg border border-[#F4E9CD] space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span className="font-semibold uppercase text-[#031926] flex items-center space-x-1.5">
                      <Clock className="w-3.5 h-3.5 text-[#468189]" />
                      <span>Predicted Cash-out Window</span>
                    </span>
                    <span className="text-[10px] font-semibold bg-[#F4E9CD] text-[#031926] px-2 py-0.5 rounded border border-[#E2D5B0]">
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
                    <div className="flex items-center space-x-1.5" onClick={(e) => e.stopPropagation()}>
                      <span className="font-bold text-[#031926] uppercase text-[11px]">
                        Model & Provenance
                      </span>
                      <div className="relative">
                        <button
                          id="info-btn-provenance"
                          onClick={() => toggleInfoPopover('provenance')}
                          className="text-slate-400 hover:text-[#468189] transition-colors"
                        >
                          <Info className="w-3 h-3" />
                        </button>
                        {activeInfoPopover === 'provenance' && (
                          <div className="absolute left-0 top-4 z-30 w-64 p-3 bg-white border border-slate-200 rounded-lg shadow-lg text-[11px] text-slate-600 leading-relaxed">
                            <p className="font-semibold text-slate-800 mb-1">Model & Provenance</p>
                            <p>Shows the exact prediction mode, model version, and supporting provenance associated with this specific prediction record.</p>
                          </div>
                        )}
                      </div>
                    </div>
                    <span className="font-mono text-[#468189] font-semibold">
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
                      <span className="font-mono text-slate-800 font-semibold">{prediction.model_version || 'cashout-location-xgb-v8-debiased'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Feature Schema:</span>
                      <span className="text-slate-800 font-medium">
                        {(prediction.model_version && prediction.model_version.includes('v8')) || (!prediction.model_version && isTrained)
                          ? 'V8 Debiased • 49 features'
                          : prediction.model_version && prediction.model_version.includes('v7')
                          ? 'V7-compat • 47 features (43 base + 4 compat)'
                          : 'V3.1 Base • 43 features'}
                      </span>
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
                      <span className="text-slate-800 font-medium">LIME Local Explanation</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-500">LIME Fidelity:</span>
                      {explanation ? (
                        explanation.explanation_status === 'UNAVAILABLE' ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-300">
                            UNAVAILABLE
                          </span>
                        ) : (
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            explanation.overall_fidelity_status === 'HIGH_FIDELITY'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : explanation.overall_fidelity_status === 'MODERATE_FIDELITY'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}>
                            {explanation.overall_fidelity_status?.replace('_', ' ') || 'LOW FIDELITY'}
                          </span>
                        )
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

                    {/* Evaluated Risk Signals */}
                    <div className="pt-2.5 mt-2 border-t border-slate-200 space-y-1.5">
                      <div className="flex items-center space-x-1.5" onClick={(e) => e.stopPropagation()}>
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                          Evaluated Risk Signals
                        </span>
                        <div className="relative">
                          <button
                            id="info-btn-risk-signals"
                            onClick={() => toggleInfoPopover('risk_signals')}
                            className="text-slate-400 hover:text-blue-600 transition-colors"
                          >
                            <Info className="w-3 h-3" />
                          </button>
                          {activeInfoPopover === 'risk_signals' && (
                            <div className="absolute right-0 top-4 z-30 w-72 p-3 bg-white border border-slate-200 rounded-lg shadow-lg text-[11px] text-slate-600 leading-relaxed">
                              <p className="font-semibold text-slate-800 mb-1">Evaluated Risk Signals</p>
                              <p>These are separate model, graph, and historical/contextual signals. They should not be interpreted as a single combined probability or as proof of a cash-out event.</p>
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex justify-between items-center text-slate-600">
                        <span className="text-slate-500 flex items-center space-x-1 cursor-help" title="Trained XGBoost ranking score for the primary candidate cluster. Relative ranking metric across Delhi candidate zones; not real-world withdrawal probability.">
                          <span>Model Ranking Score:</span>
                          <Info className="w-3 h-3 text-slate-400" />
                        </span>
                        <span className="font-mono font-semibold text-blue-700">
                          {prediction.ml_score !== undefined && prediction.ml_score !== null && !isNaN(prediction.ml_score) ? `${(prediction.ml_score * 100).toFixed(1)}%` : 'Unavailable'}
                        </span>
                      </div>
                      <div className="flex justify-between items-center text-slate-600">
                        <span className="text-slate-500 flex items-center space-x-1 cursor-help" title="Graph heuristic risk derived from transaction flow connectivity and mule network topology in the current evidence graph.">
                          <span>Graph Heuristic Risk:</span>
                          <Info className="w-3 h-3 text-slate-400" />
                        </span>
                        <span className="font-mono font-semibold text-slate-800">
                          {prediction.graph_score !== undefined && prediction.graph_score !== null && !isNaN(prediction.graph_score) ? `${(prediction.graph_score * 100).toFixed(0)}%` : 'Unavailable'}
                        </span>
                      </div>
                      <div className="flex justify-between items-center text-slate-600">
                        <span className="text-slate-500 flex items-center space-x-1 cursor-help" title="Historical geographic risk based on historical ATM/cash-out incident concentration in this candidate cluster.">
                          <span>Historical Geographic Risk:</span>
                          <Info className="w-3 h-3 text-slate-400" />
                        </span>
                        <span className="font-mono font-semibold text-slate-800">
                          {prediction.geo_score !== undefined && prediction.geo_score !== null && !isNaN(prediction.geo_score) ? `${(prediction.geo_score * 100).toFixed(0)}%` : 'Unavailable'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Operational Actions Card (B14) */}
                <div className="p-4 bg-[#F8FAFC] rounded-lg border border-[#DCE5F0] space-y-2.5">
                  <span className="text-xs font-bold text-[#031926] uppercase block">
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

      {/* ==================================================================== */}
      {/* PHASE 6: DIGITAL EVIDENCE REGISTRY & INVESTIGATOR DOSSIER */}
      {/* ==================================================================== */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-100 gap-3">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 bg-blue-50 text-blue-700 rounded-md">
              <FileCheck className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Digital Evidence Registry & Chain of Custody
              </h3>
              <p className="text-[11px] text-slate-500">
                Cryptographic SHA-256 Checksums • Tamper-Evident Versioning • Malware Scans
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              onClick={handleExportReport}
              disabled={exportingDossier}
              variant="outline"
              size="sm"
              icon={<FileText className={`w-3.5 h-3.5 text-blue-600 ${exportingDossier ? 'animate-spin' : ''}`} />}
            >
              {exportingDossier ? 'Exporting...' : 'Export Dossier'}
            </Button>
            <Button
              onClick={() => {
                setReplaceTarget(null);
                setSelectedFile(null);
                setUploadError(null);
                setUploadModalOpen(true);
              }}
              variant="primary"
              size="sm"
              icon={<Upload className="w-3.5 h-3.5" />}
            >
              Upload Evidence
            </Button>
          </div>
        </div>

        {/* Evidence Table */}
        {evidenceList.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border border-slate-200 rounded-md overflow-hidden">
              <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                <tr>
                  <th className="p-2.5">ID</th>
                  <th className="p-2.5">Version</th>
                  <th className="p-2.5">File Name & Source</th>
                  <th className="p-2.5">Size</th>
                  <th className="p-2.5">SHA-256 Checksum</th>
                  <th className="p-2.5">Scan Status</th>
                  <th className="p-2.5">Uploaded</th>
                  <th className="p-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-800">
                {evidenceList.map((ev) => {
                  const integ = integrityResults[ev.id];
                  const isChecking = checkingIntegrityId === ev.id;
                  const isSuperseded = ev.status === 'SUPERSEDED';

                  return (
                    <tr
                      key={ev.id}
                      className={`hover:bg-slate-50/80 transition-colors ${
                        isSuperseded ? 'bg-slate-50/50 text-slate-400' : ''
                      }`}
                    >
                      <td className="p-2.5 font-mono font-bold text-slate-700">
                        EV-{String(ev.id).padStart(4, '0')}
                      </td>
                      <td className="p-2.5">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            isSuperseded
                              ? 'bg-slate-200 text-slate-600'
                              : 'bg-blue-100 text-blue-800'
                          }`}
                        >
                          v{ev.version} {isSuperseded && '(Superseded)'}
                        </span>
                      </td>
                      <td className="p-2.5">
                        <div className="font-semibold text-slate-900">{ev.original_filename}</div>
                        <div className="text-[10px] text-slate-500 flex items-center space-x-1.5 mt-0.5">
                          <span>{ev.source}</span>
                          {ev.description && (
                            <>
                              <span>•</span>
                              <span className="italic">{ev.description}</span>
                            </>
                          )}
                        </div>
                      </td>
                      <td className="p-2.5 font-mono text-slate-600">
                        {(ev.size_bytes / 1024).toFixed(1)} KB
                      </td>
                      <td className="p-2.5">
                        <div className="flex items-center space-x-1.5">
                          <span
                            className="font-mono text-[11px] text-slate-700 truncate max-w-[120px]"
                            title={ev.sha256_hash}
                          >
                            {ev.sha256_hash.substring(0, 12)}...
                          </span>
                          <button
                            onClick={() => handleCheckIntegrity(ev.id)}
                            disabled={isChecking}
                            title="Verify on-disk cryptographic integrity against database hash"
                            className="text-[10px] text-blue-600 hover:text-blue-800 underline font-medium"
                          >
                            {isChecking ? 'Verifying...' : 'Verify'}
                          </button>
                        </div>
                        {integ && (
                          <div className="mt-1">
                            {integ.is_valid ? (
                              <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200 flex items-center space-x-1 w-max">
                                <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
                                <span>Verified Authentic</span>
                              </span>
                            ) : (
                              <span className="text-[10px] font-bold text-red-700 bg-red-50 px-1.5 py-0.5 rounded border border-red-200 flex items-center space-x-1 w-max">
                                <AlertTriangle className="w-2.5 h-2.5 text-red-600" />
                                <span>Integrity Violation</span>
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="p-2.5">
                        <Badge
                          variant={
                            ev.malware_scan_status === 'CLEAN'
                              ? 'success'
                              : ev.malware_scan_status === 'PENDING_SCAN'
                              ? 'warning'
                              : 'critical'
                          }
                        >
                          {ev.malware_scan_status}
                        </Badge>
                      </td>
                      <td className="p-2.5 text-[11px] text-slate-500 whitespace-nowrap">
                        {formatIST(ev.created_at)}
                      </td>
                      <td className="p-2.5 text-right whitespace-nowrap space-x-1.5">
                        <a
                          href={api.getEvidenceDownloadUrl(ev.id, caseId)}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center space-x-1 px-2 py-1 bg-white border border-slate-200 rounded text-slate-700 hover:bg-slate-50 text-[11px] font-medium"
                        >
                          <Download className="w-3 h-3 text-slate-500" />
                          <span>Download</span>
                        </a>
                        {!isSuperseded && (
                          <button
                            onClick={() => {
                              setReplaceTarget(ev);
                              setSelectedFile(null);
                              setUploadError(null);
                              setUploadModalOpen(true);
                            }}
                            className="inline-flex items-center space-x-1 px-2 py-1 bg-white border border-blue-200 rounded text-blue-700 hover:bg-blue-50 text-[11px] font-medium"
                          >
                            <RefreshCw className="w-3 h-3 text-blue-500" />
                            <span>Replace</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center bg-slate-50 border border-dashed border-slate-200 rounded-lg text-xs text-slate-500 space-y-2">
            <FileSpreadsheet className="w-8 h-8 text-slate-400 mx-auto" />
            <div className="font-semibold text-slate-700">No Digital Evidence Files Attached</div>
            <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
              Attach bank account statements, CFCFRMS seizure logs, victim deposit slips, CCTV footage, or CDR summaries with SHA-256 chain of custody verification.
            </p>
            <Button
              onClick={() => {
                setReplaceTarget(null);
                setSelectedFile(null);
                setUploadError(null);
                setUploadModalOpen(true);
              }}
              variant="outline"
              size="sm"
              icon={<Upload className="w-3.5 h-3.5" />}
            >
              Upload Initial Evidence
            </Button>
          </div>
        )}
      </div>

      {/* Cross-Jurisdiction Task Assignments & Handoffs (Phase 7) */}
      <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4 shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <div className="flex items-center space-x-2">
              <Share2 className="w-5 h-5 text-indigo-600" />
              <h3 className="font-bold text-slate-900 text-sm">
                Cross-Jurisdiction Task Assignments (Phase 7)
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Explicit, time-bounded inter-state coordination between case-owning LEA and field action teams.
            </p>
          </div>

          <Button
            onClick={() => {
              setCreateHandoffError(null);
              setCreateHandoffModalOpen(true);
            }}
            variant="primary"
            size="sm"
            icon={<Send className="w-3.5 h-3.5" />}
          >
            Initiate Cross-State Task
          </Button>
        </div>

        {handoffsList.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50/80 text-slate-600 font-semibold border-b border-slate-200">
                  <th className="p-2.5">Task ID</th>
                  <th className="p-2.5">Destination Org / Jurisdiction</th>
                  <th className="p-2.5">Purpose</th>
                  <th className="p-2.5">Evidence Scope</th>
                  <th className="p-2.5">Status</th>
                  <th className="p-2.5">Deadline</th>
                  <th className="p-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {handoffsList.map((h) => {
                  const isExpired = h.status === 'EXPIRED';
                  const isCompleted = h.status === 'COMPLETED';
                  const isRejected = h.status === 'REJECTED';
                  const isCancelled = h.status === 'CANCELLED';
                  const isTerminal = isExpired || isCompleted || isRejected || isCancelled;

                  return (
                    <tr key={h.id} className="hover:bg-slate-50/50">
                      <td className="p-2.5 font-mono font-medium text-slate-900">
                        #{h.id}
                      </td>
                      <td className="p-2.5">
                        <div className="font-medium text-slate-900">
                          {h.destination_organization_name || `Org #${h.destination_organization_id}`}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {h.target_district}, {h.target_state}
                        </div>
                      </td>
                      <td className="p-2.5">
                        <span className="font-medium text-slate-800">
                          {h.purpose.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="p-2.5">
                        <Badge
                          variant={
                            h.evidence_scope === 'ALL_EVIDENCE'
                              ? 'info'
                              : h.evidence_scope === 'SPECIFIC_EVIDENCE'
                              ? 'warning'
                              : 'neutral'
                          }
                        >
                          {h.evidence_scope}
                        </Badge>
                      </td>
                      <td className="p-2.5">
                        <Badge
                          variant={
                            h.status === 'ACCEPTED'
                              ? 'success'
                              : h.status === 'IN_PROGRESS'
                              ? 'info'
                              : h.status === 'REQUESTED'
                              ? 'warning'
                              : h.status === 'COMPLETED'
                              ? 'success'
                              : 'critical'
                          }
                        >
                          {h.status}
                        </Badge>
                      </td>
                      <td className="p-2.5 text-[11px] text-slate-500 whitespace-nowrap">
                        <div className="flex items-center space-x-1">
                          <Clock4 className="w-3 h-3 text-slate-400" />
                          <span>{formatIST(h.acknowledgement_deadline)}</span>
                        </div>
                      </td>
                      <td className="p-2.5 text-right whitespace-nowrap space-x-1">
                        {h.status === 'REQUESTED' && (
                          <>
                            <button
                              onClick={() => handleOpenActionModal(h, 'accept')}
                              className="inline-flex items-center space-x-1 px-2 py-1 bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100 rounded text-[11px] font-medium"
                            >
                              <Check className="w-3 h-3" />
                              <span>Accept</span>
                            </button>
                            <button
                              onClick={() => handleOpenActionModal(h, 'reject')}
                              className="inline-flex items-center space-x-1 px-2 py-1 bg-red-50 border border-red-200 text-red-700 hover:bg-red-100 rounded text-[11px] font-medium"
                            >
                              <XCircle className="w-3 h-3" />
                              <span>Reject</span>
                            </button>
                          </>
                        )}
                        {h.status === 'ACCEPTED' && (
                          <button
                            onClick={() => handleOpenActionModal(h, 'start')}
                            className="inline-flex items-center space-x-1 px-2 py-1 bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100 rounded text-[11px] font-medium"
                          >
                            <PlayCircle className="w-3 h-3" />
                            <span>Start Work</span>
                          </button>
                        )}
                        {(h.status === 'ACCEPTED' || h.status === 'IN_PROGRESS') && (
                          <button
                            onClick={() => handleOpenActionModal(h, 'complete')}
                            className="inline-flex items-center space-x-1 px-2 py-1 bg-indigo-50 border border-indigo-200 text-indigo-700 hover:bg-indigo-100 rounded text-[11px] font-medium"
                          >
                            <Check className="w-3 h-3" />
                            <span>Complete</span>
                          </button>
                        )}
                        {!isTerminal && (
                          <button
                            onClick={() => handleOpenActionModal(h, 'cancel')}
                            className="inline-flex items-center space-x-1 px-2 py-1 bg-slate-50 border border-slate-200 text-slate-600 hover:bg-slate-100 rounded text-[11px] font-medium"
                          >
                            <span>Cancel</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6 text-center bg-slate-50 border border-dashed border-slate-200 rounded-lg text-xs text-slate-500 space-y-2">
            <Share2 className="w-7 h-7 text-slate-400 mx-auto" />
            <div className="font-semibold text-slate-700">No Inter-Jurisdiction Tasks Assigned</div>
            <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
              If predictive cash-out hotspots or mule beneficiaries are located outside Delhi, dispatch a scoped task assignment to the local destination police cyber cell.
            </p>
          </div>
        )}
      </div>

      {/* Upload / Replace Evidence Modal */}
      {uploadModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <Upload className="w-4 h-4 text-blue-600" />
                <h4 className="font-bold text-slate-900 text-sm">
                  {replaceTarget ? `Replace Evidence v${replaceTarget.version}` : 'Upload Digital Evidence'}
                </h4>
              </div>
              <button
                onClick={() => setUploadModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            {replaceTarget && (
              <div className="p-2.5 bg-amber-50 border border-amber-200 rounded text-amber-800 text-xs">
                <strong>Replacing:</strong> {replaceTarget.original_filename} (v{replaceTarget.version}). The original version will be preserved as SUPERSEDED with its historical SHA-256 hash intact.
              </div>
            )}

            <form onSubmit={handleUploadEvidence} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Select File <span className="text-red-500">*</span>
                </label>
                <input
                  type="file"
                  onChange={(e) => {
                    const f = e.target.files?.[0] || null;
                    setSelectedFile(f);
                  }}
                  className="w-full text-xs text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 border border-slate-200 rounded p-1"
                />
                <p className="text-[10px] text-slate-400 mt-1">
                  Permitted: PDF, PNG, JPG, CSV, JSON, TXT, XLSX, DOCX (Max: 25 MB). Path traversal and scripts are strictly blocked.
                </p>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Evidence Source <span className="text-red-500">*</span>
                </label>
                <select
                  value={evidenceSource}
                  onChange={(e) => setEvidenceSource(e.target.value)}
                  className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800 bg-white"
                >
                  <option value="OFFICER_UPLOAD">Officer Document Upload</option>
                  <option value="BANK_STATEMENT">Core Banking Statement</option>
                  <option value="CFCFRMS_EXPORT">CFCFRMS Coordination Export</option>
                  <option value="VICTIM_SUBMISSION">Victim Submission / Receipt</option>
                  <option value="ATM_CCTV">ATM CCTV Footage / Image</option>
                  <option value="CDR_EXPORT">Call Detail Record (CDR) Export</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Description / Notes (Optional)
                </label>
                <textarea
                  value={evidenceDesc}
                  onChange={(e) => setEvidenceDesc(e.target.value)}
                  rows={2}
                  placeholder="Provide investigation context, seizure reference, or source notes..."
                  className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800 resize-none"
                />
              </div>

              {uploadError && (
                <div className="p-2.5 bg-red-50 border border-red-200 rounded text-red-700 text-xs">
                  {uploadError}
                </div>
              )}

              <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setUploadModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={uploadingEvidence || !selectedFile}
                  icon={<Upload className={`w-3.5 h-3.5 ${uploadingEvidence ? 'animate-spin' : ''}`} />}
                >
                  {uploadingEvidence ? 'Uploading...' : replaceTarget ? 'Save Replacement' : 'Upload Evidence'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Initiate Cross-State Assignment Modal */}
      {createHandoffModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <Send className="w-4 h-4 text-indigo-600" />
                <h4 className="font-bold text-slate-900 text-sm">
                  Initiate Cross-State Task Assignment
                </h4>
              </div>
              <button
                onClick={() => setCreateHandoffModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateHandoff} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Target State <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={targetStateInput}
                    onChange={(e) => setTargetStateInput(e.target.value)}
                    placeholder="e.g. Maharashtra"
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Target District <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={targetDistrictInput}
                    onChange={(e) => setTargetDistrictInput(e.target.value)}
                    placeholder="e.g. MUMBAI"
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Assignment Purpose <span className="text-red-500">*</span>
                </label>
                <select
                  value={handoffPurposeInput}
                  onChange={(e) => setHandoffPurposeInput(e.target.value)}
                  className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800 bg-white"
                >
                  <option value="PHYSICAL_SURVEILLANCE">Physical ATM Surveillance & Verification</option>
                  <option value="ATM_INTERCEPTION">ATM Hotspot Interception & Stakeout</option>
                  <option value="MULE_ARREST">Mule Account Holder Apprehension</option>
                  <option value="EVIDENCE_COLLECTION">CCTV / Branch Seizure & Evidence Collection</option>
                  <option value="BANK_BRANCH_VISIT">Bank Branch Inspection</option>
                  <option value="LOCAL_INQUIRY">Local Field Inquiry</option>
                  <option value="OTHER">Other Operational Task</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Shared Evidence Scope <span className="text-red-500">*</span>
                </label>
                <select
                  value={handoffScopeInput}
                  onChange={(e) => setHandoffScopeInput(e.target.value as any)}
                  className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800 bg-white"
                >
                  <option value="METADATA_ONLY">Metadata Only (Case overview & predicted hotspot)</option>
                  <option value="SPECIFIC_EVIDENCE">Specific Attached Evidence Files</option>
                  <option value="ALL_EVIDENCE">All Digital Evidence Files</option>
                </select>
              </div>

              {handoffScopeInput === 'SPECIFIC_EVIDENCE' && evidenceList.length > 0 && (
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Select Evidence Files to Share:
                  </label>
                  <div className="max-h-24 overflow-y-auto space-y-1 p-2 bg-slate-50 border border-slate-200 rounded">
                    {evidenceList.map((ev) => (
                      <label key={ev.id} className="flex items-center space-x-2 text-[11px] text-slate-700">
                        <input
                          type="checkbox"
                          checked={selectedEvidenceIdsForHandoff.includes(ev.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedEvidenceIdsForHandoff([...selectedEvidenceIdsForHandoff, ev.id]);
                            } else {
                              setSelectedEvidenceIdsForHandoff(selectedEvidenceIdsForHandoff.filter((id) => id !== ev.id));
                            }
                          }}
                        />
                        <span>{ev.original_filename} (v{ev.version})</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {createHandoffError && (
                <div className="p-2.5 bg-red-50 border border-red-200 rounded text-red-700 text-xs">
                  {createHandoffError}
                </div>
              )}

              <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setCreateHandoffModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={createHandoffLoading}
                  icon={<Send className={`w-3.5 h-3.5 ${createHandoffLoading ? 'animate-spin' : ''}`} />}
                >
                  {createHandoffLoading ? 'Dispatching...' : 'Dispatch Assignment'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirm Handoff Action Modal */}
      {handoffActionModalOpen && activeHandoffForAction && handoffActionType && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h4 className="font-bold text-slate-900 text-sm capitalize">
                {handoffActionType} Task Assignment #{activeHandoffForAction.id}
              </h4>
              <button
                onClick={() => setHandoffActionModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleExecuteHandoffAction} className="space-y-3.5 text-xs">
              {(handoffActionType === 'reject' || handoffActionType === 'cancel') && (
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    {handoffActionType === 'reject' ? 'Rejection Reason' : 'Cancellation Reason'} <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    required
                    value={actionReasonOrNotes}
                    onChange={(e) => setActionReasonOrNotes(e.target.value)}
                    rows={3}
                    placeholder="Provide justification for auditing and chain of custody..."
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800 resize-none"
                  />
                </div>
              )}

              {handoffActionType === 'complete' && (
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Field Outcome & Notes (Optional)
                  </label>
                  <textarea
                    value={actionReasonOrNotes}
                    onChange={(e) => setActionReasonOrNotes(e.target.value)}
                    rows={3}
                    placeholder="Record field outcome, suspects apprehended, seized assets, or branch verification notes..."
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800 resize-none"
                  />
                </div>
              )}

              {(handoffActionType === 'accept' || handoffActionType === 'start') && (
                <p className="text-xs text-slate-600">
                  {handoffActionType === 'accept'
                    ? `Confirm acceptance of Task #${activeHandoffForAction.id} from ${activeHandoffForAction.origin_organization_name || 'Origin LEA'}. Your organization will be granted scoped visibility.`
                    : `Mark Task #${activeHandoffForAction.id} as IN_PROGRESS. Field operations are actively underway.`}
                </p>
              )}

              {actionError && (
                <div className="p-2.5 bg-red-50 border border-red-200 rounded text-red-700 text-xs">
                  {actionError}
                </div>
              )}

              <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setHandoffActionModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={actionLoading}
                >
                  {actionLoading ? 'Processing...' : 'Confirm'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
