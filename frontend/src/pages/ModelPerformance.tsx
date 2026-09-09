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
        <div className="h-20 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
          ))}
        </div>
        <div className="h-96 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8 bg-[#0a1020] rounded-2xl border border-red-500/40 text-center space-y-4 font-mono">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Model Telemetry Unavailable</h2>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          {error || 'CyberShield AI model metadata could not be verified from the server.'}
        </p>
      </div>
    );
  }

  const isTrainedML = data.prediction_mode === 'trained_ml';

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <Cpu className="w-5 h-5 text-cyan-400" />
            <h1 className="text-xl font-bold text-white font-['JetBrains_Mono',monospace]">
              AI Model Performance & Algorithmic Validation
            </h1>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Prediction Mode: <strong className="text-cyan-400 font-semibold">{data.prediction_mode === 'trained_ml' ? 'Trained ML' : 'Deterministic Demo'}</strong> | Model Version: <strong className="text-white font-semibold">{data.model_version}</strong>
          </p>
        </div>

        {/* Prototype Evaluation Notice */}
        <div className="px-3.5 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 font-mono text-xs font-bold flex items-center space-x-2 shrink-0">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>{data.evaluation_label || 'Prototype Evaluation — Synthetic/Anonymized Demo Data'}</span>
        </div>
      </div>

      {/* Model Spec & Evaluation Data Provenance Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
        {/* MODEL SPEC */}
        <div className="p-4 rounded-xl bg-[#080e1c] border border-[#162544] space-y-2">
          <div className="text-cyan-400 font-bold uppercase tracking-wider text-[11px] pb-1 border-b border-[#162544] flex items-center justify-between">
            <span>MODEL SPECIFICATION</span>
            <span className={`px-2 py-0.5 rounded text-[10px] ${isTrainedML ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-amber-500/20 text-amber-400'}`}>
              {isTrainedML ? 'Trained ML Active' : 'Deterministic Demo'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Prediction Mode:</span>
            <span className="text-white font-semibold">{data.current_prediction_mode || 'Trained ML'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Model Version:</span>
            <span className="text-cyan-300 font-bold">{data.model_version}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Location Model:</span>
            <span className="text-slate-200">{data.model_class || 'XGBoost Candidate Location Ranker'}</span>
          </div>
          {data.calibrator_class && (
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Probability Calibrator:</span>
              <span className="text-slate-300 text-[11px]">{data.calibrator_class}</span>
            </div>
          )}
        </div>

        {/* EVALUATION DATA */}
        <div className="p-4 rounded-xl bg-[#080e1c] border border-[#162544] space-y-2">
          <div className="text-cyan-400 font-bold uppercase tracking-wider text-[11px] pb-1 border-b border-[#162544]">
            EVALUATION PROTOCOL & DATA
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Dataset Scope:</span>
            <span className="text-amber-300 font-semibold">{data.evaluation_label}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Partition Protocol:</span>
            <span className="text-slate-200">{data.dataset_split}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Sample Partitions:</span>
            <span className="text-slate-300">
              Train: {data.training_samples?.toLocaleString()} | Val: {data.validation_samples?.toLocaleString()} | Test: {data.test_samples?.toLocaleString()}
            </span>
          </div>
          {data.cold_start_test_samples && (
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Cold-Start Unseen Syndicates:</span>
              <span className="text-slate-300">{data.cold_start_test_samples?.toLocaleString()} cases</span>
            </div>
          )}
        </div>
      </div>

      {/* CORE EVALUATION METRICS PILLARS */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 font-mono">
        {/* 1. Location Prediction */}
        <div className="p-4 rounded-xl bg-[#0a1020] border border-[#162544] space-y-3">
          <div className="flex items-center space-x-2 text-cyan-400 font-bold text-xs uppercase pb-2 border-b border-[#162544]">
            <MapPin className="w-4 h-4" />
            <span>Location Prediction</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">Natural Candidate Recall:</span>
              <span className="text-cyan-300 font-bold">{data.natural_candidate_recall}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Recall@1:</span>
              <span className="text-white font-bold">{data['Recall@1']}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Recall@3:</span>
              <span className="text-emerald-400 font-bold">{data['Recall@3']}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Recall@5:</span>
              <span className="text-slate-200">{data['Recall@5']}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Precision@3:</span>
              <span className="text-slate-200">{data['Precision@3']}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Mean Reciprocal Rank (MRR):</span>
              <span className="text-cyan-300 font-bold">{data.MRR}</span>
            </div>
          </div>
        </div>

        {/* 2. Geospatial Evaluation */}
        <div className="p-4 rounded-xl bg-[#0a1020] border border-[#162544] space-y-3">
          <div className="flex items-center space-x-2 text-amber-400 font-bold text-xs uppercase pb-2 border-b border-[#162544]">
            <Compass className="w-4 h-4" />
            <span>Geospatial Evaluation</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">Median Centroid Dist Error:</span>
              <span className="text-amber-300 font-bold">{data.median_cluster_centroid_distance_error_km}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Within 5 km:</span>
              <span className="text-white font-bold">{data.within_5km}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Within 10 km:</span>
              <span className="text-white font-bold">{data.within_10km}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Within 25 km:</span>
              <span className="text-slate-300">{data.within_25km}</span>
            </div>
          </div>
        </div>

        {/* 3. Time-To-Cashout */}
        <div className="p-4 rounded-xl bg-[#0a1020] border border-[#162544] space-y-3">
          <div className="flex items-center space-x-2 text-blue-400 font-bold text-xs uppercase pb-2 border-b border-[#162544]">
            <Clock className="w-4 h-4" />
            <span>Time-To-Cashout</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">Mean Absolute Error (MAE):</span>
              <span className="text-blue-300 font-bold">{data.time_MAE_minutes}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Median Absolute Error:</span>
              <span className="text-white font-bold">{data.time_median_absolute_error}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">±60m Window Coverage:</span>
              <span className="text-emerald-400 font-bold">{data.time_window_coverage}</span>
            </div>
          </div>
        </div>

        {/* 4. Calibration & Cold-Start */}
        <div className="p-4 rounded-xl bg-[#0a1020] border border-[#162544] space-y-3">
          <div className="flex items-center space-x-2 text-emerald-400 font-bold text-xs uppercase pb-2 border-b border-[#162544]">
            <Gauge className="w-4 h-4" />
            <span>Calibration & Generalization</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">Calibrated Brier Score:</span>
              <span className="text-emerald-300 font-bold">{data.Brier_score}</span>
            </div>
            {data.cold_start_candidate_recall && (
              <div className="flex justify-between">
                <span className="text-slate-400">Cold-Start Candidate Recall:</span>
                <span className="text-white">{data.cold_start_candidate_recall}</span>
              </div>
            )}
            {data.cold_start_recall_at_1 && (
              <div className="flex justify-between">
                <span className="text-slate-400">Cold-Start Recall@1:</span>
                <span className="text-white">{data.cold_start_recall_at_1}</span>
              </div>
            )}
            {data.cold_start_recall_at_3 && (
              <div className="flex justify-between">
                <span className="text-slate-400">Cold-Start Recall@3:</span>
                <span className="text-cyan-300 font-bold">{data.cold_start_recall_at_3}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Visible Disclaimers & Operational Guidance */}
      <div className="space-y-2 font-mono text-xs">
        <div className="p-3 bg-[#080e1c] border border-cyan-500/30 rounded-xl text-slate-300 flex items-start space-x-2.5">
          <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
          <div>
            <strong className="text-cyan-300">Geospatial Granularity Note:</strong> {data.geographic_disclaimer || 'Cluster-level operational prioritization; not exact ATM/GPS prediction.'}
          </div>
        </div>

        <div className="p-3 bg-amber-950/30 border border-amber-500/30 rounded-xl text-amber-200 flex items-start space-x-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <strong className="text-amber-300">Production Requirement:</strong> {data.production_notice || 'Production performance requires retraining and independent validation on authorized historical NCRP and financial transaction data.'}
          </div>
        </div>

        {data.runtime_notice && (
          <div className="p-3 bg-[#060a15] border border-[#162544] rounded-xl text-slate-400 flex items-start space-x-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <strong className="text-slate-300">Runtime Status:</strong> {data.runtime_notice}
            </div>
          </div>
        )}
      </div>

      {/* Benchmark Metrics Comparison Table */}
      {data.metrics_comparison && data.metrics_comparison.length > 0 && (
        <div className="bg-[#0a1020] rounded-2xl border border-[#162544] overflow-hidden shadow-2xl">
          <div className="p-4 border-b border-[#162544] flex items-center justify-between">
            <h3 className="text-sm font-bold text-white font-mono uppercase">
              Comparative Evaluation Matrix (Validation & Test Split)
            </h3>
            <span className="text-xs text-cyan-400 font-mono">{data.metrics_comparison.length} Predictive Metrics</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-[#070c18] text-slate-400 uppercase tracking-wider border-b border-[#162544]">
                <tr>
                  <th className="py-3.5 px-4">Metric</th>
                  <th className="py-3.5 px-4">Historical Baseline</th>
                  <th className="py-3.5 px-4">CyberShield AI (v2)</th>
                  <th className="py-3.5 px-4">Performance Delta</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#162544] text-slate-200">
                {data.metrics_comparison.map((item, idx) => (
                  <tr key={idx} className="hover:bg-[#0d162d] transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-100">{item.metric}</td>
                    <td className="py-3 px-4 text-slate-400">{item.baseline}</td>
                    <td className="py-3 px-4 text-cyan-300 font-bold text-sm">
                      {item.cybershield}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20">
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
        <div className="bg-[#0a1020] rounded-2xl border border-[#162544] p-5 shadow-2xl">
          <div className="flex items-center space-x-2 mb-4">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-bold text-white font-mono uppercase">
              Global Feature Importance (XGBoost Split Gain Attributions)
            </h3>
          </div>

          <div className="space-y-3 font-mono text-xs">
            {data.feature_importances.map((f, idx) => (
              <div key={idx} className="p-3 bg-[#070c18] rounded-lg border border-[#162544]">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-slate-200 font-semibold">{f.feature}</span>
                  <span className="text-cyan-400 font-bold">{Math.round(f.importance * 100)}%</span>
                </div>
                <div className="w-full h-2 bg-[#121c33] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-cyan-400 rounded-full"
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
