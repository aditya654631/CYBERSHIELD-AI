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
      <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <SettingsIcon className="w-5 h-5 text-cyan-400" />
            <h1 className="text-xl font-bold text-white font-['JetBrains_Mono',monospace]">
              Platform Configuration & Policy Parameters
            </h1>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Predictive thresholds, I4C LEA integration endpoints, and cryptographic security settings
          </p>
        </div>
      </div>

      {/* Grid Settings Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-mono text-xs">
        {/* ML Threshold Configuration */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-xl space-y-4">
          <div className="flex items-center space-x-2 text-cyan-300 font-bold border-b border-[#162544] pb-3">
            <Sliders className="w-4 h-4 text-cyan-400" />
            <span>AI RISK FUSION COEFFICIENTS</span>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex justify-between mb-1 text-slate-300">
                <span>ML Candidate Ranker Weight:</span>
                <span className="text-cyan-400 font-bold">40%</span>
              </div>
              <div className="w-full h-1.5 bg-[#162544] rounded-full overflow-hidden">
                <div className="w-[40%] h-full bg-cyan-400"></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1 text-slate-300">
                <span>Graph Centrality (NetworkX) Weight:</span>
                <span className="text-cyan-400 font-bold">25%</span>
              </div>
              <div className="w-full h-1.5 bg-[#162544] rounded-full overflow-hidden">
                <div className="w-[25%] h-full bg-blue-500"></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1 text-slate-300">
                <span>Geospatial Proximity Weight:</span>
                <span className="text-cyan-400 font-bold">20%</span>
              </div>
              <div className="w-full h-1.5 bg-[#162544] rounded-full overflow-hidden">
                <div className="w-[20%] h-full bg-purple-500"></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1 text-slate-300">
                <span>Temporal Extraction Window Weight:</span>
                <span className="text-cyan-400 font-bold">15%</span>
              </div>
              <div className="w-full h-1.5 bg-[#162544] rounded-full overflow-hidden">
                <div className="w-[15%] h-full bg-emerald-400"></div>
              </div>
            </div>
          </div>
        </div>

        {/* Tactical Alert Trigger Rule */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-xl space-y-4">
          <div className="flex items-center space-x-2 text-red-400 font-bold border-b border-[#162544] pb-3">
            <Shield className="w-4 h-4" />
            <span>INTERVENTION TRIGGER RULES</span>
          </div>

          <div className="space-y-3 text-slate-300">
            <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] flex items-center justify-between">
              <span>Critical Alarm Trigger Threshold:</span>
              <span className="text-red-400 font-bold">&gt;= 80% Risk</span>
            </div>
            <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] flex items-center justify-between">
              <span>Automated Bank Hold Request:</span>
              <span className="text-emerald-400 font-bold">ENABLED (I4C API)</span>
            </div>
            <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] flex items-center justify-between">
              <span>Max Distance Radius for Hotspot:</span>
              <span className="text-cyan-300 font-bold">2.5 km Perimeter</span>
            </div>
            <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] flex items-center justify-between">
              <span>Account Masking Format:</span>
              <span className="text-slate-300 font-bold">ACC••••XXXX</span>
            </div>
          </div>
        </div>

        {/* Database & Infrastructure */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-xl space-y-3">
          <div className="flex items-center space-x-2 text-slate-200 font-bold border-b border-[#162544] pb-3">
            <Database className="w-4 h-4 text-cyan-400" />
            <span>DATA STORAGE SUBSYSTEM</span>
          </div>
          <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] space-y-1.5 text-slate-400">
            <div className="flex justify-between">
              <span>Active Engine:</span>
              <span className="text-emerald-400 font-bold">SQLite / PostgreSQL Dual Dialect</span>
            </div>
            <div className="flex justify-between">
              <span>Connection Pool:</span>
              <span className="text-white">Active (SessionLocal)</span>
            </div>
            <div className="flex justify-between">
              <span>Database URL:</span>
              <span className="text-cyan-300">sqlite:///./cybershield.db</span>
            </div>
          </div>
        </div>

        {/* Active Session Badge */}
        <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-xl space-y-3">
          <div className="flex items-center space-x-2 text-slate-200 font-bold border-b border-[#162544] pb-3">
            <Lock className="w-4 h-4 text-cyan-400" />
            <span>AUTHENTICATED OFFICER PROFILE</span>
          </div>
          <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] space-y-1.5 text-slate-400">
            <div className="flex justify-between">
              <span>Officer Name:</span>
              <span className="text-white font-bold">{user?.full_name || 'Inspector R. Verma'}</span>
            </div>
            <div className="flex justify-between">
              <span>Designated Role:</span>
              <span className="text-cyan-300 font-bold">{user?.role || 'DISTRICT_LEA'}</span>
            </div>
            <div className="flex justify-between">
              <span>Badge Token:</span>
              <span className="text-emerald-400 font-bold">{user?.badge_number || 'IND-CY-441'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
