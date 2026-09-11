import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  MapPin,
  FileText,
  ShieldAlert,
  Network,
  BellRing,
  BarChart3,
  Cpu,
  History,
  Settings as SettingsIcon,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../store/authContext';

interface NavItem {
  name: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { name: 'Complaints', path: '/complaints', icon: FileText },
  { name: 'Case Intelligence', path: '/cases/CMP-NEW-000002', icon: ShieldAlert },
  { name: 'Live Risk Map', path: '/risk-map', icon: MapPin },
  { name: 'Alert Center', path: '/alerts', icon: BellRing },
  { name: 'Transaction Network', path: '/network/CMP-NEW-000002', icon: Network },
  { name: 'Analytics', path: '/analytics', icon: BarChart3 },
  { name: 'Model Performance', path: '/model-performance', icon: Cpu },
  { name: 'System Audit', path: '/audit', icon: History },
  { name: 'Settings', path: '/settings', icon: SettingsIcon },
];

export const Sidebar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userInitials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'LE';

  return (
    <aside className="w-64 bg-[#173A63] border-r border-[#1E4A7D] flex flex-col h-screen select-none sticky top-0 shrink-0 z-30">
      {/* Platform Identity Block */}
      <div className="px-5 py-5 border-b border-[#1E4A7D]">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-md bg-white/10 border border-white/20 flex items-center justify-center text-white shrink-0">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center space-x-1.5">
              <h1 className="text-base font-bold tracking-tight text-white font-sans">
                CyberShield <span className="text-blue-300">AI</span>
              </h1>
            </div>
            <p className="text-[11px] text-blue-200/80 truncate">
              Cybercrime Predictive Intelligence
            </p>
          </div>
        </div>

        {/* Operational Scope Banner */}
        <div className="mt-3.5 px-2.5 py-1.5 rounded bg-[#122E4F] border border-[#1E4A7D] flex items-center justify-between">
          <span className="text-[11px] font-medium text-blue-100">
            I4C Pilot • Delhi NCT
          </span>
          <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Operational
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1" aria-label="Primary Navigation">
        <div className="px-3 pb-2 text-[11px] font-semibold text-blue-200/70 uppercase tracking-wider">
          Intelligence & Operations
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `group flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-[#1E4A7D] text-white font-semibold border-l-2 border-blue-400 pl-2.5 shadow-sm'
                    : 'text-blue-100/80 hover:text-white hover:bg-[#1E4A7D]/50'
                }`
              }
            >
              <div className="flex items-center space-x-2.5 min-w-0">
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{item.name}</span>
              </div>
              {item.badge && (
                <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-red-600 text-white font-bold">
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Authenticated Officer Identity Footer */}
      <div className="p-3 border-t border-[#1E4A7D] bg-[#143358]">
        <div className="p-2.5 rounded-md bg-[#122E4F] border border-[#1E4A7D] flex items-center justify-between">
          <div className="flex items-center space-x-2.5 min-w-0">
            <div className="w-8 h-8 rounded-full bg-[#1E4A7D] border border-blue-300/30 flex items-center justify-center text-white font-semibold text-xs shrink-0">
              {userInitials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-white truncate">
                {user ? user.full_name : 'Authenticated Officer'}
              </p>
              <p className="text-[11px] text-blue-200/80 truncate">
                {user ? `${user.role}` : 'Law Enforcement'}
              </p>
            </div>
          </div>

          <button
            onClick={handleLogout}
            title="Sign Out"
            aria-label="Sign Out"
            className="p-1.5 rounded text-blue-200 hover:text-white hover:bg-red-500/30 transition-colors ml-1"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
