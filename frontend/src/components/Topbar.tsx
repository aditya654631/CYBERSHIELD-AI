import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Search,
  Bell,
  LogOut,
  ChevronRight,
  Shield,
  Menu,
} from 'lucide-react';
import { useAuth } from '../store/authContext';
import { api } from '../services/api';

const ROUTE_LABELS: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/complaints': 'Complaints Management',
  '/risk-map': 'Live Risk Map',
  '/alerts': 'Alert Center',
  '/analytics': 'Analytics & Interception Metrics',
  '/model-performance': 'Model Performance',
  '/audit': 'System Audit & Compliance',
  '/settings': 'Settings & Preferences',
};

interface TopbarProps {
  onToggleMobileSidebar?: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({ onToggleMobileSidebar }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
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
      } catch {
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

  // Determine current context label
  let currentTitle = ROUTE_LABELS[location.pathname] || 'Operational Workspace';
  if (location.pathname.startsWith('/cases/')) {
    const caseId = location.pathname.split('/cases/')[1];
    currentTitle = `Case Intelligence • ${caseId}`;
  } else if (location.pathname.startsWith('/network/')) {
    const caseId = location.pathname.split('/network/')[1];
    currentTitle = `Transaction Network • ${caseId}`;
  }

  const userInitials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'LE';

  return (
    <header className="h-14 bg-white border-b border-[#DCE5F0] px-3 sm:px-6 flex items-center justify-between sticky top-0 z-20 shadow-xs">
      {/* Left: Hamburger (Mobile) + Breadcrumb / Page Context */}
      <div className="flex items-center space-x-2 sm:space-x-3 min-w-0">
        {onToggleMobileSidebar && (
          <button
            onClick={onToggleMobileSidebar}
            className="lg:hidden p-1.5 rounded-md text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors shrink-0"
            aria-label="Open sidebar menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}

        <div className="flex items-center space-x-1 sm:space-x-1.5 text-xs text-slate-500 font-medium min-w-0">
          <span className="hidden xs:inline">CyberShield</span>
          <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0 hidden xs:inline" />
          <span className="text-[#031926] font-semibold truncate max-w-[130px] sm:max-w-xs md:max-w-none">
            {currentTitle}
          </span>
        </div>

        <span className="hidden lg:inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-[#F0F6F6] text-[#468189] border border-[#9DBEBB]/50 shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          Operational Pilot
        </span>
      </div>

      {/* Right: Search, Alerts, Officer Profile */}
      <div className="flex items-center space-x-2 sm:space-x-4 shrink-0">
        {/* Quick Search */}
        <form onSubmit={handleSearch} className="relative hidden md:block w-72">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search complaint, account, UTR..."
            aria-label="Search cases and accounts"
            className="w-full pl-8 pr-3 py-1.5 bg-[#F6F8FC] border border-[#DCE5F0] rounded-md text-xs text-[#031926] placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#468189] focus:ring-1 focus:ring-[#468189] transition-colors"
          />
        </form>

        {/* Active Alerts Bell */}
        <button
          onClick={() => navigate('/alerts')}
          className="relative p-1.5 rounded-md text-slate-600 hover:text-[#468189] hover:bg-[#F0F6F6] transition-colors"
          title="Active Alerts"
          aria-label={`Active Alerts: ${newAlertCount} new`}
        >
          <Bell className="w-4 h-4" />
          {newAlertCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-600 text-[10px] font-bold text-white rounded-full flex items-center justify-center font-sans shadow-sm">
              {newAlertCount}
            </span>
          )}
        </button>

        {/* Real Authenticated Officer Profile */}
        <div className="flex items-center space-x-3 pl-3 border-l border-[#DCE5F0]">
          <div className="w-7 h-7 rounded-full bg-[#031926] text-white flex items-center justify-center text-xs font-semibold shrink-0">
            {userInitials}
          </div>

          <div className="hidden sm:block text-left leading-tight min-w-0">
            <div className="text-xs font-semibold text-[#031926] truncate">
              {user?.full_name || 'Authenticated Officer'}
            </div>
            <div className="text-[11px] text-slate-500 truncate">
              {user?.role || 'Law Enforcement'}
              {user?.organization_name ? ` • ${user.organization_name}` : ''}
            </div>
          </div>

          <button
            onClick={handleLogout}
            title="Sign Out"
            aria-label="Sign Out"
            className="p-1.5 rounded-md text-slate-400 hover:text-red-600 hover:bg-slate-100 transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
