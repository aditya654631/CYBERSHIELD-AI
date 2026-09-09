import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  AlertTriangle,
  TrendingUp,
  MapPin,
  Clock,
  DollarSign,
  Play,
  ArrowUpRight,
  Radio,
  FileText,
  Activity,
  CheckCircle2,
  Cpu,
  Eye
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import { api } from '../services/api';
import { AnalyticsOverview, HotspotCluster, Complaint } from '../types';
import { CashOutRiskMap } from '../maps/CashOutRiskMap';

const PIE_COLORS = ['#00d8ff', '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b'];

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [hotspots, setHotspots] = useState<HotspotCluster[]>([]);
  const [recentComplaints, setRecentComplaints] = useState<Complaint[]>([]);
  const [loading, setLoading] = useState(true);
  const [demoExecuting, setDemoExecuting] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [anData, mapData, compData] = await Promise.all([
          api.getAnalyticsOverview(),
          api.getRiskMap(),
          api.getComplaints({ limit: 6 })
        ]);
        setAnalytics(anData);
        setHotspots(mapData.hotspots);
        setRecentComplaints(compData);
      } catch (err) {
        console.error('Failed to load dashboard data', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Step 25: RUN SIH DEMO end-to-end trigger
  const handleRunSIHDemo = async () => {
    setDemoExecuting(true);
    try {
      // 1. Run prediction for CMP-1042 directly via backend
      await api.runPrediction('CMP-1042');
      // 2. Navigate straight to Case Intelligence for CMP-1042 with demo tour state
      navigate('/cases/CMP-1042?sih_demo=active');
    } catch (err) {
      console.error('SIH Demo execution error', err);
      navigate('/cases/CMP-1042');
    } finally {
      setDemoExecuting(false);
    }
  };

  if (loading || !analytics) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-20 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
        <div className="grid grid-cols-6 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-28 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
          ))}
        </div>
        <div className="h-96 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Hero Action Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between p-6 bg-[#0a1122] rounded-2xl border border-[#182a4d] shadow-2xl relative overflow-hidden">
        <div className="absolute -right-20 -top-20 w-80 h-80 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none"></div>

        <div>
          <div className="flex items-center space-x-3 mb-2">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
              <span>PREDICTIVE MONITORING ACTIVE</span>
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Regional Grid: Madhya Pradesh Zone
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-['JetBrains_Mono',monospace]">
            Cybercrime Predictive Intelligence Command Center
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time multi-hop financial network tracing & ATM cash-out interception telemetry
          </p>
        </div>

        {/* SIH DEMO BUTTON */}
        <div className="mt-4 md:mt-0 flex items-center space-x-3 shrink-0">
          <button
            onClick={handleRunSIHDemo}
            disabled={demoExecuting}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-xs tracking-wider shadow-[0_0_20px_rgba(0,216,255,0.25)] border border-cyan-400/30 flex items-center space-x-2 transition-all font-mono"
          >
            <Play className="w-4 h-4 fill-white text-white" />
            <span>{demoExecuting ? 'INITIALIZING DEMO...' : 'RUN SIH DEMO'}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-black/40 border border-white/20">
              CMP-1042
            </span>
          </button>
        </div>
      </div>

      {/* 6 KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* Card 1 */}
        <div className="p-4 bg-[#0a1122] rounded-xl border border-[#162544] hover:border-cyan-500/40 transition-all shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider font-mono">Active Complaints</span>
            <FileText className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white font-mono">{analytics.active_complaints}</div>
          <div className="text-[11px] text-emerald-400 mt-1 flex items-center">
            <TrendingUp className="w-3 h-3 mr-1" />
            <span>+14.2% this week</span>
          </div>
        </div>

        {/* Card 2 */}
        <div className="p-4 bg-[#0a1122] rounded-xl border border-red-500/30 hover:border-red-500/60 transition-all shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider font-mono text-red-400">Critical Risk</span>
            <ShieldAlert className="w-4 h-4 text-red-400 animate-pulse" />
          </div>
          <div className="text-2xl font-bold text-red-400 font-mono">{analytics.critical_risk_cases}</div>
          <div className="text-[11px] text-red-400/80 mt-1 font-mono">
            Requires instant freeze
          </div>
        </div>

        {/* Card 3 */}
        <div className="p-4 bg-[#0a1122] rounded-xl border border-[#162544] hover:border-cyan-500/40 transition-all shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider font-mono">Predicted Cash-Outs</span>
            <Clock className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-cyan-300 font-mono">{analytics.predicted_cashout_events}</div>
          <div className="text-[11px] text-cyan-400/80 mt-1 font-mono">
            Next 2–4 hr window
          </div>
        </div>

        {/* Card 4 */}
        <div className="p-4 bg-[#0a1122] rounded-xl border border-[#162544] hover:border-cyan-500/40 transition-all shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider font-mono">High-Risk Districts</span>
            <MapPin className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 font-mono">{analytics.high_risk_districts}</div>
          <div className="text-[11px] text-slate-400 mt-1 truncate font-mono">
            Indore, Bhopal, Ujjain
          </div>
        </div>

        {/* Card 5 */}
        <div className="p-4 bg-[#0a1122] rounded-xl border border-[#162544] hover:border-cyan-500/40 transition-all shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider font-mono">Amount At Risk</span>
            <DollarSign className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-emerald-400 font-mono">
            ₹{(analytics.total_amount_at_risk / 100000).toFixed(1)}L
          </div>
          <div className="text-[11px] text-slate-400 mt-1 font-mono">
            Under active tracing
          </div>
        </div>

        {/* Card 6 */}
        <div className="p-4 bg-[#0a1122] rounded-xl border border-[#162544] hover:border-cyan-500/40 transition-all shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider font-mono">Alerts Ack Today</span>
            <CheckCircle2 className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white font-mono">{analytics.alerts_acknowledged_today}</div>
          <div className="text-[11px] text-emerald-400 mt-1 font-mono">
            100% SLA compliance
          </div>
        </div>
      </div>

      {/* Main Grid: Live Risk Map + Critical Intelligence Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Live Cash-Out Risk Map (Leaflet) */}
        <div className="lg:col-span-8 bg-[#0a1020] rounded-2xl border border-[#162544] p-5 shadow-2xl flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2.5">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
              </span>
              <h2 className="text-base font-bold text-white font-['JetBrains_Mono',monospace]">
                LIVE CASH-OUT RISK MAP
              </h2>
              <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 font-mono">
                Indore-Bhopal Corridor
              </span>
            </div>

            <button
              onClick={() => navigate('/risk-map')}
              className="text-xs text-cyan-400 hover:text-cyan-300 font-mono flex items-center space-x-1"
            >
              <span>FULL GIS PAGE</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <CashOutRiskMap hotspots={hotspots} height="440px" highlightCluster={hotspots[0]?.cluster_name || 'Central Grid'} />

          {/* Map bottom indicators */}
          <div className="mt-4 grid grid-cols-3 gap-3 pt-3 border-t border-[#162544] text-center text-xs font-mono">
            <div className="bg-[#070c18] p-2 rounded-lg border border-[#162544]">
              <span className="text-slate-400 block text-[10px]">THREAT EPICENTER</span>
              <span className="text-red-400 font-bold truncate block">
                {hotspots.length > 0 ? `${hotspots[0].cluster_name} (${Math.round(hotspots[0].risk_score * 100)}% Risk)` : 'Surveillance Active'}
              </span>
            </div>
            <div className="bg-[#070c18] p-2 rounded-lg border border-[#162544]">
              <span className="text-slate-400 block text-[10px]">MONITORED ATMS</span>
              <span className="text-cyan-300 font-bold block">
                {hotspots.reduce((sum, h) => sum + (h.atm_count || 0), 0) || 54} Active Terminals
              </span>
            </div>
            <div className="bg-[#070c18] p-2 rounded-lg border border-[#162544]">
              <span className="text-slate-400 block text-[10px]">INTERVENTION SLA</span>
              <span className="text-emerald-400 font-bold block">Rapid Response Active</span>
            </div>
          </div>
        </div>

        {/* Right Column: Top Predicted Hotspots & Critical Feed */}
        <div className="lg:col-span-4 space-y-6">
          {/* Top Predicted Hotspots */}
          <div className="bg-[#0a1020] rounded-2xl border border-[#162544] p-5 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white font-['JetBrains_Mono',monospace] uppercase">
                Top Predicted Hotspots
              </h3>
              <span className="text-[10px] text-cyan-400 font-mono">Next 4 Hours</span>
            </div>

            <div className="space-y-3">
              {hotspots.slice(0, 4).map((hotspot, idx) => (
                <div
                  key={hotspot.id}
                  onClick={() => navigate('/risk-map')}
                  className="p-3 rounded-xl bg-[#070d1a] hover:bg-[#0e1933] border border-[#162544] hover:border-cyan-500/40 transition-all cursor-pointer group"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono text-cyan-400 font-bold">#{idx + 1}</span>
                      <span className="text-xs font-semibold text-slate-200 group-hover:text-cyan-300">
                        {hotspot.cluster_name}
                      </span>
                    </div>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${
                        hotspot.risk_level === 'CRITICAL'
                          ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                          : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                      }`}
                    >
                      {Math.round(hotspot.risk_score * 100)}% {hotspot.risk_level}
                    </span>
                  </div>

                  <div className="flex items-center justify-between mt-2 text-[11px] text-slate-400 font-mono">
                    <span>Window: {hotspot.expected_window}</span>
                    <span className="text-emerald-400 font-bold">₹{hotspot.amount_at_risk.toLocaleString('en-IN')}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Critical Intelligence Feed */}
          <div className="bg-[#0a1020] rounded-2xl border border-[#162544] p-5 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white font-['JetBrains_Mono',monospace] uppercase flex items-center space-x-2">
                <Radio className="w-4 h-4 text-red-400 animate-pulse" />
                <span>Critical Intel Feed</span>
              </h3>
              <span className="text-[10px] text-emerald-400 font-mono">LIVE SYNC</span>
            </div>

            <div className="space-y-3">
              {recentComplaints.slice(0, 2).map((comp) => (
                <div
                  key={comp.id}
                  onClick={() => navigate(`/cases/${comp.complaint_number}`)}
                  className="p-2.5 rounded-lg bg-[#070c18] border border-red-500/30 text-xs font-mono cursor-pointer hover:border-red-500/60 transition-all"
                >
                  <div className="flex items-center justify-between text-[10px] text-red-400 mb-1">
                    <span>{comp.complaint_number} • {comp.risk_level} RISK</span>
                    <span>{comp.case_status}</span>
                  </div>
                  <p className="text-slate-200 leading-tight">
                    {comp.fraud_type} in {comp.victim_location} (₹{comp.amount.toLocaleString('en-IN')} under active tracing).
                  </p>
                </div>
              ))}

              <div className="p-2.5 rounded-lg bg-[#070c18] border border-cyan-500/30 text-xs font-mono">
                <div className="flex items-center justify-between text-[10px] text-cyan-400 mb-1">
                  <span>ML INFERENCE ENGINE ACTIVE</span>
                  <span>v2 Runtime</span>
                </div>
                <p className="text-slate-300 leading-tight">
                  XGBoost v2 location ranker and time regressor operational for live incident triage.
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-[#070c18] border border-amber-500/30 text-xs font-mono">
                <div className="flex items-center justify-between text-[10px] text-amber-400 mb-1">
                  <span>PROTOTYPE DEMO SHOWCASE</span>
                  <span>Deterministic Demo</span>
                </div>
                <p className="text-slate-300 leading-tight">
                  Seeded reference case CMP-1042 available for deterministic multi-hop evaluation.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Analytics Charts Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Fraud Type Distribution */}
        <div className="bg-[#0a1020] p-5 rounded-2xl border border-[#162544] shadow-xl">
          <h4 className="text-xs font-bold text-slate-200 font-['JetBrains_Mono',monospace] uppercase mb-4">
            Fraud Type Distribution
          </h4>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={analytics.fraud_types}
                  dataKey="count"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={65}
                  innerRadius={40}
                  paddingAngle={4}
                >
                  {analytics.fraud_types.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#0c1428', borderColor: '#1b2b4d', fontSize: '11px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 text-center text-[10px] text-slate-400 font-mono">
            Primary: Investment Scams (37%)
          </div>
        </div>

        {/* Cases Over Time */}
        <div className="bg-[#0a1020] p-5 rounded-2xl border border-[#162544] shadow-xl">
          <h4 className="text-xs font-bold text-slate-200 font-['JetBrains_Mono',monospace] uppercase mb-4">
            Cases Over Time (Weekly)
          </h4>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics.cases_over_time}>
                <defs>
                  <linearGradient id="colorCases" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d8ff" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#00d8ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#162544" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0c1428', borderColor: '#1b2b4d', fontSize: '11px' }}
                />
                <Area type="monotone" dataKey="cases" stroke="#00d8ff" fillOpacity={1} fill="url(#colorCases)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Hourly Cash-Out Risk */}
        <div className="bg-[#0a1020] p-5 rounded-2xl border border-[#162544] shadow-xl">
          <h4 className="text-xs font-bold text-slate-200 font-['JetBrains_Mono',monospace] uppercase mb-4">
            Hourly Cash-Out Risk (%)
          </h4>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.hourly_risk}>
                <CartesianGrid strokeDasharray="3 3" stroke="#162544" />
                <XAxis dataKey="hour" stroke="#64748b" fontSize={9} />
                <YAxis stroke="#64748b" fontSize={10} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0c1428', borderColor: '#1b2b4d', fontSize: '11px' }}
                />
                <Bar dataKey="risk" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 text-center text-[10px] text-red-400 font-mono">
            Peak Extraction: 18:00 - 21:00 hrs
          </div>
        </div>

        {/* Risk by Region */}
        <div className="bg-[#0a1020] p-5 rounded-2xl border border-[#162544] shadow-xl">
          <h4 className="text-xs font-bold text-slate-200 font-['JetBrains_Mono',monospace] uppercase mb-4">
            Risk By Region (Index)
          </h4>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.regional_risk} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#162544" />
                <XAxis type="number" stroke="#64748b" fontSize={10} />
                <YAxis dataKey="district" type="category" stroke="#64748b" fontSize={10} width={60} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0c1428', borderColor: '#1b2b4d', fontSize: '11px' }}
                />
                <Bar dataKey="risk_index" fill="#f59e0b" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
