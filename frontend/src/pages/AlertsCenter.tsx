import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BellRing,
  AlertTriangle,
  ShieldAlert,
  CheckCircle2,
  Clock,
  MapPin,
  DollarSign,
  Eye,
  Send,
  Radio,
  Filter,
  RefreshCw
} from 'lucide-react';
import { api } from '../services/api';
import { AlertItem } from '../types';
import { formatRisk } from '../utils/formatters';

export const AlertsCenter: React.FC = () => {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [actioningId, setActioningId] = useState<number | null>(null);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const data = await api.getAlerts({
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
      });
      setAlerts(data);
    } catch (err) {
      console.error('Failed to load alerts', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    // Setup WebSocket for live dashboard alert events
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/alerts`;
    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(wsUrl);
      socket.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (data.event) {
            fetchAlerts();
          }
        } catch (e) {}
      };
    } catch (e) {}

    return () => {
      if (socket) socket.close();
    };
  }, [statusFilter]);

  const handleAcknowledge = async (id: number) => {
    setActioningId(id);
    try {
      await api.acknowledgeAlert(id, 'Ground unit assigned to ATM terminal perimeter.');
      await fetchAlerts();
    } catch (err) {
      console.error('Error acknowledging alert', err);
    } finally {
      setActioningId(null);
    }
  };

  const handleEscalate = async (id: number) => {
    setActioningId(id);
    try {
      await api.escalateAlert(id, 'Automated bank ATM hold request transmitted via I4C Gateway.');
      await fetchAlerts();
    } catch (err) {
      console.error('Error escalating alert', err);
    } finally {
      setActioningId(null);
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <BellRing className="w-5 h-5 text-red-400 animate-bounce" />
            <h1 className="text-xl font-bold text-white font-['JetBrains_Mono',monospace]">
              Tactical Alerts & Rapid Intervention Center
            </h1>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Automated predictive alarms triggered for high-risk (&gt;=80%) cash-out extractions
          </p>
        </div>

        {/* Filter */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 bg-[#070c18] px-3 py-1.5 rounded-lg border border-[#162544]">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-transparent text-xs text-slate-200 focus:outline-none font-mono cursor-pointer"
            >
              <option value="ALL">All Alert States</option>
              <option value="NEW">NEW (Unacknowledged)</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="ACTION_INITIATED">ACTION INITIATED</option>
            </select>
          </div>

          <button
            onClick={fetchAlerts}
            className="p-2 rounded-lg bg-[#070c18] border border-[#162544] text-slate-300 hover:text-cyan-400"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Alert Cards List */}
      <div className="space-y-4">
        {alerts.map((alert) => {
          const isCritical = alert.severity === 'CRITICAL';
          const isNew = alert.status === 'NEW';

          return (
            <div
              key={alert.id}
              className={`p-5 rounded-2xl border transition-all shadow-xl ${
                isCritical
                  ? isNew
                    ? 'bg-[#120a14] border-red-500/60 shadow-[0_0_20px_rgba(239,68,68,0.15)]'
                    : 'bg-[#0a1020] border-red-500/30'
                  : 'bg-[#0a1020] border-[#162544]'
              }`}
            >
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold flex items-center space-x-1.5 ${
                        isCritical
                          ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                          : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                      }`}
                    >
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
                      <span>{alert.severity}</span>
                    </span>

                    <span className="text-sm font-bold text-white font-mono">{alert.title}</span>

                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
                        alert.status === 'NEW'
                          ? 'bg-red-500 text-white animate-pulse'
                          : alert.status === 'ACKNOWLEDGED'
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      }`}
                    >
                      STATUS: {alert.status}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-slate-300">
                    <div className="flex items-center space-x-1 text-cyan-300">
                      <MapPin className="w-3.5 h-3.5" />
                      <span>{alert.location_name}</span>
                    </div>
                    <span>•</span>
                    <div className="flex items-center space-x-1 text-amber-300">
                      <Clock className="w-3.5 h-3.5" />
                      <span>Window: {alert.expected_window}</span>
                    </div>
                    <span>•</span>
                    <div className="flex items-center space-x-1 text-emerald-400 font-bold">
                      <DollarSign className="w-3.5 h-3.5" />
                      <span>₹{alert.amount_at_risk.toLocaleString('en-IN')}</span>
                    </div>
                    <span>•</span>
                    <div className="text-slate-400">
                      Risk Score: <strong className="text-red-400">{formatRisk(alert.risk_score)}</strong>
                    </div>
                  </div>

                  {alert.action_notes && (
                    <div className="text-[11px] text-slate-400 font-mono bg-[#070c18] p-2 rounded border border-[#162544]">
                      Officer Action: {alert.action_notes}
                      {alert.acknowledged_by && ` (${alert.acknowledged_by})`}
                    </div>
                  )}
                </div>

                {/* Tactical Actions */}
                <div className="flex items-center space-x-2.5 shrink-0">
                  <button
                    onClick={() => navigate(`/cases/${alert.complaint_number}`)}
                    className="px-3 py-2 rounded-lg bg-[#0e1933] hover:bg-[#15254d] border border-cyan-500/30 text-cyan-300 text-xs font-mono font-bold flex items-center space-x-1.5 transition-all"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>VIEW CASE</span>
                  </button>

                  {alert.status === 'NEW' && (
                    <button
                      onClick={() => handleAcknowledge(alert.id)}
                      disabled={actioningId === alert.id}
                      className="px-3.5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-bold flex items-center space-x-1.5 transition-all shadow-[0_0_15px_rgba(0,216,255,0.3)]"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>ACKNOWLEDGE</span>
                    </button>
                  )}

                  {alert.status !== 'ACTION_INITIATED' && (
                    <button
                      onClick={() => handleEscalate(alert.id)}
                      disabled={actioningId === alert.id}
                      className="px-3.5 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-mono font-bold flex items-center space-x-1.5 transition-all shadow-[0_0_15px_rgba(239,68,68,0.3)]"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>ESCALATE TO BANK / GATEWAY</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
