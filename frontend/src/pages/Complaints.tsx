import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Plus,
  Search,
  Filter,
  Eye,
  X,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  CheckCircle2,
  Clock,
  ArrowUpDown,
  Building2,
  MapPin,
  CreditCard,
  Network
} from 'lucide-react';
import { api } from '../services/api';
import { Complaint, HotspotCluster } from '../types';
import { apiErrorMessage, toLocalDateTimeInput } from '../utils/predictionDisplay';

export const Complaints: React.FC = () => {
  const navigate = useNavigate();

  // Data state
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [totalRecords, setTotalRecords] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Filter state
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [caseStatus, setCaseStatus] = useState('ALL');
  const [fraudType, setFraudType] = useState('ALL');
  const [district, setDistrict] = useState('ALL');
  const [predictionStatus, setPredictionStatus] = useState('ALL');
  const [alertStatus, setAlertStatus] = useState('ALL');

  // Highlight state for newly registered complaint
  const [newlyCreatedNumber, setNewlyCreatedNumber] = useState<string | null>(null);

  // Registration Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [registrationPhase, setRegistrationPhase] = useState('Registering...');
  const [locationCatalog, setLocationCatalog] = useState<HotspotCluster[]>([]);

  // Modal Form Inputs: Section A - Complaint Details
  const [newVictimName, setNewVictimName] = useState('Aman Sharma');
  const [newFraudType, setNewFraudType] = useState('Investment Scam');
  const [newAmount, setNewAmount] = useState('85000');
  const [newIncidentTime, setNewIncidentTime] = useState(() => toLocalDateTimeInput(new Date(Date.now() - 3600000 * 2)));
  const [newReportedAt, setNewReportedAt] = useState(() => toLocalDateTimeInput());
  const [newDescription, setNewDescription] = useState('Victim deceived into transferring funds through fraudulent investment platform.');

  // Section B - Location (Delhi Pilot)
  const [newDistrict, setNewDistrict] = useState('South West Delhi');
  const [newLocality, setNewLocality] = useState('Dwarka');
  const [newVictimLat, setNewVictimLat] = useState('');
  const [newVictimLon, setNewVictimLon] = useState('');

  // Section C - Transaction Details
  const [newChannel, setNewChannel] = useState('UPI');
  const [newVictimBank, setNewVictimBank] = useState('State Bank of India');
  const [newBeneficiaryBank, setNewBeneficiaryBank] = useState('HDFC Bank');
  const [newBeneficiaryId, setNewBeneficiaryId] = useState('mule.recipient@okhdfcbank');
  const [newTransactionRef, setNewTransactionRef] = useState(() => `UTR-DL-${Date.now().toString().slice(-6)}`);
  const [newTransactionTime, setNewTransactionTime] = useState(() => toLocalDateTimeInput(new Date(Date.now() - 3600000 * 2)));
  const [newIfsc, setNewIfsc] = useState('');
  const [newBeneficiaryAccount, setNewBeneficiaryAccount] = useState('');
  const [newBeneficiaryUpi, setNewBeneficiaryUpi] = useState('');
  const [newPhoneOrMerchant, setNewPhoneOrMerchant] = useState('');
  const [newAdditionalRefs, setNewAdditionalRefs] = useState('');
  const [newDemoMode, setNewDemoMode] = useState(false);

  useEffect(() => {
    api.getClusters().then(setLocationCatalog).catch(() => setLocationCatalog([]));
  }, []);

  const districtLocalities = locationCatalog.filter((location) => location.district === newDistrict);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Load complaints from PostgreSQL via backend API
  const fetchComplaints = useCallback(async (targetPage = page) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getComplaintsRegistry({
        search: debouncedSearch.trim() || undefined,
        case_status: caseStatus !== 'ALL' ? caseStatus : undefined,
        fraud_type: fraudType !== 'ALL' ? fraudType : undefined,
        district: district !== 'ALL' ? district : undefined,
        prediction_status: predictionStatus !== 'ALL' ? predictionStatus : undefined,
        alert_status: alertStatus !== 'ALL' ? alertStatus : undefined,
        page: targetPage,
        limit: pageSize,
        state: 'Delhi',
      });
      setComplaints(data.complaints);
      setTotalRecords(data.total);
      setTotalPages(data.totalPages);
      setPage(data.page);
    } catch (err: any) {
      console.error('Failed to load registered complaints', err);
      setError('Unable to load registered complaints from database. Please check connection and retry.');
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, caseStatus, fraudType, district, predictionStatus, alertStatus, pageSize, page]);

  useEffect(() => {
    fetchComplaints(page);
  }, [debouncedSearch, caseStatus, fraudType, district, predictionStatus, alertStatus, page]);

  // Handle Search Submission
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchComplaints(1);
  };

  // Reset Filters
  const handleResetFilters = () => {
    setSearch('');
    setDebouncedSearch('');
    setCaseStatus('ALL');
    setFraudType('ALL');
    setDistrict('ALL');
    setPredictionStatus('ALL');
    setAlertStatus('ALL');
    setPage(1);
  };

  // Register New Complaint Mutation
  const handleCreateComplaint = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setRegistrationPhase('Registering...');
    setFormError(null);
    try {
      const latVal = newVictimLat.trim() ? parseFloat(newVictimLat.trim()) : null;
      const lonVal = newVictimLon.trim() ? parseFloat(newVictimLon.trim()) : null;
      if ((latVal == null) !== (lonVal == null)) throw new Error('Enter both latitude and longitude, or leave both empty.');
      if (latVal != null && (!Number.isFinite(latVal) || latVal < -90 || latVal > 90 || !Number.isFinite(lonVal) || lonVal! < -180 || lonVal! > 180)) {
        throw new Error('Enter valid latitude and longitude coordinates.');
      }
      if (!newLocality.trim()) throw new Error('Enter a Delhi locality.');
      if (newIncidentTime && newReportedAt && new Date(newIncidentTime) > new Date(newReportedAt)) throw new Error('Reported time must be on or after incident time.');
      if (newTransactionTime && newReportedAt && new Date(newTransactionTime) > new Date(newReportedAt)) throw new Error('Transaction time must be on or before reported time.');

      const created = await api.createComplaint({
        victim_name: newVictimName.trim(),
        fraud_type: newFraudType,
        amount: parseFloat(newAmount),
        incident_time: newIncidentTime ? new Date(newIncidentTime).toISOString() : undefined,
        reported_at: newReportedAt ? new Date(newReportedAt).toISOString() : undefined,
        description: newDescription.trim(),
        state: 'Delhi',
        district: newDistrict,
        locality: newLocality.trim(),
        victim_location: `${newLocality.trim()}, ${newDistrict}, Delhi`,
        victim_lat: latVal,
        victim_lon: lonVal,
        payment_channel: newChannel,
        victim_bank: newVictimBank.trim(),
        beneficiary_bank: newBeneficiaryBank.trim(),
        beneficiary_id: newBeneficiaryId.trim(),
        transaction_ref: newTransactionRef.trim(),
        transaction_time: newTransactionTime ? new Date(newTransactionTime).toISOString() : undefined,
        ifsc_code: newIfsc.trim() || undefined,
        beneficiary_account: newBeneficiaryAccount.trim() || undefined,
        beneficiary_upi: newBeneficiaryUpi.trim() || undefined,
        phone_or_merchant: newPhoneOrMerchant.trim() || undefined,
        additional_refs: newAdditionalRefs.trim() || undefined,
        demo_mode: newDemoMode,
      });

      // Auto-Prediction Orchestration: Complaint persistence must remain successful even if prediction fails
      let analysisError: string | null = null;
      setRegistrationPhase('Predicting top 3 locations...');
      try {
        await api.runPrediction(created.complaint_number);
      } catch (predErr) {
        analysisError = apiErrorMessage(predErr, 'Complaint saved. Automatic analysis failed; use Run Predictive Analysis to retry.');
        console.warn('[Auto-Prediction] Prediction execution skipped/failed, case remains safely persisted:', predErr);
      }

      // Close modal
      setIsModalOpen(false);

      // Section 3: Immediately redirect to /cases/{complaint_number}
      navigate(`/cases/${created.complaint_number}`, { state: { analysisError } });
    } catch (err: any) {
      console.error('Failed to register complaint', err);
      setFormError(apiErrorMessage(err, err?.message || 'Failed to register complaint'));
    } finally {
      setCreating(false);
    }
  };

  // Helper formatting for timestamps
  const formatDateTime = (isoString?: string) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    } catch {
      return isoString;
    }
  };

  // Badges styling
  const renderPredictionBadge = (status?: string) => {
    const s = (status || 'NOT RUN').toUpperCase();
    if (s === 'AVAILABLE' || s === 'COMPLETED') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          AVAILABLE
        </span>
      );
    }
    if (s === 'PROCESSING' || s === 'IN_PROGRESS') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          PROCESSING
        </span>
      );
    }
    if (s === 'UNAVAILABLE' || s === 'FAILED') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-red-50 text-red-700 border border-red-200">
          UNAVAILABLE
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
        NOT RUN
      </span>
    );
  };

  const renderAlertBadge = (status?: string) => {
    const s = (status || 'NOT GENERATED').toUpperCase();
    if (s === 'ACKNOWLEDGED') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          ACKNOWLEDGED
        </span>
      );
    }
    if (s === 'GENERATED' || s === 'NEW' || s === 'ACTIVE') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-orange-50 text-orange-700 border border-orange-200">
          GENERATED
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
        NOT GENERATED
      </span>
    );
  };

  const renderCaseStatusBadge = (status?: string) => {
    const s = (status || 'ACTIVE').replace(/_/g, ' ').toUpperCase();
    if (s === 'ACTIVE') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200">
          ACTIVE
        </span>
      );
    }
    if (s.includes('INVESTIGATION')) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
          UNDER INVESTIGATION
        </span>
      );
    }
    if (s === 'ALERTED') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200">
          ALERTED
        </span>
      );
    }
    if (s === 'CLOSED' || s === 'RESOLVED') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
          {s}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
        {s}
      </span>
    );
  };

  return (
    <div className="space-y-4 pb-12">
      {/* Header Section */}
      <div className="bg-white border border-[#DCE5F0] rounded-lg p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-md bg-blue-50 text-blue-600 border border-blue-200">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-[#173A63] tracking-tight">
                Complaints Registry
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Delhi Pilot Operational Law Enforcement Case Intake & Surveillance Registry
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={() => {
            setFormError(null);
            setIsModalOpen(true);
          }}
          className="inline-flex items-center justify-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded shadow-xs transition-colors shrink-0 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>+ REGISTER COMPLAINT</span>
        </button>
      </div>

      {/* Operational Search & Filter Bar */}
      <div className="bg-white border border-[#DCE5F0] rounded-lg p-4 shadow-xs space-y-3">
        <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
          {/* Search Input */}
          <form onSubmit={handleSearchSubmit} className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by Complaint Number (e.g. CMP-NEW-000418), Victim, Locality, or UTR..."
              className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-300 rounded text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white transition-colors"
            />
          </form>

          {/* Reset Filters button */}
          {(search || caseStatus !== 'ALL' || fraudType !== 'ALL' || district !== 'ALL' || predictionStatus !== 'ALL' || alertStatus !== 'ALL') && (
            <button
              onClick={handleResetFilters}
              className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded border border-slate-200 transition-colors shrink-0"
              title="Reset all filters"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset Filters</span>
            </button>
          )}
        </div>

        {/* Operational Filter Dropdowns */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2.5 pt-1">
          {/* Filter: Case Status */}
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Case Status
            </label>
            <select
              value={caseStatus}
              onChange={(e) => {
                setCaseStatus(e.target.value);
                setPage(1);
              }}
              className="w-full px-2 py-1.5 bg-slate-50 border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
            >
              <option value="ALL">All Case Status</option>
              <option value="ACTIVE">Active</option>
              <option value="UNDER_INVESTIGATION">Under Investigation</option>
              <option value="ALERTED">Alerted</option>
              <option value="RESOLVED">Resolved / Closed</option>
            </select>
          </div>

          {/* Filter: Fraud Types */}
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Fraud Type
            </label>
            <select
              value={fraudType}
              onChange={(e) => {
                setFraudType(e.target.value);
                setPage(1);
              }}
              className="w-full px-2 py-1.5 bg-slate-50 border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
            >
              <option value="ALL">All Fraud Types</option>
              <option value="Investment">Investment Scam</option>
              <option value="UPI">UPI / QR Fraud</option>
              <option value="Digital Arrest">Digital Arrest</option>
              <option value="Job">Part-time Job</option>
              <option value="Loan">Loan App Extortion</option>
              <option value="Phishing">Impersonation / Phishing</option>
            </select>
          </div>

          {/* Filter: Districts */}
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Delhi District
            </label>
            <select
              value={district}
              onChange={(e) => {
                setDistrict(e.target.value);
                setPage(1);
              }}
              className="w-full px-2 py-1.5 bg-slate-50 border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
            >
              <option value="ALL">All Districts</option>
              <option value="Central Delhi">Central Delhi</option>
              <option value="East Delhi">East Delhi</option>
              <option value="New Delhi">New Delhi</option>
              <option value="North Delhi">North Delhi</option>
              <option value="North East Delhi">North East Delhi</option>
              <option value="North West Delhi">North West Delhi</option>
              <option value="Shahdara">Shahdara</option>
              <option value="South Delhi">South Delhi</option>
              <option value="South East Delhi">South East Delhi</option>
              <option value="South West Delhi">South West Delhi</option>
              <option value="West Delhi">West Delhi</option>
            </select>
          </div>

          {/* Filter: Prediction Status */}
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Prediction Status
            </label>
            <select
              value={predictionStatus}
              onChange={(e) => {
                setPredictionStatus(e.target.value);
                setPage(1);
              }}
              className="w-full px-2 py-1.5 bg-slate-50 border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
            >
              <option value="ALL">All Predictions</option>
              <option value="NOT RUN">NOT RUN</option>
              <option value="AVAILABLE">AVAILABLE</option>
            </select>
          </div>

          {/* Filter: Alert Status */}
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Alert Status
            </label>
            <select
              value={alertStatus}
              onChange={(e) => {
                setAlertStatus(e.target.value);
                setPage(1);
              }}
              className="w-full px-2 py-1.5 bg-slate-50 border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
            >
              <option value="ALL">All Alerts</option>
              <option value="NOT GENERATED">NOT GENERATED</option>
              <option value="GENERATED">GENERATED</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Table Surface */}
      <div className="bg-white border border-[#DCE5F0] rounded-lg shadow-xs overflow-hidden">
        {/* Desktop Table View (>= md) */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-3.5 whitespace-nowrap">Case ID</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Victim</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Fraud Type</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Amount</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Location</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Channel</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Prediction</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Alert</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Case Status</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Reported</th>
                <th className="py-3 px-3.5 text-right whitespace-nowrap">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-800">
              {loading ? (
                // Table Skeleton
                Array.from({ length: 8 }).map((_, idx) => (
                  <tr key={`skel-${idx}`} className="animate-pulse">
                    <td className="py-3.5 px-3.5">
                      <div className="h-4 bg-slate-200 rounded w-24" />
                    </td>
                    <td className="py-3.5 px-3.5">
                      <div className="h-4 bg-slate-200 rounded w-28" />
                    </td>
                    <td className="py-3.5 px-3.5">
                      <div className="h-4 bg-slate-200 rounded w-24" />
                    </td>
                    <td className="py-3.5 px-3.5">
                      <div className="h-4 bg-slate-200 rounded w-16" />
                    </td>
                    <td className="py-3.5 px-3.5">
                      <div className="h-4 bg-slate-200 rounded w-32" />
                    </td>
                    <td className="py-3.5 px-3.5">
                      <div className="h-4 bg-slate-200 rounded w-12" />
                    </td>
                    <td className="py-3.5 px-3.5">
                      <div className="h-4 bg-slate-200 rounded w-16" />
                    </td>
                    <td className="py-3.5 px-3.5">
                      <div className="h-4 bg-slate-200 rounded w-20" />
                    </td>
                    <td className="py-3.5 px-3.5">
                      <div className="h-4 bg-slate-200 rounded w-16" />
                    </td>
                    <td className="py-3.5 px-3.5">
                      <div className="h-4 bg-slate-200 rounded w-24" />
                    </td>
                    <td className="py-3.5 px-3.5 text-right">
                      <div className="h-6 bg-slate-200 rounded w-20 ml-auto" />
                    </td>
                  </tr>
                ))
              ) : error ? (
                // Error State
                <tr>
                  <td colSpan={11} className="py-12 px-4 text-center">
                    <div className="max-w-md mx-auto flex flex-col items-center space-y-3">
                      <div className="w-10 h-10 rounded-full bg-red-50 text-red-600 flex items-center justify-center border border-red-200">
                        <ShieldAlert className="w-5 h-5" />
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-sm font-semibold text-slate-900">
                          Unable to load registered complaints
                        </h4>
                        <p className="text-xs text-slate-500">{error}</p>
                      </div>
                      <button
                        onClick={() => fetchComplaints(page)}
                        className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded border border-blue-200 transition-colors"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>RETRY</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ) : complaints.length === 0 ? (
                // Empty State
                <tr>
                  <td colSpan={11} className="py-12 px-4 text-center">
                    <div className="max-w-md mx-auto flex flex-col items-center space-y-3">
                      <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center border border-slate-200">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-sm font-semibold text-slate-900">
                          No registered Delhi complaints found
                        </h4>
                        <p className="text-xs text-slate-500">
                          No operational cases match the specified search and filter parameters.
                        </p>
                      </div>
                      <button
                        onClick={() => {
                          setFormError(null);
                          setIsModalOpen(true);
                        }}
                        className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded shadow-xs transition-colors"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>+ REGISTER COMPLAINT</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                // Rows
                complaints.map((c) => {
                  const isHighlighted = c.complaint_number === newlyCreatedNumber;
                  return (
                    <tr
                      key={c.id}
                      className={`hover:bg-slate-50/80 transition-colors ${
                        isHighlighted ? 'bg-blue-50/60 border-l-4 border-l-blue-600' : ''
                      }`}
                    >
                      {/* CASE ID */}
                      <td className="py-3 px-3.5 font-mono font-bold text-slate-900 whitespace-nowrap">
                        <button
                          onClick={() => navigate(`/cases/${c.complaint_number}`)}
                          className="hover:text-blue-700 hover:underline transition-colors text-left font-mono"
                          title="Open Case Intelligence"
                        >
                          {c.complaint_number}
                        </button>
                      </td>

                      {/* VICTIM */}
                      <td className="py-3 px-3.5 text-slate-700 whitespace-nowrap">
                        {c.victim_name || 'Anonymous Complainant'}
                      </td>

                      {/* FRAUD TYPE */}
                      <td className="py-3 px-3.5 text-slate-700 whitespace-nowrap">
                        {c.fraud_type}
                      </td>

                      {/* AMOUNT */}
                      <td className="py-3 px-3.5 font-semibold text-slate-900 whitespace-nowrap">
                        ₹{Number(c.amount).toLocaleString('en-IN')}
                      </td>

                      {/* LOCATION */}
                      <td className="py-3 px-3.5 whitespace-nowrap">
                        <div className="flex flex-col">
                          <span className="font-medium text-slate-900">
                            {c.locality || c.victim_location.split(',')[0]}
                          </span>
                          <span className="text-[11px] text-slate-500">
                            {c.district || 'Delhi'}, Delhi
                          </span>
                        </div>
                      </td>

                      {/* CHANNEL */}
                      <td className="py-3 px-3.5 whitespace-nowrap">
                        <span className="px-1.5 py-0.5 rounded text-[11px] font-mono bg-slate-100 text-slate-700 border border-slate-200">
                          {c.payment_channel || 'UPI'}
                        </span>
                      </td>

                      {/* PREDICTION */}
                      <td className="py-3 px-3.5 whitespace-nowrap">
                        {renderPredictionBadge(c.prediction_status)}
                      </td>

                      {/* ALERT */}
                      <td className="py-3 px-3.5 whitespace-nowrap">
                        {renderAlertBadge(c.alert_status)}
                      </td>

                      {/* CASE STATUS */}
                      <td className="py-3 px-3.5 whitespace-nowrap">
                        {renderCaseStatusBadge(c.case_status)}
                      </td>

                      {/* REPORTED */}
                      <td className="py-3 px-3.5 text-slate-600 whitespace-nowrap font-mono text-[11px]">
                        {formatDateTime(c.reported_at)}
                      </td>

                      {/* ACTION */}
                      <td className="py-3 px-3.5 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end space-x-1.5">
                          <button
                            onClick={() => navigate(`/cases/${c.complaint_number}`)}
                            className="px-2.5 py-1 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded transition-colors"
                          >
                            VIEW CASE
                          </button>
                          <button
                            onClick={() => navigate(`/network/${c.complaint_number}`)}
                            title="View Transaction Network"
                            className="p-1 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded border border-transparent hover:border-slate-200 transition-colors"
                          >
                            <Network className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile Card Presentation (< md) */}
        <div className="md:hidden divide-y divide-slate-100">
          {loading ? (
            Array.from({ length: 4 }).map((_, idx) => (
              <div key={`skel-m-${idx}`} className="p-4 animate-pulse space-y-2">
                <div className="h-4 bg-slate-200 rounded w-28" />
                <div className="h-3 bg-slate-200 rounded w-48" />
                <div className="h-3 bg-slate-200 rounded w-36" />
              </div>
            ))
          ) : error ? (
            <div className="p-6 text-center space-y-3">
              <ShieldAlert className="w-6 h-6 text-red-600 mx-auto" />
              <p className="text-xs text-slate-600">{error}</p>
              <button
                onClick={() => fetchComplaints(page)}
                className="px-3 py-1.5 text-xs font-semibold text-blue-700 bg-blue-50 rounded border border-blue-200"
              >
                RETRY
              </button>
            </div>
          ) : complaints.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">
              No registered Delhi complaints found matching filters.
            </div>
          ) : (
            complaints.map((c) => {
              const isHighlighted = c.complaint_number === newlyCreatedNumber;
              return (
                <div
                  key={`m-${c.id}`}
                  className={`p-3.5 space-y-2.5 transition-colors ${
                    isHighlighted ? 'bg-blue-50/60 border-l-4 border-l-blue-600' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <button
                      onClick={() => navigate(`/cases/${c.complaint_number}`)}
                      className="font-mono font-bold text-xs text-blue-700 hover:underline"
                    >
                      {c.complaint_number}
                    </button>
                    {renderCaseStatusBadge(c.case_status)}
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-800">{c.victim_name || 'Anonymous'}</span>
                    <span className="font-bold text-slate-900">₹{Number(c.amount).toLocaleString('en-IN')}</span>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-slate-500">
                    <span>{c.fraud_type} • {c.payment_channel || 'UPI'}</span>
                    <span>{c.locality || c.district || 'Delhi'}</span>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                    {renderPredictionBadge(c.prediction_status)}
                    {renderAlertBadge(c.alert_status)}
                  </div>

                  <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-[11px] text-slate-400">
                    <span>{formatDateTime(c.reported_at)}</span>
                    <div className="flex items-center space-x-1.5">
                      <button
                        onClick={() => navigate(`/cases/${c.complaint_number}`)}
                        className="px-2.5 py-1 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded"
                      >
                        VIEW CASE
                      </button>
                      <button
                        onClick={() => navigate(`/network/${c.complaint_number}`)}
                        title="Transaction Network"
                        className="p-1 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded border border-slate-200"
                      >
                        <Network className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Pagination Bar */}
        {!loading && !error && complaints.length > 0 && (
          <div className="py-3 px-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-600">
            <div>
              Showing{' '}
              <span className="font-semibold text-slate-900">
                {(page - 1) * pageSize + 1}
              </span>{' '}
              to{' '}
              <span className="font-semibold text-slate-900">
                {Math.min(page * pageSize, totalRecords)}
              </span>{' '}
              of{' '}
              <span className="font-semibold text-slate-900">
                {totalRecords.toLocaleString('en-IN')}
              </span>{' '}
              Delhi complaints
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                disabled={page <= 1}
                className="inline-flex items-center space-x-1 px-2.5 py-1 bg-white border border-slate-300 rounded text-slate-700 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Previous</span>
              </button>

              <span className="text-xs font-medium text-slate-700 px-2">
                Page {page} of {totalPages}
              </span>

              <button
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                disabled={page >= totalPages}
                className="inline-flex items-center space-x-1 px-2.5 py-1 bg-white border border-slate-300 rounded text-slate-700 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* OPERATIONAL COMPLAINT REGISTRATION MODAL */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-3 sm:p-4">
          <div className="bg-white border border-slate-300 rounded-lg shadow-xl w-full max-w-3xl max-h-[92vh] sm:max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-slate-50 sticky top-0 z-10">
              <div className="flex items-center space-x-2.5">
                <div className="p-1.5 rounded bg-blue-100 text-blue-700">
                  <Plus className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
                    Register Cyber Incident Complaint
                  </h3>
                  <p className="text-xs text-slate-500">
                    Jurisdiction: Delhi Pilot Enforcement Area
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setIsModalOpen(false);
                  setFormError(null);
                }}
                className="text-slate-400 hover:text-slate-700 p-1 rounded hover:bg-slate-200 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Form Error */}
            {formError && (
              <div className="m-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-xs flex items-center space-x-2">
                <ShieldAlert className="w-4 h-4 shrink-0 text-red-500" />
                <span>{formError}</span>
              </div>
            )}

            {/* Modal Form */}
            <form onSubmit={handleCreateComplaint} className="p-5 space-y-5 text-xs">
              {/* SECTION A: COMPLAINT DETAILS */}
              <div className="p-4 bg-slate-50/70 border border-slate-200 rounded-lg space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
                    <span>SECTION A — COMPLAINT DETAILS</span>
                  </h4>
                  <span className="text-[11px] text-slate-500">Core Incident Dossier</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Victim Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newVictimName}
                      onChange={(e) => setNewVictimName(e.target.value)}
                      placeholder="Full Name of Complainant"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Fraud Type Modus <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={newFraudType}
                      onChange={(e) => setNewFraudType(e.target.value)}
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                      required
                    >
                      <option value="Investment Scam">Investment Scam</option>
                      <option value="UPI / QR Code Fraud">UPI / QR Code Fraud</option>
                      <option value="Digital Arrest / Sextortion">Digital Arrest / Sextortion</option>
                      <option value="Part-time Job Fraud">Part-time Job Fraud</option>
                      <option value="Loan App Extortion">Loan App Extortion</option>
                      <option value="Impersonation / Phishing">Impersonation / Phishing</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Amount Lost (INR) <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="1"
                      value={newAmount}
                      onChange={(e) => setNewAmount(e.target.value)}
                      placeholder="e.g. 85000"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 font-semibold focus:outline-none focus:ring-1 focus:ring-blue-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Incident Date & Time <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="datetime-local"
                      value={newIncidentTime}
                      onChange={(e) => setNewIncidentTime(e.target.value)}
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      required
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-slate-700 font-medium mb-1">
                      Reported Date & Time <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="datetime-local"
                      value={newReportedAt}
                      onChange={(e) => setNewReportedAt(e.target.value)}
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      required
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-slate-700 font-medium mb-1">
                      Complaint Description / Short Narrative <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      rows={2}
                      value={newDescription}
                      onChange={(e) => setNewDescription(e.target.value)}
                      placeholder="Officer notes regarding the victim interview, initial deception vector, and first hop transfer details..."
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                      required
                    />
                  </div>
                </div>
              </div>

              {/* SECTION B: LOCATION (DELHI PILOT) */}
              <div className="p-4 bg-slate-50/70 border border-slate-200 rounded-lg space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
                    <span>SECTION B — LOCATION (DELHI PILOT)</span>
                  </h4>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-medium">
                    State: Delhi (Operational Pilot)
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-700 font-medium mb-1">State</label>
                    <input
                      type="text"
                      value="Delhi"
                      disabled
                      className="w-full px-3 py-1.5 bg-slate-100 border border-slate-200 rounded text-slate-500 cursor-not-allowed font-medium"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Delhi District <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={newDistrict}
                      onChange={(e) => {
                        setNewDistrict(e.target.value);
                        setNewLocality('');
                        setNewVictimLat('');
                        setNewVictimLon('');
                      }}
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                      required
                    >
                      <option value="Central Delhi">Central Delhi</option>
                      <option value="East Delhi">East Delhi</option>
                      <option value="New Delhi">New Delhi</option>
                      <option value="North Delhi">North Delhi</option>
                      <option value="North East Delhi">North East Delhi</option>
                      <option value="North West Delhi">North West Delhi</option>
                      <option value="Shahdara">Shahdara</option>
                      <option value="South Delhi">South Delhi</option>
                      <option value="South East Delhi">South East Delhi</option>
                      <option value="South West Delhi">South West Delhi</option>
                      <option value="West Delhi">West Delhi</option>
                    </select>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-slate-700 font-medium mb-1">
                      Locality / Incident Location <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newLocality}
                      list="delhi-localities"
                      onChange={(e) => {
                        setNewLocality(e.target.value);
                        setNewVictimLat('');
                        setNewVictimLon('');
                      }}
                      placeholder="e.g. Dwarka, Connaught Place, Rohini, Saket"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      required
                    />
                    <datalist id="delhi-localities">
                      {districtLocalities.map((location) => <option key={location.id} value={location.cluster_name} />)}
                    </datalist>
                    <p className="text-[11px] text-slate-500 mt-1">
                      {districtLocalities.length ? `${districtLocalities.length} supported locations in this district. Choose a suggestion for the most precise locality match.` : 'Enter a known Delhi locality; analysis uses the Delhi location catalog.'}
                    </p>
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Victim Latitude <span className="text-slate-400 font-normal">(Optional)</span>
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={newVictimLat}
                      onChange={(e) => setNewVictimLat(e.target.value)}
                      placeholder="e.g. 28.5921"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Victim Longitude <span className="text-slate-400 font-normal">(Optional)</span>
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={newVictimLon}
                      onChange={(e) => setNewVictimLon(e.target.value)}
                      placeholder="e.g. 77.0460"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                </div>
              </div>

              {/* SECTION C: TRANSACTION DETAILS */}
              <div className="p-4 bg-slate-50/70 border border-slate-200 rounded-lg space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
                    <span>SECTION C — TRANSACTION DETAILS</span>
                  </h4>
                  <span className="text-[11px] text-slate-500">First-Hop Transfer Record</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Payment Channel <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={newChannel}
                      onChange={(e) => setNewChannel(e.target.value)}
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                      required
                    >
                      <option value="UPI">UPI (Immediate)</option>
                      <option value="IMPS">IMPS</option>
                      <option value="NEFT">NEFT</option>
                      <option value="RTGS">RTGS</option>
                      <option value="NetBanking">NetBanking</option>
                      <option value="Card">Debit / Credit Card</option>
                      <option value="Wallet">Prepaid Wallet</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Transaction Date & Time <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="datetime-local"
                      value={newTransactionTime}
                      onChange={(e) => setNewTransactionTime(e.target.value)}
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Victim Bank / Provider <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newVictimBank}
                      onChange={(e) => setNewVictimBank(e.target.value)}
                      placeholder="e.g. State Bank of India, PNB, ICICI"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Beneficiary Bank / Provider <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newBeneficiaryBank}
                      onChange={(e) => setNewBeneficiaryBank(e.target.value)}
                      placeholder="e.g. HDFC Bank, Axis Bank, Paytm Bank"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Beneficiary Identifier <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newBeneficiaryId}
                      onChange={(e) => setNewBeneficiaryId(e.target.value)}
                      placeholder="e.g. UPI VPA or masked account"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Transaction / UTR Reference ID <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newTransactionRef}
                      onChange={(e) => setNewTransactionRef(e.target.value)}
                      placeholder="e.g. UTR-DL-2026-992144"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      IFSC / Branch Code <span className="text-slate-400 font-normal">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      value={newIfsc}
                      onChange={(e) => setNewIfsc(e.target.value)}
                      placeholder="e.g. HDFC0001234"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Beneficiary Account Number <span className="text-slate-400 font-normal">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      value={newBeneficiaryAccount}
                      onChange={(e) => setNewBeneficiaryAccount(e.target.value)}
                      placeholder="e.g. 50100234567890"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Beneficiary UPI ID <span className="text-slate-400 font-normal">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      value={newBeneficiaryUpi}
                      onChange={(e) => setNewBeneficiaryUpi(e.target.value)}
                      placeholder="e.g. mule.receiver@okhdfcbank"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-medium mb-1">
                      Phone / Wallet / Merchant ID <span className="text-slate-400 font-normal">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      value={newPhoneOrMerchant}
                      onChange={(e) => setNewPhoneOrMerchant(e.target.value)}
                      placeholder="e.g. +91 9811223344"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                </div>
              </div>

              {/* SECTION D: SIMULATION / DEMO MODE */}
              <div className="p-3.5 bg-blue-50/60 border border-blue-200 rounded-lg flex items-start space-x-3">
                <input
                  type="checkbox"
                  id="demo-mode-checkbox"
                  checked={newDemoMode}
                  onChange={(e) => setNewDemoMode(e.target.checked)}
                  className="mt-1 h-4 w-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 cursor-pointer"
                />
                <label htmlFor="demo-mode-checkbox" className="text-xs text-slate-700 cursor-pointer select-none">
                  <span className="font-bold text-[#173A63] block">Controlled Demo Simulation (demo_mode: true)</span>
                  <span className="text-slate-500 block mt-0.5 leading-normal">
                    Persists a deterministic, conserved 3-hop transaction layering trail in PostgreSQL with 6 account entities, 5 transaction edges, and 2 terminal ATM cash-out endpoints. Leave unchecked for genuine officer evidence input.
                  </span>
                </label>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex flex-col-reverse sm:flex-row sm:items-center justify-end gap-2 sm:space-x-3 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => {
                    setIsModalOpen(false);
                    setFormError(null);
                  }}
                  className="w-full sm:w-auto px-4 py-2 bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 font-medium rounded transition-colors text-center"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="w-full sm:w-auto px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded shadow-xs flex items-center justify-center space-x-1.5 transition-colors disabled:opacity-50 cursor-pointer"
                >
                  <span>{creating ? registrationPhase : 'REGISTER COMPLAINT'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
