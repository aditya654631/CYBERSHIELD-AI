import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Plus,
  Search,
  Filter,
  Eye,
  BrainCircuit,
  Network,
  X,
  ShieldAlert,
  ArrowUpDown,
  Calendar,
  DollarSign,
  CheckCircle2
} from 'lucide-react';
import { api } from '../services/api';
import { Complaint } from '../types';
import { formatRisk } from '../utils/formatters';

export const Complaints: React.FC = () => {
  const navigate = useNavigate();
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [fraudType, setFraudType] = useState('ALL');
  const [riskLevel, setRiskLevel] = useState('ALL');

  // Create Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newFraudType, setNewFraudType] = useState('Investment Scam');
  const [newAmount, setNewAmount] = useState('85000');
  const [newLocation, setNewLocation] = useState('MP Nagar, Bhopal');
  const [newChannel, setNewChannel] = useState('UPI');
  const [newVictimName, setNewVictimName] = useState('Arun Patil');
  const [creating, setCreating] = useState(false);

  const fetchComplaints = async () => {
    setLoading(true);
    try {
      const data = await api.getComplaints({
        fraud_type: fraudType !== 'ALL' ? fraudType : undefined,
        risk_level: riskLevel !== 'ALL' ? riskLevel : undefined,
        search: search.trim() || undefined,
      });
      setComplaints(data);
    } catch (err) {
      console.error('Failed to load complaints', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchComplaints();
  }, [fraudType, riskLevel]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchComplaints();
  };

  const handleCreateComplaint = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const created = await api.createComplaint({
        fraud_type: newFraudType,
        amount: parseFloat(newAmount),
        victim_location: newLocation,
        payment_channel: newChannel,
        victim_name: newVictimName,
      });
      setIsModalOpen(false);
      // Refresh complaints and navigate to case
      await fetchComplaints();
      navigate(`/cases/${created.complaint_number}`);
    } catch (err) {
      console.error('Failed to create complaint', err);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header with Create Demo Complaint Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <FileText className="w-5 h-5 text-cyan-400" />
            <h1 className="text-xl font-bold text-white font-['JetBrains_Mono',monospace]">
              Incident Complaint Management
            </h1>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Surveillance ledger of registered cybercrime and mule-layering reports
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2.5 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-mono font-bold rounded-xl flex items-center space-x-2 shadow-[0_0_15px_rgba(0,216,255,0.3)] transition-all shrink-0"
        >
          <Plus className="w-4 h-4" />
          <span>+ REGISTER NEW COMPLAINT</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 bg-[#0a1020] rounded-2xl border border-[#162544] flex flex-wrap items-center justify-between gap-4 shadow-xl">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 min-w-[280px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search Complaint Number (e.g. CMP-1042), Location, Victim..."
            className="w-full pl-10 pr-4 py-2 bg-[#070c18] border border-[#1b2b4d] rounded-lg text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:border-cyan-400 font-mono"
          />
        </form>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-2 bg-[#070c18] px-3 py-1.5 rounded-lg border border-[#162544]">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={fraudType}
              onChange={(e) => setFraudType(e.target.value)}
              className="bg-transparent text-xs text-slate-200 focus:outline-none font-mono cursor-pointer"
            >
              <option value="ALL">All Fraud Modus</option>
              <option value="Investment">Investment Scam</option>
              <option value="UPI">UPI Fraud</option>
              <option value="Digital Arrest">Digital Arrest</option>
              <option value="Job">Part-time Job</option>
            </select>
          </div>

          <div className="flex items-center space-x-2 bg-[#070c18] px-3 py-1.5 rounded-lg border border-[#162544]">
            <select
              value={riskLevel}
              onChange={(e) => setRiskLevel(e.target.value)}
              className="bg-transparent text-xs text-slate-200 focus:outline-none font-mono cursor-pointer"
            >
              <option value="ALL">All Risk Levels</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
            </select>
          </div>
        </div>
      </div>

      {/* Complaints Table */}
      <div className="bg-[#0a1020] rounded-2xl border border-[#162544] overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[#070c18] text-slate-400 uppercase tracking-wider border-b border-[#162544]">
              <tr>
                <th className="py-3.5 px-4">Complaint ID</th>
                <th className="py-3.5 px-4">Fraud Type</th>
                <th className="py-3.5 px-4">Amount</th>
                <th className="py-3.5 px-4">Victim Location</th>
                <th className="py-3.5 px-4">Payment Channel</th>
                <th className="py-3.5 px-4">Risk Level</th>
                <th className="py-3.5 px-4">Prediction Status</th>
                <th className="py-3.5 px-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#162544] text-slate-300">
              {complaints.map((c) => {
                const is1042 = c.complaint_number === 'CMP-1042';
                return (
                  <tr
                    key={c.id}
                    className={`hover:bg-[#0d162d] transition-colors ${
                      is1042 ? 'bg-[#0e1b38]/50 border-l-4 border-l-cyan-400' : ''
                    }`}
                  >
                    <td className="py-3.5 px-4 font-bold text-cyan-300">
                      <div className="flex items-center space-x-1.5">
                        <span>{c.complaint_number}</span>
                        {is1042 && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                            DEMO
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-200">{c.fraud_type}</td>
                    <td className="py-3.5 px-4 font-bold text-emerald-400">
                      ₹{c.amount.toLocaleString('en-IN')}
                    </td>
                    <td className="py-3.5 px-4 text-slate-300 truncate max-w-[160px]">
                      {c.victim_location}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="px-2 py-0.5 rounded bg-[#162544] text-slate-300">
                        {c.payment_channel}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                          c.risk_level === 'CRITICAL'
                            ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                            : c.risk_level === 'HIGH'
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                            : 'bg-blue-500/20 text-blue-400 border border-blue-500/40'
                        }`}
                      >
                        {c.risk_level} ({formatRisk(c.risk_score)})
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`text-[10px] font-bold ${
                          c.prediction_status === 'COMPLETED'
                            ? 'text-emerald-400'
                            : 'text-amber-400'
                        }`}
                      >
                        {c.prediction_status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => navigate(`/cases/${c.complaint_number}`)}
                          title="Open Case Intelligence"
                          className="p-1.5 rounded bg-cyan-500/10 text-cyan-300 hover:bg-cyan-500/20 transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => navigate(`/cases/${c.complaint_number}`)}
                          title="Run Prediction"
                          className="p-1.5 rounded bg-purple-500/10 text-purple-300 hover:bg-purple-500/20 transition-colors"
                        >
                          <BrainCircuit className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => navigate(`/network/${c.complaint_number}`)}
                          title="View Network"
                          className="p-1.5 rounded bg-blue-500/10 text-blue-300 hover:bg-blue-500/20 transition-colors"
                        >
                          <Network className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* CREATE DEMO COMPLAINT MODAL */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0a1020] border border-cyan-500/50 rounded-2xl p-6 w-full max-w-md shadow-2xl relative">
            <div className="flex items-center justify-between pb-3 border-b border-[#162544] mb-4">
              <div className="flex items-center space-x-2">
                <Plus className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-bold text-white font-mono uppercase">
                  Register Cyber Incident Complaint
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateComplaint} className="space-y-4 font-mono text-xs">
              <div>
                <label className="block text-slate-300 mb-1">Victim Name</label>
                <input
                  type="text"
                  value={newVictimName}
                  onChange={(e) => setNewVictimName(e.target.value)}
                  className="w-full px-3 py-2 bg-[#070c18] border border-[#1b2b4d] rounded-lg text-slate-200 focus:outline-none focus:border-cyan-400"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Fraud Type Modus</label>
                <select
                  value={newFraudType}
                  onChange={(e) => setNewFraudType(e.target.value)}
                  className="w-full px-3 py-2 bg-[#070c18] border border-[#1b2b4d] rounded-lg text-slate-200 focus:outline-none focus:border-cyan-400 cursor-pointer"
                >
                  <option value="Investment Scam">Investment Scam</option>
                  <option value="UPI / QR Code Fraud">UPI / QR Code Fraud</option>
                  <option value="Digital Arrest / Sextortion">Digital Arrest / Sextortion</option>
                  <option value="Part-time Job Fraud">Part-time Job Fraud</option>
                  <option value="Loan App Extortion">Loan App Extortion</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Amount Siphoned (INR)</label>
                <input
                  type="number"
                  value={newAmount}
                  onChange={(e) => setNewAmount(e.target.value)}
                  className="w-full px-3 py-2 bg-[#070c18] border border-[#1b2b4d] rounded-lg text-emerald-400 font-bold focus:outline-none focus:border-cyan-400"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Incident Location (City / District)</label>
                <input
                  type="text"
                  value={newLocation}
                  onChange={(e) => setNewLocation(e.target.value)}
                  placeholder="e.g. MP Nagar, Bhopal"
                  className="w-full px-3 py-2 bg-[#070c18] border border-[#1b2b4d] rounded-lg text-slate-200 focus:outline-none focus:border-cyan-400"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Payment Channel</label>
                <select
                  value={newChannel}
                  onChange={(e) => setNewChannel(e.target.value)}
                  className="w-full px-3 py-2 bg-[#070c18] border border-[#1b2b4d] rounded-lg text-slate-200 focus:outline-none focus:border-cyan-400 cursor-pointer"
                >
                  <option value="UPI">UPI (Immediate)</option>
                  <option value="IMPS">IMPS</option>
                  <option value="NEFT">NEFT</option>
                  <option value="NetBanking">NetBanking</option>
                </select>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={creating}
                  className="w-full py-2.5 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold rounded-lg shadow-lg flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
                >
                  <span>{creating ? 'REGISTERING...' : 'REGISTER & TRIGGER INFERENCE'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
