import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  Activity,
  MapPin,
  FileText,
  Network,
  BellRing,
  BarChart3,
  Cpu,
  History,
  Settings,
  Flame,
  Radio,
  LogOut,
  ChevronRight
} from 'lucide-react';
import { useAuth } from '../store/authContext';

const NAV_ITEMS = [
  { name: 'Command Center', path: '/dashboard', icon: Activity },
  { name: 'Live Risk Map', path: '/risk-map', icon: MapPin },
  { name: 'Complaints', path: '/complaints', icon: FileText },
  { name: 'Case Intelligence', path: '/cases/CMP-1042', icon: ShieldAlert, badge: 'CMP-1042' },
  { name: 'Transaction Network', path: '/network/CMP-1042', icon: Network },
  { name: 'Alerts Center', path: '/alerts', icon: BellRing },
  { name: 'Analytics', path: '/analytics', icon: BarChart3 },
  { name: 'Model Performance', path: '/model-performance', icon: Cpu },
  { name: 'System Audit', path: '/audit', icon: History },
  { name: 'Settings', path: '/settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="w-72 bg-[#090e1d] border-r border-[#162544] flex flex-col h-screen select-none sticky top-0 shrink-0 z-30">
      {/* Brand Header */}
      <div className="p-5 border-b border-[#162544]">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shadow-[0_0_15px_rgba(0,216,255,0.25)]">
            <ShieldAlert className="w-6 h-6 animate-pulse-subtle" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <h1 className="text-lg font-bold tracking-wider text-slate-100 uppercase font-['JetBrains_Mono',monospace]">
                Cyber<span className="text-cyan-400">Shield</span>
              </h1>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/30">
                AI
              </span>
            </div>
            <p className="text-[11px] text-slate-400 tracking-wide font-medium">
              Predict. Alert. Intervene. Protect.
            </p>
          </div>
        </div>

        {/* Live Threat Bar */}
        <div className="mt-4 px-3 py-2 rounded-md bg-[#060a15] border border-cyan-900/40 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[11px] font-mono text-emerald-400 tracking-wider">PREDICTIVE RADAR</span>
          </div>
          <span className="text-[10px] text-slate-400 font-mono">I4C SECURE</span>
        </div>
      </div>

      {/* Navigation List */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1.5">
        <div className="px-3 pb-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider font-mono">
          Operations & Intelligence
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `group flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/40 shadow-[0_0_12px_rgba(0,216,255,0.15)] font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-[#101a33] border border-transparent'
                }`
              }
            >
              <div className="flex items-center space-x-3">
                <Icon className="w-4 h-4 transition-transform group-hover:scale-110" />
                <span>{item.name}</span>
              </div>
              {item.badge && (
                <span className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-red-500/20 text-red-400 border border-red-500/30 font-bold">
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </div>

      {/* Bottom Officer Profile */}
      <div className="p-3 border-t border-[#162544] bg-[#070b17]">
        <div className="p-2.5 rounded-lg bg-[#0c1428] border border-[#1b2b4d] flex items-center justify-between">
          <div className="flex items-center space-x-2.5 min-w-0">
            <div className="w-8 h-8 rounded-full bg-cyan-950 border border-cyan-500/30 flex items-center justify-center text-cyan-300 font-bold text-xs font-mono">
              {user ? user.full_name.substring(0, 2).toUpperCase() : 'LE'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-slate-200 truncate">
                {user ? user.full_name : 'Authorized Officer'}
              </p>
              <div className="flex items-center space-x-1.5">
                <span className="text-[10px] font-mono text-cyan-400 font-medium">
                  {user ? user.role : 'LEA'}
                </span>
                <span className="text-[9px] text-slate-400 font-mono">
                  {user ? user.badge_number : 'OFFICER'}
                </span>
              </div>
            </div>
          </div>

          <button
            onClick={handleLogout}
            title="Secure Officer Logout"
            className="p-1.5 rounded hover:bg-red-500/10 text-slate-400 hover:text-red-400 transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
