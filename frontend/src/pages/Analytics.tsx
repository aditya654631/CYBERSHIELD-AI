import React, { useEffect, useState } from 'react';
import {
  BarChart3,
  TrendingUp,
  PieChart as PieIcon,
  Clock,
  ShieldAlert,
  MapPin
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts';
import { api } from '../services/api';
import { AnalyticsOverview } from '../types';

const COLORS = ['#00d8ff', '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b'];

export const Analytics: React.FC = () => {
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const data = await api.getAnalyticsOverview();
        setAnalytics(data);
      } catch (err) {
        console.error('Failed to load analytics', err);
      } finally {
        setLoading(false);
      }
    };
    fetchAnalytics();
  }, []);

  if (loading || !analytics) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-20 bg-white rounded-xl border border-[#DCE5F0]"></div>
        <div className="grid grid-cols-2 gap-6">
          <div className="h-80 bg-white rounded-xl border border-[#DCE5F0]"></div>
          <div className="h-80 bg-white rounded-xl border border-[#DCE5F0]"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-5 h-5 text-blue-600 shrink-0" />
            <h1 className="text-lg font-bold text-[#173A63] font-sans">
              Macro Cybercrime Intelligence Analytics
            </h1>
          </div>
          <p className="text-xs text-slate-500 font-sans mt-0.5">
            Cross-jurisdictional telemetry, modus operandi trends, and cash-out velocity
          </p>
        </div>
        <div className="text-right text-xs font-medium text-blue-700">
          Sync: Automated I4C Daily Consolidation
        </div>
      </div>

      {/* 4 Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block">TOTAL COMPLAINTS LOGGED</span>
          <span className="text-2xl font-bold text-slate-900 mt-1 block">{analytics.active_complaints}</span>
          <span className="text-xs text-emerald-600 font-medium block mt-1">+18.5% YoY</span>
        </div>

        <div className="p-4 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block">AMOUNT AT RISK ACCUMULATED</span>
          <span className="text-2xl font-bold text-emerald-700 mt-1 block">
            ₹{(analytics.total_amount_at_risk / 100000).toFixed(1)} Lakhs
          </span>
          <span className="text-xs text-slate-500 block mt-1">₹42.8L Protected</span>
        </div>

        <div className="p-4 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block">AVERAGE ALERT DISPATCH TIME</span>
          <span className="text-2xl font-bold text-blue-700 mt-1 block">3.4 Mins</span>
          <span className="text-xs text-blue-600 block mt-1">Sub-5 min target achieved</span>
        </div>

        <div className="p-4 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block">HIGH RISK MULE DENSITY</span>
          <span className="text-2xl font-bold text-amber-700 mt-1 block">82 Accounts</span>
          <span className="text-xs text-amber-600 block mt-1">Under active lien watch</span>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Fraud Categories */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <h3 className="text-sm font-bold text-[#173A63] uppercase mb-4">
            Fraud Modus Operandi Breakdown
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={analytics.fraud_types}
                  dataKey="count"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  innerRadius={50}
                  paddingAngle={5}
                >
                  {analytics.fraud_types.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#DCE5F0', color: '#1e293b', fontSize: '11px', borderRadius: '6px' }} />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Complaints Timeline */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <h3 className="text-sm font-bold text-[#173A63] uppercase mb-4">
            Complaints & Risk Velocity Over Time
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics.cases_over_time}>
                <CartesianGrid strokeDasharray="3 3" stroke="#DCE5F0" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} />
                <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#DCE5F0', color: '#1e293b', fontSize: '11px', borderRadius: '6px' }} />
                <Area type="monotone" dataKey="cases" stroke="#2563eb" fill="#2563eb" fillOpacity={0.15} name="Cases" />
                <Area type="monotone" dataKey="risk" stroke="#dc2626" fill="#dc2626" fillOpacity={0.15} name="Risk Index" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Hourly Cash-Out Risk */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <h3 className="text-sm font-bold text-[#173A63] uppercase mb-4">
            ATM Cash-Out Risk by Hour of Day
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.hourly_risk}>
                <CartesianGrid strokeDasharray="3 3" stroke="#DCE5F0" />
                <XAxis dataKey="hour" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} />
                <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#DCE5F0', color: '#1e293b', fontSize: '11px', borderRadius: '6px' }} />
                <Bar dataKey="risk" fill="#dc2626" name="Risk %" radius={[4, 4, 0, 0]} />
                <Bar dataKey="cashouts" fill="#2563eb" name="Cash-out Events" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Regional Risk Comparison */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <h3 className="text-sm font-bold text-[#173A63] uppercase mb-4">
            Regional District Threat Index
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.regional_risk} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#DCE5F0" />
                <XAxis type="number" stroke="#64748b" fontSize={10} />
                <YAxis dataKey="district" type="category" stroke="#64748b" fontSize={10} width={80} />
                <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#DCE5F0', color: '#1e293b', fontSize: '11px', borderRadius: '6px' }} />
                <Bar dataKey="risk_index" fill="#d97706" name="Threat Index" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
