import React, { useEffect, useState, useRef } from 'react';
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
  RefreshCw,
  Info,
  Archive,
  AlertOctagon,
  XCircle,
  Activity,
  Layers,
  Mail,
  MessageSquare,
  Webhook,
  Wifi,
} from 'lucide-react';
import { api } from '../services/api';
import { AlertItem, NotificationOutboxItem, AlertChannelsStatusResponse } from '../types';
import { formatINR } from '../utils/formatters';
import { useAuth } from '../store/authContext';

export const AlertsCenter: React.FC = () => {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [channelsStatus, setChannelsStatus] = useState<AlertChannelsStatusResponse | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [actioningId, setActioningId] = useState<number | null>(null);
  const [selectedOutboxAlert, setSelectedOutboxAlert] = useState<AlertItem | null>(null);
  const [outboxEvents, setOutboxEvents] = useState<NotificationOutboxItem[]>([]);
  const [loadingOutbox, setLoadingOutbox] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastSyncCursorRef = useRef<number>(0);

  const canAct = user && ['I4C_ADMIN', 'STATE_LEA', 'DISTRICT_LEA', 'BANK_OFFICER'].includes(user.role);

  const fetchChannelsStatus = async () => {
    try {
      const data = await api.getAlertChannelsStatus();
      setChannelsStatus(data);
    } catch (err) {
      console.error('Failed to load channels status', err);
    }
  };

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const [data] = await Promise.all([
        api.getAlerts({
          status: statusFilter !== 'ALL' ? statusFilter : undefined,
        }),
        fetchChannelsStatus(),
      ]);
      setAlerts(data);
      if (data.length > 0) {
        const maxId = Math.max(...data.map((a) => a.id));
        lastSyncCursorRef.current = Math.max(lastSyncCursorRef.current, maxId);
      }
    } catch (err) {
      console.error('Failed to load alerts', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncMissed = async () => {
    try {
      const res = await api.syncAlerts({ since_id: lastSyncCursorRef.current });
      if (res && res.items && res.items.length > 0) {
        setAlerts((prev) => {
          const map = new Map(prev.map((a) => [a.id, a]));
          for (const item of res.items) {
            map.set(item.id, item);
          }
          return Array.from(map.values()).sort((a, b) => b.id - a.id);
        });
        lastSyncCursorRef.current = Math.max(lastSyncCursorRef.current, res.cursor);
      }
    } catch (err) {
      console.error('Missed alert sync failed', err);
    }
  };

  useEffect(() => {
    fetchAlerts();

    // Authenticated WebSocket connection with Missed-Alert Replay sync
    let socket: WebSocket | null = null;
    let isSubscribed = true;
    let reconnectDelay = 2000;

    const connectWebSocket = () => {
      if (!isSubscribed || !token) return;

      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const defaultWsUrl = `${wsProtocol}//${window.location.host}/ws/alerts`;
      const baseWsUrl = import.meta.env.VITE_WS_URL || defaultWsUrl;
      const wsUrl = `${baseWsUrl}?token=${encodeURIComponent(token)}`;

      try {
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
          setWsConnected(true);
          reconnectDelay = 2000;
          // Reconnect replay: fetch any missed alerts that occurred while offline
          handleSyncMissed();
        };

        socket.onmessage = (evt) => {
          try {
            const data = JSON.parse(evt.data);
            if (data.event) {
              fetchAlerts();
            }
          } catch (e) {}
        };

        socket.onclose = (evt) => {
          setWsConnected(false);
          if (evt.code === 1008) {
            console.warn('Alerts WebSocket authentication failed (1008). Stopped auto-reconnect.');
            return;
          }
          if (isSubscribed) {
            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectDelay = Math.min(reconnectDelay * 1.5, 30000);
              connectWebSocket();
            }, reconnectDelay);
          }
        };

        socket.onerror = () => {
          setWsConnected(false);
          if (socket) socket.close();
        };
      } catch (e) {
        console.error('WebSocket connection error:', e);
      }
    };

    connectWebSocket();

    return () => {
      isSubscribed = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socket) socket.close();
    };
  }, [statusFilter, token]);

  const handleAcknowledge = async (id: number) => {
    if (!canAct) return;
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
    if (!canAct) return;
    setActioningId(id);
    try {
      await api.escalateAlert(id, 'Automated bank ATM hold request transmitted [SIMULATED PROTOTYPE].');
      await fetchAlerts();
    } catch (err) {
      console.error('Error escalating alert', err);
    } finally {
      setActioningId(null);
    }
  };

  const handleViewOutbox = async (alert: AlertItem) => {
    setSelectedOutboxAlert(alert);
    setLoadingOutbox(true);
    try {
      const events = await api.getAlertOutbox(alert.id);
      setOutboxEvents(events);
    } catch (err) {
      console.error('Failed to load alert outbox events', err);
    } finally {
      setLoadingOutbox(false);
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <BellRing className="w-5 h-5 text-red-600 shrink-0" />
            <h1 className="text-lg font-bold text-[#031926] font-sans">
              Tactical Alerts & Rapid Intervention Center
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Durable transactional alerts backed by reliable outbox delivery, bounded retry backoff, and prediction supersession
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
              <option value="DELIVERED">DELIVERED</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="ACTION_INITIATED">ACTION INITIATED</option>
              <option value="SUPERSEDED">SUPERSEDED (Older Prediction)</option>
              <option value="EXPIRED">EXPIRED (Past Window)</option>
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

      {/* Multi-Channel Delivery Status Bar */}
      {channelsStatus && (
        <div className="bg-white border border-[#DCE5F0] rounded-lg p-3.5 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
              <Activity className="w-3.5 h-3.5 text-blue-600" />
              <span>Multi-Channel Delivery Grid</span>
            </span>
            <span className="text-[10px] text-slate-400">
              Synced: {new Date(channelsStatus.timestamp || Date.now()).toLocaleTimeString()}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
            {/* Dashboard / WS */}
            <div className="p-2.5 rounded-md bg-slate-50 border border-slate-200 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-slate-700 flex items-center space-x-1">
                  <Wifi className="w-3.5 h-3.5 text-blue-600" />
                  <span>WebSocket</span>
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  channelsStatus.dashboard_websocket?.configured ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-200 text-slate-700'
                }`}>
                  {channelsStatus.dashboard_websocket?.mode || 'LIVE'}
                </span>
              </div>
              <div className="text-[11px] text-slate-500">
                Active Connections: <strong className="text-slate-800">{channelsStatus.dashboard_websocket?.details?.active_connections ?? (wsConnected ? 1 : 0)}</strong>
              </div>
            </div>

            {/* Email */}
            <div className="p-2.5 rounded-md bg-slate-50 border border-slate-200 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-slate-700 flex items-center space-x-1">
                  <Mail className="w-3.5 h-3.5 text-purple-600" />
                  <span>Email</span>
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  channelsStatus.email?.mode === 'LIVE'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-purple-50 text-purple-700 border border-purple-200'
                }`}>
                  {channelsStatus.email?.mode || 'SIMULATED'}
                </span>
              </div>
              <div className="text-[11px] text-slate-500">
                Gateway: <strong className="text-slate-800">{channelsStatus.email?.details?.smtp_host ? 'Custom SMTP' : 'Sandbox Simulator'}</strong>
              </div>
            </div>

            {/* SMS */}
            <div className="p-2.5 rounded-md bg-slate-50 border border-slate-200 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-slate-700 flex items-center space-x-1">
                  <MessageSquare className="w-3.5 h-3.5 text-amber-600" />
                  <span>SMS</span>
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  channelsStatus.sms?.mode === 'LIVE'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-amber-50 text-amber-700 border border-amber-200'
                }`}>
                  {channelsStatus.sms?.mode || 'SIMULATED'}
                </span>
              </div>
              <div className="text-[11px] text-slate-500">
                Gateway: <strong className="text-slate-800">{channelsStatus.sms?.details?.gateway_provider || 'Mock Gateway'}</strong>
              </div>
            </div>

            {/* Partner Webhook */}
            <div className="p-2.5 rounded-md bg-slate-50 border border-slate-200 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-slate-700 flex items-center space-x-1">
                  <Webhook className="w-3.5 h-3.5 text-teal-600" />
                  <span>Partner Webhook</span>
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  channelsStatus.partner_webhook?.mode === 'LIVE'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-teal-50 text-teal-700 border border-teal-200'
                }`}>
                  {channelsStatus.partner_webhook?.mode || 'SIMULATED'}
                </span>
              </div>
              <div className="text-[11px] text-slate-500">
                Signature: <strong className="text-slate-800">{channelsStatus.partner_webhook?.details?.signature_algorithm || 'HMAC-SHA256'}</strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Truthful Operational Banner */}
      <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg flex items-start space-x-3 text-xs text-amber-900 shadow-xs">
        <Info className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold">Operational Integration Status: </span>
          <span>
            Alert delivery and outgoing notifications commit atomically in the persistent database outbox across Dashboard WebSocket, Email, SMS, and HMAC-signed Partner Webhook channels. Bank hold transmissions operate in <strong>SIMULATED PROTOTYPE</strong> mode and will not freeze live external accounts.
          </span>
        </div>
      </div>

      {/* Alert Cards List */}
      <div className="space-y-3">
        {loading && alerts.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500 bg-white rounded-lg border border-[#DCE5F0]">
            Loading tactical alerts...
          </div>
        ) : alerts.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500 bg-white rounded-lg border border-[#DCE5F0]">
            No alerts found matching filter criteria.
          </div>
        ) : (
          alerts.map((alert) => {
            const isCritical = alert.severity === 'CRITICAL';
            const isHigh = alert.severity === 'HIGH';
            const isNew = alert.status === 'NEW';
            const isSuperseded = alert.status === 'SUPERSEDED';
            const isExpired = alert.status === 'EXPIRED';
            const isSimulatedAction = alert.status === 'ACTION_INITIATED';

            return (
              <div
                key={alert.id}
                className={`p-4 sm:p-5 rounded-lg border bg-white shadow-xs transition-colors hover:border-slate-300 ${
                  isSuperseded || isExpired
                    ? 'border-l-4 border-l-slate-400 opacity-80 border-r-[#DCE5F0] border-t-[#DCE5F0] border-b-[#DCE5F0]'
                    : isCritical
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
                          isSuperseded || isExpired
                            ? 'bg-slate-100 text-slate-700 border border-slate-300'
                            : isCritical
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : isHigh
                            ? 'bg-orange-50 text-orange-700 border border-orange-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            isSuperseded || isExpired
                              ? 'bg-slate-500'
                              : isCritical
                              ? 'bg-red-600'
                              : isHigh
                              ? 'bg-orange-600'
                              : 'bg-amber-600'
                          }`}
                        ></span>
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
                          isSuperseded
                            ? 'bg-slate-200 text-slate-800'
                            : isExpired
                            ? 'bg-amber-100 text-amber-800'
                            : isNew
                            ? 'bg-red-600 text-white'
                            : alert.status === 'ACKNOWLEDGED'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : alert.status === 'DELIVERED'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        }`}
                      >
                        STATUS: {alert.status} {isSimulatedAction && '[SIMULATED]'}
                      </span>

                      {alert.delivery_status && (
                        <span className="text-[10px] px-2 py-0.5 rounded font-medium bg-purple-50 text-purple-700 border border-purple-200">
                          OUTBOX: {alert.delivery_status} (Attempts: {alert.attempt_count || 1})
                        </span>
                      )}
                    </div>

                    {/* Multi-Channel Delivery Badges */}
                    {alert.channel_delivery_status && Object.keys(alert.channel_delivery_status).length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                        <span className="text-[10px] text-slate-400 font-medium">Channels:</span>
                        {Object.entries(alert.channel_delivery_status).map(([ch, info]) => {
                          const isDelivered = info.status === 'DELIVERED';
                          const isFailed = info.status === 'FAILED' || info.status === 'PERMANENT_FAILURE';
                          return (
                            <span
                              key={ch}
                              title={`${ch}: ${info.status}${info.mode ? ` (${info.mode})` : ''}${info.last_error ? ` — Error: ${info.last_error}` : ''}`}
                              className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium flex items-center space-x-1 ${
                                isDelivered
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : isFailed
                                  ? 'bg-red-50 text-red-700 border border-red-200'
                                  : 'bg-slate-100 text-slate-700 border border-slate-200'
                              }`}
                            >
                              <span>
                                {ch === 'DASHBOARD_WEBSOCKET' ? 'WS' : ch === 'EMAIL' ? 'Email' : ch === 'SMS' ? 'SMS' : 'Webhook'}:
                              </span>
                              <strong>{info.status}</strong>
                              {info.mode && <span className="text-[9px] opacity-75">[{info.mode}]</span>}
                            </span>
                          );
                        })}
                      </div>
                    )}

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

                    {isSuperseded && alert.superseded_by_prediction_id && (
                      <div className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-md border border-slate-200 flex items-center space-x-2">
                        <Archive className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                        <span>
                          Superseded by newer Prediction #{alert.superseded_by_prediction_id} (History preserved).
                        </span>
                      </div>
                    )}

                    {alert.last_error && (
                      <div className="text-xs text-red-700 bg-red-50 p-2.5 rounded-md border border-red-200 flex items-start space-x-2">
                        <XCircle className="w-3.5 h-3.5 text-red-600 shrink-0 mt-0.5" />
                        <span>Delivery Error: {alert.last_error}</span>
                      </div>
                    )}

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
                      onClick={() => handleViewOutbox(alert)}
                      title="View durable outbox delivery audit trail"
                      className="px-3 py-1.5 rounded-md bg-white hover:bg-slate-50 border border-[#DCE5F0] text-slate-700 text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-xs"
                    >
                      <Layers className="w-3.5 h-3.5 text-purple-600" />
                      <span>OUTBOX AUDIT</span>
                    </button>

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

                    {(alert.status === 'NEW' || alert.status === 'DELIVERED') && (
                      <button
                        onClick={() => handleAcknowledge(alert.id)}
                        disabled={actioningId === alert.id || !canAct}
                        title={!canAct ? 'Requires LEA or Bank Officer role' : undefined}
                        className="px-3.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-xs disabled:opacity-50"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>ACKNOWLEDGE</span>
                      </button>
                    )}

                    {!['ACTION_INITIATED', 'SUPERSEDED', 'EXPIRED'].includes(alert.status) && (
                      <button
                        onClick={() => handleEscalate(alert.id)}
                        disabled={actioningId === alert.id || !canAct}
                        title={!canAct ? 'Requires LEA or Bank Officer role' : 'Requests simulated hold in audit trail'}
                        className="px-3.5 py-1.5 rounded-md bg-red-600 hover:bg-red-700 text-white text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-xs disabled:opacity-50"
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>ESCALATE (SIMULATED HOLD)</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Outbox Audit Trail Modal */}
      {selectedOutboxAlert && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-lg border border-[#DCE5F0] shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col">
            <div className="p-4 border-b border-[#DCE5F0] flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-[#031926] flex items-center space-x-2">
                  <Layers className="w-4 h-4 text-[#468189]" />
                  <span>Durable Outbox Delivery Audit Trail</span>
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Alert #{selectedOutboxAlert.id} ({selectedOutboxAlert.complaint_number}) — {selectedOutboxAlert.location_name}
                </p>
              </div>
              <button
                onClick={() => setSelectedOutboxAlert(null)}
                className="p-1 rounded-md text-slate-400 hover:text-slate-700"
              >
                ✕
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-3 flex-1 text-xs">
              {loadingOutbox ? (
                <div className="p-6 text-center text-slate-500">Loading outbox events...</div>
              ) : outboxEvents.length === 0 ? (
                <div className="p-6 text-center text-slate-500">No outbox events recorded for this alert.</div>
              ) : (
                outboxEvents.map((ev) => {
                  const deliveryRes = ev.payload?.delivery_result;
                  return (
                    <div key={ev.id} className="p-3 bg-slate-50 rounded-md border border-[#DCE5F0] space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-800 flex items-center space-x-1.5">
                          <span>{ev.event_type}</span>
                          <span className="text-[10px] text-slate-500 font-mono">({ev.channel})</span>
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded font-semibold text-[10px] ${
                            ev.status === 'DELIVERED'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : ev.status === 'PERMANENT_FAILURE'
                              ? 'bg-red-50 text-red-700 border border-red-200'
                              : ev.status === 'FAILED'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-blue-50 text-blue-700 border border-blue-200'
                          }`}
                        >
                          {ev.status}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-slate-600 text-[11px]">
                        <div>Channel: <strong>{ev.channel}</strong></div>
                        <div>Attempts: <strong>{ev.attempt_count} / {ev.max_attempts}</strong></div>
                        <div>Prediction Version: <strong>v{ev.prediction_version || 1}</strong></div>
                        <div>Idempotency Key: <code className="text-[10px] bg-white px-1 py-0.5 rounded border">{ev.idempotency_key}</code></div>
                        {deliveryRes?.mode && <div>Mode: <strong>{deliveryRes.mode}</strong></div>}
                        {deliveryRes?.recipient && <div>Recipient: <strong>{deliveryRes.recipient}</strong></div>}
                        {deliveryRes?.signature_algorithm && <div>Signature: <strong>{deliveryRes.signature_algorithm}</strong></div>}
                        {deliveryRes?.status_code && <div>HTTP Status: <strong>{deliveryRes.status_code}</strong></div>}
                      </div>

                      {ev.last_error && (
                        <div className="p-2 bg-red-50 text-red-700 rounded text-[11px] border border-red-200">
                          <strong>Last Error:</strong> {ev.last_error}
                        </div>
                      )}

                      <div className="text-[10px] text-slate-400 flex items-center justify-between pt-1">
                        <span>Created: {new Date(ev.created_at).toLocaleString()}</span>
                        {ev.delivered_at && <span>Delivered: {new Date(ev.delivered_at).toLocaleString()}</span>}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            <div className="p-3 border-t border-[#DCE5F0] bg-slate-50 flex justify-end">
              <button
                onClick={() => setSelectedOutboxAlert(null)}
                className="px-4 py-1.5 bg-white border border-[#DCE5F0] rounded-md text-xs font-medium text-slate-700 hover:bg-slate-100"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
