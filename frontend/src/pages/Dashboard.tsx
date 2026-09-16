import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  AlertTriangle,
  Clock,
  ArrowUpRight,
  FileText,
  CheckCircle2,
  ChevronRight,
  IndianRupee,
  Layers,
} from 'lucide-react';
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import { api } from '../services/api';
import { DashboardSummary, HotspotCluster } from '../types';
import { CashOutRiskMap } from '../maps/CashOutRiskMap';
import { Card } from '../components/common/Card';
import { MetricCard } from '../components/common/MetricCard';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { LoadingState } from '../components/common/LoadingState';
import { formatIST } from '../utils/predictionDisplay';

const PIE_COLORS = ['#dc2626', '#d97706', '#2563eb', '#16a34a'];

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [hotspots, setHotspots] = useState<HotspotCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [sumData, mapData] = await Promise.all([
          api.getDashboardSummary(),
          api.getRiskMap()
        ]);
        if (isMounted) {
          setSummary(sumData);
          setHotspots(mapData.hotspots || []);
        }
      } catch (err: any) {
        console.error('Failed to load dashboard data', err);
        if (isMounted) {
          setError('Unable to load database-driven dashboard telemetry. Please verify backend service connectivity.');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };
    fetchData();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleViewPilotCase = () => {
    navigate('/cases/CMP-NEW-000002');
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <LoadingState message="Loading database-driven operational telemetry..." className="py-24" />
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="p-8 bg-white rounded-lg border border-red-200 text-center space-y-4 max-w-xl mx-auto my-12 shadow-sm">
        <AlertTriangle className="w-10 h-10 text-red-600 mx-auto" />
        <h2 className="text-base font-bold text-slate-900">Dashboard Telemetry Unavailable</h2>
        <p className="text-xs text-slate-600 max-w-md mx-auto">
          {error || 'Unable to retrieve live database records. No fallback mock data is displayed.'}
        </p>
        <Button
          onClick={() => window.location.reload()}
          variant="secondary"
          size="sm"
        >
          Retry Connection
        </Button>
      </div>
    );
  }

  const { kpis, risk_distribution, mode_distribution, recent_complaints, recent_alerts } = summary;

  const riskChartData = [
    { name: 'CRITICAL', count: risk_distribution.CRITICAL, fill: '#dc2626' },
    { name: 'HIGH', count: risk_distribution.HIGH, fill: '#d97706' },
    { name: 'MEDIUM', count: risk_distribution.MEDIUM, fill: '#2563eb' },
    { name: 'LOW', count: risk_distribution.LOW, fill: '#16a34a' }
  ];

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <div className="bg-white rounded-lg border border-[#DCE5F0] p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs text-slate-500 mb-1">
            <span className="font-semibold text-[#173A63]">Delhi Pilot</span>
            <span>•</span>
            <span>Synchronized DB Snapshot ({new Date(summary.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })})</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#173A63]">
            Operational Overview
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Cybercrime Predictive Intelligence & Intervention Platform • Pilot Operations
          </p>
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          <Button
            onClick={handleViewPilotCase}
            variant="primary"
            size="sm"
            icon={<ChevronRight className="w-4 h-4" />}
          >
            <span>View Pilot Case</span>
            <span className="ml-1 text-[11px] px-1.5 py-0.2 rounded bg-blue-700 text-white font-mono">
              CMP-NEW-000002
            </span>
          </Button>
        </div>
      </div>

      {/* 6 DB-Backed KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2.5 sm:gap-3.5">
        <MetricCard
          label="Active Complaints"
          value={kpis.active_complaints.toLocaleString('en-IN')}
          subtitle="Active, review & alerted"
          icon={<FileText className="w-4 h-4" />}
        />
        <MetricCard
          label="High-Priority Predictions"
          value={kpis.high_risk_predictions.toLocaleString('en-IN')}
          subtitle="Latest high / critical"
          variant="critical"
          icon={<ShieldAlert className="w-4 h-4" />}
        />
        <MetricCard
          label="Active Alerts"
          value={kpis.active_alerts.toLocaleString('en-IN')}
          subtitle="Awaiting officer dispatch"
          variant="warning"
          icon={<AlertTriangle className="w-4 h-4" />}
        />
        <MetricCard
          label="Acknowledged Alerts"
          value={kpis.acknowledged_alerts.toLocaleString('en-IN')}
          subtitle="Action initiated"
          variant="success"
          icon={<CheckCircle2 className="w-4 h-4" />}
        />
        <MetricCard
          label="Amount Under Trace"
          value={`₹${(kpis.total_amount_at_risk / 100000).toFixed(1)}L`}
          subtitle="Active complaint volume"
          icon={<IndianRupee className="w-4 h-4" />}
        />
        <MetricCard
          label="Alert Response SLA"
          value={kpis.response_time_label}
          subtitle="Mean time to acknowledge"
          icon={<Clock className="w-4 h-4" />}
        />
      </div>

      {/* Main Grid: Live Risk Map + Alerts Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Live Cash-Out Risk Map */}
        <div className="lg:col-span-8 bg-white rounded-lg border border-[#DCE5F0] p-4 sm:p-5 shadow-xs flex flex-col">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="text-sm font-bold text-[#173A63]">
                Live Cash-Out Hotspot Map
              </h2>
              <p className="text-xs text-slate-500">
                Intervention candidate clusters across 9 Delhi pilot zones
              </p>
            </div>

            <Button
              onClick={() => navigate('/risk-map')}
              variant="outline"
              size="sm"
              icon={<ArrowUpRight className="w-3.5 h-3.5" />}
            >
              Full GIS View
            </Button>
          </div>

          <div className="h-[320px] sm:h-96 w-full rounded-md overflow-hidden border border-[#DCE5F0] relative">
            <CashOutRiskMap
              hotspots={hotspots}
              priorityHotspotIds={hotspots.slice(0, 3).map(h => h.id)}
            />
          </div>
        </div>

        {/* Priority Hotspots & Alerts Column */}
        <div className="lg:col-span-4 space-y-4">
          {/* Priority Candidate Clusters */}
          <div className="bg-white rounded-lg border border-[#DCE5F0] p-4 shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-[#DCE5F0] mb-3">
              <h3 className="text-xs font-bold text-[#173A63] uppercase tracking-wider">
                Priority Interception Hotspots
              </h3>
              <span className="text-[11px] text-slate-500 font-medium">Top Candidates</span>
            </div>

            <div className="space-y-2.5">
              {hotspots.slice(0, 3).map((hotspot, idx) => (
                <div
                  key={hotspot.id}
                  onClick={() => navigate('/risk-map')}
                  className="p-2.5 rounded border border-[#DCE5F0] hover:border-blue-300 hover:bg-blue-50/40 cursor-pointer transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono font-bold text-blue-600">#{idx + 1}</span>
                      <span className="text-xs font-semibold text-slate-800">
                        {hotspot.cluster_name}
                      </span>
                    </div>
                    <Badge
                      variant={hotspot.risk_level === 'CRITICAL' ? 'critical' : 'warning'}
                      size="sm"
                    >
                      {Math.round(hotspot.risk_score * 100)}% {hotspot.risk_level}
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between mt-1.5 text-[11px] text-slate-500">
                    <span>Window: {hotspot.expected_window}</span>
                    <span className="font-semibold text-slate-700">₹{hotspot.amount_at_risk.toLocaleString('en-IN')}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Alerts Feed */}
          <div className="bg-white rounded-lg border border-[#DCE5F0] p-4 shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-[#DCE5F0] mb-3">
              <h3 className="text-xs font-bold text-[#173A63] uppercase tracking-wider">
                Recent Alerts Feed
              </h3>
              <button
                onClick={() => navigate('/alerts')}
                className="text-xs text-blue-600 hover:text-blue-700 hover:underline font-medium"
              >
                All Alerts →
              </button>
            </div>

            <div className="space-y-2">
              {recent_alerts.length === 0 ? (
                <div className="text-xs text-slate-500 py-4 text-center">
                  No active alerts recorded.
                </div>
              ) : (
                recent_alerts.slice(0, 3).map((alert) => (
                  <div
                    key={alert.id}
                    onClick={() => navigate('/alerts')}
                    className="p-2.5 rounded border border-[#DCE5F0] hover:bg-blue-50/30 cursor-pointer transition-colors"
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-mono font-semibold text-blue-700">{alert.complaint_number}</span>
                      <Badge
                        variant={alert.status === 'ACKNOWLEDGED' ? 'success' : 'critical'}
                        size="sm"
                      >
                        {alert.status}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-700 font-medium truncate">
                      {alert.location_name} • ₹{alert.amount_at_risk.toLocaleString('en-IN')}
                    </p>
                    <div className="text-[11px] text-slate-500 flex justify-between mt-1">
                      <span>{alert.expected_window}</span>
                      <span>{formatIST(alert.created_at)}</span>
                    </div>
                  </div>
                ))
              )}

              {/* Provenance note */}
              <div className="pt-2 border-t border-[#DCE5F0] flex items-center justify-between text-[11px] text-slate-500">
                <span>Provenance Distribution:</span>
                <span className="font-medium text-[#173A63]">
                  {mode_distribution.trained_ml} ML / {mode_distribution.deterministic_demo} Demo
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Analytics & Priority Distribution Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title="Operational Priority Distribution"
          subtitle="Current active prediction distribution by severity tier"
        >
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskChartData} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={12} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#ffffff', borderColor: '#DCE5F0', borderRadius: '6px', fontSize: '12px' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {riskChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          title="Prediction Engine Provenance"
          subtitle="Ratio of trained ML pipeline vs deterministic test cases"
        >
          <div className="h-64 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={[
                    { name: 'Trained ML', value: mode_distribution.trained_ml },
                    { name: 'Deterministic Demo', value: mode_distribution.deterministic_demo }
                  ]}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                >
                  <Cell fill="#2563eb" />
                  <Cell fill="#94a3b8" />
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#ffffff', borderColor: '#DCE5F0', borderRadius: '6px', fontSize: '12px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* DB-Backed Recent Complaints Table */}
      <Card
        title="Recent Complaints (Database Ledger)"
        subtitle="Latest complaints filed and linked to transaction topologies"
        action={
          <Button
            onClick={() => navigate('/complaints')}
            variant="ghost"
            size="sm"
            icon={<ArrowUpRight className="w-3.5 h-3.5" />}
          >
            View All Complaints
          </Button>
        }
      >
        {/* Desktop Table: shown at md and above */}
        <div className="hidden md:block overflow-x-auto -mx-5 -mb-5">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-[#F8FAFC] border-y border-[#DCE5F0] text-slate-700 font-semibold">
                <th className="px-5 py-2.5">Complaint ID</th>
                <th className="px-3 py-2.5">Fraud Type</th>
                <th className="px-3 py-2.5">Amount</th>
                <th className="px-3 py-2.5">District / State</th>
                <th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5">Reported Date</th>
                <th className="px-3 py-2.5">Prediction</th>
                <th className="px-5 py-2.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#DCE5F0]">
              {recent_complaints.map((comp) => (
                <tr
                  key={comp.id}
                  onClick={() => navigate(`/cases/${comp.complaint_number}`)}
                  className="hover:bg-blue-50/20 cursor-pointer transition-colors"
                >
                  <td className="px-5 py-3 font-mono font-semibold text-blue-700">{comp.complaint_number}</td>
                  <td className="px-3 py-3 text-slate-700">{comp.fraud_type}</td>
                  <td className="px-3 py-3 font-semibold text-slate-900">₹{comp.amount.toLocaleString('en-IN')}</td>
                  <td className="px-3 py-3 text-slate-600">{comp.district || comp.state || '—'}</td>
                  <td className="px-3 py-3">
                    <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                      {comp.case_status}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-slate-500">
                    {comp.reported_at ? formatIST(comp.reported_at) : '—'}
                  </td>
                  <td className="px-3 py-3">
                    {comp.prediction_available ? (
                      <Badge
                        variant={comp.latest_risk_level === 'CRITICAL' ? 'critical' : comp.latest_risk_level === 'HIGH' ? 'high' : 'medium'}
                        size="sm"
                      >
                        {comp.latest_risk_level} • {comp.latest_rank1_location || 'Available'}
                      </Badge>
                    ) : (
                      <span className="text-[11px] text-slate-400">Pending</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <span className="text-blue-700 font-medium hover:underline text-xs">
                      Inspect →
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile Card Presentation: shown below md */}
        <div className="md:hidden divide-y divide-[#DCE5F0] -mx-4 -mb-4">
          {recent_complaints.map((comp) => (
            <div
              key={comp.id}
              onClick={() => navigate(`/cases/${comp.complaint_number}`)}
              className="p-3.5 hover:bg-blue-50/30 cursor-pointer transition-colors space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-bold text-xs text-blue-700">{comp.complaint_number}</span>
                <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                  {comp.case_status}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-700 font-medium">{comp.fraud_type}</span>
                <span className="font-bold text-slate-900">₹{comp.amount.toLocaleString('en-IN')}</span>
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>{comp.district || comp.state || 'Delhi'}</span>
                <span>{comp.reported_at ? formatIST(comp.reported_at) : '—'}</span>
              </div>
              <div className="flex items-center justify-between pt-1 text-xs">
                <div>
                  {comp.prediction_available ? (
                    <Badge
                      variant={comp.latest_risk_level === 'CRITICAL' ? 'critical' : comp.latest_risk_level === 'HIGH' ? 'high' : 'medium'}
                      size="sm"
                    >
                      {comp.latest_risk_level} • {comp.latest_rank1_location || 'Available'}
                    </Badge>
                  ) : (
                    <span className="text-[11px] text-slate-400">Pending</span>
                  )}
                </div>
                <span className="text-blue-700 font-semibold text-xs">Inspect →</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};
