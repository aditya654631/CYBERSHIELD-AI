import React, { useEffect, useState } from 'react';
import {
  BarChart3,
  TrendingUp,
  PieChart as PieIcon,
  Clock,
  ShieldAlert,
  MapPin,
  DollarSign
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
        <div className="h-20 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
        <div className="grid grid-cols-2 gap-6">
          <div className="h-80 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
          <div className="h-80 bg-[#0c1428] rounded-xl border border-[#162544]"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-5 h-5 text-cyan-400" />
            <h1 className="text-xl font-bold text-white font-['JetBrains_Mono',monospace]">
              Macro Cybercrime Intelligence Analytics
            </h1>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Cross-jurisdictional telemetry, modus operandi trends, and cash-out velocity
          </p>
        </div>
        <div className="text-right text-xs font-mono text-cyan-400">
          Sync: Automated I4C Daily Consolidation
        </div>
      </div>

      {/* 4 Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 bg-[#0a1020] rounded-xl border border-[#162544]">
          <span className="text-xs text-slate-400 font-mono block">TOTAL COMPLAINTS LOGGED</span>
          <span className="text-2xl font-bold text-white font-mono">{analytics.active_complaints}</span>
          <span className="text-[11px] text-emerald-400 block mt-1">+18.5% YoY</span>
        </div>

        <div className="p-4 bg-[#0a1020] rounded-xl border border-[#162544]">
          <span className="text-xs text-slate-400 font-mono block">AMOUNT AT RISK ACCUMULATED</span>
          <span className="text-2xl font-bold text-emerald-400 font-mono">
            ₹{(analytics.total_amount_at_risk / 100000).toFixed(1)} Lakhs
          </span>
          <span className="text-[11px] text-slate-400 block mt-1">₹42.8L Protected</span>
        </div>

        <div className="p-4 bg-[#0a1020] rounded-xl border border-[#162544]">
          <span className="text-xs text-slate-400 font-mono block">AVERAGE ALERT DISPATCH TIME</span>
          <span className="text-2xl font-bold text-cyan-300 font-mono">3.4 Mins</span>
          <span className="text-[11px] text-cyan-400 block mt-1">Sub-5 min target achieved</span>
        </div>

        <div className="p-4 bg-[#0a1020] rounded-xl border border-[#162544]">
          <span className="text-xs text-slate-400 font-mono block">HIGH RISK MULE DENSITY</span>
          <span className="text-2xl font-bold text-amber-400 font-mono">82 Accounts</span>
          <span className="text-[11px] text-amber-400 block mt-1">Under active lien watch</span>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Fraud Categories */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-xl">
          <h3 className="text-sm font-bold text-white font-mono uppercase mb-4">
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
                <Tooltip contentStyle={{ backgroundColor: '#0c1428', borderColor: '#1b2b4d', fontSize: '11px' }} />
                <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Complaints Timeline */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-xl">
          <h3 className="text-sm font-bold text-white font-mono uppercase mb-4">
            Complaints & Risk Velocity Over Time
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics.cases_over_time}>
                <CartesianGrid strokeDasharray="3 3" stroke="#162544" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} />
                <Tooltip contentStyle={{ backgroundColor: '#0c1428', borderColor: '#1b2b4d', fontSize: '11px' }} />
                <Area type="monotone" dataKey="cases" stroke="#00d8ff" fill="#00d8ff" fillOpacity={0.2} name="Cases" />
                <Area type="monotone" dataKey="risk" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} name="Risk Index" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Hourly Cash-Out Risk */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-xl">
          <h3 className="text-sm font-bold text-white font-mono uppercase mb-4">
            ATM Cash-Out Risk by Hour of Day
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.hourly_risk}>
                <CartesianGrid strokeDasharray="3 3" stroke="#162544" />
                <XAxis dataKey="hour" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} />
                <Tooltip contentStyle={{ backgroundColor: '#0c1428', borderColor: '#1b2b4d', fontSize: '11px' }} />
                <Bar dataKey="risk" fill="#ef4444" name="Risk %" radius={[4, 4, 0, 0]} />
                <Bar dataKey="cashouts" fill="#3b82f6" name="Cash-out Events" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Regional Risk Comparison */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-xl">
          <h3 className="text-sm font-bold text-white font-mono uppercase mb-4">
            Regional District Threat Index
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.regional_risk} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#162544" />
                <XAxis type="number" stroke="#64748b" fontSize={10} />
                <YAxis dataKey="district" type="category" stroke="#64748b" fontSize={10} width={80} />
                <Tooltip contentStyle={{ backgroundColor: '#0c1428', borderColor: '#1b2b4d', fontSize: '11px' }} />
                <Bar dataKey="risk_index" fill="#f59e0b" name="Threat Index" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
