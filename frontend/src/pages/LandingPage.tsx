import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield,
  Lock,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  TrendingUp,
  MapPin,
  GitFork,
  Bell,
  FileCheck,
  Building2,
  Users,
  Landmark,
  KeyRound,
  Eye,
  Activity,
  Menu,
  X,
  Clock,
  Compass,
  Radio,
  Layers,
  Database,
  Workflow,
  Cpu,
  FileText,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';
import { useAuth, DEMO_CREDENTIALS } from '../store/authContext';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    setMobileMenuOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const subtleGridStyle = {
    backgroundImage:
      'linear-gradient(to right, rgba(3, 25, 38, 0.035) 1px, transparent 1px), linear-gradient(to bottom, rgba(3, 25, 38, 0.035) 1px, transparent 1px)',
    backgroundSize: '40px 40px',
  };

  return (
    <div className="min-h-screen bg-white text-[#031926] font-sans selection:bg-[#468189] selection:text-white">
      {/* ======================================================================
          1. STICKY NAVBAR (INSTITUTIONAL LIGHT THEME)
      ====================================================================== */}
      <header
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${
          scrolled
            ? 'bg-white/95 backdrop-blur-md shadow-sm border-b border-[#DCE5F0]'
            : 'bg-white border-b border-[#E7ECF3]'
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* LEFT: Project Identity */}
          <div
            className="flex items-center space-x-3 cursor-pointer"
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          >
            <div className="w-9 h-9 rounded-lg bg-[#031926] flex items-center justify-center shadow-xs border border-[#468189]/40">
              <Shield className="w-5 h-5 text-[#77ACA2]" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-lg font-bold tracking-tight text-[#031926]">
                  CyberShield <span className="text-[#468189]">AI</span>
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#F0F6F6] text-[#468189] border border-[#9DBEBB]/50">
                  DELHI PILOT
                </span>
              </div>
              <p className="text-[10px] text-slate-500 hidden sm:block">
                Predictive Cash-Out Intelligence & Intervention Support
              </p>
            </div>
          </div>

          {/* CENTER: Navigation Links (Desktop) */}
          <nav className="hidden md:flex items-center space-x-7 text-xs font-semibold text-slate-600">
            <button
              onClick={() => scrollToSection('pipeline')}
              className="hover:text-[#468189] transition-colors"
            >
              Pipeline
            </button>
            <button
              onClick={() => scrollToSection('capabilities')}
              className="hover:text-[#468189] transition-colors"
            >
              Capabilities
            </button>
            <button
              onClick={() => scrollToSection('why-cybershield')}
              className="hover:text-[#468189] transition-colors"
            >
              Why CyberShield
            </button>
            <button
              onClick={() => scrollToSection('transparency')}
              className="hover:text-[#468189] transition-colors"
            >
              Model Transparency
            </button>
            <button
              onClick={() => scrollToSection('alerting')}
              className="hover:text-[#468189] transition-colors"
            >
              Alerting
            </button>
            <button
              onClick={() => scrollToSection('security')}
              className="hover:text-[#468189] transition-colors"
            >
              Security
            </button>
          </nav>

          {/* RIGHT: Login CTA */}
          <div className="hidden sm:flex items-center space-x-3">
            <button
              onClick={() => navigate('/login')}
              className="px-4 py-2 rounded-lg bg-[#468189] hover:bg-[#386970] text-white text-xs font-semibold shadow-xs transition-colors flex items-center space-x-1.5"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Officer Login</span>
            </button>
          </div>

          {/* Mobile Hamburger Button */}
          <div className="flex sm:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-md text-slate-600 hover:text-[#031926] hover:bg-slate-100 focus:outline-none"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="sm:hidden bg-white border-b border-[#DCE5F0] px-4 pt-2 pb-4 space-y-2 animate-in slide-in-from-top-2">
            <button
              onClick={() => scrollToSection('pipeline')}
              className="block w-full text-left py-2 text-xs font-semibold text-slate-700 hover:text-[#468189]"
            >
              Operational Pipeline
            </button>
            <button
              onClick={() => scrollToSection('capabilities')}
              className="block w-full text-left py-2 text-xs font-semibold text-slate-700 hover:text-[#468189]"
            >
              Capabilities
            </button>
            <button
              onClick={() => scrollToSection('why-cybershield')}
              className="block w-full text-left py-2 text-xs font-semibold text-slate-700 hover:text-[#468189]"
            >
              Why CyberShield
            </button>
            <button
              onClick={() => scrollToSection('transparency')}
              className="block w-full text-left py-2 text-xs font-semibold text-slate-700 hover:text-[#468189]"
            >
              Model Transparency
            </button>
            <button
              onClick={() => scrollToSection('alerting')}
              className="block w-full text-left py-2 text-xs font-semibold text-slate-700 hover:text-[#468189]"
            >
              Alerting
            </button>
            <button
              onClick={() => scrollToSection('security')}
              className="block w-full text-left py-2 text-xs font-semibold text-slate-700 hover:text-[#468189]"
            >
              Security
            </button>
            <div className="pt-2 border-t border-slate-100">
              <button
                onClick={() => navigate('/login')}
                className="w-full py-2.5 px-4 rounded-lg bg-[#468189] text-white text-xs font-semibold text-center flex items-center justify-center space-x-1.5"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Officer Login</span>
              </button>
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="pt-16">
        {/* ======================================================================
            2. HERO SECTION (WHITE + LIGHT BEIGE #FAF8F2 + SUBTLE GRID)
        ====================================================================== */}
        <section
          className="relative overflow-hidden bg-[#FAF8F2] border-b border-[#E7ECF3] py-16 sm:py-20 lg:py-24"
          style={subtleGridStyle}
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
              {/* LEFT: Hero Copy & Actions */}
              <div className="lg:col-span-7 space-y-6">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white border border-[#DCE5F0] text-[#031926] text-xs font-semibold shadow-2xs">
                  <span className="w-2 h-2 rounded-full bg-[#468189] animate-pulse" />
                  <span className="text-slate-600 font-medium">National Cybercrime Pilot</span>
                  <span className="text-slate-300">•</span>
                  <span className="text-[#468189] font-semibold">SIH 2026 / AxiomSix</span>
                </div>

                <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-[#031926] tracking-tight leading-[1.18]">
                  Predict Cash-Out Risk.{' '}
                  <span className="text-[#468189]">Act Before the Money Disappears.</span>
                </h1>

                <p className="text-sm sm:text-base text-slate-700 leading-relaxed max-w-2xl font-normal">
                  AI-assisted cybercrime intelligence that reconstructs money trails, predicts likely cash-out zones
                  and operational windows, explains the prediction, and converts intelligence into coordinated
                  intervention decision support.
                </p>

                {/* Compact Trust / Status Chips */}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-white text-[#031926] border border-[#DCE5F0] shadow-2xs">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#468189] mr-1.5" />
                    V8 Debiased ML
                  </span>
                  <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-white text-[#031926] border border-[#DCE5F0] shadow-2xs">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#468189] mr-1.5" />
                    49 Location Features
                  </span>
                  <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-white text-[#031926] border border-[#DCE5F0] shadow-2xs">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#468189] mr-1.5" />
                    60 Delhi Zones
                  </span>
                  <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-white text-[#031926] border border-[#DCE5F0] shadow-2xs">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#468189] mr-1.5" />
                    LIME Explainability
                  </span>
                  <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-[#F4E9CD]/50 text-[#031926] border border-[#F4E9CD] shadow-2xs">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#77ACA2] mr-1.5" />
                    Controlled Delhi Pilot
                  </span>
                </div>

                {/* Primary CTA Buttons */}
                <div className="flex flex-wrap items-center gap-3 pt-3">
                  <button
                    onClick={() => navigate('/login')}
                    className="px-6 py-3 rounded-lg bg-[#468189] hover:bg-[#386970] text-white font-semibold text-sm shadow-sm transition-all flex items-center space-x-2"
                  >
                    <Lock className="w-4 h-4" />
                    <span>Officer Login</span>
                  </button>

                  <button
                    onClick={() => scrollToSection('pipeline')}
                    className="px-6 py-3 rounded-lg bg-white hover:bg-slate-50 border border-[#031926]/20 text-[#031926] font-semibold text-sm shadow-2xs transition-all flex items-center space-x-1.5"
                  >
                    <span>Explore Platform</span>
                    <ArrowRight className="w-4 h-4 text-slate-500" />
                  </button>
                </div>
              </div>

              {/* RIGHT: Operational Intelligence Preview Card */}
              <div className="lg:col-span-5">
                <div className="bg-white rounded-xl border border-[#DCE5F0] shadow-lg overflow-hidden">
                  {/* Institutional Header */}
                  <div className="bg-[#031926] text-white px-5 py-3.5 flex items-center justify-between border-b border-[#0E2A3A]">
                    <div className="flex items-center space-x-2">
                      <Shield className="w-4 h-4 text-[#77ACA2]" />
                      <span className="text-xs font-bold tracking-wide">CASE INTELLIGENCE DISPATCH</span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#072130] text-[#9DBEBB] border border-[#0E2A3A]">
                      T+18m Window
                    </span>
                  </div>

                  {/* Incident Snapshot */}
                  <div className="p-4 bg-[#F8FAFC] border-b border-[#E7ECF3] grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-[10px] font-medium text-slate-500 block uppercase">Reference</span>
                      <span className="font-mono font-bold text-[#031926]">CMP-2026-DEL-0842</span>
                    </div>
                    <div>
                      <span className="text-[10px] font-medium text-slate-500 block uppercase">Fraud Amount</span>
                      <span className="font-mono font-bold text-[#468189]">₹2,50,000 (3 Hops)</span>
                    </div>
                  </div>

                  {/* Top-3 Zones Mini Preview */}
                  <div className="p-4 space-y-2.5">
                    <div className="flex items-center justify-between text-[11px] font-bold text-slate-700">
                      <span>V8 PREDICTED CASHOUT ZONES</span>
                      <span className="text-slate-400 font-mono text-[10px]">Model: XGB-V8</span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-white border border-[#468189]/40 flex items-center justify-between shadow-2xs">
                      <div className="flex items-center space-x-2.5">
                        <div className="w-5 h-5 rounded-full bg-[#468189] text-white text-[10px] font-bold flex items-center justify-center">
                          1
                        </div>
                        <div>
                          <div className="text-xs font-bold text-[#031926]">Patparganj Industrial Area</div>
                          <div className="text-[10px] text-slate-500">Cluster #42 • 14 Candidate ATMs</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-mono font-bold text-[#468189]">0.88</span>
                        <span className="block text-[9px] font-bold text-red-600 uppercase">High Priority</span>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-white border border-slate-200 flex items-center justify-between">
                      <div className="flex items-center space-x-2.5">
                        <div className="w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-[10px] font-bold flex items-center justify-center">
                          2
                        </div>
                        <div>
                          <div className="text-xs font-bold text-[#031926]">Laxmi Nagar Commercial Hub</div>
                          <div className="text-[10px] text-slate-500">Cluster #19 • 9 Candidate ATMs</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-mono font-semibold text-slate-700">0.74</span>
                        <span className="block text-[9px] font-semibold text-amber-600 uppercase">Medium</span>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-white border border-slate-200 flex items-center justify-between">
                      <div className="flex items-center space-x-2.5">
                        <div className="w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-[10px] font-bold flex items-center justify-center">
                          3
                        </div>
                        <div>
                          <div className="text-xs font-bold text-[#031926]">Mayur Vihar Phase 1</div>
                          <div className="text-[10px] text-slate-500">Cluster #07 • 6 Candidate ATMs</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-mono font-semibold text-slate-700">0.62</span>
                        <span className="block text-[9px] font-semibold text-slate-500 uppercase">Monitor</span>
                      </div>
                    </div>
                  </div>

                  {/* Card Footer Provenance */}
                  <div className="p-3 bg-[#F8FAFC] border-t border-[#E7ECF3] flex items-center justify-between text-[10px] text-slate-500 font-mono">
                    <span>LIME: High ATM Density (+0.32)</span>
                    <span className="text-[#468189] font-medium">Tamper-Evident Audit #A81F</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            4. CURRENT OPERATIONAL PIPELINE (FROM COMPLAINT TO INTERVENTION)
        ====================================================================== */}
        <section id="pipeline" className="py-16 sm:py-20 bg-white border-b border-[#E7ECF3]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <span className="text-xs font-bold text-[#468189] uppercase tracking-wider block mb-1">
                Operational Architecture
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-[#031926]">
                FROM COMPLAINT TO INTERVENTION
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mt-2">
                A streamlined, eight-stage pipeline transforming incoming fraud signals into synchronized field action.
              </p>
            </div>

            {/* 8-Step Horizontal/Grid Flow */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Step 01 */}
              <div className="p-5 rounded-xl bg-[#FAF8F2] border border-[#E7ECF3] hover:border-[#468189]/50 transition-colors flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-mono font-bold text-[#468189] bg-white px-2 py-0.5 rounded border border-[#DCE5F0]">
                      01
                    </span>
                    <Database className="w-4 h-4 text-slate-400" />
                  </div>
                  <h3 className="text-sm font-bold text-[#031926] mb-1.5">Complaint Intake</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Standardized ingestion of complaint parameters, timestamps, fraud typologies, and initial transfer evidence.
                  </p>
                </div>
              </div>

              {/* Step 02 */}
              <div className="p-5 rounded-xl bg-[#FAF8F2] border border-[#E7ECF3] hover:border-[#468189]/50 transition-colors flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-mono font-bold text-[#468189] bg-white px-2 py-0.5 rounded border border-[#DCE5F0]">
                      02
                    </span>
                    <GitFork className="w-4 h-4 text-slate-400" />
                  </div>
                  <h3 className="text-sm font-bold text-[#031926] mb-1.5">Money Trail Reconstruction</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Graph-based tracing across beneficiary and mule-account hops to identify terminal liquidity endpoints.
                  </p>
                </div>
              </div>

              {/* Step 03 */}
              <div className="p-5 rounded-xl bg-[#FAF8F2] border border-[#E7ECF3] hover:border-[#468189]/50 transition-colors flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-mono font-bold text-[#468189] bg-white px-2 py-0.5 rounded border border-[#DCE5F0]">
                      03
                    </span>
                    <TrendingUp className="w-4 h-4 text-slate-400" />
                  </div>
                  <h3 className="text-sm font-bold text-[#031926] mb-1.5">V8 Cash-Out Prediction</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Debiased XGBoost ranking evaluating 49 location features across all 60 Delhi candidate zones.
                  </p>
                </div>
              </div>

              {/* Step 04 */}
              <div className="p-5 rounded-xl bg-[#FAF8F2] border border-[#E7ECF3] hover:border-[#468189]/50 transition-colors flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-mono font-bold text-[#468189] bg-white px-2 py-0.5 rounded border border-[#DCE5F0]">
                      04
                    </span>
                    <Clock className="w-4 h-4 text-slate-400" />
                  </div>
                  <h3 className="text-sm font-bold text-[#031926] mb-1.5">Golden-Hour Intelligence</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Time model estimation of withdrawal velocity to calculate the viable field intervention window.
                  </p>
                </div>
              </div>

              {/* Step 05 */}
              <div className="p-5 rounded-xl bg-[#FAF8F2] border border-[#E7ECF3] hover:border-[#468189]/50 transition-colors flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-mono font-bold text-[#468189] bg-white px-2 py-0.5 rounded border border-[#DCE5F0]">
                      05
                    </span>
                    <MapPin className="w-4 h-4 text-slate-400" />
                  </div>
                  <h3 className="text-sm font-bold text-[#031926] mb-1.5">ATM/CSP Context</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Contextual scoring of physical cash access points, ATM clusters, and banking touchpoints in candidate zones.
                  </p>
                </div>
              </div>

              {/* Step 06 */}
              <div className="p-5 rounded-xl bg-[#FAF8F2] border border-[#E7ECF3] hover:border-[#468189]/50 transition-colors flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-mono font-bold text-[#468189] bg-white px-2 py-0.5 rounded border border-[#DCE5F0]">
                      06
                    </span>
                    <Workflow className="w-4 h-4 text-slate-400" />
                  </div>
                  <h3 className="text-sm font-bold text-[#031926] mb-1.5">Intervention Plan</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Actionable decision support: jurisdictional assignment, field dispatch briefing, and bank lien coordination.
                  </p>
                </div>
              </div>

              {/* Step 07 */}
              <div className="p-5 rounded-xl bg-[#FAF8F2] border border-[#E7ECF3] hover:border-[#468189]/50 transition-colors flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-mono font-bold text-[#468189] bg-white px-2 py-0.5 rounded border border-[#DCE5F0]">
                      07
                    </span>
                    <Radio className="w-4 h-4 text-slate-400" />
                  </div>
                  <h3 className="text-sm font-bold text-[#031926] mb-1.5">Multi-Channel Alerts</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Targeted dispatch across live dashboard feeds, simulated SMS/Email channels, and partner webhooks.
                  </p>
                </div>
              </div>

              {/* Step 08 */}
              <div className="p-5 rounded-xl bg-[#FAF8F2] border border-[#E7ECF3] hover:border-[#468189]/50 transition-colors flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-mono font-bold text-[#468189] bg-white px-2 py-0.5 rounded border border-[#DCE5F0]">
                      08
                    </span>
                    <Activity className="w-4 h-4 text-slate-400" />
                  </div>
                  <h3 className="text-sm font-bold text-[#031926] mb-1.5">Outcome & Monitoring</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Closed-loop recording of field outcomes, recovery auditing, and ongoing model drift governance.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            5. PLATFORM CAPABILITIES SECTION (6 PREMIUM CARDS)
        ====================================================================== */}
        <section id="capabilities" className="py-16 sm:py-20 bg-[#FAF8F2] border-b border-[#E7ECF3]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <span className="text-xs font-bold text-[#468189] uppercase tracking-wider block mb-1">
                Core Capabilities
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-[#031926]">
                Institutional Intelligence Modules
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mt-2">
                Engineered for high-trust law enforcement investigation and proactive cybercrime intervention.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Card 1: PREDICT */}
              <div className="bg-white p-6 rounded-xl border border-[#DCE5F0] shadow-2xs hover:shadow-sm hover:border-[#468189]/60 transition-all">
                <div className="w-10 h-10 rounded-lg bg-[#F0F6F6] text-[#468189] flex items-center justify-center mb-4 border border-[#9DBEBB]/50">
                  <TrendingUp className="w-5 h-5" />
                </div>
                <div className="text-[10px] font-bold text-[#468189] uppercase tracking-wider mb-1">PREDICT</div>
                <h3 className="text-base font-bold text-[#031926] mb-2">V8 Top-3 Cash-Out Zones</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Ranks likely physical withdrawal clusters across 60 candidate zones using debiased gradient boosting.
                </p>
              </div>

              {/* Card 2: EXPLAIN */}
              <div className="bg-white p-6 rounded-xl border border-[#DCE5F0] shadow-2xs hover:shadow-sm hover:border-[#468189]/60 transition-all">
                <div className="w-10 h-10 rounded-lg bg-[#F0F6F6] text-[#468189] flex items-center justify-center mb-4 border border-[#9DBEBB]/50">
                  <Eye className="w-5 h-5" />
                </div>
                <div className="text-[10px] font-bold text-[#468189] uppercase tracking-wider mb-1">EXPLAIN</div>
                <h3 className="text-base font-bold text-[#031926] mb-2">LIME Local Explainability</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Deconstructs feature weights for each predicted zone so officers understand the exact rationale.
                </p>
              </div>

              {/* Card 3: TIME */}
              <div className="bg-white p-6 rounded-xl border border-[#DCE5F0] shadow-2xs hover:shadow-sm hover:border-[#468189]/60 transition-all">
                <div className="w-10 h-10 rounded-lg bg-[#F0F6F6] text-[#468189] flex items-center justify-center mb-4 border border-[#9DBEBB]/50">
                  <Clock className="w-5 h-5" />
                </div>
                <div className="text-[10px] font-bold text-[#468189] uppercase tracking-wider mb-1">TIME</div>
                <h3 className="text-base font-bold text-[#031926] mb-2">Golden-Hour Operational Window</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Calculates estimated cash-out velocity to prioritize immediate interventions before funds disperse.
                </p>
              </div>

              {/* Card 4: PRIORITIZE */}
              <div className="bg-white p-6 rounded-xl border border-[#DCE5F0] shadow-2xs hover:shadow-sm hover:border-[#468189]/60 transition-all">
                <div className="w-10 h-10 rounded-lg bg-[#F0F6F6] text-[#468189] flex items-center justify-center mb-4 border border-[#9DBEBB]/50">
                  <MapPin className="w-5 h-5" />
                </div>
                <div className="text-[10px] font-bold text-[#468189] uppercase tracking-wider mb-1">PRIORITIZE</div>
                <h3 className="text-base font-bold text-[#031926] mb-2">ATM/CSP Contextual Intelligence</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Identifies high-density cash dispenser clusters and CSP nodes inside candidate zones for tactical deployment.
                </p>
              </div>

              {/* Card 5: COORDINATE */}
              <div className="bg-white p-6 rounded-xl border border-[#DCE5F0] shadow-2xs hover:shadow-sm hover:border-[#468189]/60 transition-all">
                <div className="w-10 h-10 rounded-lg bg-[#F0F6F6] text-[#468189] flex items-center justify-center mb-4 border border-[#9DBEBB]/50">
                  <Workflow className="w-5 h-5" />
                </div>
                <div className="text-[10px] font-bold text-[#468189] uppercase tracking-wider mb-1">COORDINATE</div>
                <h3 className="text-base font-bold text-[#031926] mb-2">Intervention + Handoff + Bank Workflow</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Generates cross-jurisdiction transfer dossiers and bank lien sandbox coordination packages.
                </p>
              </div>

              {/* Card 6: LEARN FROM OUTCOMES */}
              <div className="bg-white p-6 rounded-xl border border-[#DCE5F0] shadow-2xs hover:shadow-sm hover:border-[#468189]/60 transition-all">
                <div className="w-10 h-10 rounded-lg bg-[#F0F6F6] text-[#468189] flex items-center justify-center mb-4 border border-[#9DBEBB]/50">
                  <Activity className="w-5 h-5" />
                </div>
                <div className="text-[10px] font-bold text-[#468189] uppercase tracking-wider mb-1">LEARN FROM OUTCOMES</div>
                <h3 className="text-base font-bold text-[#031926] mb-2">Outcome Evaluation & Drift Monitoring</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Tracks intervention efficacy, actual withdrawal locations, and statistical population drift metrics.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            6. "WHY CYBERSHIELD" SECTION (DIFFERENTIATORS)
        ====================================================================== */}
        <section id="why-cybershield" className="py-16 sm:py-20 bg-white border-b border-[#E7ECF3]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <span className="text-xs font-bold text-[#468189] uppercase tracking-wider block mb-1">
                Platform Differentiation
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-[#031926]">
                Why CyberShield AI
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mt-2">
                Ground-truth principles guiding our architecture, methodology, and operational governance.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Differentiator 1 */}
              <div className="p-5 rounded-xl border border-[#E7ECF3] bg-[#FAF8F2] space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-[#031926]">
                  <CheckCircle2 className="w-4 h-4 text-[#468189] shrink-0" />
                  <span>Victim-Location Debiased Ranking</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed pl-6">
                  Separates the complainant's filing district from the suspect's cash-out destination using money-trail signals rather than naive geographic proximity.
                </p>
              </div>

              {/* Differentiator 2 */}
              <div className="p-5 rounded-xl border border-[#E7ECF3] bg-[#FAF8F2] space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-[#031926]">
                  <CheckCircle2 className="w-4 h-4 text-[#468189] shrink-0" />
                  <span>Persisted & Versioned Prediction Snapshots</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed pl-6">
                  Every inference is locked with its exact 49-feature vector, model artifact hash, and timestamp for evidentiary reproducibility.
                </p>
              </div>

              {/* Differentiator 3 */}
              <div className="p-5 rounded-xl border border-[#E7ECF3] bg-[#FAF8F2] space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-[#031926]">
                  <CheckCircle2 className="w-4 h-4 text-[#468189] shrink-0" />
                  <span>Local LIME Explainability</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed pl-6">
                  Provides granular positive and negative feature attributions so investigators never act on unexplainable black-box recommendations.
                </p>
              </div>

              {/* Differentiator 4 */}
              <div className="p-5 rounded-xl border border-[#E7ECF3] bg-[#FAF8F2] space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-[#031926]">
                  <CheckCircle2 className="w-4 h-4 text-[#468189] shrink-0" />
                  <span>Cross-Jurisdiction Coordination</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed pl-6">
                  Enables originating cyber cells to hand off validated evidence packets directly to destination units where physical cash-out is imminent.
                </p>
              </div>

              {/* Differentiator 5 */}
              <div className="p-5 rounded-xl border border-[#E7ECF3] bg-[#FAF8F2] space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-[#031926]">
                  <CheckCircle2 className="w-4 h-4 text-[#468189] shrink-0" />
                  <span>Decision-Support Intervention Plans</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed pl-6">
                  Formulates tactical options and banking communications for human investigator authorization, maintaining human-in-the-loop control.
                </p>
              </div>

              {/* Differentiator 6 */}
              <div className="p-5 rounded-xl border border-[#E7ECF3] bg-[#FAF8F2] space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-[#031926]">
                  <CheckCircle2 className="w-4 h-4 text-[#468189] shrink-0" />
                  <span>Outcome & Drift Governance</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed pl-6">
                  Systematically audits confirmed field results against predictions and monitors data distributions to detect emerging fraud shifts.
                </p>
              </div>
            </div>

            {/* Scope / Truthfulness Affirmation */}
            <div className="mt-8 p-4 rounded-lg bg-[#FAF8F2] border border-[#DCE5F0] text-center max-w-3xl mx-auto">
              <p className="text-xs text-slate-600 leading-relaxed">
                <strong className="text-[#031926]">Truthful Scope:</strong> CyberShield AI does not claim perfect accuracy, autonomous law enforcement authority, live NCRP production integration, or real automated account freezing. It is designed and evaluated as high-trust investigator decision support.
              </p>
            </div>
          </div>
        </section>

        {/* ======================================================================
            7. MODEL TRANSPARENCY SECTION
        ====================================================================== */}
        <section id="transparency" className="py-16 sm:py-20 bg-[#FAF8F2] border-b border-[#E7ECF3]" style={subtleGridStyle}>
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <span className="text-xs font-bold text-[#468189] uppercase tracking-wider block mb-1">
                Engineering Governance
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-[#031926]">
                MODEL TRANSPARENCY
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mt-2">
                Full transparency into active model specifications, training parameters, and evaluation scope.
              </p>
            </div>

            {/* Specification Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
              <div className="p-4 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs text-center">
                <span className="text-[10px] font-semibold text-slate-400 block uppercase">Active Model</span>
                <span className="text-xs font-bold text-[#031926] font-mono mt-1 block truncate">
                  cashout-location-xgb-v8-debiased
                </span>
              </div>
              <div className="p-4 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs text-center">
                <span className="text-[10px] font-semibold text-slate-400 block uppercase">Feature Count</span>
                <span className="text-base font-extrabold text-[#468189] font-mono mt-0.5 block">49</span>
              </div>
              <div className="p-4 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs text-center">
                <span className="text-[10px] font-semibold text-slate-400 block uppercase">Candidate Universe</span>
                <span className="text-xs font-bold text-[#031926] mt-1 block">60 Delhi clusters</span>
              </div>
              <div className="p-4 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs text-center">
                <span className="text-[10px] font-semibold text-slate-400 block uppercase">Explainability</span>
                <span className="text-xs font-bold text-[#468189] mt-1 block">LIME</span>
              </div>
              <div className="p-4 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs text-center">
                <span className="text-[10px] font-semibold text-slate-400 block uppercase">Time Intelligence</span>
                <span className="text-xs font-bold text-[#031926] font-mono mt-1 block truncate">
                  cashout-time-xgb-v3
                </span>
              </div>
              <div className="p-4 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs text-center">
                <span className="text-[10px] font-semibold text-slate-400 block uppercase">Evaluation Context</span>
                <span className="text-xs font-bold text-[#031926] mt-1 block">Controlled Synthetic Delhi Pilot</span>
              </div>
            </div>

            {/* Mandatory Transparency Disclosure Box */}
            <div className="bg-white rounded-xl border border-[#DCE5F0] p-6 sm:p-7 shadow-xs max-w-4xl mx-auto space-y-4">
              <div className="flex items-start space-x-3">
                <AlertCircle className="w-5 h-5 text-[#468189] shrink-0 mt-0.5" />
                <div className="space-y-2">
                  <h3 className="text-xs font-bold text-[#031926] uppercase tracking-wide">
                    Evaluation Scope & Academic Integrity
                  </h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    CyberShield AI's current prototype model is trained and evaluated on controlled synthetic Delhi cybercrime scenarios designed to reproduce multi-hop financial and geographic patterns. These metrics are prototype evaluation results and are not presented as real NCRP production accuracy.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            8. CONTROLLED SYNTHETIC DATA SECTION
        ====================================================================== */}
        <section className="py-12 bg-white border-b border-[#E7ECF3]">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="p-5 sm:p-6 rounded-xl bg-[#F0F6F6] border border-[#9DBEBB]/60 space-y-2.5">
              <div className="flex items-center space-x-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#468189] text-white uppercase tracking-wider">
                  CONTROLLED TRAINING ENVIRONMENT
                </span>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed font-medium">
                CyberShield AI is trained on a controlled synthetic Delhi dataset that simulates complaint attributes,
                transaction paths, mule-account movement, cash-out behavior and geographic context. This allows the
                complete prediction and intervention pipeline to be demonstrated safely without exposing real victim or
                banking PII.
              </p>
            </div>
          </div>
        </section>

        {/* ======================================================================
            9. OPERATIONAL INTELLIGENCE SECTION (7-STAGE CHAIN)
        ====================================================================== */}
        <section className="py-16 sm:py-20 bg-[#FAF8F2] border-b border-[#E7ECF3]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <span className="text-xs font-bold text-[#468189] uppercase tracking-wider block mb-1">
                Operational Intelligence
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-[#031926]">
                The Complete Investigation Chain
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mt-2">
                Every investigative decision answers seven fundamental questions before tactical field deployment.
              </p>
            </div>

            {/* Visual 7-Stage Chain */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3">
              {/* WHERE */}
              <div className="bg-white p-4 rounded-xl border border-[#DCE5F0] shadow-2xs text-center flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-mono font-bold text-[#468189] block uppercase">WHERE</span>
                  <h4 className="text-xs font-bold text-[#031926] mt-1 mb-1">V8 Top-3 Candidate Zones</h4>
                  <p className="text-[11px] text-slate-600 leading-tight">
                    Ranked geographic clusters across Delhi
                  </p>
                </div>
              </div>

              {/* WHEN */}
              <div className="bg-white p-4 rounded-xl border border-[#DCE5F0] shadow-2xs text-center flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-mono font-bold text-[#468189] block uppercase">WHEN</span>
                  <h4 className="text-xs font-bold text-[#031926] mt-1 mb-1">Golden-Hour Window</h4>
                  <p className="text-[11px] text-slate-600 leading-tight">
                    Estimated withdrawal velocity & time horizon
                  </p>
                </div>
              </div>

              {/* WHY */}
              <div className="bg-white p-4 rounded-xl border border-[#DCE5F0] shadow-2xs text-center flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-mono font-bold text-[#468189] block uppercase">WHY</span>
                  <h4 className="text-xs font-bold text-[#031926] mt-1 mb-1">LIME Explanation</h4>
                  <p className="text-[11px] text-slate-600 leading-tight">
                    Auditable local feature contributions
                  </p>
                </div>
              </div>

              {/* WHERE INSIDE */}
              <div className="bg-white p-4 rounded-xl border border-[#DCE5F0] shadow-2xs text-center flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-mono font-bold text-[#468189] block uppercase">WHERE INSIDE</span>
                  <h4 className="text-xs font-bold text-[#031926] mt-1 mb-1">ATM/CSP Context</h4>
                  <p className="text-[11px] text-slate-600 leading-tight">
                    Prioritized physical dispenser nodes
                  </p>
                </div>
              </div>

              {/* WHAT NEXT */}
              <div className="bg-white p-4 rounded-xl border border-[#DCE5F0] shadow-2xs text-center flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-mono font-bold text-[#468189] block uppercase">WHAT NEXT</span>
                  <h4 className="text-xs font-bold text-[#031926] mt-1 mb-1">Intervention Plan</h4>
                  <p className="text-[11px] text-slate-600 leading-tight">
                    Inter-jurisdiction dispatch & bank actions
                  </p>
                </div>
              </div>

              {/* WHAT HAPPENED */}
              <div className="bg-white p-4 rounded-xl border border-[#DCE5F0] shadow-2xs text-center flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-mono font-bold text-[#468189] block uppercase">WHAT HAPPENED</span>
                  <h4 className="text-xs font-bold text-[#031926] mt-1 mb-1">Outcome Evaluation</h4>
                  <p className="text-[11px] text-slate-600 leading-tight">
                    Recovery feedback & action attribution
                  </p>
                </div>
              </div>

              {/* MONITOR */}
              <div className="bg-white p-4 rounded-xl border border-[#DCE5F0] shadow-2xs text-center flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-mono font-bold text-[#468189] block uppercase">MONITOR</span>
                  <h4 className="text-xs font-bold text-[#031926] mt-1 mb-1">Drift Intelligence</h4>
                  <p className="text-[11px] text-slate-600 leading-tight">
                    Population shift & calibration tracking
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            10. ALERTING SECTION (TRUTHFUL CHANNELS)
        ====================================================================== */}
        <section id="alerting" className="py-16 sm:py-20 bg-white border-b border-[#E7ECF3]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <span className="text-xs font-bold text-[#468189] uppercase tracking-wider block mb-1">
                Operational Alerting
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-[#031926]">
                MULTI-CHANNEL OPERATIONAL ALERTING
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mt-2">
                Multi-tier dispatch infrastructure designed for coordinated inter-agency field response.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-6">
              {/* Dashboard / WebSocket */}
              <div className="p-5 rounded-xl border border-[#DCE5F0] bg-[#FAF8F2] flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold text-[#031926]">Dashboard / WebSocket</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                      LIVE
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Streaming in-browser alerts and real-time dashboard banner notifications for active duty officers.
                  </p>
                </div>
              </div>

              {/* Email */}
              <div className="p-5 rounded-xl border border-[#DCE5F0] bg-[#FAF8F2] flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold text-[#031926]">Email Dispatch</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                      SIMULATED
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Automated formal case intelligence briefs formatted for jurisdictional supervisory review.
                  </p>
                </div>
              </div>

              {/* SMS */}
              <div className="p-5 rounded-xl border border-[#DCE5F0] bg-[#FAF8F2] flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold text-[#031926]">SMS Broadcast</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                      SIMULATED
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    High-urgency golden-hour alert broadcast designed for field officers and rapid response units.
                  </p>
                </div>
              </div>

              {/* Partner Webhook */}
              <div className="p-5 rounded-xl border border-[#DCE5F0] bg-[#FAF8F2] flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold text-[#031926]">Partner Webhook</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-300">
                      SANDBOX
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Programmatic JSON payload delivery for banking partner fraud systems and nodal coordination.
                  </p>
                </div>
              </div>
            </div>

            <div className="text-center text-xs text-slate-500 font-medium">
              "Pilot environments clearly distinguish simulated, sandbox and live delivery modes."
            </div>
          </div>
        </section>

        {/* ======================================================================
            11. SECURITY & GOVERNANCE SECTION
        ====================================================================== */}
        <section id="security" className="py-16 sm:py-20 bg-[#FAF8F2] border-b border-[#E7ECF3]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <span className="text-xs font-bold text-[#468189] uppercase tracking-wider block mb-1">
                Zero Trust Architecture
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-[#031926]">
                Security & Governance Controls
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mt-2">
                Engineered with strict access boundaries, non-repudiation, and human oversight.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              <div className="p-5 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs space-y-1.5">
                <div className="text-xs font-bold text-[#031926]">RBAC & Jurisdiction Isolation</div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Rigorous data boundary enforcement ensuring district, state, and national officers only access authorized cases.
                </p>
              </div>

              <div className="p-5 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs space-y-1.5">
                <div className="text-xs font-bold text-[#031926]">Prediction Provenance</div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Cryptographic verification linking every prediction to its generating model version, feature vector, and inference timestamp.
                </p>
              </div>

              <div className="p-5 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs space-y-1.5">
                <div className="text-xs font-bold text-[#031926]">Tamper-Evident Prediction Audit</div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Append-only logging records every prediction, explanation, and officer action to protect evidentiary integrity.
                </p>
              </div>

              <div className="p-5 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs space-y-1.5">
                <div className="text-xs font-bold text-[#031926]">Versioned Historical Records</div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Full lineage tracking for investigation states, preventing retroactive modification of earlier findings.
                </p>
              </div>

              <div className="p-5 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs space-y-1.5">
                <div className="text-xs font-bold text-[#031926]">PII-Minimized Notifications</div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Outbound alert payloads redact sensitive complainant and banking details, sharing only operational necessities.
                </p>
              </div>

              <div className="p-5 rounded-xl bg-white border border-[#DCE5F0] shadow-2xs space-y-1.5">
                <div className="text-xs font-bold text-[#031926]">No Autonomous Enforcement</div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  All predictive outputs serve as investigative decision support; field deployment and bank freezes require officer authorization.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            12. FINAL CTA SECTION (CLEAN INSTITUTIONAL DEEP NAVY BAND)
        ====================================================================== */}
        <section className="py-16 sm:py-20 bg-[#031926] text-white">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
            <div className="w-12 h-12 rounded-xl bg-[#072130] text-[#77ACA2] flex items-center justify-center mx-auto border border-[#0E2A3A]">
              <Shield className="w-6 h-6" />
            </div>

            <h2 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-white tracking-tight">
              Operational Intelligence. <br />
              <span className="text-[#77ACA2]">Actionable Before Cash-Out.</span>
            </h2>

            <p className="text-xs sm:text-sm text-slate-300 max-w-xl mx-auto leading-relaxed">
              Empowering cybercrime investigators with debiased ML cash-out predictions, local LIME explainability,
              and coordinated inter-agency decision support.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-3">
              <button
                onClick={() => navigate('/login')}
                className="px-6 py-3 rounded-lg bg-[#468189] hover:bg-[#386970] text-white font-semibold text-xs shadow-md transition-all flex items-center space-x-2"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Officer Login</span>
              </button>

              <button
                onClick={() => scrollToSection('pipeline')}
                className="px-6 py-3 rounded-lg bg-[#072130] hover:bg-[#0E2A3A] text-slate-200 font-semibold text-xs border border-[#0E2A3A] transition-all"
              >
                Explore Platform
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* ======================================================================
          13. FOOTER
      ====================================================================== */}
      <footer className="bg-white border-t border-[#DCE5F0] py-10 text-slate-500 text-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 pb-6 border-b border-slate-100">
            <div className="flex items-center space-x-3">
              <div className="w-7 h-7 rounded bg-[#031926] flex items-center justify-center">
                <Shield className="w-4 h-4 text-[#77ACA2]" />
              </div>
              <div>
                <span className="font-bold text-[#031926]">CyberShield AI</span>
                <span className="text-slate-400 ml-2 font-mono text-[11px]">Delhi Controlled Pilot</span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-6 text-xs font-medium text-slate-600">
              <button onClick={() => scrollToSection('pipeline')} className="hover:text-[#468189] transition-colors">
                Pipeline
              </button>
              <button onClick={() => scrollToSection('capabilities')} className="hover:text-[#468189] transition-colors">
                Capabilities
              </button>
              <button onClick={() => scrollToSection('why-cybershield')} className="hover:text-[#468189] transition-colors">
                Why CyberShield
              </button>
              <button onClick={() => scrollToSection('transparency')} className="hover:text-[#468189] transition-colors">
                Model Transparency
              </button>
              <button onClick={() => scrollToSection('alerting')} className="hover:text-[#468189] transition-colors">
                Alerting
              </button>
              <button onClick={() => scrollToSection('security')} className="hover:text-[#468189] transition-colors">
                Security
              </button>
              <button onClick={() => navigate('/login')} className="text-[#468189] hover:underline font-semibold">
                Officer Login
              </button>
            </div>
          </div>

          <div className="pt-6 flex flex-col sm:flex-row items-center justify-between text-[11px] text-slate-500 gap-2">
            <div>
              CyberShield AI • AxiomSix • SIH 2026 • Delhi Controlled Pilot
            </div>
            <div className="text-slate-400">
              Prototype developed for research and evaluation. Not an official government deployment.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};
