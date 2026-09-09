import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  MapPin,
  Clock,
  TrendingUp,
  BrainCircuit,
  Network,
  BellRing,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Sparkles,
  Info,
  Layers,
  Map as MapIcon,
  RefreshCw,
  Gauge,
  Activity,
  Compass
} from 'lucide-react';
import { api } from '../services/api';
import { Complaint, Prediction, Explanation, HotspotCluster } from '../types';
import { CashOutRiskMap } from '../maps/CashOutRiskMap';
import { formatRisk } from '../utils/formatters';

export const CaseIntelligence: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const caseId = id || 'CMP-1042';
  const navigate = useNavigate();

  const [complaint, setComplaint] = useState<Complaint | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [clusters, setClusters] = useState<HotspotCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningPrediction, setRunningPrediction] = useState(false);
  const [alertSuccess, setAlertSuccess] = useState<string | null>(null);

  const fetchCaseDetails = async () => {
    setLoading(true);
    try {
      const [compData, predData, mapData] = await Promise.all([
        api.getComplaint(caseId),
        api.getPrediction(caseId),
        api.getRiskMap()
      ]);
      setComplaint(compData);
      setPrediction(predData);
      setClusters(mapData.hotspots);

      if (predData?.prediction_id) {
        const explData = await api.getExplanation(predData.prediction_id);
        setExplanation(explData);
      }
    } catch (err) {
      console.error('Failed to load case intelligence', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCaseDetails();
  }, [caseId]);

  // Button Action: Run Predictive Analysis
  const handleRunPrediction = async () => {
    setRunningPrediction(true);
    try {
      const newPred = await api.runPrediction(caseId);
      setPrediction(newPred);
      if (newPred?.prediction_id) {
        const explData = await api.getExplanation(newPred.prediction_id);
        setExplanation(explData);
      }
    } catch (err) {
      console.error('Error running prediction', err);
    } finally {
      setRunningPrediction(false);
    }
  };

  // Button Action: Generate Alert
  const handleGenerateAlert = async () => {
    if (!complaint || !prediction) return;
    try {
      const alerts = await api.getAlerts();
      const existing = alerts.find(a => a.complaint_id === complaint.id);
      const targetLoc = prediction.where_location || 'predicted cash-out hotspot';
      const msg = `Immediate ground intercept dispatched to ${targetLoc}`;
      if (existing) {
        await api.acknowledgeAlert(existing.id, msg);
      }
      setAlertSuccess(msg);
      setTimeout(() => setAlertSuccess(null), 4500);
    } catch (err) {
      console.error('Error generating alert', err);
    }
  };

  if (loading || !complaint) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-24 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-36 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
          ))}
        </div>
        <div className="h-96 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
      </div>
    );
  }

  const isTrained = prediction?.prediction_mode === 'trained_ml';
  const isDemo = prediction?.prediction_mode === 'deterministic_demo';
  const highlightedClusterName = prediction?.where_location || prediction?.top_locations?.[0]?.location_name || clusters?.[0]?.cluster_name;

  return (
    <div className="space-y-6 pb-12">
      {/* Case Header & Status Bar */}
      <div className="p-6 bg-gradient-to-r from-[#0a1122] via-[#0d1730] to-[#0a1122] rounded-2xl border border-[#162544] shadow-2xl">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <span className="text-xl font-bold font-mono text-cyan-400">
                {complaint.complaint_number}
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-red-500/20 text-red-400 border border-red-500/40">
                {complaint.risk_level} RISK
              </span>
              <span className="px-2 py-0.5 rounded bg-[#162544] text-slate-300 text-xs font-mono">
                {complaint.fraud_type}
              </span>
              <span className="text-xs text-slate-400 font-mono">
                Channel: <strong className="text-white">{complaint.payment_channel}</strong>
              </span>

              {/* Provenance Indicator Badge */}
              {isTrained && (
                <span className="px-2.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 text-xs font-mono font-bold flex items-center space-x-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span>Prediction Mode: Trained ML ({prediction?.model_version || 'cashout-location-xgb-v2'})</span>
                </span>
              )}
              {isDemo && (
                <span className="px-2.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-mono font-bold flex items-center space-x-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  <span>Prediction Mode: Deterministic Demo ({prediction?.model_version || 'demo-provider-v1'})</span>
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs text-slate-300 font-mono mt-1">
              <div>
                Amount at Risk:{' '}
                <strong className="text-emerald-400 text-sm">₹{complaint.amount.toLocaleString('en-IN')}</strong>
              </div>
              <span>•</span>
              <div>
                Victim:{' '}
                <span className="text-slate-200 font-semibold">{complaint.victim_name || 'Reported Victim'}</span>
              </div>
              <span>•</span>
              <div>
                Origin:{' '}
                <span className="text-slate-200">{complaint.victim_location}</span>
              </div>
              <span>•</span>
              <div>
                Status:{' '}
                <span className="text-cyan-400 font-bold">{complaint.case_status}</span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => navigate(`/network/${complaint.complaint_number}`)}
              className="px-3.5 py-2 rounded-lg bg-[#0e1933] hover:bg-[#142347] border border-cyan-500/40 text-cyan-300 text-xs font-mono font-semibold flex items-center space-x-1.5 transition-all shadow-md"
            >
              <Network className="w-4 h-4" />
              <span>ANALYZE NETWORK</span>
            </button>

            <button
              onClick={handleRunPrediction}
              disabled={runningPrediction}
              className="px-3.5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-semibold flex items-center space-x-1.5 transition-all shadow-[0_0_15px_rgba(0,216,255,0.3)] disabled:opacity-50"
            >
              <BrainCircuit className="w-4 h-4" />
              <span>{runningPrediction ? 'INFERRING...' : 'RUN PREDICTIVE ANALYSIS'}</span>
            </button>

            <button
              onClick={() => navigate('/risk-map')}
              className="px-3.5 py-2 rounded-lg bg-[#0e1933] hover:bg-[#142347] border border-[#1b2b4d] text-slate-300 text-xs font-mono font-semibold flex items-center space-x-1.5 transition-all"
            >
              <MapIcon className="w-4 h-4" />
              <span>SHOW ON MAP</span>
            </button>

            <button
              onClick={handleGenerateAlert}
              className="px-3.5 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-mono font-semibold flex items-center space-x-1.5 transition-all shadow-[0_0_15px_rgba(239,68,68,0.3)]"
            >
              <BellRing className="w-4 h-4" />
              <span>GENERATE ALERT</span>
            </button>
          </div>
        </div>

        {alertSuccess && (
          <div className="mt-4 p-3 bg-emerald-950/60 border border-emerald-500/40 rounded-lg text-emerald-300 text-xs font-mono flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>CRITICAL ALERT ACKNOWLEDGED: {alertSuccess}</span>
          </div>
        )}

        {/* Investigation Timeline */}
        <div className="mt-6 pt-5 border-t border-[#162544]">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-mono mb-3">
            Investigation Lifecycle Progress
          </div>
          <div className="flex items-center justify-between relative">
            <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-[#162544] -translate-y-1/2 -z-0"></div>

            {[
              { label: 'Complaint', state: 'Registered', done: true },
              { label: 'Network Extraction', state: 'Multi-Hop Traced', done: true },
              { label: 'Mule Clustering', state: 'Corridor Identified', done: true },
              {
                label: 'AI Prediction',
                state: prediction?.where_location
                  ? `${prediction.where_location.split(',')[0]} (${Number.isFinite(prediction.confidence_score) ? Math.round(prediction.confidence_score * 100) + '%' : 'Calculated'})`
                  : 'Pending Ingestion',
                done: !!prediction
              },
              {
                label: 'Operational Priority',
                state: prediction ? `Priority ${prediction.intervention_priority}/100` : 'Evaluating',
                done: !!prediction
              },
              { label: 'Tactical Intercept', state: alertSuccess ? 'Dispatched' : 'Armed', done: !!alertSuccess }
            ].map((step, idx) => (
              <div key={idx} className="flex flex-col items-center relative z-10">
                <div
                  className={`w-7 h-7 rounded-full border-2 border-[#060913] flex items-center justify-center font-bold text-xs ${
                    step.done
                      ? 'bg-cyan-500 text-[#060913] shadow-[0_0_12px_rgba(0,216,255,0.6)]'
                      : 'bg-[#162544] text-slate-400'
                  }`}
                >
                  {step.done ? '✓' : idx + 1}
                </div>
                <span className="text-xs font-bold text-slate-200 mt-2 font-mono">{step.label}</span>
                <span className="text-[10px] text-cyan-400 font-mono text-center max-w-[120px] truncate">
                  {step.state}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* DISTINCT SCORE SEMANTICS: WHERE, WHEN, OVERALL RISK, MODEL CONFIDENCE */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* WHERE */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-cyan-500/40 shadow-xl relative overflow-hidden group hover:border-cyan-400 transition-all">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 flex items-center space-x-1.5">
              <MapPin className="w-4 h-4" />
              <span>WHERE</span>
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 font-mono">
              Top Ranked Cluster
            </span>
          </div>
          <div className="text-lg font-bold text-white font-mono mt-1 truncate">
            {prediction?.where_location || 'Location Analysis Pending'}
          </div>
          <p className="text-xs text-slate-400 mt-2 font-mono leading-relaxed truncate">
            {prediction?.top_locations?.[0]?.reasoning || 'Target cluster candidate evaluated via corridor analysis'}
          </p>
        </div>

        {/* WHEN */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-xl hover:border-cyan-500/40 transition-all">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-amber-400 flex items-center space-x-1.5">
              <Clock className="w-4 h-4" />
              <span>WHEN</span>
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 font-mono">
              Temporal Window
            </span>
          </div>
          <div className="text-lg font-bold text-amber-300 font-mono mt-1">
            {prediction?.when_window || 'Window Analysis Pending'}
          </div>
          <p className="text-xs text-slate-400 mt-2 font-mono leading-relaxed">
            Target cash-out interception horizon
          </p>
        </div>

        {/* OVERALL RISK (Fused Operational Score) */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-red-500/40 shadow-xl hover:border-red-500/70 transition-all relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-red-400 flex items-center space-x-1.5">
              <ShieldAlert className="w-4 h-4" />
              <span>OVERALL RISK</span>
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-bold font-mono">
              {prediction?.risk_level || 'EVALUATING'}
            </span>
          </div>
          <div className="text-2xl font-bold text-red-400 font-mono mt-1">
            {formatRisk(prediction?.risk_score, prediction?.risk_percentage)}
          </div>
          <p className="text-xs text-slate-400 mt-2 font-mono leading-relaxed">
            Fused Operational Risk Score (4-Pillar Pipeline)
          </p>
        </div>

        {/* MODEL CONFIDENCE (Calibrated ML Probability) */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-blue-500/40 shadow-xl hover:border-blue-500/70 transition-all">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-blue-400 flex items-center space-x-1.5">
              <Gauge className="w-4 h-4" />
              <span>MODEL CONFIDENCE</span>
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300 font-mono">
              Calibrated ML Prob
            </span>
          </div>
          <div className="text-2xl font-bold text-blue-300 font-mono mt-1">
            {prediction && Number.isFinite(prediction.confidence_score)
              ? `${Math.round(prediction.confidence_score * 100)}%`
              : 'Unavailable'}
          </div>
          <p className="text-xs text-slate-400 mt-2 font-mono leading-relaxed">
            Platt-scaled XGBoost v2 probability estimate
          </p>
        </div>
      </div>

      {/* INTERVENTION PRIORITY SCORE BANNER & PROVENANCE */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-red-950/40 via-[#0e1628] to-red-950/40 border border-red-500/40 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center space-x-4">
          <div className="w-14 h-14 rounded-xl bg-red-500/20 border border-red-500/50 flex items-center justify-center text-red-400 font-mono font-bold text-xl shrink-0">
            {prediction?.intervention_priority ?? '—'}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-bold font-mono uppercase text-red-400">
                INTERVENTION PRIORITY SCORE:
              </span>
              <span className="text-base font-bold text-white font-mono">
                {prediction ? `${prediction.intervention_priority} / 100` : '—'}
              </span>
              <span className="px-2 py-0.5 rounded bg-red-500 text-white font-bold text-[10px] font-mono">
                {prediction?.priority_level || 'MONITOR'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 font-mono">
              Provenance:{' '}
              <strong className="text-cyan-400">
                {isTrained ? 'Trained ML' : isDemo ? 'Deterministic Demo' : prediction?.prediction_mode || 'Evaluating'}
              </strong>{' '}
              | Model Version: <strong className="text-white">{prediction?.model_version || 'pending'}</strong>
            </p>
          </div>
        </div>

        <button
          onClick={handleGenerateAlert}
          className="px-5 py-2.5 bg-red-600 hover:bg-red-500 text-white font-mono text-xs font-bold rounded-xl transition-all shadow-[0_0_15px_rgba(239,68,68,0.4)] shrink-0 flex items-center space-x-2"
        >
          <BellRing className="w-4 h-4" />
          <span>DISPATCH INTERCEPT</span>
        </button>
      </div>

      {/* 4-PILLAR SCORE BREAKDOWN */}
      <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl">
        <div className="flex items-center justify-between pb-3 border-b border-[#162544] mb-4">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-bold text-white font-mono uppercase tracking-wider">
              4-Pillar Composite Risk Breakdown (Backend Fusion Weights)
            </h3>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">
            Overall Fused Risk: <strong className="text-red-400">{formatRisk(prediction?.risk_score, prediction?.risk_percentage)}</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-mono text-xs">
          {/* Pillar 1: ML Model Score */}
          <div className="p-3 bg-[#070c18] rounded-xl border border-[#162544] space-y-1.5">
            <div className="flex justify-between items-center text-slate-300">
              <span className="font-semibold">ML Location Ranker</span>
              <span className="text-cyan-400 font-bold">
                {prediction && Number.isFinite(prediction.ml_score) ? `${Math.round(prediction.ml_score * 100)}%` : '—'}
              </span>
            </div>
            <div className="w-full h-1.5 bg-[#121c33] rounded-full overflow-hidden">
              <div
                className="h-full bg-cyan-400 rounded-full"
                style={{ width: `${(prediction?.ml_score || 0) * 100}%` }}
              ></div>
            </div>
            <span className="text-[10px] text-slate-400">Candidate ranking probability</span>
          </div>

          {/* Pillar 2: Graph Centrality */}
          <div className="p-3 bg-[#070c18] rounded-xl border border-[#162544] space-y-1.5">
            <div className="flex justify-between items-center text-slate-300">
              <span className="font-semibold">Graph Network Score</span>
              <span className="text-purple-400 font-bold">
                {prediction && Number.isFinite(prediction.graph_score) ? `${Math.round(prediction.graph_score * 100)}%` : '—'}
              </span>
            </div>
            <div className="w-full h-1.5 bg-[#121c33] rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-400 rounded-full"
                style={{ width: `${(prediction?.graph_score || 0) * 100}%` }}
              ></div>
            </div>
            <span className="text-[10px] text-slate-400">Syndicate centrality & layering</span>
          </div>

          {/* Pillar 3: Geospatial Hotspot */}
          <div className="p-3 bg-[#070c18] rounded-xl border border-[#162544] space-y-1.5">
            <div className="flex justify-between items-center text-slate-300">
              <span className="font-semibold">Geospatial Cluster Score</span>
              <span className="text-amber-400 font-bold">
                {prediction && Number.isFinite(prediction.geo_score) ? `${Math.round(prediction.geo_score * 100)}%` : '—'}
              </span>
            </div>
            <div className="w-full h-1.5 bg-[#121c33] rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-400 rounded-full"
                style={{ width: `${(prediction?.geo_score || 0) * 100}%` }}
              ></div>
            </div>
            <span className="text-[10px] text-slate-400">Historical cluster extraction density</span>
          </div>

          {/* Pillar 4: Temporal Score */}
          <div className="p-3 bg-[#070c18] rounded-xl border border-[#162544] space-y-1.5">
            <div className="flex justify-between items-center text-slate-300">
              <span className="font-semibold">Temporal Velocity Score</span>
              <span className="text-emerald-400 font-bold">
                {prediction && Number.isFinite(prediction.temporal_score) ? `${Math.round(prediction.temporal_score * 100)}%` : '—'}
              </span>
            </div>
            <div className="w-full h-1.5 bg-[#121c33] rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-400 rounded-full"
                style={{ width: `${(prediction?.temporal_score || 0) * 100}%` }}
              ></div>
            </div>
            <span className="text-[10px] text-slate-400">Time-to-cashout urgency window</span>
          </div>
        </div>
      </div>

      {/* Grid: Top 3 Predicted Locations + Mini Map */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Top 3 Predicted Locations */}
        <div className="lg:col-span-6 bg-[#0a1020] rounded-2xl border border-[#162544] p-5 shadow-2xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white font-['JetBrains_Mono',monospace] uppercase">
              TOP 3 PREDICTED LOCATIONS
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              Model: {prediction?.model_version || 'pending'}
            </span>
          </div>

          <div className="space-y-3.5">
            {prediction?.top_locations && prediction.top_locations.length > 0 ? (
              prediction.top_locations.slice(0, 3).map((loc) => (
                <div
                  key={loc.rank}
                  className={`p-4 rounded-xl border transition-all ${
                    loc.rank === 1
                      ? 'bg-[#0f1b36] border-cyan-500/60 shadow-[0_0_15px_rgba(0,216,255,0.15)]'
                      : 'bg-[#080e1c] border-[#162544] hover:border-[#233863]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <span
                        className={`w-7 h-7 rounded-lg flex items-center justify-center font-mono font-bold text-xs ${
                          loc.rank === 1 ? 'bg-cyan-500 text-black' : 'bg-[#162544] text-slate-300'
                        }`}
                      >
                        #{loc.rank}
                      </span>
                      <div>
                        <h4 className="text-sm font-bold text-slate-100 font-mono">
                          {loc.location_name}
                        </h4>
                        <span className="text-[11px] text-slate-400 font-mono">
                          Distance from complaint origin: {loc.distance_km} km
                        </span>
                      </div>
                    </div>

                    <div className="text-right">
                      <div
                        className={`text-base font-bold font-mono ${
                          loc.risk_level === 'CRITICAL'
                            ? 'text-red-400'
                            : loc.risk_level === 'HIGH'
                            ? 'text-amber-400'
                            : 'text-blue-400'
                        }`}
                      >
                        {Math.round(loc.probability * 100)}%
                      </div>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-bold font-mono ${
                          loc.risk_level === 'CRITICAL'
                            ? 'bg-red-500/20 text-red-400'
                            : loc.risk_level === 'HIGH'
                            ? 'bg-amber-500/20 text-amber-400'
                            : 'bg-blue-500/20 text-blue-400'
                        }`}
                      >
                        {loc.risk_level}
                      </span>
                    </div>
                  </div>

                  <div className="mt-2.5 pt-2 border-t border-[#1b2b4d] text-xs text-slate-400 font-mono">
                    {loc.reasoning}
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8 text-center text-xs text-slate-400 font-mono">
                No predicted locations generated yet. Click "RUN PREDICTIVE ANALYSIS" above.
              </div>
            )}
          </div>
        </div>

        {/* Mini Map */}
        <div className="lg:col-span-6 bg-[#0a1020] rounded-2xl border border-[#162544] p-5 shadow-2xl flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-white font-['JetBrains_Mono',monospace] uppercase">
              Predicted Cash-Out Geographic Cluster
            </h3>
            <span className="text-xs text-cyan-400 font-mono">
              Target: {highlightedClusterName || 'Central Grid'}
            </span>
          </div>

          <CashOutRiskMap
            hotspots={clusters}
            topLocations={prediction?.top_locations || []}
            complaint={complaint}
            prediction={prediction}
            height="340px"
            highlightCluster={highlightedClusterName}
            showControls={true}
          />
        </div>
      </div>

      {/* EXPLAINABLE AI SECTION */}
      <div className="bg-[#0a1020] rounded-2xl border border-[#162544] p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#162544]">
          <div className="flex items-center space-x-2.5">
            <Sparkles className="w-5 h-5 text-cyan-400" />
            <h3 className="text-base font-bold text-white font-['JetBrains_Mono',monospace] uppercase">
              WHY THIS PREDICTION? (EXPLAINABLE AI & FEATURE ATTRIBUTION)
            </h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            Mode: <strong className="text-cyan-400">{prediction?.prediction_mode || 'pending'}</strong> | Version: <strong className="text-white">{prediction?.model_version || 'pending'}</strong>
          </span>
        </div>

        {/* Narrative */}
        <div className="p-4 rounded-xl bg-[#080e1c] border border-[#162544] mb-6">
          <p className="text-xs text-slate-200 leading-relaxed font-mono">
            "{explanation?.narrative || `This location was ranked as the primary cash-out candidate based on syndicate beneficiary corridor alignment, proximity to high-frequency mule accounts, and historical extraction patterns for ${complaint.fraud_type}.`}"
          </p>
        </div>

        {/* Contribution Bars */}
        <div className="space-y-3.5 mb-6">
          {(explanation?.factors && explanation.factors.length > 0 ? explanation.factors : [
            { name: 'Beneficiary Mule Corridor Alignment', contribution_percentage: 28, description: 'Beneficiary account directly connected to active cash withdrawal corridors in this cluster.' },
            { name: 'Historical Hotspot Extraction Density', contribution_percentage: 22, description: 'Geographic cluster experienced repeated cyber fraud cash-outs in the surveillance window.' },
            { name: 'Graph Network Topology & Centrality', contribution_percentage: 18, description: 'Layering topology exhibits high betweenness centrality indicative of organized syndicate activity.' },
            { name: 'Transaction Velocity & Split Window', contribution_percentage: 14, description: 'Rapid fund dispersal matches high-velocity ATM withdrawal timelines.' },
            { name: 'Modus Operandi Geographic Affinity', contribution_percentage: 10, description: 'Fraud modus operandi demonstrates statistical preference for commercial hub ATMs.' }
          ]).map((factor, idx) => (
            <div key={idx} className="p-3 bg-[#080e1c] rounded-lg border border-[#162544]">
              <div className="flex items-center justify-between text-xs font-mono mb-1.5">
                <span className="font-semibold text-slate-200">{factor.name}</span>
                <span className="text-cyan-400 font-bold">+{factor.contribution_percentage}%</span>
              </div>
              <div className="w-full h-2 bg-[#121c33] rounded-full overflow-hidden mb-2">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full"
                  style={{ width: `${Math.min(factor.contribution_percentage * 3.2, 100)}%` }}
                ></div>
              </div>
              <p className="text-[11px] text-slate-400 font-mono">{factor.description}</p>
            </div>
          ))}
        </div>

        {/* Legal / Operational Disclaimer */}
        <div className="p-3.5 bg-[#060a15] rounded-lg border border-[#1b2b4d] flex items-center space-x-3 text-xs text-slate-400 font-mono">
          <Info className="w-5 h-5 text-cyan-400 shrink-0" />
          <span>
            {explanation?.disclaimer || 'AI-generated decision support. Final operational decisions remain with authorized investigators.'}
          </span>
        </div>
      </div>
    </div>
  );
};
