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
  Server,
  Terminal,
  ExternalLink,
  Zap,
} from 'lucide-react';
import { useAuth, DEMO_CREDENTIALS } from '../store/authContext';
import { InfoPopover } from '../components/common/InfoPopover';

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

  const handleControlledPilotLogin = () => {
    navigate('/login', { state: { prefillPilot: true } });
  };

  const scrollToSection = (id: string) => {
    setMobileMenuOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="min-h-screen bg-[#0E1E38] text-slate-100 font-sans selection:bg-blue-600 selection:text-white">
      {/* ======================================================================
          1. STICKY NAVBAR
      ====================================================================== */}
      <header
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${
          scrolled
            ? 'bg-[#0E1E38]/95 backdrop-blur-md shadow-lg border-b border-[#1E3A60]'
            : 'bg-[#0E1E38] border-b border-[#1A3356]'
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* LEFT: Project Identity */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center shadow-md shadow-blue-500/20 border border-blue-400/30">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-lg font-bold tracking-tight text-white">
                  CyberShield <span className="text-blue-400">AI</span>
                </span>
                <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-900/60 text-blue-300 border border-blue-700/50">
                  I4C PILOT
                </span>
              </div>
              <p className="text-[10px] text-slate-400 hidden sm:block">Predictive Cash-Out Intelligence</p>
            </div>
          </div>

          {/* CENTER: Navigation Links (Desktop) */}
          <nav className="hidden md:flex items-center space-x-6 text-xs font-medium text-slate-300">
            <button onClick={() => scrollToSection('platform')} className="hover:text-white transition-colors">
              Platform
            </button>
            <button onClick={() => scrollToSection('how-it-works')} className="hover:text-white transition-colors">
              How It Works
            </button>
            <button onClick={() => scrollToSection('capabilities')} className="hover:text-white transition-colors">
              Capabilities
            </button>
            <button onClick={() => scrollToSection('transparency')} className="hover:text-white transition-colors">
              Model Transparency
            </button>
            <button onClick={() => scrollToSection('security')} className="hover:text-white transition-colors">
              Security
            </button>
          </nav>

          {/* RIGHT: Login CTA */}
          <div className="hidden sm:flex items-center space-x-3">
            <button
              onClick={() => navigate('/login')}
              className="px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-sm transition-colors flex items-center space-x-1.5"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Officer Login</span>
            </button>
          </div>

          {/* Mobile Hamburger Button */}
          <div className="flex sm:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-md text-slate-300 hover:text-white hover:bg-slate-800 focus:outline-none"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="sm:hidden bg-[#0E1E38] border-b border-[#1E3A60] px-4 pt-2 pb-4 space-y-3 animate-in slide-in-from-top-2">
            <button
              onClick={() => scrollToSection('platform')}
              className="block w-full text-left py-2 text-xs font-medium text-slate-300 hover:text-white"
            >
              Platform
            </button>
            <button
              onClick={() => scrollToSection('how-it-works')}
              className="block w-full text-left py-2 text-xs font-medium text-slate-300 hover:text-white"
            >
              How It Works
            </button>
            <button
              onClick={() => scrollToSection('capabilities')}
              className="block w-full text-left py-2 text-xs font-medium text-slate-300 hover:text-white"
            >
              Capabilities
            </button>
            <button
              onClick={() => scrollToSection('transparency')}
              className="block w-full text-left py-2 text-xs font-medium text-slate-300 hover:text-white"
            >
              Model Transparency
            </button>
            <button
              onClick={() => scrollToSection('security')}
              className="block w-full text-left py-2 text-xs font-medium text-slate-300 hover:text-white"
            >
              Security
            </button>
            <div className="pt-2 border-t border-slate-800">
              <button
                onClick={() => navigate('/login')}
                className="w-full py-2.5 px-4 rounded-md bg-blue-600 text-white text-xs font-semibold text-center flex items-center justify-center space-x-1.5"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Officer Login</span>
              </button>
            </div>
          </div>
        )}
      </header>

      {/* Main Container */}
      <main className="pt-16">
        {/* ======================================================================
            2. HERO SECTION
        ====================================================================== */}
        <section className="relative overflow-hidden bg-gradient-to-b from-[#0E1E38] via-[#122544] to-[#0E1E38] py-16 sm:py-20 lg:py-24 border-b border-[#1E3A60]">
          {/* Subtle grid background */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f3b640a_1px,transparent_1px),linear-gradient(to_bottom,#1f3b640a_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none" />

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
              {/* LEFT: Value Proposition */}
              <div className="lg:col-span-6 space-y-6">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-900/40 border border-blue-500/30 text-blue-300 text-xs font-semibold tracking-wide uppercase">
                  <Activity className="w-3.5 h-3.5 text-blue-400" />
                  <span>From Complaints to Actionable Intelligence</span>
                  <InfoPopover
                    title="Actionable Intelligence"
                    content="CyberShield AI correlates complaint intake data with financial money-trail patterns to predict high-risk cash-out zones before funds are liquidated at physical ATMs."
                  />
                </div>

                <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight leading-[1.15]">
                  Predict Cash-Out Risk. <br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-cyan-300 to-blue-200">
                    Act Before the Money Disappears.
                  </span>
                </h1>

                <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-xl">
                  CyberShield AI transforms cybercrime complaints and pre-withdrawal financial signals into ranked geographic
                  intelligence, helping investigators identify likely cash-out zones and coordinate faster intervention.
                </p>

                {/* Primary Actions */}
                <div className="flex flex-wrap items-center gap-3 pt-2">
                  <button
                    onClick={() => navigate('/login')}
                    className="px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm shadow-lg shadow-blue-600/30 transition-all flex items-center space-x-2"
                  >
                    <Lock className="w-4 h-4" />
                    <span>Officer Login</span>
                  </button>

                  <button
                    onClick={() => scrollToSection('how-it-works')}
                    className="px-5 py-3 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-slate-200 font-semibold text-sm transition-all"
                  >
                    See How It Works
                  </button>

                  <button
                    onClick={() => scrollToSection('pilot-access')}
                    className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center space-x-1 pl-2"
                  >
                    <span>Controlled Pilot Access</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Trust Pills */}
                <div className="pt-4 border-t border-slate-800/80 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-medium text-slate-400">
                  <div className="flex items-center space-x-1.5 bg-slate-900/60 px-2.5 py-1.5 rounded border border-slate-800">
                    <CheckCircle2 className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span className="truncate">DELHI PILOT</span>
                  </div>
                  <div className="flex items-center space-x-1.5 bg-slate-900/60 px-2.5 py-1.5 rounded border border-slate-800">
                    <CheckCircle2 className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span className="truncate">AI-ASSISTED</span>
                  </div>
                  <div className="flex items-center space-x-1.5 bg-slate-900/60 px-2.5 py-1.5 rounded border border-slate-800">
                    <CheckCircle2 className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span className="truncate">CASE-SCOPED</span>
                  </div>
                  <div className="flex items-center space-x-1.5 bg-slate-900/60 px-2.5 py-1.5 rounded border border-slate-800">
                    <CheckCircle2 className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span className="truncate">SECURE LEA</span>
                  </div>
                </div>
              </div>

              {/* RIGHT: Hero Product Preview (Controlled Demo) */}
              <div className="lg:col-span-6">
                <div className="bg-[#152B4D] rounded-xl border border-[#2A4D7C] shadow-2xl p-5 sm:p-6 relative overflow-hidden">
                  {/* Top Bar Indicator */}
                  <div className="flex items-center justify-between border-b border-slate-700/80 pb-3 mb-4">
                    <div className="flex items-center space-x-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        CONTROLLED DEMO
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-900/60 text-blue-300 border border-blue-700/50">
                        CASE FOCUS
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-cyan-900/60 text-cyan-300 border border-cyan-700/50">
                        TRAINED ML
                      </span>
                    </div>
                    <div className="flex items-center space-x-1.5 text-[11px] text-slate-400 font-mono">
                      <span>T+18m Window</span>
                      <InfoPopover
                        title="Trained ML Prediction"
                        content="Ranked candidate zones are generated by the active V8 Debiased location model using observed pre-withdrawal transaction evidence."
                      />
                    </div>
                  </div>

                  {/* Complaint Quick Header */}
                  <div className="grid grid-cols-2 gap-3 mb-4 bg-slate-900/60 p-3 rounded-lg border border-slate-800 text-xs">
                    <div>
                      <span className="text-[10px] text-slate-400 block uppercase">Complaint Reference</span>
                      <span className="font-mono font-bold text-white">CMP-DEMO-2481</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block uppercase">Fraud Amount</span>
                      <span className="font-mono font-bold text-amber-400">₹2,00,000</span>
                    </div>
                  </div>

                  {/* Mini Map & Prediction Cards Preview */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-xs font-semibold text-slate-200">
                      <span>Top-3 Candidate Cash-Out Zones</span>
                      <span className="text-[11px] text-slate-400">Delhi Pilot (60 Clusters)</span>
                    </div>

                    {/* Zone 1 */}
                    <div className="p-3 rounded-lg bg-slate-900/80 border border-blue-500/40 flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-6 h-6 rounded-full bg-blue-600 text-white font-bold text-xs flex items-center justify-center">
                          1
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white">Patparganj Industrial Area</div>
                          <div className="text-[10px] text-slate-400">East Delhi Mule Terminal Corridor</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-mono font-bold text-cyan-400">Score 0.88</div>
                        <div className="text-[10px] text-red-400 font-semibold">High Priority</div>
                      </div>
                    </div>

                    {/* Zone 2 */}
                    <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-700/70 flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-6 h-6 rounded-full bg-slate-700 text-slate-200 font-bold text-xs flex items-center justify-center">
                          2
                        </div>
                        <div>
                          <div className="text-xs font-bold text-slate-200">Laxmi Nagar</div>
                          <div className="text-[10px] text-slate-400">Commercial ATM Cluster Node</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-mono font-semibold text-slate-300">Score 0.74</div>
                        <div className="text-[10px] text-amber-400">Medium Priority</div>
                      </div>
                    </div>

                    {/* Zone 3 */}
                    <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-700/70 flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-6 h-6 rounded-full bg-slate-700 text-slate-200 font-bold text-xs flex items-center justify-center">
                          3
                        </div>
                        <div>
                          <div className="text-xs font-bold text-slate-200">Mayur Vihar Phase 1</div>
                          <div className="text-[10px] text-slate-400">Sub-corridor Cash-Out Hub</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-mono font-semibold text-slate-300">Score 0.62</div>
                        <div className="text-[10px] text-slate-400">Secondary Alert</div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-800 text-[10px] text-slate-400 flex items-center justify-between">
                    <span>Inference: V8 Debiased XGBoost</span>
                    <span className="text-blue-400 font-medium">Static Controlled Demo Preview</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            3. PROBLEM → SOLUTION
        ====================================================================== */}
        <section id="platform" className="py-16 sm:py-20 bg-[#F8FAFC] text-slate-900 border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <span className="text-xs font-bold text-blue-700 uppercase tracking-wider">Operational Reality</span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-2">
                The Transition from Reactive Logging to Proactive Interception
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-stretch">
              {/* THE CHALLENGE */}
              <div className="bg-white p-6 sm:p-8 rounded-xl border border-red-200 shadow-sm relative">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-red-50 text-red-700 text-xs font-bold mb-4">
                  <span>THE CHALLENGE</span>
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-3">Cyber-fraud response is often reactive.</h3>
                <ul className="space-y-3.5 text-xs sm:text-sm text-slate-600">
                  <li className="flex items-start space-x-2.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 mt-2 shrink-0" />
                    <span>Complaints arrive at high volume across multiple state jurisdictions.</span>
                  </li>
                  <li className="flex items-start space-x-2.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 mt-2 shrink-0" />
                    <span>Stolen funds move through layered mule accounts within minutes of transfer.</span>
                  </li>
                  <li className="flex items-start space-x-2.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 mt-2 shrink-0" />
                    <span>Physical cash-out activity frequently occurs far from the victim's location.</span>
                  </li>
                  <li className="flex items-start space-x-2.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 mt-2 shrink-0" />
                    <span>Investigators need timely geographic intelligence before funds are withdrawn.</span>
                  </li>
                </ul>
              </div>

              {/* A SMARTER APPROACH */}
              <div className="bg-white p-6 sm:p-8 rounded-xl border border-blue-200 shadow-sm relative">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-blue-50 text-blue-700 text-xs font-bold mb-4">
                  <span>A SMARTER APPROACH</span>
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-3">From complaint to actionable location intelligence.</h3>
                
                {/* Visual Workflow Steps */}
                <div className="space-y-2 text-xs font-medium text-slate-700">
                  <div className="p-2 rounded bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <span>1. Complaint Intake & Financial Evidence</span>
                    <span className="text-[10px] text-blue-600 font-bold">NCRP Signal</span>
                  </div>
                  <div className="p-2 rounded bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <span>2. Transaction Network Analysis</span>
                    <span className="text-[10px] text-blue-600 font-bold">Mule Multi-Hop</span>
                  </div>
                  <div className="p-2 rounded bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <span>3. ML Cash-Out Prediction</span>
                    <span className="text-[10px] text-blue-600 font-bold">V8 Model</span>
                  </div>
                  <div className="p-2 rounded bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <span>4. Top-3 Geographic Candidates</span>
                    <span className="text-[10px] text-blue-600 font-bold">Ranked Zones</span>
                  </div>
                  <div className="p-2 rounded bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <span>5. Case-Focused Risk Map</span>
                    <span className="text-[10px] text-blue-600 font-bold">GIS Context</span>
                  </div>
                  <div className="p-2 rounded bg-blue-50 border border-blue-200 text-blue-900 font-bold flex items-center justify-between">
                    <span>6. Investigator / Bank Rapid Alert</span>
                    <span className="text-[10px] text-blue-700 uppercase">Field Action</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            4. HOW IT WORKS
        ====================================================================== */}
        <section id="how-it-works" className="py-16 sm:py-20 bg-white text-slate-900 border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-14">
              <span className="text-xs font-bold text-blue-700 uppercase tracking-wider">End-to-End Workflow</span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-2">
                How CyberShield AI Operates
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mt-2">
                A structured four-step pipeline transforming raw complaint records into calibrated field decisions.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {/* STEP 01 */}
              <div className="p-6 rounded-xl bg-slate-50 border border-slate-200 relative hover:border-blue-300 transition-colors">
                <span className="text-xs font-mono font-bold text-blue-700">STEP 01</span>
                <h3 className="text-base font-bold text-slate-900 mt-2 mb-2">Complaint Intelligence</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Capture fraud type, amount, time, transaction references and available financial evidence.
                </p>
              </div>

              {/* STEP 02 */}
              <div className="p-6 rounded-xl bg-slate-50 border border-slate-200 relative hover:border-blue-300 transition-colors">
                <span className="text-xs font-mono font-bold text-blue-700">STEP 02</span>
                <h3 className="text-base font-bold text-slate-900 mt-2 mb-2">Money-Trail Analysis</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Build case-scoped financial relationships and identify beneficiary, intermediary and terminal account signals.
                </p>
              </div>

              {/* STEP 03 */}
              <div className="p-6 rounded-xl bg-slate-50 border border-slate-200 relative hover:border-blue-300 transition-colors">
                <span className="text-xs font-mono font-bold text-blue-700">STEP 03</span>
                <h3 className="text-base font-bold text-slate-900 mt-2 mb-2">Predictive Location Ranking</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Evaluate the full 60-cluster Delhi pilot candidate universe and rank likely cash-out zones using trained ML.
                </p>
              </div>

              {/* STEP 04 */}
              <div className="p-6 rounded-xl bg-slate-50 border border-slate-200 relative hover:border-blue-300 transition-colors">
                <span className="text-xs font-mono font-bold text-blue-700">STEP 04</span>
                <h3 className="text-base font-bold text-slate-900 mt-2 mb-2">Proactive Intervention</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Surface Top-3 geographic candidates and investigation intelligence for timely field coordination.
                </p>
              </div>
            </div>

            {/* Workflow Mid-CTA */}
            <div className="mt-12 text-center bg-[#F1F5F9] p-6 rounded-xl border border-slate-200 max-w-2xl mx-auto">
              <p className="text-sm font-bold text-slate-800 mb-3">Ready to explore the investigation workspace?</p>
              <button
                onClick={() => navigate('/login')}
                className="px-6 py-2.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-sm transition-colors inline-flex items-center space-x-2"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Officer Login</span>
              </button>
              <p className="text-[11px] text-slate-500 mt-2">Authorized investigator access</p>
            </div>
          </div>
        </section>

        {/* ======================================================================
            5. CORE CAPABILITIES
        ====================================================================== */}
        <section id="capabilities" className="py-16 sm:py-20 bg-[#0E1E38] text-white border-b border-[#1E3A60]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-14">
              <span className="text-xs font-bold text-blue-400 uppercase tracking-wider">Enterprise Modules</span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-white mt-2">
                Core Investigation Capabilities
              </h2>
              <p className="text-xs sm:text-sm text-slate-400 mt-2">
                Designed for high-throughput cybercrime operations and multi-agency response teams.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Card 1 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D] hover:border-blue-400/50 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-blue-600/20 text-blue-400 flex items-center justify-center mb-4 border border-blue-500/30">
                  <TrendingUp className="w-5 h-5" />
                </div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">Predictive Analytics</h3>
                  <InfoPopover
                    title="Predictive Analytics"
                    content="Infers candidate cluster rankings across 60 Delhi zones using debiased gradient boosting over multi-hop money trails."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Rank likely cash-out zones using trained ML inference.
                </p>
              </div>

              {/* Card 2 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D] hover:border-blue-400/50 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-cyan-600/20 text-cyan-400 flex items-center justify-center mb-4 border border-cyan-500/30">
                  <Shield className="w-5 h-5" />
                </div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">Case Intelligence</h3>
                  <InfoPopover
                    title="Case Intelligence"
                    content="Synthesizes complainant reports, banking statements, suspect accounts, and model outputs into a single pane of glass."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Unify complaint details, evidence, transaction flow and predictions.
                </p>
              </div>

              {/* Card 3 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D] hover:border-blue-400/50 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-indigo-600/20 text-indigo-400 flex items-center justify-center mb-4 border border-indigo-500/30">
                  <MapPin className="w-5 h-5" />
                </div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">GIS Risk Map</h3>
                  <InfoPopover
                    title="GIS Risk Map"
                    content="Geographic visualization with candidate cluster bounds, ATM density overlays, and case-focused risk heatmaps."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Visualize case-specific geographic candidates and contextual risk layers.
                </p>
              </div>

              {/* Card 4 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D] hover:border-blue-400/50 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-blue-600/20 text-blue-400 flex items-center justify-center mb-4 border border-blue-500/30">
                  <GitFork className="w-5 h-5" />
                </div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">Transaction Graph</h3>
                  <InfoPopover
                    title="Transaction Graph"
                    content="Interactive directed graph modeling beneficiary, intermediary, and mule accounts across multiple layers of transfers."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Follow multi-hop movement across beneficiary and intermediary accounts.
                </p>
              </div>

              {/* Card 5 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D] hover:border-blue-400/50 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-amber-600/20 text-amber-400 flex items-center justify-center mb-4 border border-amber-500/30">
                  <Bell className="w-5 h-5" />
                </div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">Alerts</h3>
                  <InfoPopover
                    title="Alert Management"
                    content="Real-time alert dispatch to jurisdictional police units and partner banks for immediate account freeze actions."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Surface high-priority intelligence for investigator workflows.
                </p>
              </div>

              {/* Card 6 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D] hover:border-blue-400/50 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-emerald-600/20 text-emerald-400 flex items-center justify-center mb-4 border border-emerald-500/30">
                  <FileCheck className="w-5 h-5" />
                </div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">Audit & Evidence</h3>
                  <InfoPopover
                    title="Audit Trail"
                    content="Cryptographically verified action ledger tracking prediction provenance, officer actions, and evidence chain-of-custody."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Maintain prediction provenance, evidence lifecycle and system audit history.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            6. DIFFERENTIATOR
        ====================================================================== */}
        <section className="py-16 sm:py-20 bg-slate-900 text-white border-b border-[#1E3A60]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
              <div className="lg:col-span-6 space-y-4">
                <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider">Methodological Rigor</span>
                <h2 className="text-2xl sm:text-3xl font-extrabold text-white leading-tight">
                  Location intelligence driven by the money trail — not simply the victim's location.
                </h2>
                <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                  CyberShield AI's debiased location pipeline is designed so victim geography alone does not determine predicted
                  cash-out zones. Legitimate pre-withdrawal transaction-network and geographic evidence drives the ranking.
                </p>
                <div className="pt-2 text-[11px] text-slate-400 italic">
                  * Note: Evaluated under controlled experimental conditions; not presented as a real-world accuracy guarantee.
                </div>
              </div>

              <div className="lg:col-span-6">
                <div className="bg-[#11223F] p-6 rounded-xl border border-[#234573] space-y-3">
                  <div className="text-xs font-bold text-slate-300 border-b border-slate-700 pb-2 flex items-center justify-between">
                    <span>DEBIASED CORRIDOR RESOLUTION</span>
                    <span className="text-cyan-400 font-mono text-[11px]">V8 Pipeline</span>
                  </div>

                  <div className="flex flex-col space-y-2 text-xs">
                    <div className="p-2.5 rounded bg-slate-800/80 border border-slate-700 flex items-center justify-between">
                      <span className="text-slate-300">Victim Origin (Complainant)</span>
                      <span className="font-mono text-slate-400 font-semibold">Dwarka (South West Delhi)</span>
                    </div>

                    <div className="text-center text-slate-500 font-bold">↓</div>

                    <div className="p-2.5 rounded bg-slate-800/80 border border-blue-800/60 flex items-center justify-between">
                      <span className="text-slate-300">Beneficiary / Mule Network</span>
                      <span className="font-mono text-blue-300 font-semibold">3-Hop Flow Traced</span>
                    </div>

                    <div className="text-center text-slate-500 font-bold">↓</div>

                    <div className="p-2.5 rounded bg-blue-900/40 border border-blue-500/40 flex items-center justify-between">
                      <span className="text-slate-200">Terminal Mule Corridor</span>
                      <span className="font-mono text-cyan-300 font-semibold">East Delhi Cluster Corridor</span>
                    </div>

                    <div className="text-center text-slate-500 font-bold">↓</div>

                    <div className="p-3 rounded bg-slate-900 border border-cyan-500/50 space-y-1.5">
                      <span className="text-[11px] text-slate-400 block font-semibold">ML Location Ranking (Top 3 Candidates)</span>
                      <div className="grid grid-cols-3 gap-2 text-center text-xs font-bold font-mono">
                        <div className="bg-blue-600/30 p-1.5 rounded border border-blue-500/40 text-blue-200">#1 Patparganj</div>
                        <div className="bg-slate-800 p-1.5 rounded text-slate-300">#2 Laxmi Nagar</div>
                        <div className="bg-slate-800 p-1.5 rounded text-slate-300">#3 Mayur Vihar</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            7. MODEL TRANSPARENCY
        ====================================================================== */}
        <section id="transparency" className="py-16 sm:py-20 bg-[#0E1E38] text-white border-b border-[#1E3A60]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-900/50 border border-cyan-500/30 text-cyan-300 text-xs font-semibold mb-3">
                <Eye className="w-3.5 h-3.5" />
                <span>Model Provenance & Disclosure</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-white">
                Built for Explainable Operational Intelligence
              </h2>
            </div>

            {/* Model Spec Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
              <div className="p-3 rounded-lg bg-[#142646] border border-[#23426D] text-center">
                <span className="text-[10px] text-slate-400 block uppercase">Model</span>
                <span className="text-xs font-bold text-white font-mono">Ranker V8</span>
              </div>
              <div className="p-3 rounded-lg bg-[#142646] border border-[#23426D] text-center">
                <span className="text-[10px] text-slate-400 block uppercase">Scope</span>
                <span className="text-xs font-bold text-white">Delhi Pilot</span>
              </div>
              <div className="p-3 rounded-lg bg-[#142646] border border-[#23426D] text-center">
                <span className="text-[10px] text-slate-400 block uppercase">Candidate Universe</span>
                <span className="text-xs font-bold text-white">60 Clusters</span>
              </div>
              <div className="p-3 rounded-lg bg-[#142646] border border-[#23426D] text-center">
                <span className="text-[10px] text-slate-400 block uppercase">Prediction Output</span>
                <span className="text-xs font-bold text-cyan-300">Top-3 Zones</span>
              </div>
              <div className="p-3 rounded-lg bg-[#142646] border border-[#23426D] text-center">
                <span className="text-[10px] text-slate-400 block uppercase">Mode</span>
                <span className="text-xs font-bold text-emerald-400">Trained ML</span>
              </div>
              <div className="p-3 rounded-lg bg-[#142646] border border-[#23426D] text-center">
                <span className="text-[10px] text-slate-400 block uppercase">Training Context</span>
                <span className="text-xs font-bold text-slate-300 truncate block">Synthetic Delhi</span>
              </div>
            </div>

            {/* Evaluation Setup Box */}
            <div className="bg-[#122544] p-6 sm:p-8 rounded-xl border border-[#254A78] mb-8">
              <div className="flex items-center justify-between border-b border-slate-700/80 pb-3 mb-6">
                <div>
                  <h3 className="text-sm font-bold text-white">PROTOTYPE TRAINING & EVALUATION SETUP</h3>
                  <p className="text-[11px] text-slate-400">Controlled synthetic corpus benchmark setup</p>
                </div>
                <span className="px-2.5 py-1 rounded text-[10px] font-bold bg-blue-900/80 text-blue-200 border border-blue-700">
                  RESEARCH BENCHMARK
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 text-center">
                <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800">
                  <div className="text-2xl font-black text-white font-mono">10,000</div>
                  <div className="text-xs text-slate-300 font-semibold mt-1">Controlled Synthetic Delhi Cases</div>
                </div>
                <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800">
                  <div className="text-2xl font-black text-cyan-400 font-mono">417K+</div>
                  <div className="text-xs text-slate-300 font-semibold mt-1">Candidate-Cluster Samples</div>
                </div>
                <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800">
                  <div className="text-2xl font-black text-blue-400 font-mono">5 Seeds</div>
                  <div className="text-xs text-slate-300 font-semibold mt-1">Random-Seed Experiments</div>
                </div>
              </div>

              <div className="mt-4 text-center">
                <span className="text-[11px] text-amber-300/90 font-medium">
                  PROTOTYPE TRAINING & EVALUATION FIGURES (Not national production statistics)
                </span>
              </div>
            </div>

            {/* Truthful Data Disclosure */}
            <div className="bg-slate-900/90 p-5 rounded-lg border border-slate-800 text-xs text-slate-400 space-y-2">
              <p>
                <strong className="text-slate-200">Data Disclosure:</strong> This prototype is trained and evaluated on controlled synthetic Delhi data.
                Complaint-level NCRP and financial transaction records contain sensitive operational and financial information and were not publicly available to the project team.
                The framework is designed for future retraining on authorized, anonymized operational data when made available by relevant agencies and participating financial institutions.
              </p>
              <p className="text-[11px] text-slate-400">
                Prototype evaluation metrics must not be interpreted as real NCRP production accuracy.
              </p>
            </div>
          </div>
        </section>

        {/* ======================================================================
            8. STAKEHOLDER SECTION
        ====================================================================== */}
        <section className="py-16 sm:py-20 bg-white text-slate-900 border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-14">
              <span className="text-xs font-bold text-blue-700 uppercase tracking-wider">Multi-Agency Ecosystem</span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-2">
                Built for Coordinated Cybercrime Response
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Stakeholder 1 */}
              <div className="p-6 rounded-xl bg-[#F8FAFC] border border-slate-200 hover:border-blue-300 transition-colors flex flex-col justify-between">
                <div>
                  <div className="w-10 h-10 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center mb-4">
                    <Building2 className="w-5 h-5" />
                  </div>
                  <h3 className="text-base font-bold text-slate-900 mb-2">I4C / National Coordination</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Supports cross-jurisdiction intelligence sharing and coordinated cybercrime response across state borders.
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-200 text-[11px] text-blue-700 font-semibold">
                  Strategic Oversight
                </div>
              </div>

              {/* Stakeholder 2 */}
              <div className="p-6 rounded-xl bg-[#F8FAFC] border border-slate-200 hover:border-blue-300 transition-colors flex flex-col justify-between">
                <div>
                  <div className="w-10 h-10 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center mb-4">
                    <Users className="w-5 h-5" />
                  </div>
                  <h3 className="text-base font-bold text-slate-900 mb-2">State & Local LEAs</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Helps investigators prioritize likely cash-out zones and coordinate timely field intervention and ATM intercept units.
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-200 text-[11px] text-indigo-700 font-semibold">
                  Field Enforcement
                </div>
              </div>

              {/* Stakeholder 3 */}
              <div className="p-6 rounded-xl bg-[#F8FAFC] border border-slate-200 hover:border-blue-300 transition-colors flex flex-col justify-between">
                <div>
                  <div className="w-10 h-10 rounded-lg bg-cyan-100 text-cyan-700 flex items-center justify-center mb-4">
                    <Landmark className="w-5 h-5" />
                  </div>
                  <h3 className="text-base font-bold text-slate-900 mb-2">Banks / Financial Institutions</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Supports faster contextual alerts and coordination for potential fund protection, rapid account lien, and recovery.
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-200 text-[11px] text-cyan-700 font-semibold">
                  Asset Protection
                </div>
              </div>
            </div>

            {/* Stakeholder Action */}
            <div className="mt-12 text-center">
              <p className="text-xs text-slate-500 mb-3">Access the investigator workspace</p>
              <button
                onClick={() => navigate('/login')}
                className="px-6 py-2.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-sm transition-colors inline-flex items-center space-x-2"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Officer Login</span>
              </button>
            </div>
          </div>
        </section>

        {/* ======================================================================
            9. I4C NATIONAL COMMAND — CONTROLLED PILOT LOGIN SECTION
        ====================================================================== */}
        <section id="pilot-access" className="py-16 sm:py-20 bg-[#0B172B] text-white border-b border-[#1E3A60]">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="bg-gradient-to-b from-[#13284A] to-[#0F1E36] rounded-2xl border border-blue-500/40 p-6 sm:p-10 shadow-2xl relative">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-700/80 pb-4 mb-6">
                <div>
                  <span className="text-xs font-bold text-blue-400 uppercase tracking-wider block">Authorized Prototype Access</span>
                  <h2 className="text-2xl font-bold text-white mt-1">I4C National Command</h2>
                  <p className="text-xs text-slate-300 mt-0.5">Controlled Pilot Access</p>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="px-2.5 py-1 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    CONTROLLED PILOT ENVIRONMENT
                  </span>
                  <span className="px-2.5 py-1 rounded text-[10px] font-semibold bg-blue-900/60 text-blue-300 border border-blue-700/50">
                    SYNTHETIC DEMONSTRATION DATA
                  </span>
                </div>
              </div>

              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed mb-6">
                Access the CyberShield AI Delhi Pilot investigation environment to explore case intelligence, trained ML predictions,
                transaction graphs, case-focused risk mapping and alert workflows.
              </p>

              {/* Controlled Pilot Credentials Box */}
              <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-700/80 mb-6">
                <div className="flex items-center justify-between mb-3 text-xs font-semibold text-slate-300">
                  <span className="flex items-center space-x-1.5">
                    <KeyRound className="w-3.5 h-3.5 text-blue-400" />
                    <span>Dedicated Pilot Evaluation Account</span>
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">Non-Production / Synthetic Only</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="p-2.5 rounded bg-slate-800/80 border border-slate-700">
                    <span className="text-[10px] text-slate-400 block">Pilot Role</span>
                    <span className="font-semibold text-white">I4C National Command</span>
                  </div>
                  <div className="p-2.5 rounded bg-slate-800/80 border border-slate-700">
                    <span className="text-[10px] text-slate-400 block">Email</span>
                    <span className="font-mono text-cyan-300 font-semibold">{DEMO_CREDENTIALS.I4C_ADMIN.email}</span>
                  </div>
                  <div className="p-2.5 rounded bg-slate-800/80 border border-slate-700">
                    <span className="text-[10px] text-slate-400 block">Password</span>
                    <span className="font-mono text-cyan-300 font-semibold">{DEMO_CREDENTIALS.I4C_ADMIN.pass}</span>
                  </div>
                  <div className="p-2.5 rounded bg-slate-800/80 border border-slate-700">
                    <span className="text-[10px] text-slate-400 block">Environment</span>
                    <span className="font-medium text-slate-200">Delhi Pilot • Controlled Synthetic Data</span>
                  </div>
                </div>
              </div>

              {/* Login Actions */}
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={handleControlledPilotLogin}
                  className="px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs shadow-md transition-colors flex items-center space-x-2"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>Sign in to Controlled Pilot</span>
                </button>

                <button
                  type="button"
                  onClick={() => navigate('/login')}
                  className="px-5 py-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs border border-slate-700 transition-colors flex items-center space-x-1.5"
                >
                  <Lock className="w-3.5 h-3.5" />
                  <span>Access Controlled Pilot</span>
                </button>

                <button
                  type="button"
                  onClick={() => navigate('/login')}
                  className="px-5 py-3 rounded-lg bg-transparent hover:bg-slate-800/50 text-slate-300 font-medium text-xs border border-slate-700/60 transition-colors"
                >
                  Standard Officer Login
                </button>
              </div>

              <p className="text-[11px] text-slate-400 mt-4">
                Controlled pilot credentials provide access to synthetic demonstration data only.
              </p>
            </div>
          </div>
        </section>

        {/* ======================================================================
            10. SECURITY BY DESIGN
        ====================================================================== */}
        <section id="security" className="py-16 sm:py-20 bg-[#0E1E38] text-white border-b border-[#1E3A60]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-14">
              <span className="text-xs font-bold text-blue-400 uppercase tracking-wider">Zero Trust Architecture</span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-white mt-2">
                Designed Around Controlled Investigator Access
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Card 1 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D]">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">Role-Based Access</h3>
                  <InfoPopover
                    title="Role-Based Access"
                    content="Strict authorization gates ensuring LEA officers, bank fraud analysts, and auditors only access permitted operational scopes."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Authenticated role-scoped investigator workflows.
                </p>
              </div>

              {/* Card 2 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D]">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">Case-Scoped Intelligence</h3>
                  <InfoPopover
                    title="Case Isolation"
                    content="Case transactions, evidence files, and predictive rankings are isolated within rigorous case-boundary perimeters."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Case-specific transaction and withdrawal attribution.
                </p>
              </div>

              {/* Card 3 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D]">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">Prediction Provenance</h3>
                  <InfoPopover
                    title="Prediction Provenance"
                    content="Every inference captures model version, feature vector schema, hash integrity, and local LIME fidelity metrics."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Every prediction identifies its inference mode and model version.
                </p>
              </div>

              {/* Card 4 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D]">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">Audit Trail</h3>
                  <InfoPopover
                    title="Audit Verification"
                    content="Operational actions, status transitions, and prediction generation are written to an append-only audit trail."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Operational actions and evidence lifecycle remain visible.
                </p>
              </div>

              {/* Card 5 */}
              <div className="p-6 rounded-xl bg-[#142646] border border-[#23426D]">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">Secure Streaming</h3>
                  <InfoPopover
                    title="Secure Streaming"
                    content="Real-time alert channels utilize short-lived single-use authentication tokens to protect live WebSocket telemetry."
                  />
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Short-lived WebSocket authentication tickets protect streaming sessions.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================================
            11. SECONDARY OFFICER LOGIN BAND
        ====================================================================== */}
        <section className="py-6 bg-[#162D50] border-b border-[#254A78]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center space-x-3 text-center sm:text-left">
              <Shield className="w-5 h-5 text-blue-400 shrink-0 hidden sm:block" />
              <div>
                <span className="text-xs font-bold text-white uppercase tracking-wide">Authorized Investigator?</span>
                <p className="text-xs text-slate-300">Continue to the secure CyberShield workspace.</p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <span className="text-[11px] text-slate-400 hidden md:block">Role-based access • Delhi Pilot</span>
              <button
                onClick={() => navigate('/login')}
                className="px-5 py-2 rounded-md bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs shadow-sm transition-colors flex items-center space-x-1.5"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Officer Login</span>
              </button>
            </div>
          </div>
        </section>

        {/* ======================================================================
            12. FINAL CTA SECTION (DARK NAVY FULL-WIDTH)
        ====================================================================== */}
        <section className="py-16 sm:py-20 bg-[#081220] text-white">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
            <div className="w-12 h-12 rounded-xl bg-blue-600/20 text-blue-400 flex items-center justify-center mx-auto border border-blue-500/30">
              <Shield className="w-6 h-6" />
            </div>

            <h2 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-white tracking-tight">
              Turn Cybercrime Complaints into Proactive Intelligence.
            </h2>

            <p className="text-xs sm:text-sm text-slate-300 max-w-2xl mx-auto leading-relaxed">
              Access CyberShield AI's investigation workspace, predictive cash-out location ranking and case-focused risk mapping.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                onClick={() => navigate('/login')}
                className="px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs shadow-lg shadow-blue-600/20 transition-all flex items-center space-x-2"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Officer Login</span>
              </button>

              <button
                onClick={() => scrollToSection('pilot-access')}
                className="px-6 py-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs border border-slate-700 transition-all"
              >
                Controlled Pilot Access
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* ======================================================================
          13. FOOTER
      ====================================================================== */}
      <footer className="bg-[#050C16] border-t border-[#132237] py-12 text-slate-400 text-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-8 mb-8 pb-8 border-b border-slate-800/80">
            <div className="md:col-span-6 space-y-2">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-bold text-white">CyberShield AI</span>
                <span className="text-[10px] text-blue-400 font-semibold">Delhi Pilot • Controlled Prototype</span>
              </div>
              <p className="text-xs text-slate-400 max-w-md">
                Predictive Cybercrime Intelligence & Financial Interception Platform
              </p>
            </div>

            <div className="md:col-span-6 flex flex-wrap gap-4 sm:gap-6 justify-start md:justify-end items-center text-xs">
              <button onClick={() => scrollToSection('platform')} className="hover:text-white transition-colors">
                Platform
              </button>
              <button onClick={() => scrollToSection('how-it-works')} className="hover:text-white transition-colors">
                How It Works
              </button>
              <button onClick={() => scrollToSection('capabilities')} className="hover:text-white transition-colors">
                Capabilities
              </button>
              <button onClick={() => scrollToSection('security')} className="hover:text-white transition-colors">
                Security
              </button>
              <button onClick={() => scrollToSection('transparency')} className="hover:text-white transition-colors">
                Model Transparency
              </button>
              <button onClick={() => navigate('/login')} className="text-blue-400 hover:text-blue-300 font-semibold transition-colors">
                Officer Login
              </button>
            </div>
          </div>

          <div className="text-[11px] text-slate-500 leading-relaxed text-center md:text-left">
            Prototype developed for predictive cybercrime analytics. Demonstration and model evaluation data are controlled synthetic data unless explicitly identified otherwise.
          </div>
        </div>
      </footer>
    </div>
  );
};
