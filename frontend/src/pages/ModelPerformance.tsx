import React, { useEffect, useState } from 'react';
import {
  Cpu,
  ShieldAlert,
  AlertTriangle,
  Info,
  CheckCircle2,
  TrendingUp,
  Award,
  Layers,
  Sparkles,
  MapPin,
  Clock,
  Gauge,
  Compass,
  Database,
  Hash,
  Activity,
  History,
  HelpCircle
} from 'lucide-react';
import { api } from '../services/api';
import { ModelPerformanceData } from '../types';

export const ModelPerformance: React.FC = () => {
  const [data, setData] = useState<ModelPerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPerf = async () => {
      try {
        const res = await api.getModelPerformance();
        setData(res);
      } catch (err: any) {
        console.error('Failed to load model performance', err);
        setError('Failed to retrieve model performance telemetry from backend.');
      } finally {
        setLoading(false);
      }
    };
    fetchPerf();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-20 bg-white rounded-xl border border-[#DCE5F0]"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-white rounded-xl border border-[#DCE5F0]"></div>
          ))}
        </div>
        <div className="h-96 bg-white rounded-xl border border-[#DCE5F0]"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8 bg-white rounded-lg border border-red-200 text-center space-y-4 max-w-xl mx-auto shadow-xs">
        <AlertTriangle className="w-8 h-8 text-red-600 mx-auto" />
        <h2 className="text-lg font-bold text-slate-900">Model Telemetry Unavailable</h2>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          {error || 'CyberShield AI model metadata could not be verified from the server.'}
        </p>
      </div>
    );
  }

  // Runtime status indicators
  const runtimeStatus = data.runtime_info?.runtime_status || (data.prediction_mode === 'trained_ml' ? 'TRAINED_READY' : 'DEMO_ACTIVE');
  const isTrainedReady = runtimeStatus === 'TRAINED_READY';
  const isLoadFailed = runtimeStatus === 'LOAD_FAILED';
  const isDemoActive = runtimeStatus === 'DEMO_ACTIVE';

  // Evaluation status indicators
  const evalStatus = data.evaluation_info?.evaluation_status || (data.natural_candidate_recall ? 'AVAILABLE' : 'UNAVAILABLE');
  const isEvalAvailable = evalStatus === 'AVAILABLE';

  const renderMetric = (val?: string | number | null, fallback = 'Not evaluated') => {
    if (val !== undefined && val !== null && val !== '') {
      return <span className="font-bold">{val}</span>;
    }
    return <span className="text-slate-400 italic text-[11px] font-normal">{fallback}</span>;
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <Cpu className="w-5 h-5 text-blue-600 shrink-0" />
            <h1 className="text-lg font-bold text-[#173A63] font-sans">
              AI Model Performance & Runtime Governance
            </h1>
          </div>
          <p className="text-xs text-slate-500 font-sans mt-0.5">
            Authoritative Runtime: <strong className="text-blue-700 font-semibold">{data.model_version}</strong> | Mode: <strong className="text-slate-900 font-semibold">{data.current_prediction_mode}</strong>
          </p>
        </div>

        {/* Evaluation Governance Notice */}
        <div className="px-3.5 py-1.5 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold flex items-center space-x-2 shrink-0">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>{data.evaluation_label || 'Prototype Evaluation — Synthetic/Anonymized Demo Data'}</span>
        </div>
      </div>

      {/* SECTION 1: Current Runtime vs Historical Provenance */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        {/* CURRENT RUNTIME CARD */}
        <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-2">
          <div className="text-[#173A63] font-bold uppercase tracking-wider text-[11px] pb-1 border-b border-[#DCE5F0] flex items-center justify-between">
            <div className="flex items-center space-x-1.5">
              <Activity className="w-3.5 h-3.5 text-blue-600" />
              <span>CURRENT RUNTIME ENGINE</span>
            </div>
            {isTrainedReady && (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center space-x-1">
                <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                <span>Trained Model Ready</span>
              </span>
            )}
            {isLoadFailed && (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-red-50 text-red-700 border border-red-200 flex items-center space-x-1">
                <AlertTriangle className="w-3 h-3 text-red-600" />
                <span>Model Load Failed</span>
              </span>
            )}
            {isDemoActive && (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200 flex items-center space-x-1">
                <Sparkles className="w-3 h-3 text-amber-600" />
                <span>Deterministic Demo Active</span>
              </span>
            )}
          </div>

          <div className="flex items-center justify-between">
            <span className="text-slate-500">Runtime Status:</span>
            <span className="font-semibold text-slate-900">{runtimeStatus}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Loaded Model:</span>
            <span className="text-blue-700 font-bold break-all sm:break-normal">{data.model_version}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Location Model:</span>
            <span className="text-slate-800 break-all sm:break-normal">{data.location_model_version || 'Unavailable'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Time Model:</span>
            <span className="text-slate-800 break-all sm:break-normal">{data.time_model_version || 'Unavailable'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Feature Schema:</span>
            <span className="text-blue-700 font-bold">
              {data.runtime_info?.feature_schema_version || 'v7_compat'} ({data.location_features_count ?? 47} Location Signals)
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Calibrator:</span>
            <span className="text-emerald-700 font-semibold">{data.calibration_method || 'Platt Logistic Regression'}</span>
          </div>
          {data.runtime_info?.location_artifact_hash_short && (
            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center space-x-1">
                <Hash className="w-3 h-3 text-slate-400" />
                <span>Artifact SHA-256:</span>
              </span>
              <span className="font-mono text-slate-600 text-[11px]" title={data.runtime_info.location_artifact_hash || ''}>
                {data.runtime_info.location_artifact_hash_short}
              </span>
            </div>
          )}
          {data.runtime_info?.load_error && (
            <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-red-800 text-[11px]">
              <strong>Load Failure:</strong> {data.runtime_info.load_error}
            </div>
          )}
        </div>

        {/* SAVED PREDICTIONS PROVENANCE CARD */}
        <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-2">
          <div className="text-[#173A63] font-bold uppercase tracking-wider text-[11px] pb-1 border-b border-[#DCE5F0] flex items-center justify-between">
            <div className="flex items-center space-x-1.5">
              <History className="w-3.5 h-3.5 text-blue-600" />
              <span>SAVED PREDICTION PROVENANCE</span>
            </div>
            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700 border border-blue-200">
              Immutable History
            </span>
          </div>
          <div className="text-slate-600 text-xs leading-relaxed space-y-2">
            <p>
              {data.saved_prediction_provenance?.description || (
                `Saved database records retain the model version under which they were originally produced ` +
                `(e.g., demo-provider-v1 for SIH deterministic demo cases like CMP-1042, or cashout-location-xgb-v4 for historical records).`
              )}
            </p>
            <div className="p-2 bg-slate-50 rounded border border-slate-200 text-[11px] space-y-1">
              <div className="flex justify-between">
                <span className="text-slate-500">Live Inference Engine:</span>
                <span className="font-bold text-blue-800">{data.model_version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Demo Case Engine (CMP-1042):</span>
                <span className="font-mono text-slate-700">demo-provider-v1</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Historical Seed Complaints:</span>
                <span className="font-mono text-slate-700">cashout-location-xgb-v4</span>
              </div>
            </div>
            <p className="text-[11px] text-slate-500 italic">
              * Upgrading or retraining runtime models does not rewrite previous official saved outputs.
            </p>
          </div>
        </div>
      </div>

      {/* SECTION 2: Evaluation Evidence Provenance */}
      <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-3">
        <div className="flex items-center justify-between pb-1.5 border-b border-[#DCE5F0]">
          <div className="flex items-center space-x-2">
            <Database className="w-4 h-4 text-blue-600" />
            <span className="text-[#173A63] font-bold uppercase tracking-wider text-[11px]">
              EVALUATION EVIDENCE & DATA PROVENANCE
            </span>
          </div>
          {isEvalAvailable ? (
            <span className="px-2.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
              Evaluation Evidence Verified
            </span>
          ) : (
            <span className="px-2.5 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
              {evalStatus}: {data.evaluation_info?.availability_reason || 'Evaluation metadata not bound'}
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          <div>
            <span className="text-slate-500 block text-[11px]">Evaluated Model:</span>
            <span className="font-bold text-slate-900">{data.evaluation_info?.evaluated_model_version || data.model_version}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[11px]">Dataset Specification:</span>
            <span className="font-medium text-slate-800">{data.dataset_type || 'multi_regime_synthetic_delhi_v7'}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[11px]">Validation Split:</span>
            <span className="font-medium text-slate-800">{data.dataset_split || 'Internal Validation Split'}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[11px]">Training Universe:</span>
            <span className="font-bold text-blue-700">
              {data.training_samples ? `${data.training_samples.toLocaleString()} cases` : 'Not recorded'}
            </span>
          </div>
        </div>

        {data.synthetic_disclosure && (
          <div className="p-2.5 bg-blue-50/50 border border-blue-200 rounded text-[11px] text-blue-900 flex items-start space-x-2">
            <Info className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
            <span>
              <strong>Provenance Disclosure:</strong> {data.synthetic_disclosure}
            </span>
          </div>
        )}

        {!isEvalAvailable && data.evaluation_info?.availability_reason && (
          <div className="p-2.5 bg-amber-50 border border-amber-200 rounded text-[11px] text-amber-900 flex items-start space-x-2">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
            <span>
              <strong>Evaluation Availability Notice:</strong> {data.evaluation_info.availability_reason} Trained runtime inference remains active.
            </span>
          </div>
        )}
      </div>

      {/* SECTION 3: Research Models Governance */}
      {data.research_models && data.research_models.length > 0 && (
        <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-2 shadow-xs">
          <div className="flex items-center justify-between pb-1 border-b border-slate-200">
            <div className="flex items-center space-x-2">
              <Layers className="w-4 h-4 text-slate-700" />
              <span className="text-[#173A63] font-bold uppercase tracking-wider text-[11px]">
                RESEARCH MODELS & PRE-REGISTERED PROMOTION AUDIT
              </span>
            </div>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
              RESEARCH ONLY • NOT ACTIVE IN PRODUCTION
            </span>
          </div>

          {data.research_models.map((rm, idx) => (
            <div key={idx} className="space-y-2 pt-1">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <span className="text-slate-500 block text-[11px]">Research Candidate:</span>
                  <span className="font-mono font-bold text-slate-800 text-xs">{rm.model_name}</span>
                  <span className="block text-[10px] text-slate-600 mt-0.5">Architecture: {rm.model_type || 'XGBoost'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Pre-Registered Gate:</span>
                  <span className="font-mono font-semibold text-slate-800 text-xs">{rm.qualification_gate || 'Top-3 Gain >= +1.00 pp'}</span>
                  <span className="block text-[10px] text-slate-600 mt-0.5">
                    Observed: {rm.observed_gain || '+0.07 pp'} (Required: {rm.required_gain || '+1.00 pp'})
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Promotion Decision:</span>
                  <span className="font-bold text-amber-800 text-xs block">{rm.promotion_status}</span>
                  <span className="block text-[10px] text-emerald-700 font-medium mt-0.5">
                    Production Unaffected • Retained {rm.official_production_model || 'V7-compat'}
                  </span>
                </div>
              </div>
              {rm.details && (
                <div className="text-[11px] text-slate-600 bg-white p-2.5 rounded border border-slate-200">
                  {rm.details}
                </div>
              )}
            </div>
          ))}

          <div className="mt-2 pt-2 border-t border-slate-200 text-[11px] text-slate-600 flex items-start space-x-2">
            <Info className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
            <span>
              <strong>Consortium Governance:</strong> Hyperledger Fabric operates exclusively as a verified multi-organization intelligence ledger (BankA, BankB, BankC, I4C, LEA) and tamper-evident prediction audit anchor. Blockchain signals do not alter official production rankings.
            </span>
          </div>
        </div>
      )}

      {/* SECTION 4: Core Evaluation Metrics Pillars */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* 1. Location Prediction */}
        <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-blue-700 font-bold text-xs uppercase pb-2 border-b border-[#DCE5F0]">
            <MapPin className="w-4 h-4" />
            <span>Location Ranking</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Natural Candidate Recall:</span>
              <span className="text-blue-700">{renderMetric(data.natural_candidate_recall)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Recall@1:</span>
              <span className="text-slate-900">{renderMetric(data['Recall@1'])}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Recall@3:</span>
              <span className="text-emerald-700">{renderMetric(data['Recall@3'])}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Recall@5:</span>
              <span className="text-slate-700">{renderMetric(data['Recall@5'])}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Precision@3:</span>
              <span className="text-slate-700">{renderMetric(data['Precision@3'])}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Mean Reciprocal Rank:</span>
              <span className="text-blue-700">{renderMetric(data.MRR)}</span>
            </div>
          </div>
        </div>

        {/* 2. Geospatial Evaluation */}
        <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-amber-700 font-bold text-xs uppercase pb-2 border-b border-[#DCE5F0]">
            <Compass className="w-4 h-4" />
            <span>Geospatial Evaluation</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Median Centroid Dist Error:</span>
              <span className="text-amber-800">{renderMetric(data.median_cluster_centroid_distance_error_km)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Within 5 km:</span>
              <span className="text-slate-900">{renderMetric(data.within_5km)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Within 10 km:</span>
              <span className="text-slate-900">{renderMetric(data.within_10km)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Within 25 km:</span>
              <span className="text-slate-700">{renderMetric(data.within_25km)}</span>
            </div>
          </div>
        </div>

        {/* 3. Time-To-Cashout */}
        <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-blue-700 font-bold text-xs uppercase pb-2 border-b border-[#DCE5F0]">
            <Clock className="w-4 h-4" />
            <span>Time-To-Cashout</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Mean Absolute Error (MAE):</span>
              <span className="text-blue-700">{renderMetric(data.time_MAE_minutes)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Median Absolute Error:</span>
              <span className="text-slate-900">{renderMetric(data.time_median_absolute_error)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">±60m Window Coverage:</span>
              <span className="text-emerald-700">{renderMetric(data.time_window_coverage)}</span>
            </div>
          </div>
        </div>

        {/* 4. Calibration & Generalization */}
        <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-emerald-700 font-bold text-xs uppercase pb-2 border-b border-[#DCE5F0]">
            <Gauge className="w-4 h-4" />
            <span>Calibration & Generalization</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Expected Calibration Error:</span>
              <span className="text-emerald-700">{renderMetric(data.internal_ece !== undefined && data.internal_ece !== null ? data.internal_ece : data.Brier_score)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Cold-Start Candidate Recall:</span>
              <span className="text-slate-900">{renderMetric(data.cold_start_candidate_recall)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Cold-Start Recall@1:</span>
              <span className="text-slate-900">{renderMetric(data.cold_start_recall_at_1)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Cold-Start Recall@3:</span>
              <span className="text-blue-700">{renderMetric(data.cold_start_recall_at_3)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Disclaimers */}
      <div className="space-y-2 text-xs">
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-blue-900 flex items-start space-x-2.5">
          <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
          <div>
            <strong className="text-blue-950">Geospatial Granularity Note:</strong> {data.geographic_disclaimer || 'Cluster-level operational prioritization (2.5 km radius); not exact ATM/GPS coordinate prediction.'}
          </div>
        </div>

        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 flex items-start space-x-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <strong className="text-amber-950">Production Notice:</strong> {data.production_notice || 'Production deployment requires authorized historical NCRP complaint, transaction, account and withdrawal data for retraining, calibration and independent validation.'}
          </div>
        </div>

        {data.runtime_notice && (
          <div className="p-3 bg-[#F6F8FC] border border-[#DCE5F0] rounded-lg text-slate-700 flex items-start space-x-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <strong className="text-slate-900">Runtime Notice:</strong> {data.runtime_notice}
            </div>
          </div>
        )}
      </div>

      {/* Benchmark Metrics Comparison Table */}
      {data.metrics_comparison && data.metrics_comparison.length > 0 && (
        <div className="bg-white rounded-lg border border-[#DCE5F0] overflow-hidden shadow-xs">
          <div className="p-4 border-b border-[#DCE5F0] bg-[#F8FAFC] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-[#173A63] uppercase">
                Comparative Evaluation Matrix (Validation & Test Split)
              </h3>
              <p className="text-[11px] text-slate-500">
                Evaluation target: <strong className="text-blue-700">{data.evaluation_info?.evaluated_model_version || data.model_version}</strong>
              </p>
            </div>
            <span className="text-xs text-blue-700 font-semibold self-start sm:self-auto">
              {data.metrics_comparison.length} Evaluated Signals
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F8FAFC] text-slate-600 uppercase tracking-wider border-b border-[#DCE5F0]">
                <tr>
                  <th className="py-3 px-4 font-semibold">Metric</th>
                  <th className="py-3 px-4 font-semibold">Baseline / Reference</th>
                  <th className="py-3 px-4 font-semibold">{data.evaluation_info?.evaluated_model_version || 'CyberShield Model'}</th>
                  <th className="py-3 px-4 font-semibold">Performance Delta</th>
                  <th className="py-3 px-4 font-semibold">Comparability & Provenance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#DCE5F0] text-slate-700">
                {data.metrics_comparison.map((item, idx) => {
                  const isComparable = item.comparable !== false && item.delta !== 'Not comparable';
                  return (
                    <tr key={idx} className="hover:bg-blue-50/30 transition-colors">
                      <td className="py-3 px-4 font-medium text-slate-900">{item.metric}</td>
                      <td className="py-3 px-4 text-slate-500">{item.baseline ?? 'None'}</td>
                      <td className="py-3 px-4 text-blue-700 font-bold text-sm">
                        {item.cybershield ?? 'Not evaluated'}
                      </td>
                      <td className="py-3 px-4">
                        {isComparable ? (
                          <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
                            {item.delta}
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-semibold border border-slate-200">
                            Not comparable
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-500 text-[11px] max-w-xs">
                        {item.comparability_note || (isComparable ? 'Compatible benchmark set' : 'Evaluation sets or objectives differ')}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Global Feature Importances */}
      {data.feature_importances && data.feature_importances.length > 0 && (
        <div className="bg-white rounded-lg border border-[#DCE5F0] p-5 shadow-xs">
          <div className="flex items-center space-x-2 mb-4">
            <Sparkles className="w-4 h-4 text-blue-600" />
            <h3 className="text-sm font-bold text-[#173A63] uppercase">
              Authoritative Feature Importance (XGBoost Split Gain Attributions)
            </h3>
          </div>

          <div className="space-y-3 text-xs">
            {data.feature_importances.map((f, idx) => (
              <div key={idx} className="p-3 bg-[#F6F8FC] rounded-lg border border-[#DCE5F0]">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-slate-800 font-medium">
                    {f.feature} {f.feature_code && <span className="text-[10px] text-slate-400 font-mono">({f.feature_code})</span>}
                  </span>
                  <span className="text-blue-700 font-bold">{(f.importance * 100).toFixed(1)}%</span>
                </div>
                <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-600 rounded-full"
                    style={{ width: `${Math.min(f.importance * 100 * 2.5, 100)}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
