import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Shield,
  Lock,
  Mail,
  ArrowRight,
  AlertCircle,
  KeyRound,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ArrowLeft,
  Sparkles,
} from 'lucide-react';
import { useAuth, DEMO_CREDENTIALS } from '../store/authContext';
import { UserRole } from '../types';

export const Login: React.FC = () => {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showDemoAccounts, setShowDemoAccounts] = useState(false);

  // Check for session expiration notice and sanitize legacy stored demo identities on mount
  useEffect(() => {
    const notice = sessionStorage.getItem('cybershield_session_expired');
    if (notice) {
      setSessionExpiredNotice(notice);
      sessionStorage.removeItem('cybershield_session_expired');
    }

    // Check if user came from a pilot button requesting prefilled credentials
    if ((location.state as any)?.prefillPilot) {
      const cred = DEMO_CREDENTIALS.I4C_ADMIN;
      setEmail(cred.email);
      setPassword(cred.pass);
    }

    // Clean up any stale legacy MP/Indore keys if stored in browser
    const legacyKeys = [
      'lastLoginEmail',
      'selectedDemoRole',
      'lastUser',
      'lastAccount',
      'rememberedEmail',
      'cybershield_last_email',
      'email'
    ];
    legacyKeys.forEach((k) => {
      const val = localStorage.getItem(k) || sessionStorage.getItem(k);
      if (val && (val.includes('indore') || val.includes('mp.police') || val.includes('mp_police'))) {
        localStorage.removeItem(k);
        sessionStorage.removeItem(k);
      }
    });
  }, [location.state]);

  const sanitizeAndValidateEmail = (inputVal: string): boolean => {
    const val = inputVal.trim().toLowerCase();
    if (val === 'district.lea@indore.police.gov.in') {
      setEmail('');
      setPassword('');
      setError('This legacy pilot identity has been retired. Please select the South Delhi demo account.');
      return false;
    }
    if (val === 'state.lea@mp.police.gov.in') {
      setEmail('');
      setPassword('');
      setError('This legacy pilot identity has been retired. Please select the Delhi State demo account.');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSessionExpiredNotice(null);

    if (!sanitizeAndValidateEmail(email)) {
      return;
    }

    setLoading(true);

    try {
      await login(email.trim(), password);
      navigate('/dashboard');
    } catch (err: any) {
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

  const handleUsePilotCredentials = () => {
    const cred = DEMO_CREDENTIALS.I4C_ADMIN;
    setEmail(cred.email);
    setPassword(cred.pass);
    setError(null);
    setSessionExpiredNotice(null);
  };

  return (
    <div className="min-h-screen bg-[#031926] flex flex-col items-center justify-center p-4 sm:p-6 lg:p-8">
      {/* Top Navigation Bar */}
      <div className="w-full max-w-4xl mb-4 flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-300 hover:text-white transition-colors bg-[#072130] hover:bg-[#0E2A3A] px-3 py-1.5 rounded-md border border-[#0E2A3A]"
        >
          <ArrowLeft className="w-3.5 h-3.5 text-[#77ACA2]" />
          <span>← Back to Home</span>
        </button>

        <div className="text-[11px] text-[#9DBEBB] font-mono hidden sm:block">
          CyberShield AI • Delhi Pilot v1.0.0
        </div>
      </div>

      <div className="w-full max-w-4xl bg-white rounded-xl shadow-2xl border border-[#DCE5F0] overflow-hidden grid grid-cols-1 md:grid-cols-12">
        {/* LEFT / INSTITUTIONAL BRAND PANEL */}
        <div className="md:col-span-5 bg-[#031926] text-white p-5 sm:p-8 flex flex-col justify-between relative border-r border-[#0E2A3A]">
          <div>
            {/* Government Context */}
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#072130] text-[#9DBEBB] text-[11px] font-medium border border-[#0E2A3A] mb-6">
              <Shield className="w-3.5 h-3.5 text-[#77ACA2]" />
              <span>National Law Enforcement Portal</span>
            </div>

            {/* Brand Title */}
            <div className="space-y-2">
              <h1 className="text-2xl font-bold tracking-tight">
                CyberShield <span className="text-[#77ACA2]">AI</span>
              </h1>
              <p className="text-xs text-slate-300 font-medium">
                Cybercrime Predictive Intelligence & Intervention Platform
              </p>
            </div>

            <p className="text-xs text-slate-300/80 mt-4 leading-relaxed">
              Decision-support platform for proactive cybercrime intervention, multi-hop financial tracking, and cash-out interception.
            </p>

            {/* Operational Focus List */}
            <div className="mt-8 space-y-3 text-xs text-slate-200">
              <div className="flex items-start space-x-2.5">
                <CheckCircle2 className="w-4 h-4 text-[#77ACA2] shrink-0 mt-0.5" />
                <span>Calibrated cash-out hotspot prediction</span>
              </div>
              <div className="flex items-start space-x-2.5">
                <CheckCircle2 className="w-4 h-4 text-[#77ACA2] shrink-0 mt-0.5" />
                <span>Multi-hop mule network path tracing</span>
              </div>
              <div className="flex items-start space-x-2.5">
                <CheckCircle2 className="w-4 h-4 text-[#77ACA2] shrink-0 mt-0.5" />
                <span>Tamper-Evident Prediction Audit</span>
              </div>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-[#0E2A3A] text-[11px] text-[#9DBEBB]/80">
            Delhi Pilot Prototype • I4C / SIH 2026
          </div>
        </div>

        {/* RIGHT / LOGIN FORM PANEL */}
        <div className="md:col-span-7 p-4 sm:p-8 md:p-10 flex flex-col justify-between bg-white">
          <div>
            <div className="mb-5">
              <h2 className="text-lg font-bold text-[#031926]">Secure Investigator Access</h2>
              <p className="text-xs text-slate-500 mt-1">
                Enter your official law enforcement or banking credentials to access the intelligence console.
              </p>
            </div>

            {/* Dedicated Controlled Pilot Quick Card */}
            <div className="mb-5 p-3.5 bg-[#F0F6F6] rounded-lg border border-[#9DBEBB]/60">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[#468189]" />
                  <span className="text-xs font-bold text-[#031926]">I4C National Command Pilot</span>
                </div>
                <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-[#468189] text-white uppercase tracking-wider">
                  CONTROLLED PILOT • SYNTHETIC DATA
                </span>
              </div>
              <div className="text-[11px] text-slate-600 mb-2.5 flex items-center justify-between font-mono">
                <span>admin@cybershield.gov.in</span>
                <span className="text-slate-400">••••••••••••</span>
              </div>
              <button
                type="button"
                onClick={handleUsePilotCredentials}
                className="w-full py-1.5 px-3 bg-white hover:bg-[#F0F6F6] border border-[#9DBEBB] text-[#468189] font-semibold text-xs rounded transition-colors text-center shadow-2xs"
              >
                Use Pilot Credentials
              </button>
            </div>

            {/* Active Session Notice (Secondary) */}
            {isAuthenticated && (
              <div className="mb-4 p-3 rounded-md bg-[#F0F6F6] border border-[#9DBEBB] text-[#031926] text-xs flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-[#468189] shrink-0" />
                  <span>An authenticated session is already active.</span>
                </div>
                <button
                  type="button"
                  onClick={() => navigate('/dashboard')}
                  className="px-2.5 py-1 bg-[#468189] hover:bg-[#386970] text-white rounded text-[11px] font-semibold transition-colors flex items-center space-x-1 shadow-2xs"
                >
                  <span>Continue to Dashboard</span>
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            )}

            {/* Session Expired Notice */}
            {sessionExpiredNotice && (
              <div className="mb-4 p-3 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>{sessionExpiredNotice}</span>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="mb-4 p-3 rounded-md bg-red-50 border border-red-200 text-red-700 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5" htmlFor="login-email">
                  Official Email / Username
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="login-email"
                    name="username"
                    type="email"
                    autoComplete="username"
                    required
                    value={email}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (!sanitizeAndValidateEmail(val)) {
                        return;
                      }
                      setEmail(val);
                      if (error && error.includes('legacy pilot identity')) {
                        setError(null);
                      }
                    }}
                    placeholder="officer@police.gov.in"
                    className="w-full pl-9 pr-3 py-2 bg-white border border-[#DCE5F0] rounded-md text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#468189] focus:border-[#468189] transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5" htmlFor="login-password">
                  Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="login-password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full pl-9 pr-3 py-2 bg-white border border-[#DCE5F0] rounded-md text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#468189] focus:border-[#468189] transition-colors"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-[#468189] hover:bg-[#386970] text-white font-medium text-sm rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-[#468189] focus:ring-offset-2 flex items-center justify-center space-x-2 disabled:opacity-60 shadow-sm mt-2"
              >
                {loading ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <span>Sign In to Console</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            {/* Other Prototype Roles Quick Select */}
            <div className="mt-5 pt-4 border-t border-[#DCE5F0]">
              <button
                type="button"
                onClick={() => setShowDemoAccounts(!showDemoAccounts)}
                className="w-full flex items-center justify-between text-xs text-slate-600 hover:text-[#031926] font-medium py-1"
              >
                <span className="flex items-center space-x-1.5">
                  <KeyRound className="w-3.5 h-3.5 text-[#468189]" />
                  <span>Other Prototype Role Accounts</span>
                </span>
                {showDemoAccounts ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>

              {showDemoAccounts && (
                <div className="mt-2.5 grid grid-cols-1 sm:grid-cols-2 gap-1.5 p-2 bg-[#F6F8FC] rounded-md border border-[#DCE5F0]">
                  {(Object.keys(DEMO_CREDENTIALS) as UserRole[]).map((r) => {
                    const cred = DEMO_CREDENTIALS[r];
                    return (
                      <button
                        key={r}
                        type="button"
                        onClick={() => handleSelectDemoAccount(r)}
                        className="text-left px-2.5 py-1.5 rounded bg-white hover:bg-[#F0F6F6] hover:border-[#9DBEBB] border border-[#DCE5F0] text-xs transition-colors truncate"
                      >
                        <div className="font-medium text-slate-800 truncate">{cred.title}</div>
                        <div className="text-[10px] text-slate-500 truncate">{cred.email}</div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Compliance & Security Notice */}
          <div className="mt-6 pt-4 border-t border-slate-100">
            <p className="text-[11px] text-slate-400 leading-tight">
              Authorized personnel only. Access and operational actions are logged to a tamper-evident audit ledger in compliance with MHA/I4C standards.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
