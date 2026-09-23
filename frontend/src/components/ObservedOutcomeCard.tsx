import React, { useEffect, useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Info,
  ShieldAlert,
  History,
  Edit3,
  PlusCircle,
  DollarSign,
  MapPin,
  Clock,
  Target,
  RefreshCw,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../store/authContext';
import {
  OutcomeEvaluation,
  OutcomeObservation,
  OutcomeType,
  OutcomeSource,
  OutcomeVerificationStatus,
  OutcomeCreatePayload,
  OutcomeCorrectPayload,
} from '../types';
import { Button } from './common/Button';
import { Badge } from './common/Badge';

interface ObservedOutcomeCardProps {
  complaintId: number;
  predictionId?: number | null;
}

export const ObservedOutcomeCard: React.FC<ObservedOutcomeCardProps> = ({
  complaintId,
  predictionId,
}) => {
  const { user } = useAuth();
  const [data, setData] = useState<OutcomeEvaluation | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const [showLineage, setShowLineage] = useState<boolean>(false);
  const [showTooltip, setShowTooltip] = useState<boolean>(false);

  // Modal state
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [modalMode, setModalMode] = useState<'create' | 'correct'>('create');
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Form state
  const [outcomeType, setOutcomeType] = useState<OutcomeType>('CONFIRMED_CASHOUT');
  const [source, setSource] = useState<OutcomeSource>('OFFICER_MANUAL');
  const [observedEventTime, setObservedEventTime] = useState<string>('');
  const [actualLocationName, setActualLocationName] = useState<string>('');
  const [actualLat, setActualLat] = useState<string>('');
  const [actualLon, setActualLon] = useState<string>('');
  const [withdrawalAmount, setWithdrawalAmount] = useState<string>('');
  const [verifiedHeldAmount, setVerifiedHeldAmount] = useState<string>('');
  const [recoveredAmount, setRecoveredAmount] = useState<string>('');
  const [verificationStatus, setVerificationStatus] =
    useState<OutcomeVerificationStatus>('VERIFIED');
  const [isSynthetic, setIsSynthetic] = useState<boolean>(false);
  const [isExcluded, setIsExcluded] = useState<boolean>(false);
  const [exclusionReason, setExclusionReason] = useState<string>('');
  const [correctionReason, setCorrectionReason] = useState<string>('');
  const [notes, setNotes] = useState<string>('');

  const canEdit =
    user?.role &&
    ['I4C_ADMIN', 'STATE_LEA', 'DISTRICT_LEA'].includes(user.role);

  const fetchEvaluation = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getComplaintOutcomeEvaluation(complaintId);
      setData(res);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || 'Failed to load outcome evaluation.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvaluation();
  }, [complaintId]);

  const openCreateModal = () => {
    setModalMode('create');
    setOutcomeType('CONFIRMED_CASHOUT');
    setSource('OFFICER_MANUAL');
    setObservedEventTime('');
    setActualLocationName('');
    setActualLat('');
    setActualLon('');
    setWithdrawalAmount('');
    setVerifiedHeldAmount('');
    setRecoveredAmount('');
    setVerificationStatus('VERIFIED');
    setIsSynthetic(false);
    setIsExcluded(false);
    setExclusionReason('');
    setCorrectionReason('');
    setNotes('');
    setActionError(null);
    setModalOpen(true);
  };

  const openCorrectModal = () => {
    if (!data || !data.has_outcome) return;
    const active = data.lineage?.find((o) => o.record_status === 'ACTIVE') || (data.lineage && data.lineage[0]);
    setModalMode('correct');
    setOutcomeType(active?.outcome_type || 'CONFIRMED_CASHOUT');
    setSource(active?.source || 'OFFICER_MANUAL');
    setObservedEventTime(
      active?.observed_event_time
        ? new Date(active.observed_event_time).toISOString().slice(0, 16)
        : ''
    );
    setActualLocationName(active?.actual_location_name || '');
    setActualLat(active?.actual_lat !== null && active?.actual_lat !== undefined ? String(active.actual_lat) : '');
    setActualLon(active?.actual_lon !== null && active?.actual_lon !== undefined ? String(active.actual_lon) : '');
    setWithdrawalAmount(
      active?.actual_withdrawal_amount_inr !== null && active?.actual_withdrawal_amount_inr !== undefined
        ? String(active.actual_withdrawal_amount_inr)
        : ''
    );
    setVerifiedHeldAmount(
      active?.verified_held_amount_inr !== null && active?.verified_held_amount_inr !== undefined
        ? String(active.verified_held_amount_inr)
        : ''
    );
    setRecoveredAmount(
      active?.actual_recovered_amount_inr !== null && active?.actual_recovered_amount_inr !== undefined
        ? String(active.actual_recovered_amount_inr)
        : ''
    );
    setVerificationStatus(active?.verification_status || 'VERIFIED');
    setIsSynthetic(active?.is_synthetic || false);
    setIsExcluded(active?.is_excluded || false);
    setExclusionReason(active?.exclusion_reason || '');
    setCorrectionReason('');
    setNotes(active?.notes || '');
    setActionError(null);
    setModalOpen(true);
  };

  const handleSubmitModal = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    setActionError(null);

    try {
      if (modalMode === 'create') {
        const payload: OutcomeCreatePayload = {
          outcome_type: outcomeType,
          source: source,
          observed_event_time: observedEventTime ? new Date(observedEventTime).toISOString() : undefined,
          actual_location_name: actualLocationName || undefined,
          actual_lat: actualLat ? parseFloat(actualLat) : undefined,
          actual_lon: actualLon ? parseFloat(actualLon) : undefined,
          actual_withdrawal_amount_inr: withdrawalAmount ? parseFloat(withdrawalAmount) : undefined,
          verified_held_amount_inr: verifiedHeldAmount ? parseFloat(verifiedHeldAmount) : undefined,
          actual_recovered_amount_inr: recoveredAmount ? parseFloat(recoveredAmount) : undefined,
          verification_status: verificationStatus,
          is_synthetic: isSynthetic,
          is_excluded: isExcluded,
          exclusion_reason: isExcluded ? exclusionReason : undefined,
          notes: notes || undefined,
        };
        await api.ingestOutcome(complaintId, payload);
      } else {
        if (!correctionReason.trim()) {
          setActionError('A valid correction reason is required for append-only audit tracking.');
          setActionLoading(false);
          return;
        }
        const activeOutcomeId = data?.outcome_id;
        if (!activeOutcomeId) {
          setActionError('Active outcome ID not found.');
          setActionLoading(false);
          return;
        }
        const payload: OutcomeCorrectPayload = {
          correction_reason: correctionReason.trim(),
          outcome_type: outcomeType,
          source: source,
          observed_event_time: observedEventTime ? new Date(observedEventTime).toISOString() : undefined,
          actual_location_name: actualLocationName || undefined,
          actual_lat: actualLat ? parseFloat(actualLat) : undefined,
          actual_lon: actualLon ? parseFloat(actualLon) : undefined,
          actual_withdrawal_amount_inr: withdrawalAmount ? parseFloat(withdrawalAmount) : undefined,
          verified_held_amount_inr: verifiedHeldAmount ? parseFloat(verifiedHeldAmount) : undefined,
          actual_recovered_amount_inr: recoveredAmount ? parseFloat(recoveredAmount) : undefined,
          verification_status: verificationStatus,
          is_excluded: isExcluded,
          exclusion_reason: isExcluded ? exclusionReason : undefined,
          notes: notes || undefined,
        };
        await api.correctOutcome(activeOutcomeId, payload);
      }

      setModalOpen(false);
      await fetchEvaluation();
    } catch (err: any) {
      setActionError(
        err?.response?.data?.detail || 'Failed to submit outcome record.'
      );
    } finally {
      setActionLoading(false);
    }
  };

  const formatIST = (isoString?: string | null) => {
    if (!isoString) return 'Unavailable';
    try {
      const d = new Date(isoString);
      return d.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden text-xs">
      {/* Header */}
      <div className="flex items-center justify-between p-4 bg-slate-50/80 border-b border-slate-200">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 bg-blue-100/80 text-blue-700 rounded-md">
            <Target className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wider">
                Observed Outcome & Model Evaluation
              </h3>
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowTooltip(!showTooltip)}
                  className="text-slate-400 hover:text-blue-600 transition-colors"
                  title="About Observed Outcome"
                >
                  <Info className="w-3.5 h-3.5" />
                </button>
                {showTooltip && (
                  <div className="absolute left-0 top-5 z-30 w-72 p-3 bg-white border border-slate-200 rounded-lg shadow-lg text-[11px] text-slate-600 leading-relaxed font-normal">
                    <p className="font-semibold text-slate-800 mb-1">
                      Observed Outcome & Verification
                    </p>
                    <p>
                      Observed outcomes capture verified field and banking feedback.
                      This evidence is compared directly against the historical
                      persisted prediction to evaluate spatial and timing accuracy
                      without automatically retraining the model.
                    </p>
                  </div>
                )}
              </div>
            </div>
            <p className="text-[11px] text-slate-500">
              Evaluates historical prediction against ground-truth field resolution.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {canEdit && (
            <>
              {data && data.has_outcome ? (
                <Button
                  onClick={openCorrectModal}
                  variant="outline"
                  size="sm"
                  icon={<Edit3 className="w-3.5 h-3.5 text-blue-600" />}
                >
                  Correct Outcome
                </Button>
              ) : (
                <Button
                  onClick={openCreateModal}
                  variant="primary"
                  size="sm"
                  icon={<PlusCircle className="w-3.5 h-3.5" />}
                >
                  Record Outcome
                </Button>
              )}
            </>
          )}

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded transition-colors"
            title={isExpanded ? 'Collapse section' : 'Expand section'}
          >
            {isExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Body */}
      {isExpanded && (
        <div className="p-4 space-y-4">
          {loading ? (
            <div className="p-6 text-center text-slate-500 flex items-center justify-center space-x-2">
              <RefreshCw className="w-4 h-4 animate-spin text-blue-600" />
              <span>Loading outcome intelligence...</span>
            </div>
          ) : error ? (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-700 flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : !data || !data.has_outcome ? (
            <div className="p-6 text-center bg-slate-50 border border-dashed border-slate-200 rounded-lg space-y-2">
              <Target className="w-7 h-7 text-slate-400 mx-auto" />
              <div className="font-semibold text-slate-700">
                No Observed Outcome Recorded
              </div>
              <p className="text-[11px] text-slate-500 max-w-md mx-auto">
                No verified field outcome has been registered for this case yet.
                Authorized LEA officers can record observed cash-out locations,
                confirmed CCTV timestamps, or banking recovery actions.
              </p>
              <div className="p-2 bg-amber-50/70 border border-amber-200/80 rounded text-[11px] text-amber-800 max-w-md mx-auto">
                <strong>Cohort Status:</strong> No authorized real-world evaluation cohort is available for this case.
              </div>
            </div>
          ) : (
            <>
              {/* Cohort Status Banner */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-lg border bg-slate-50/50">
                <div className="flex items-center space-x-2">
                  <span className="text-slate-600 font-medium">Evaluation Cohort:</span>
                  <span
                    className={`px-2.5 py-0.5 rounded text-[10px] font-bold border ${
                      data.cohort === 'CONTROLLED_SYNTHETIC'
                        ? 'bg-purple-50 text-purple-700 border-purple-200'
                        : data.cohort === 'AUTHORIZED_OPERATIONAL'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : data.cohort === 'EXCLUDED'
                        ? 'bg-red-50 text-red-700 border-red-200'
                        : 'bg-slate-100 text-slate-700 border-slate-300'
                    }`}
                  >
                    {data.cohort.replace('_', ' ')}
                  </span>
                </div>

                <div className="text-[11px] text-slate-500">
                  {data.cohort === 'CONTROLLED_SYNTHETIC' ? (
                    <span className="text-purple-700 font-medium">
                      Controlled synthetic evaluation case. Excluded from real-world operational accuracy.
                    </span>
                  ) : data.cohort === 'AUTHORIZED_OPERATIONAL' ? (
                    <span className="text-emerald-700 font-medium">
                      Authorized operational evaluation cohort (eligible for real-world metrics).
                    </span>
                  ) : data.cohort === 'EXCLUDED' ? (
                    <span className="text-red-600">
                      Excluded from operational metrics: {data.lineage[0]?.exclusion_reason || 'Marked excluded'}
                    </span>
                  ) : (
                    <span className="text-slate-500">
                      Unverified cohort — pending officer validation.
                    </span>
                  )}
                </div>
              </div>

              {/* Prediction vs Observed Outcome Scorecard */}
              <div className="border border-slate-200 rounded-lg p-3.5 bg-gradient-to-r from-blue-50/20 to-indigo-50/20 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-200">
                  <span className="font-bold text-[#031926] uppercase text-[11px] tracking-wider">
                    Prediction vs Observed Outcome
                  </span>
                  <span className="font-mono text-slate-500 text-[10px]">
                    Prediction #{data.prediction_id || 'N/A'} • Outcome #{data.outcome_id || 'N/A'}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
                  {/* Top-1 Hit */}
                  <div className="p-2.5 bg-white rounded border border-slate-200 space-y-1">
                    <div className="text-[10px] text-slate-500 font-medium">Top-1 Hit</div>
                    <div className="text-sm font-bold">
                      {data.evaluation.top1_hit === true ? (
                        <span className="text-emerald-700 flex items-center space-x-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>YES</span>
                        </span>
                      ) : data.evaluation.top1_hit === false ? (
                        <span className="text-slate-600 flex items-center space-x-1">
                          <XCircle className="w-3.5 h-3.5 text-slate-400" />
                          <span>NO</span>
                        </span>
                      ) : (
                        <span className="text-slate-400">Unavailable</span>
                      )}
                    </div>
                  </div>

                  {/* Top-3 Hit */}
                  <div className="p-2.5 bg-white rounded border border-slate-200 space-y-1">
                    <div className="text-[10px] text-slate-500 font-medium">Top-3 Hit</div>
                    <div className="text-sm font-bold">
                      {data.evaluation.top3_hit === true ? (
                        <span className="text-emerald-700 flex items-center space-x-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>YES</span>
                        </span>
                      ) : data.evaluation.top3_hit === false ? (
                        <span className="text-slate-600 flex items-center space-x-1">
                          <XCircle className="w-3.5 h-3.5 text-slate-400" />
                          <span>NO</span>
                        </span>
                      ) : (
                        <span className="text-slate-400">Unavailable</span>
                      )}
                    </div>
                  </div>

                  {/* Top-5 Hit */}
                  <div className="p-2.5 bg-white rounded border border-slate-200 space-y-1">
                    <div className="text-[10px] text-slate-500 font-medium">Top-5 Hit</div>
                    <div className="text-sm font-bold">
                      {data.evaluation.top5_hit === true ? (
                        <span className="text-emerald-700 flex items-center space-x-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>YES</span>
                        </span>
                      ) : data.evaluation.top5_hit === false ? (
                        <span className="text-slate-600 flex items-center space-x-1">
                          <XCircle className="w-3.5 h-3.5 text-slate-400" />
                          <span>NO</span>
                        </span>
                      ) : (
                        <span className="text-slate-400">Unavailable</span>
                      )}
                    </div>
                  </div>

                  {/* Observed Rank */}
                  <div className="p-2.5 bg-white rounded border border-slate-200 space-y-1">
                    <div className="text-[10px] text-slate-500 font-medium">Observed Rank</div>
                    <div className="text-sm font-bold font-mono text-blue-700">
                      {data.evaluation.observed_rank !== null && data.evaluation.observed_rank !== undefined
                        ? `#${data.evaluation.observed_rank}`
                        : 'Unavailable'}
                    </div>
                  </div>

                  {/* Spatial Error */}
                  <div className="p-2.5 bg-white rounded border border-slate-200 space-y-1">
                    <div className="text-[10px] text-slate-500 font-medium">Spatial Error</div>
                    <div className="text-sm font-bold font-mono text-slate-900">
                      {data.evaluation.spatial_error_km !== null && data.evaluation.spatial_error_km !== undefined
                        ? `${data.evaluation.spatial_error_km.toFixed(1)} km`
                        : 'Unavailable'}
                    </div>
                  </div>

                  {/* Lead Time */}
                  <div className="p-2.5 bg-white rounded border border-slate-200 space-y-1">
                    <div className="text-[10px] text-slate-500 font-medium">Lead Time</div>
                    <div className="text-sm font-bold text-slate-900 truncate" title={data.evaluation.lead_time_human || ''}>
                      {data.evaluation.lead_time_minutes !== null && data.evaluation.lead_time_minutes !== undefined ? (
                        <span>
                          {data.evaluation.lead_time_minutes > 0
                            ? `${data.evaluation.lead_time_minutes} min`
                            : `${Math.abs(data.evaluation.lead_time_minutes)} min late`}
                        </span>
                      ) : (
                        <span className="text-slate-400">Unavailable</span>
                      )}
                    </div>
                  </div>
                </div>

                {data.evaluation.spatial_error_status && data.evaluation.spatial_error_status !== 'CALCULATED' && (
                  <div className="text-[10px] text-slate-500 italic">
                    * Spatial distance: {data.evaluation.spatial_error_status.replace(/_/g, ' ')}.
                  </div>
                )}
              </div>

              {/* Observed Location & Event Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Left: Location & Event Metadata */}
                <div className="p-3 bg-white rounded-lg border border-slate-200 space-y-2">
                  <div className="font-semibold text-slate-800 text-[11px] uppercase tracking-wider flex items-center space-x-1.5">
                    <MapPin className="w-3.5 h-3.5 text-blue-600" />
                    <span>Observed Event Details</span>
                  </div>
                  <div className="space-y-1 text-slate-600">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Event Type:</span>
                      <strong className="text-slate-800">
                        {data.lineage[0]?.outcome_type?.replace(/_/g, ' ') || 'Unknown'}
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Observed Time:</span>
                      <span className="font-mono text-slate-800">
                        {formatIST(data.lineage[0]?.observed_event_time)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Confirmed Location:</span>
                      <span className="font-semibold text-slate-800">
                        {data.lineage[0]?.actual_location_name || 'Not specified'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Coordinates:</span>
                      <span className="font-mono text-slate-700">
                        {data.lineage[0]?.actual_lat && data.lineage[0]?.actual_lon
                          ? `${data.lineage[0].actual_lat.toFixed(4)}, ${data.lineage[0].actual_lon.toFixed(4)}`
                          : 'Unavailable'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Reporting Source:</span>
                      <span className="text-slate-800">
                        {data.lineage[0]?.source?.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Verification Status:</span>
                      <Badge
                        variant={
                          data.lineage[0]?.verification_status === 'VERIFIED'
                            ? 'success'
                            : data.lineage[0]?.verification_status === 'PENDING_VERIFICATION'
                            ? 'warning'
                            : 'neutral'
                        }
                      >
                        {data.lineage[0]?.verification_status}
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Right: Financial Recoveries (Strictly Separated) */}
                <div className="p-3 bg-white rounded-lg border border-slate-200 space-y-2">
                  <div className="font-semibold text-slate-800 text-[11px] uppercase tracking-wider flex items-center space-x-1.5">
                    <DollarSign className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Financial Metrics (Separated)</span>
                  </div>
                  <div className="space-y-1 text-slate-600">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Attempted Withdrawal:</span>
                      <span className="font-mono font-semibold text-slate-900">
                        {data.financial.withdrawal_amount_inr !== null && data.financial.withdrawal_amount_inr !== undefined
                          ? `₹${data.financial.withdrawal_amount_inr.toLocaleString('en-IN')}`
                          : 'Unavailable'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Verified Hold:</span>
                      <span className="font-mono font-semibold text-blue-700">
                        {data.financial.verified_hold_amount_inr !== null && data.financial.verified_hold_amount_inr !== undefined
                          ? `₹${data.financial.verified_hold_amount_inr.toLocaleString('en-IN')}`
                          : '₹0'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Verified Recovery:</span>
                      <span className="font-mono font-semibold text-emerald-700">
                        {data.financial.recovered_amount_inr !== null && data.financial.recovered_amount_inr !== undefined
                          ? `₹${data.financial.recovered_amount_inr.toLocaleString('en-IN')}`
                          : '₹0'}
                      </span>
                    </div>
                  </div>

                  <div className="p-2 bg-amber-50/80 border border-amber-200 rounded text-[10px] text-amber-800 leading-snug">
                    <strong>Notice:</strong> Verified Hold and Recovery amounts are reported
                    separately to avoid double-counting. They are never summed together as &quot;money saved&quot;.
                  </div>
                </div>
              </div>

              {/* Correction Lineage Section */}
              {data.lineage && data.lineage.length > 0 && (
                <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800 text-[11px] flex items-center space-x-1.5">
                      <History className="w-3.5 h-3.5 text-slate-500" />
                      <span>Observation Audit Lineage ({data.lineage.length} record{data.lineage.length > 1 ? 's' : ''})</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowLineage(!showLineage)}
                      className="text-[11px] text-blue-600 hover:text-blue-800 font-medium"
                    >
                      {showLineage ? 'Hide Lineage' : 'View Full History'}
                    </button>
                  </div>

                  {showLineage && (
                    <div className="overflow-x-auto pt-1">
                      <table className="w-full text-left text-[11px] border border-slate-200 rounded bg-white">
                        <thead className="bg-slate-100/70 border-b border-slate-200 text-slate-700">
                          <tr>
                            <th className="p-2">Ver</th>
                            <th className="p-2">Status</th>
                            <th className="p-2">Outcome Type</th>
                            <th className="p-2">Observed Location</th>
                            <th className="p-2">Correction Reason</th>
                            <th className="p-2">Actor</th>
                            <th className="p-2">Recorded At</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {data.lineage.map((obs) => (
                            <tr
                              key={obs.id}
                              className={obs.record_status === 'SUPERSEDED' ? 'bg-slate-50/70 text-slate-400' : 'bg-white font-medium text-slate-800'}
                            >
                              <td className="p-2 font-mono">v{obs.version}</td>
                              <td className="p-2">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                    obs.record_status === 'ACTIVE'
                                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                      : 'bg-slate-200 text-slate-600'
                                  }`}
                                >
                                  {obs.record_status}
                                </span>
                              </td>
                              <td className="p-2">{obs.outcome_type}</td>
                              <td className="p-2">{obs.actual_location_name || 'N/A'}</td>
                              <td className="p-2 italic text-slate-600">{obs.correction_reason || 'Initial observation'}</td>
                              <td className="p-2">{obs.ingested_by_role || 'LEA'}</td>
                              <td className="p-2 font-mono text-[10px]">{formatIST(obs.received_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Record / Correct Outcome Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-lg shadow-xl border border-slate-200 w-full max-w-xl p-5 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h4 className="font-bold text-slate-900 text-sm">
                {modalMode === 'create'
                  ? 'Record Observed Outcome'
                  : 'Correct Outcome (Append-Only Lineage)'}
              </h4>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmitModal} className="space-y-3 text-xs">
              {actionError && (
                <div className="p-2.5 bg-red-50 border border-red-200 rounded text-red-700">
                  {actionError}
                </div>
              )}

              {modalMode === 'correct' && (
                <div className="p-2.5 bg-amber-50 border border-amber-200 rounded text-amber-900 space-y-1">
                  <label className="block font-semibold">
                    Correction Justification Reason <span className="text-red-500">*</span>
                  </label>
                  <p className="text-[11px] text-amber-700">
                    Existing observation will not be overwritten. A new active version will be appended to the permanent audit trail.
                  </p>
                  <input
                    type="text"
                    required
                    value={correctionReason}
                    onChange={(e) => setCorrectionReason(e.target.value)}
                    placeholder="e.g. CCTV verified cashout occurred at Karol Bagh branch instead of CP"
                    className="w-full border border-amber-300 rounded px-2.5 py-1.5 text-xs text-slate-800 bg-white"
                  />
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Outcome Event Type
                  </label>
                  <select
                    value={outcomeType}
                    onChange={(e) => setOutcomeType(e.target.value as OutcomeType)}
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  >
                    <option value="CONFIRMED_CASHOUT">CONFIRMED CASHOUT</option>
                    <option value="UNSUCCESSFUL_ATTEMPT">UNSUCCESSFUL ATTEMPT</option>
                    <option value="FALSE_POSITIVE_ACTIVITY">FALSE POSITIVE ACTIVITY</option>
                    <option value="CANCELLED_NO_CASHOUT">CANCELLED NO CASHOUT</option>
                    <option value="UNKNOWN">UNKNOWN</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Reporting Source
                  </label>
                  <select
                    value={source}
                    onChange={(e) => setSource(e.target.value as OutcomeSource)}
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  >
                    <option value="OFFICER_MANUAL">Officer Manual Report</option>
                    <option value="CFCFRMS_IMPORT">CFCFRMS Import</option>
                    <option value="BANK_REPORT">Bank Report</option>
                    <option value="COURT_RECORD">Court Record</option>
                    <option value="AUTOMATED_MONITORING">Automated Monitoring</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Observed Event Time
                  </label>
                  <input
                    type="datetime-local"
                    value={observedEventTime}
                    onChange={(e) => setObservedEventTime(e.target.value)}
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Confirmed Location Name
                  </label>
                  <input
                    type="text"
                    value={actualLocationName}
                    onChange={(e) => setActualLocationName(e.target.value)}
                    placeholder="e.g. Connaught Place Circle"
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Latitude (Observed)
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    value={actualLat}
                    onChange={(e) => setActualLat(e.target.value)}
                    placeholder="e.g. 28.6315"
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Longitude (Observed)
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    value={actualLon}
                    onChange={(e) => setActualLon(e.target.value)}
                    placeholder="e.g. 77.2167"
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  />
                </div>
              </div>

              {/* Financial Inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Withdrawal (INR)
                  </label>
                  <input
                    type="number"
                    value={withdrawalAmount}
                    onChange={(e) => setWithdrawalAmount(e.target.value)}
                    placeholder="0"
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Verified Hold (INR)
                  </label>
                  <input
                    type="number"
                    value={verifiedHeldAmount}
                    onChange={(e) => setVerifiedHeldAmount(e.target.value)}
                    placeholder="0"
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Recovered (INR)
                  </label>
                  <input
                    type="number"
                    value={recoveredAmount}
                    onChange={(e) => setRecoveredAmount(e.target.value)}
                    placeholder="0"
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Verification Status
                  </label>
                  <select
                    value={verificationStatus}
                    onChange={(e) =>
                      setVerificationStatus(
                        e.target.value as OutcomeVerificationStatus
                      )
                    }
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  >
                    <option value="VERIFIED">VERIFIED</option>
                    <option value="UNVERIFIED">UNVERIFIED</option>
                    <option value="PENDING_VERIFICATION">
                      PENDING VERIFICATION
                    </option>
                  </select>
                </div>

                <div className="flex items-center space-x-4 pt-5">
                  <label className="flex items-center space-x-1.5 font-medium text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isSynthetic}
                      onChange={(e) => setIsSynthetic(e.target.checked)}
                      className="rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                    />
                    <span>Synthetic Case</span>
                  </label>

                  <label className="flex items-center space-x-1.5 font-medium text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isExcluded}
                      onChange={(e) => setIsExcluded(e.target.checked)}
                      className="rounded border-slate-300 text-red-600 focus:ring-red-500"
                    />
                    <span>Exclude Metric</span>
                  </label>
                </div>
              </div>

              {isExcluded && (
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Exclusion Reason <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={exclusionReason}
                    onChange={(e) => setExclusionReason(e.target.value)}
                    placeholder="e.g. Incomplete jurisdiction data or out-of-scope testing"
                    className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800"
                  />
                </div>
              )}

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Investigation Notes
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  placeholder="Additional field verification notes..."
                  className="w-full border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-800 resize-none"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={actionLoading}
                >
                  {actionLoading ? 'Saving...' : modalMode === 'create' ? 'Record Outcome' : 'Confirm Correction'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
