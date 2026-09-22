import React, { useEffect, useState } from 'react';
import {
  Settings as SettingsIcon,
  Shield,
  Sliders,
  Database,
  Lock,
  Server,
  Cpu,
  Radio,
} from 'lucide-react';
import { useAuth } from '../store/authContext';
import { api } from '../services/api';
import { SystemStatus } from '../types';

export const Settings: React.FC = () => {
  const { user } = useAuth();
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const fetchStatus = async () => {
      try {
        const data = await api.getSystemStatus();
        if (mounted) {
          setSystemStatus(data);
        }
      } catch (err) {
        console.error('Failed to load system status:', err);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    fetchStatus();
    return () => {
      mounted = false;
    };
  }, []);

  const getEnvBadgeClass = (env?: string) => {
    switch ((env || '').toLowerCase()) {
      case 'production':
      case 'prod':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'demo':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      default:
        return 'bg-blue-100 text-blue-800 border-blue-300';
    }
  };

  const getArtifactBadgeClass = (status?: string) => {
    switch (status) {
      case 'COMPATIBLE':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'VERSION_MISMATCH':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      default:
        return 'bg-red-100 text-red-800 border-red-300';
    }
  };

  return (
    <div className="space-y-6 pb-12 max-w-5xl">
      {/* Header */}
      <div className="p-4 sm:p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <SettingsIcon className="w-5 h-5 text-blue-600 shrink-0" />
            <h1 className="text-base sm:text-lg font-bold text-[#031926] font-sans">
              Platform Diagnostics & Policy Parameters
            </h1>
          </div>
          <p className="text-xs text-slate-500 font-sans mt-0.5">
            Verified runtime telemetry, ML artifact integrity, and officer jurisdiction enforcement
          </p>
        </div>
        <div>
          <span
            className={`px-2.5 py-1 text-xs font-bold font-mono rounded-md border uppercase ${getEnvBadgeClass(
              systemStatus?.environment
            )}`}
          >
            {loading ? 'CHECKING...' : systemStatus?.environment || 'DEVELOPMENT'}
          </span>
        </div>
      </div>

      {/* Grid Settings Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
        {/* ML Engine & Model Verification */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs space-y-4">
          <div className="flex items-center space-x-2 text-[#031926] font-bold border-b border-[#DCE5F0] pb-3">
            <Cpu className="w-4 h-4 text-blue-600" />
            <span>AI ML ENGINE & VERIFIED ARTIFACTS</span>
          </div>

          <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] space-y-2 text-slate-600">
            <div className="flex justify-between items-center">
              <span>ML Engine Status:</span>
              <span className="font-bold text-emerald-700">
                {loading ? 'Checking...' : systemStatus?.ml_engine.status || 'OPERATIONAL'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span>Classifier Model:</span>
              <span className="font-mono text-slate-800 font-bold">
                {loading ? 'Checking...' : systemStatus?.ml_engine.model_version || 'v7_compat'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span>Time-to-Disbursement:</span>
              <span className="font-mono text-slate-800 font-medium">
                {loading ? 'Checking...' : systemStatus?.ml_engine.time_model_version || 'cashout-time-xgb-v3'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span>Artifact Integrity:</span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${getArtifactBadgeClass(
                  systemStatus?.ml_engine.artifact_verification
                )}`}
              >
                {loading ? 'VERIFYING...' : systemStatus?.ml_engine.artifact_verification || 'COMPATIBLE'}
              </span>
            </div>
            {systemStatus?.ml_engine.runtime_versions && (
              <div className="pt-2 border-t border-slate-200 text-[10px] text-slate-500 space-y-1">
                <div className="flex justify-between">
                  <span>scikit-learn: {systemStatus.ml_engine.runtime_versions.scikit_learn}</span>
                  <span>xgboost: {systemStatus.ml_engine.runtime_versions.xgboost}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Database & Infrastructure */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-[#031926] font-bold border-b border-[#DCE5F0] pb-3">
            <Database className="w-4 h-4 text-blue-600" />
            <span>DATA STORAGE & ENGINE SUBSYSTEM</span>
          </div>
          <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] space-y-2 text-slate-600">
            <div className="flex justify-between items-center">
              <span>Active Engine:</span>
              <span className="text-emerald-700 font-bold uppercase font-mono">
                {loading
                  ? 'Checking...'
                  : `${systemStatus?.database.engine || 'PostgreSQL'} ${
                      systemStatus?.database.is_persistent ? '(Persistent Cloud)' : '(Local Session)'
                    }`}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span>Database Connection:</span>
              <span
                className={`font-semibold ${
                  systemStatus?.database.status === 'connected' ? 'text-emerald-700' : 'text-slate-700'
                }`}
              >
                {loading
                  ? 'Querying pool...'
                  : systemStatus?.database.status === 'connected'
                  ? 'Active (Connected)'
                  : 'Degraded'}
              </span>
            </div>
            {systemStatus?.database.latency_ms !== undefined && (
              <div className="flex justify-between items-center">
                <span>Query Latency:</span>
                <span className="font-mono text-slate-700">{systemStatus.database.latency_ms} ms</span>
              </div>
            )}
            <div className="flex justify-between items-center">
              <span>WebSocket Streaming:</span>
              <span className="font-semibold text-blue-700">
                {loading ? 'Checking...' : `${systemStatus?.websocket.active_clients || 0} active client(s)`}
              </span>
            </div>
          </div>
        </div>

        {/* Operational Integrations & Simulation Notices */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs space-y-4">
          <div className="flex items-center space-x-2 text-[#031926] font-bold border-b border-[#DCE5F0] pb-3">
            <Radio className="w-4 h-4 text-blue-600" />
            <span>EXTERNAL INTEGRATIONS (TRUTHFUL STATUS)</span>
          </div>

          <div className="space-y-2.5 text-slate-600">
            <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] space-y-1">
              <div className="flex justify-between items-center">
                <span className="font-medium text-slate-800">Core Banking Gateway:</span>
                <span className="text-amber-700 font-bold bg-amber-50 px-2 py-0.5 rounded border border-amber-200 text-[10px]">
                  {systemStatus?.integrations.bank_gateway.status || 'SIMULATED_LOCAL'}
                </span>
              </div>
              <p className="text-[10px] text-slate-500">
                {systemStatus?.integrations.bank_gateway.description ||
                  'Local prototype mode: External core-banking gateway not connected.'}
              </p>
            </div>

            <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] space-y-1">
              <div className="flex justify-between items-center">
                <span className="font-medium text-slate-800">Consortium Blockchain:</span>
                <span className="text-indigo-700 font-bold bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200 text-[10px]">
                  {systemStatus?.integrations.blockchain_gateway.status || 'STANDBY_FABRIC_LOCAL'}
                </span>
              </div>
              <p className="text-[10px] text-slate-500">
                {systemStatus?.integrations.blockchain_gateway.description ||
                  'Consortium chaincode testnet available; production gateway standby.'}
              </p>
            </div>
          </div>
        </div>

        {/* Active Session & Jurisdiction Badge */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-[#031926] font-bold border-b border-[#DCE5F0] pb-3">
            <Lock className="w-4 h-4 text-blue-600" />
            <span>AUTHENTICATED OPERATOR CONTEXT</span>
          </div>
          <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] space-y-1.5 text-slate-600">
            <div className="flex justify-between">
              <span>Officer Name:</span>
              <span className="text-slate-900 font-bold">{user?.full_name || 'Active Officer'}</span>
            </div>
            <div className="flex justify-between">
              <span>Designated Role:</span>
              <span className="text-blue-700 font-bold">{user?.role || 'OFFICER'}</span>
            </div>
            <div className="flex justify-between">
              <span>Jurisdiction State:</span>
              <span className="text-slate-800 font-medium">{user?.state || 'All-India (National)'}</span>
            </div>
            <div className="flex justify-between">
              <span>Jurisdiction District:</span>
              <span className="text-slate-800 font-medium">{user?.district || 'All Districts'}</span>
            </div>
            <div className="flex justify-between">
              <span>Badge Token:</span>
              <span className="text-emerald-700 font-bold">{user?.badge_number || 'N/A'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
