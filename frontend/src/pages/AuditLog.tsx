import React, { useEffect, useState } from 'react';
import {
  History,
  ShieldCheck,
  Filter,
  RefreshCw,
  Search,
  User,
  Clock,
  FileText
} from 'lucide-react';
import { api } from '../services/api';
import { AuditLogItem } from '../types';

export const AuditLog: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('ALL');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await api.getAuditLogs({
        action: actionFilter !== 'ALL' ? actionFilter : undefined,
      });
      setLogs(data);
    } catch (err) {
      console.error('Failed to load audit logs', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [actionFilter]);

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <History className="w-5 h-5 text-cyan-400" />
            <h1 className="text-xl font-bold text-white font-['JetBrains_Mono',monospace]">
              Regulatory Audit Ledger & Chain of Custody
            </h1>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Immutable trace of officer logins, case inspections, predictive inferences, and alert escalations
          </p>
        </div>

        {/* Filter */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 bg-[#070c18] px-3 py-1.5 rounded-lg border border-[#162544]">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="bg-transparent text-xs text-slate-200 focus:outline-none font-mono cursor-pointer"
            >
              <option value="ALL">All Actions</option>
              <option value="LOGIN">LOGIN</option>
              <option value="CASE_VIEWED">CASE_VIEWED</option>
              <option value="PREDICTION_RUN">PREDICTION_RUN</option>
              <option value="NETWORK_VIEWED">NETWORK_VIEWED</option>
              <option value="ALERT_ACKNOWLEDGED">ALERT_ACKNOWLEDGED</option>
              <option value="ALERT_ESCALATED">ALERT_ESCALATED</option>
            </select>
          </div>

          <button
            onClick={fetchLogs}
            className="p-2 rounded-lg bg-[#070c18] border border-[#162544] text-slate-300 hover:text-cyan-400"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Audit Table */}
      <div className="bg-[#0a1020] rounded-2xl border border-[#162544] overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[#070c18] text-slate-400 uppercase tracking-wider border-b border-[#162544]">
              <tr>
                <th className="py-3.5 px-4">Timestamp (UTC)</th>
                <th className="py-3.5 px-4">Officer Name</th>
                <th className="py-3.5 px-4">Role / Jurisdiction</th>
                <th className="py-3.5 px-4">Action</th>
                <th className="py-3.5 px-4">Case / Target</th>
                <th className="py-3.5 px-4">Details / Result</th>
                <th className="py-3.5 px-4">IP Address</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#162544] text-slate-300">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-[#0d162d] transition-colors">
                  <td className="py-3 px-4 text-slate-400">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="py-3 px-4 font-semibold text-slate-100">{log.officer_name}</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded bg-[#162544] text-cyan-300 font-bold text-[10px]">
                      {log.role}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                        log.action.includes('ALERT')
                          ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                          : log.action.includes('PREDICTION')
                          ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                          : log.action.includes('LOGIN')
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                      }`}
                    >
                      {log.action}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-cyan-400 font-bold">{log.case_number || 'N/A'}</td>
                  <td className="py-3 px-4 text-slate-300 max-w-xs truncate">{log.details || '—'}</td>
                  <td className="py-3 px-4 text-slate-400">{log.ip_address}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
