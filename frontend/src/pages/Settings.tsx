import React from 'react';
import {
  Settings as SettingsIcon,
  Shield,
  Server,
  Sliders,
  Database,
  Lock,
  Radio,
  CheckCircle2
} from 'lucide-react';
import { useAuth } from '../store/authContext';

export const Settings: React.FC = () => {
  const { user } = useAuth();

  return (
    <div className="space-y-6 pb-12 max-w-5xl">
      {/* Header */}
      <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <SettingsIcon className="w-5 h-5 text-blue-600 shrink-0" />
            <h1 className="text-lg font-bold text-[#173A63] font-sans">
              Platform Configuration & Policy Parameters
            </h1>
          </div>
          <p className="text-xs text-slate-500 font-sans mt-0.5">
            Predictive thresholds, I4C LEA integration endpoints, and cryptographic security settings
          </p>
        </div>
      </div>

      {/* Grid Settings Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
        {/* ML Threshold Configuration */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs space-y-4">
          <div className="flex items-center space-x-2 text-[#173A63] font-bold border-b border-[#DCE5F0] pb-3">
            <Sliders className="w-4 h-4 text-blue-600" />
            <span>AI RISK FUSION COEFFICIENTS</span>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex justify-between mb-1 text-slate-600">
                <span>ML Candidate Ranker Weight:</span>
                <span className="text-blue-700 font-bold">40%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <div className="w-[40%] h-full bg-blue-600"></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1 text-slate-600">
                <span>Graph Centrality (NetworkX) Weight:</span>
                <span className="text-blue-700 font-bold">25%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <div className="w-[25%] h-full bg-blue-500"></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1 text-slate-600">
                <span>Geospatial Proximity Weight:</span>
                <span className="text-blue-700 font-bold">20%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <div className="w-[20%] h-full bg-indigo-500"></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1 text-slate-600">
                <span>Temporal Extraction Window Weight:</span>
                <span className="text-blue-700 font-bold">15%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <div className="w-[15%] h-full bg-emerald-500"></div>
              </div>
            </div>
          </div>
        </div>

        {/* Tactical Alert Trigger Rule */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs space-y-4">
          <div className="flex items-center space-x-2 text-red-700 font-bold border-b border-[#DCE5F0] pb-3">
            <Shield className="w-4 h-4 text-red-600" />
            <span>INTERVENTION TRIGGER RULES</span>
          </div>

          <div className="space-y-2.5 text-slate-600">
            <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
              <span>Critical Alarm Trigger Threshold:</span>
              <span className="text-red-700 font-bold">&gt;= 80% Risk</span>
            </div>
            <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
              <span>Automated Bank Hold Request:</span>
              <span className="text-emerald-700 font-bold">ENABLED (I4C API)</span>
            </div>
            <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
              <span>Max Distance Radius for Hotspot:</span>
              <span className="text-blue-700 font-bold">2.5 km Perimeter</span>
            </div>
            <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] flex items-center justify-between">
              <span>Account Masking Format:</span>
              <span className="text-slate-700 font-semibold font-mono">ACC••••XXXX</span>
            </div>
          </div>
        </div>

        {/* Database & Infrastructure */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-[#173A63] font-bold border-b border-[#DCE5F0] pb-3">
            <Database className="w-4 h-4 text-blue-600" />
            <span>DATA STORAGE SUBSYSTEM</span>
          </div>
          <div className="p-2.5 bg-[#F6F8FC] rounded-md border border-[#DCE5F0] space-y-1.5 text-slate-600">
            <div className="flex justify-between">
              <span>Active Engine:</span>
              <span className="text-emerald-700 font-bold">PostgreSQL Engine</span>
            </div>
            <div className="flex justify-between">
              <span>Connection Pool:</span>
              <span className="text-slate-800 font-medium">Active (SessionLocal)</span>
            </div>
            <div className="flex justify-between">
              <span>Dialect Support:</span>
              <span className="text-blue-700 font-medium">PostgreSQL 15+ (Production)</span>
            </div>
          </div>
        </div>

        {/* Active Session Badge */}
        <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-[#173A63] font-bold border-b border-[#DCE5F0] pb-3">
            <Lock className="w-4 h-4 text-blue-600" />
            <span>AUTHENTICATED OFFICER PROFILE</span>
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
              <span>Badge Token:</span>
              <span className="text-emerald-700 font-bold">{user?.badge_number || 'N/A'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
