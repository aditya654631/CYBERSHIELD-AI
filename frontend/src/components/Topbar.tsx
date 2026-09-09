import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Bell,
  Radio,
  ShieldCheck,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../store/authContext';
import { api } from '../services/api';

export const Topbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [newAlertCount, setNewAlertCount] = useState<number>(0);

  useEffect(() => {
    let mounted = true;
    const fetchAlertCount = async () => {
      try {
        const alerts = await api.getAlerts({ status: 'NEW' });
        if (mounted) {
          setNewAlertCount(alerts.length);
        }
      } catch (err) {
        // silent catch
      }
    };
    fetchAlertCount();
    const interval = setInterval(fetchAlertCount, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/complaints?search=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="h-16 bg-[#070c1a]/95 backdrop-blur-md border-b border-[#162544] px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Global Search Bar */}
      <form onSubmit={handleSearch} className="relative w-96">
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search CMP ID, location, mule account, IFSC..."
          className="w-full pl-10 pr-4 py-2 bg-[#0c1428] border border-[#1b2b4d] rounded-lg text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/30 transition-all font-mono"
        />
        <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center space-x-1">
          <kbd className="px-1.5 py-0.5 text-[9px] font-mono text-slate-400 bg-[#121c38] border border-[#233357] rounded">
            Enter
          </kbd>
        </div>
      </form>

      {/* System Status Indicators & Actions */}
      <div className="flex items-center space-x-4">
        {/* System Online Badge */}
        <div className="hidden sm:flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-950/40 border border-emerald-500/30">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-xs font-mono text-emerald-400 font-medium">SYSTEM ONLINE</span>
        </div>

        {/* Live Intelligence Indicator */}
        <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-full bg-cyan-950/40 border border-cyan-500/30">
          <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span className="text-xs font-mono text-cyan-300 font-medium tracking-wide">
            LIVE TELEMETRY
          </span>
        </div>

        {/* Notifications */}
        <button
          onClick={() => navigate('/alerts')}
          className="relative p-2 rounded-lg bg-[#0c1428] border border-[#1b2b4d] text-slate-300 hover:text-cyan-400 hover:border-cyan-500/40 transition-colors"
          title="Active Alerts"
        >
          <Bell className="w-4 h-4" />
          {newAlertCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-[10px] font-bold text-white rounded-full flex items-center justify-center font-mono">
              {newAlertCount}
            </span>
          )}
        </button>

        {/* Officer Profile Pill */}
        <div className="flex items-center space-x-2.5 pl-2 border-l border-[#162544]">
          <div className="text-right">
            <div className="text-xs font-bold text-slate-200">
              {user?.full_name || 'Inspector Rajesh Verma'}
            </div>
            <div className="text-[10px] font-mono text-cyan-400">
              {user?.role || 'DISTRICT_LEA'} • {user?.organization_name?.split(' ')[0] || 'Indore LEA'}
            </div>
          </div>
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/40 flex items-center justify-center text-cyan-300 shadow-[0_0_10px_rgba(0,216,255,0.2)]">
            <ShieldCheck className="w-5 h-5" />
          </div>

          <button
            onClick={handleLogout}
            title="Sign Out"
            className="p-1.5 rounded-lg bg-[#0c1428] border border-[#1b2b4d] text-slate-400 hover:text-red-400 hover:border-red-500/30 transition-all ml-1"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
