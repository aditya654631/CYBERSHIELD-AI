import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  Lock,
  Mail,
  ArrowRight,
  ShieldCheck,
  Building2,
  AlertCircle,
  KeyRound,
  CheckCircle2,
  HelpCircle,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { useAuth, DEMO_CREDENTIALS } from '../store/authContext';
import { UserRole } from '../types';

export const Login: React.FC = () => {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [authSuccessStep, setAuthSuccessStep] = useState<string | null>(null);
  const [showDemoAccounts, setShowDemoAccounts] = useState(false);

  // Check for session expiration notice on mount
  useEffect(() => {
    const notice = sessionStorage.getItem('cybershield_session_expired');
    if (notice) {
      setSessionExpiredNotice(notice);
      sessionStorage.removeItem('cybershield_session_expired');
    }
  }, []);

  // If already authenticated, redirect
  useEffect(() => {
    if (isAuthenticated && !authSuccessStep) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate, authSuccessStep]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSessionExpiredNotice(null);
    setLoading(true);

    try {
      await login(email.trim(), password);
      // Brief restrained transition as required by Phase 27
      setAuthSuccessStep('Identity verified. Loading secure workspace...');
      setTimeout(() => {
        navigate('/dashboard');
      }, 700);
    } catch (err: any) {
      // Professional generic error as required by Phase 26 (do not reveal account existence)
      setError(
        err.response?.data?.detail === 'Invalid officer credentials or password'
          ? 'Authentication failed. Check your Officer ID and password.'
          : err.response?.data?.detail || 'Authentication service error. Ensure the CyberShield backend is operational.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDemoAccount = (roleKey: UserRole) => {
    const cred = DEMO_CREDENTIALS[roleKey];
    setEmail(cred.email);
    setPassword(cred.pass);
    setError(null);
    setSessionExpiredNotice(null);
  };

  return (
    <div className="min-h-screen bg-[#070b16] flex flex-col justify-center items-center px-4 py-8 relative overflow-x-hidden">
      {/* Subtle geospatial grid & lighting background */}
      <div className="absolute inset-0 bg-[radial-gradient(#14223d_1px,transparent_1px)] [background-size:28px_28px] opacity-40 pointer-events-none"></div>
      <div className="absolute top-1/4 left-1/3 -translate-x-1/2 w-[600px] h-[350px] bg-cyan-600/5 blur-[140px] rounded-full pointer-events-none"></div>
      <div className="absolute bottom-1/4 right-1/3 w-[500px] h-[300px] bg-blue-600/5 blur-[120px] rounded-full pointer-events-none"></div>

      {/* Main Container */}
      <div className="w-full max-w-5xl z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
        {/* LEFT / INSTITUTIONAL PORTAL COLUMN */}
        <div className="lg:col-span-6 bg-[#0a1122]/90 border border-[#162544] rounded-2xl p-8 shadow-2xl backdrop-blur-md flex flex-col justify-between">
          <div>
            {/* Header badges */}
            <div className="flex flex-wrap items-center gap-2 mb-6">
              <span className="px-2.5 py-1 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-mono text-[10px] font-bold tracking-wider">
                SECURE LAW ENFORCEMENT ACCESS
              </span>
              <span className="px-2 py-1 rounded bg-[#101c36] border border-[#1b2f57] text-slate-400 font-mono text-[10px]">
                Authorized Personnel Only
              </span>
            </div>

            {/* Brand Title */}
            <div className="space-y-2 mb-6">
              <div className="flex items-center space-x-3">
                <div className="w-11 h-11 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-[0_0_15px_rgba(0,216,255,0.2)] shrink-0">
                  <ShieldAlert className="w-6 h-6" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold tracking-wide text-white font-['JetBrains_Mono',monospace]">
                    Cyber<span className="text-cyan-400">Shield</span> AI
                  </h1>
                  <span className="text-[10px] text-slate-400 font-mono">
                    SIH Prototype — Cybercrime Intelligence Platform
                  </span>
                </div>
              </div>
              <h2 className="text-sm font-semibold text-slate-200 mt-2">
                Cybercrime Predictive Intelligence & Intervention Platform
              </h2>
              <p className="text-xs text-slate-400 italic font-mono">
                "Predict. Alert. Intervene. Protect."
              </p>
            </div>

            {/* Mission / Architecture Brief */}
            <div className="p-4 rounded-xl bg-[#070d1a] border border-[#162544] space-y-2.5 text-xs text-slate-300 font-mono">
              <div className="flex items-start space-x-2">
                <span className="text-cyan-400 font-bold">•</span>
                <span>Automated multi-hop financial transaction layer extraction across nodal banks.</span>
              </div>
              <div className="flex items-start space-x-2">
                <span className="text-cyan-400 font-bold">•</span>
                <span>Trained XGBoost v2 location ranker & time regressor with Platt probability calibration.</span>
              </div>
              <div className="flex items-start space-x-2">
                <span className="text-cyan-400 font-bold">•</span>
                <span>Real-time rapid response dispatch to physical ATM and cashier extraction corridors.</span>
              </div>
            </div>
          </div>

          {/* Institutional footer */}
          <div className="mt-8 pt-4 border-t border-[#162544] flex flex-wrap items-center justify-between text-[11px] text-slate-400 font-mono gap-2">
            <span>Protected access • Role-based authorization • Activity audited</span>
            <span>SIH26184</span>
          </div>
        </div>

        {/* RIGHT / OFFICER AUTHENTICATION PANEL */}
        <div className="lg:col-span-6 bg-[#0a1122]/90 border border-[#162544] rounded-2xl p-8 shadow-2xl backdrop-blur-md flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#162544] mb-6">
              <div>
                <h3 className="text-base font-bold text-white font-mono">Officer Sign In</h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">
                  Authenticate using authorized departmental credentials
                </p>
              </div>
              <div className="w-8 h-8 rounded-lg bg-[#0c162c] border border-[#1a2f57] flex items-center justify-center text-cyan-400">
                <Lock className="w-4 h-4" />
              </div>
            </div>

            {/* Session Expired Notice */}
            {sessionExpiredNotice && (
              <div className="mb-4 p-3 rounded-xl bg-amber-950/40 border border-amber-500/40 text-amber-300 text-xs font-mono flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
                <span>{sessionExpiredNotice}</span>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="mb-4 p-3 rounded-xl bg-red-950/40 border border-red-500/40 text-red-300 text-xs font-mono flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                <span>{error}</span>
              </div>
            )}

            {/* Success Feedback Step */}
            {authSuccessStep && (
              <div className="mb-4 p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-xs font-mono flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400 animate-pulse" />
                <span>{authSuccessStep}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5 font-mono">
                  Officer ID / Official Email
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="district.lea@indore.police.gov.in"
                    required
                    disabled={loading || !!authSuccessStep}
                    className="w-full pl-10 pr-4 py-2.5 bg-[#070d1a] border border-[#1a2b4d] rounded-xl text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:border-cyan-400 font-mono transition-all disabled:opacity-50"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5 font-mono">
                  Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    required
                    disabled={loading || !!authSuccessStep}
                    className="w-full pl-10 pr-4 py-2.5 bg-[#070d1a] border border-[#1a2b4d] rounded-xl text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:border-cyan-400 font-mono transition-all disabled:opacity-50"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                <label className="flex items-center space-x-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="rounded border-[#1a2b4d] bg-[#070d1a] text-cyan-500 focus:ring-0"
                  />
                  <span>Remember this device</span>
                </label>
                <span className="text-[11px] text-slate-400">Encrypted TLS 1.3</span>
              </div>

              <button
                type="submit"
                disabled={loading || !!authSuccessStep}
                className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold text-xs font-mono tracking-wider shadow-[0_0_20px_rgba(0,216,255,0.25)] flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
              >
                {loading ? (
                  <span className="flex items-center space-x-2">
                    <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                    <span>Authenticating...</span>
                  </span>
                ) : authSuccessStep ? (
                  <span className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Identity Verified</span>
                  </span>
                ) : (
                  <>
                    <span>Secure Sign In</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Prototype Demo Accounts Accordion (Phase 31) */}
          <div className="mt-6 pt-4 border-t border-[#162544]">
            <button
              type="button"
              onClick={() => setShowDemoAccounts(!showDemoAccounts)}
              className="w-full flex items-center justify-between text-xs font-mono text-cyan-400 hover:text-cyan-300 py-1"
            >
              <div className="flex items-center space-x-1.5">
                <KeyRound className="w-3.5 h-3.5" />
                <span className="font-semibold">Prototype Demo Accounts (SIH Evaluation)</span>
              </div>
              {showDemoAccounts ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>

            {showDemoAccounts && (
              <div className="mt-3 space-y-2 max-h-48 overflow-y-auto pr-1">
                {(Object.keys(DEMO_CREDENTIALS) as UserRole[]).map((roleKey) => {
                  const cred = DEMO_CREDENTIALS[roleKey];
                  return (
                    <div
                      key={roleKey}
                      onClick={() => handleSelectDemoAccount(roleKey)}
                      className="p-2 rounded-lg bg-[#070d1a] hover:bg-[#0f1b36] border border-[#1a2b4d] cursor-pointer transition-all flex items-center justify-between text-xs font-mono"
                    >
                      <div className="min-w-0 pr-2">
                        <div className="text-slate-200 font-semibold truncate">{cred.title}</div>
                        <div className="text-[10px] text-slate-400 truncate">{cred.email}</div>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-[#13203c] text-cyan-300 text-[10px] shrink-0">
                        Fill Credentials
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
