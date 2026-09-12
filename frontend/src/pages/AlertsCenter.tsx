import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BellRing,
  AlertTriangle,
  ShieldAlert,
  CheckCircle2,
  Clock,
  MapPin,
  Eye,
  Send,
  Radio,
  Filter,
  RefreshCw
} from 'lucide-react';
import { api } from '../services/api';
import { AlertItem } from '../types';
import { formatINR } from '../utils/formatters';

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
    const WS_URL =
      import.meta.env.VITE_WS_URL ||
      'wss://cybershield-ai-production-66121.up.railway.app/ws/alerts';
    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(WS_URL);
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <BellRing className="w-5 h-5 text-red-600 shrink-0" />
            <h1 className="text-lg font-bold text-[#173A63] font-sans">
              Tactical Alerts & Rapid Intervention Center
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Automated predictive alarms triggered for high-risk (&gt;=80%) cash-out extractions
          </p>
        </div>

        {/* Filter */}
        <div className="flex items-center space-x-2 sm:space-x-3 w-full sm:w-auto justify-between sm:justify-start">
          <div className="flex items-center space-x-2 bg-white px-3 py-1.5 rounded-md border border-[#DCE5F0] flex-1 sm:flex-initial">
            <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-transparent text-xs text-slate-700 focus:outline-none cursor-pointer w-full sm:w-auto"
            >
              <option value="ALL">All Alert States</option>
              <option value="NEW">NEW (Unacknowledged)</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="ACTION_INITIATED">ACTION INITIATED</option>
            </select>
          </div>

          <button
            onClick={fetchAlerts}
            title="Refresh alerts"
            className="p-2 rounded-md bg-white border border-[#DCE5F0] text-slate-600 hover:text-blue-600 hover:bg-blue-50 transition-colors shrink-0"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Alert Cards List */}
      <div className="space-y-3">
        {alerts.map((alert) => {
          const isCritical = alert.severity === 'CRITICAL';
          const isHigh = alert.severity === 'HIGH';
          const isNew = alert.status === 'NEW';

          return (
            <div
              key={alert.id}
              className={`p-4 sm:p-5 rounded-lg border bg-white shadow-xs transition-colors hover:border-slate-300 ${
                isCritical
                  ? 'border-l-4 border-l-red-600 border-r-[#DCE5F0] border-t-[#DCE5F0] border-b-[#DCE5F0]'
                  : isHigh
                  ? 'border-l-4 border-l-orange-500 border-r-[#DCE5F0] border-t-[#DCE5F0] border-b-[#DCE5F0]'
                  : 'border-[#DCE5F0]'
              }`}
            >
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="space-y-2 min-w-0">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span
                      className={`px-2.5 py-0.5 rounded text-xs font-semibold flex items-center space-x-1.5 ${
                        isCritical
                          ? 'bg-red-50 text-red-700 border border-red-200'
                          : isHigh
                          ? 'bg-orange-50 text-orange-700 border border-orange-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${isCritical ? 'bg-red-600' : isHigh ? 'bg-orange-600' : 'bg-amber-600'}`}></span>
                      <span>{alert.severity}</span>
                    </span>

                    <span className="text-sm font-bold text-slate-900 break-words">{alert.title}</span>

                    {alert.prediction_id && (
                      <span className="text-[10px] px-2 py-0.5 rounded font-medium bg-blue-50 text-blue-700 border border-blue-200">
                        PREDICTION #{alert.prediction_id}
                      </span>
                    )}

                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-semibold ${
                        isNew
                          ? 'bg-red-600 text-white'
                          : alert.status === 'ACKNOWLEDGED'
                          ? 'bg-amber-50 text-amber-700 border border-amber-200'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}
                    >
                      STATUS: {alert.status}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
                    <div className="flex items-center space-x-1 text-blue-700 font-medium">
                      <MapPin className="w-3.5 h-3.5 shrink-0" />
                      <span className="truncate">{alert.location_name}</span>
                    </div>
                    <span>•</span>
                    <div className="flex items-center space-x-1 text-slate-600">
                      <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span>Window: {alert.expected_window}</span>
                    </div>
                    <span>•</span>
                    <div className="flex items-center space-x-1 text-emerald-700 font-semibold">
                      <span>{formatINR(alert.amount_at_risk)}</span>
                    </div>
                    <span>•</span>
                    <div className="text-slate-500">
                      Operational Priority: <strong className={isCritical ? 'text-red-700' : isHigh ? 'text-orange-700' : 'text-amber-700'}>{alert.severity}</strong>
                    </div>
                  </div>

                  {alert.action_notes && (
                    <div className="text-xs text-slate-600 bg-[#F6F8FC] p-2.5 rounded-md border border-[#DCE5F0] break-words">
                      Officer Action: {alert.action_notes}
                      {alert.acknowledged_by && ` (${alert.acknowledged_by})`}
                    </div>
                  )}
                </div>

                {/* Tactical Actions */}
                <div className="flex flex-wrap items-center gap-2 sm:gap-2.5 shrink-0 pt-2 lg:pt-0">
                  <button
                    onClick={() => navigate(`/cases/${alert.complaint_number}`)}
                    className="px-3 py-1.5 rounded-md bg-white hover:bg-blue-50 border border-[#DCE5F0] text-blue-700 text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-xs"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>VIEW CASE</span>
                  </button>

                  <button
                    onClick={() => navigate(`/risk-map`)}
                    className="px-3 py-1.5 rounded-md bg-white hover:bg-blue-50 border border-[#DCE5F0] text-blue-700 text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-xs"
                  >
                    <MapPin className="w-3.5 h-3.5" />
                    <span>RISK MAP</span>
                  </button>

                  {alert.status === 'NEW' && (
                    <button
                      onClick={() => handleAcknowledge(alert.id)}
                      disabled={actioningId === alert.id}
                      className="px-3.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-xs disabled:opacity-60"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>ACKNOWLEDGE</span>
                    </button>
                  )}

                  {alert.status !== 'ACTION_INITIATED' && (
                    <button
                      onClick={() => handleEscalate(alert.id)}
                      disabled={actioningId === alert.id}
                      className="px-3.5 py-1.5 rounded-md bg-red-600 hover:bg-red-700 text-white text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-xs disabled:opacity-60"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>ESCALATE TO BANK</span>
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
