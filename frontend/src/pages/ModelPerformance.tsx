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
  Compass
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

  const isTrainedML = data.prediction_mode === 'trained_ml';

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <Cpu className="w-5 h-5 text-blue-600 shrink-0" />
            <h1 className="text-lg font-bold text-[#173A63] font-sans">
              AI Model Performance & Algorithmic Validation
            </h1>
          </div>
          <p className="text-xs text-slate-500 font-sans mt-0.5">
            Prediction Mode: <strong className="text-blue-700 font-semibold">{data.prediction_mode === 'trained_ml' ? 'Trained ML' : 'Deterministic Demo'}</strong> | Model Version: <strong className="text-slate-900 font-semibold">{data.model_version}</strong>
          </p>
        </div>

        {/* Prototype Evaluation Notice */}
        <div className="px-3.5 py-1.5 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold flex items-center space-x-2 shrink-0">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>{data.evaluation_label || 'Prototype Evaluation — Synthetic/Anonymized Demo Data'}</span>
        </div>
      </div>

      {/* Model Spec & Evaluation Data Provenance Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        {/* MODEL SPEC */}
        <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-2">
          <div className="text-[#173A63] font-bold uppercase tracking-wider text-[11px] pb-1 border-b border-[#DCE5F0] flex items-center justify-between">
            <span>MODEL SPECIFICATION</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${isTrainedML ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700'}`}>
              {isTrainedML ? 'Trained ML Active' : 'Deterministic Demo'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Prediction Mode:</span>
            <span className="text-slate-900 font-semibold">{data.current_prediction_mode || 'Trained ML'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Model Version:</span>
            <span className="text-blue-700 font-bold break-all sm:break-normal">{data.model_version}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Location Model:</span>
            <span className="text-slate-800 break-all sm:break-normal">{data.location_model_version || 'unavailable'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Time Model:</span>
            <span className="text-slate-800 break-all sm:break-normal">{data.time_model_version || 'unavailable'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Location Feature Count:</span>
            <span className="text-blue-700 font-bold">{data.location_features_count ?? 43} Engineered Signals</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Time Feature Count:</span>
            <span className="text-blue-700 font-bold">{data.time_features_count ?? 20} Temporal Signals</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Calibration Method:</span>
            <span className="text-emerald-700 font-semibold">{data.calibration_method || 'Isotonic (5-Fold CV)'}</span>
          </div>
        </div>

        {/* DATA PROVENANCE */}
        <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-2">
          <div className="text-[#173A63] font-bold uppercase tracking-wider text-[11px] pb-1 border-b border-[#DCE5F0]">
            EVALUATION DATA PROVENANCE
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Total Pilot Universe:</span>
            <span className="text-slate-900 font-semibold">{data.training_samples?.toLocaleString()} cases</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Active Cash-Out Clusters:</span>
            <span className="text-slate-900 font-semibold">{data.active_clusters_count ?? 60} Clusters</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Atm Coverage:</span>
            <span className="text-slate-900 font-semibold">{data.atm_coverage_count?.toLocaleString() ?? '1,200+'} Terminals</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Validation Split:</span>
            <span className="text-slate-900">{data.dataset_split}</span>
          </div>
          {data.cold_start_test_samples && (
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Cold-Start Unseen Syndicates:</span>
              <span className="text-slate-800">{data.cold_start_test_samples?.toLocaleString()} cases</span>
            </div>
          )}
        </div>
      </div>

      {/* RESEARCH & ABLATION STATUS CARD (B.6 Qualification Audit) */}
      <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-2 shadow-xs">
        <div className="flex items-center justify-between pb-1 border-b border-slate-200">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-slate-700" />
            <span className="text-[#173A63] font-bold uppercase tracking-wider text-[11px]">
              RESEARCH PIPELINE & ABLATION AUDIT (PHASE B.6)
            </span>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
            RESEARCH ONLY • NOT ACTIVE IN PRODUCTION
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
          <div>
            <span className="text-slate-500 block text-[11px]">Official Production Model:</span>
            <span className="font-mono font-bold text-blue-800 text-xs">cashout-location-xgb-v7-compat</span>
            <span className="block text-[10px] text-emerald-700 font-medium mt-0.5">Active runtime inference engine</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[11px]">Research Candidate:</span>
            <span className="font-mono font-bold text-slate-800 text-xs">Blockchain Shadow Re-Ranker V1</span>
            <span className="block text-[10px] text-slate-600 mt-0.5">Evaluated in Phase B.6 ablation study</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[11px]">Promotion Qualification Decision:</span>
            <span className="font-bold text-amber-800 text-xs block">DID NOT MEET PROMOTION GATE</span>
            <span className="block text-[10px] text-slate-600 mt-0.5">
              Gate (+1.0 pp Top-3) not met (+0.07 pp observed). Retained validated V7 model.
            </span>
          </div>
        </div>
        <div className="mt-2 pt-2 border-t border-slate-200 text-[11px] text-slate-600 flex items-start space-x-2">
          <Info className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
          <span>
            <strong>Consortium Governance:</strong> Hyperledger Fabric operates exclusively as a verified multi-organization intelligence ledger (BankA, BankB, BankC, I4C, LEA) and tamper-evident prediction audit anchor. Blockchain signals do not alter official production rankings.
          </span>
        </div>
      </div>

      {/* CORE EVALUATION METRICS PILLARS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* 1. Location Prediction */}
        <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-blue-700 font-bold text-xs uppercase pb-2 border-b border-[#DCE5F0]">
            <MapPin className="w-4 h-4" />
            <span>Location Prediction</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Natural Candidate Recall:</span>
              <span className="text-blue-700 font-bold">{data.natural_candidate_recall}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Recall@1:</span>
              <span className="text-slate-900 font-bold">{data['Recall@1']}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Recall@3:</span>
              <span className="text-emerald-700 font-bold">{data['Recall@3']}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Recall@5:</span>
              <span className="text-slate-700">{data['Recall@5']}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Precision@3:</span>
              <span className="text-slate-700">{data['Precision@3']}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Mean Reciprocal Rank (MRR):</span>
              <span className="text-blue-700 font-bold">{data.MRR}</span>
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
              <span className="text-amber-800 font-bold">{data.median_cluster_centroid_distance_error_km}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Within 5 km:</span>
              <span className="text-slate-900 font-bold">{data.within_5km}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Within 10 km:</span>
              <span className="text-slate-900 font-bold">{data.within_10km}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Within 25 km:</span>
              <span className="text-slate-700">{data.within_25km}</span>
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
              <span className="text-blue-700 font-bold">{data.time_MAE_minutes}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Median Absolute Error:</span>
              <span className="text-slate-900 font-bold">{data.time_median_absolute_error}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">±60m Window Coverage:</span>
              <span className="text-emerald-700 font-bold">{data.time_window_coverage}</span>
            </div>
          </div>
        </div>

        {/* 4. Calibration & Cold-Start */}
        <div className="p-4 rounded-lg bg-white border border-[#DCE5F0] shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-emerald-700 font-bold text-xs uppercase pb-2 border-b border-[#DCE5F0]">
            <Gauge className="w-4 h-4" />
            <span>Calibration & Generalization</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Calibrated Brier Score:</span>
              <span className="text-emerald-700 font-bold">{data.Brier_score}</span>
            </div>
            {data.cold_start_candidate_recall && (
              <div className="flex justify-between">
                <span className="text-slate-500">Cold-Start Candidate Recall:</span>
                <span className="text-slate-900">{data.cold_start_candidate_recall}</span>
              </div>
            )}
            {data.cold_start_recall_at_1 && (
              <div className="flex justify-between">
                <span className="text-slate-500">Cold-Start Recall@1:</span>
                <span className="text-slate-900">{data.cold_start_recall_at_1}</span>
              </div>
            )}
            {data.cold_start_recall_at_3 && (
              <div className="flex justify-between">
                <span className="text-slate-500">Cold-Start Recall@3:</span>
                <span className="text-blue-700 font-bold">{data.cold_start_recall_at_3}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Visible Disclaimers & Operational Guidance */}
      <div className="space-y-2 text-xs">
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-blue-900 flex items-start space-x-2.5">
          <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
          <div>
            <strong className="text-blue-950">Geospatial Granularity Note:</strong> {data.geographic_disclaimer || 'Cluster-level operational prioritization; not exact ATM/GPS prediction.'}
          </div>
        </div>

        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 flex items-start space-x-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <strong className="text-amber-950">Production Requirement:</strong> {data.production_notice || 'Production performance requires retraining and independent validation on authorized historical NCRP and financial transaction data.'}
          </div>
        </div>

        {data.runtime_notice && (
          <div className="p-3 bg-[#F6F8FC] border border-[#DCE5F0] rounded-lg text-slate-700 flex items-start space-x-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <strong className="text-slate-900">Runtime Status:</strong> {data.runtime_notice}
            </div>
          </div>
        )}
      </div>

      {/* Benchmark Metrics Comparison Table */}
      {data.metrics_comparison && data.metrics_comparison.length > 0 && (
        <div className="bg-white rounded-lg border border-[#DCE5F0] overflow-hidden shadow-xs">
          <div className="p-4 border-b border-[#DCE5F0] bg-[#F8FAFC] flex items-center justify-between">
            <h3 className="text-sm font-bold text-[#173A63] uppercase">
              Comparative Evaluation Matrix (Validation & Test Split)
            </h3>
            <span className="text-xs text-blue-700 font-semibold">{data.metrics_comparison.length} Predictive Metrics</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F8FAFC] text-slate-600 uppercase tracking-wider border-b border-[#DCE5F0]">
                <tr>
                  <th className="py-3 px-4 font-semibold">Metric</th>
                  <th className="py-3 px-4 font-semibold">Historical Baseline</th>
                  <th className="py-3 px-4 font-semibold">CyberShield AI (v2)</th>
                  <th className="py-3 px-4 font-semibold">Performance Delta</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#DCE5F0] text-slate-700">
                {data.metrics_comparison.map((item, idx) => (
                  <tr key={idx} className="hover:bg-blue-50/30 transition-colors">
                    <td className="py-3 px-4 font-medium text-slate-900">{item.metric}</td>
                    <td className="py-3 px-4 text-slate-500">{item.baseline}</td>
                    <td className="py-3 px-4 text-blue-700 font-bold text-sm">
                      {item.cybershield}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
                        {item.delta}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Feature Importances Grid */}
      {data.feature_importances && data.feature_importances.length > 0 && (
        <div className="bg-white rounded-lg border border-[#DCE5F0] p-5 shadow-xs">
          <div className="flex items-center space-x-2 mb-4">
            <Sparkles className="w-4 h-4 text-blue-600" />
            <h3 className="text-sm font-bold text-[#173A63] uppercase">
              Global Feature Importance (XGBoost Split Gain Attributions)
            </h3>
          </div>

          <div className="space-y-3 text-xs">
            {data.feature_importances.map((f, idx) => (
              <div key={idx} className="p-3 bg-[#F6F8FC] rounded-lg border border-[#DCE5F0]">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-slate-800 font-medium">{f.feature}</span>
                  <span className="text-blue-700 font-bold">{Math.round(f.importance * 100)}%</span>
                </div>
                <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-600 rounded-full"
                    style={{ width: `${Math.min(f.importance * 100 * 2.2, 100)}%` }}
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
