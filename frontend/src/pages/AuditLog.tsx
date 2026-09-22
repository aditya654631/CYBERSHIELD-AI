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
import { formatIST } from '../utils/predictionDisplay';

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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <History className="w-5 h-5 text-[#468189] shrink-0" />
            <h1 className="text-lg font-bold text-[#031926] font-sans">
              Regulatory Audit Ledger & Chain of Custody
            </h1>
          </div>
          <p className="text-xs text-slate-500 font-sans mt-0.5">
            Immutable trace of officer logins, case inspections, predictive inferences, and alert escalations
          </p>
        </div>

        {/* Filter */}
        <div className="flex items-center space-x-2 sm:space-x-3 w-full sm:w-auto justify-between sm:justify-start">
          <div className="flex items-center space-x-2 bg-white px-3 py-1.5 rounded-md border border-[#DCE5F0] flex-1 sm:flex-initial">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="bg-transparent text-xs text-slate-700 focus:outline-none cursor-pointer"
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
            title="Refresh logs"
            className="p-2 rounded-md bg-white border border-[#DCE5F0] text-slate-600 hover:text-blue-600 hover:bg-blue-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Audit Table */}
      <div className="bg-white rounded-lg border border-[#DCE5F0] overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F8FAFC] text-slate-600 uppercase tracking-wider border-b border-[#DCE5F0]">
              <tr>
                <th className="py-3 px-4 font-semibold">Timestamp</th>
                <th className="py-3 px-4 font-semibold">Officer Name</th>
                <th className="py-3 px-4 font-semibold">Role / Jurisdiction</th>
                <th className="py-3 px-4 font-semibold">Action</th>
                <th className="py-3 px-4 font-semibold">Case / Target</th>
                <th className="py-3 px-4 font-semibold">Details / Result</th>
                <th className="py-3 px-4 font-semibold">IP Address</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#DCE5F0] text-slate-700">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-blue-50/30 transition-colors">
                  <td className="py-3 px-4 text-slate-500">
                    {formatIST(log.created_at)}
                  </td>
                  <td className="py-3 px-4 font-semibold text-slate-900">{log.officer_name}</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold border border-blue-200 text-[10px]">
                      {log.role}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`px-2 py-0.5 rounded font-semibold text-[10px] ${
                        log.action.includes('ALERT')
                          ? 'bg-red-50 text-red-700 border border-red-200'
                          : log.action.includes('PREDICTION')
                          ? 'bg-purple-50 text-purple-700 border border-purple-200'
                          : log.action.includes('LOGIN')
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-blue-50 text-blue-700 border border-blue-200'
                      }`}
                    >
                      {log.action}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-blue-700 font-semibold font-mono">{log.case_number || 'N/A'}</td>
                  <td className="py-3 px-4 text-slate-600 max-w-xs truncate">{log.details || '—'}</td>
                  <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">{log.ip_address}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
