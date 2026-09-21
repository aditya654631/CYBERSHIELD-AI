import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Compass,
  Filter,
  Search,
  AlertTriangle,
  Eye,
  Shield,
  Clock,
  Layers,
  MapPin,
  CheckCircle2,
  HelpCircle,
  Activity,
  AlertCircle,
  BellRing,
  Info,
  Calendar,
  RotateCcw,
  SlidersHorizontal,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { api } from '../services/api';
import { HotspotCluster, ATMLocationItem, Complaint, Prediction, PredictionLocationItem, GISOverviewResponse, RegionItem } from '../types';
import { CashOutRiskMap } from '../maps/CashOutRiskMap';
import { PredictionTiming } from '../components/PredictionTiming';
import { modelScore, predictionScoreNote } from '../utils/predictionDisplay';

const DELHI_DISTRICTS = [
  'ALL',
  'Central',
  'New Delhi',
  'South',
  'South East',
  'South West',
  'North',
  'North East',
  'North West',
  'West',
  'East',
  'Shahdara',
];

const CRIME_CATEGORIES = [
  'ALL',
  'UPI Fraud',
  'Phishing',
  'Investment Scam',
  'Impersonation',
  'Loan App Scam',
  'Job Fraud',
  'Sextortion',
  'SIM Swap',
  'ATM Card Cloning',
];

export const RiskMap: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // URL Initialized Filter State
  const initialTimeBasis = searchParams.get('time_basis') || 'predicted_window';
  const initialStartTime = searchParams.get('start_time') || '';
  const initialEndTime = searchParams.get('end_time') || '';
  const initialCrimeCategory = searchParams.get('crime_category') || 'ALL';
  const initialDistrict = searchParams.get('district') || 'ALL';
  const initialRisk = searchParams.get('risk_level') || 'ALL';
  const initialCaseParam = searchParams.get('case') || searchParams.get('complaint') || '';
  const initialRegionParam = searchParams.get('region_id') || searchParams.get('region') || 'delhi';

  // Region State (Phase 12)
  const [regions, setRegions] = useState<RegionItem[]>([]);
  const [selectedRegionId, setSelectedRegionId] = useState<string>(initialRegionParam);

  // Filter State
  const [timeBasis, setTimeBasis] = useState<string>(initialTimeBasis);
  const [startTime, setStartTime] = useState<string>(initialStartTime);
  const [endTime, setEndTime] = useState<string>(initialEndTime);
  const [crimeCategory, setCrimeCategory] = useState<string>(initialCrimeCategory);
  const [districtFilter, setDistrictFilter] = useState<string>(initialDistrict);
  const [riskFilter, setRiskFilter] = useState<string>(initialRisk);
  const [filterValidationError, setFilterValidationError] = useState<string | null>(null);
  const [showFilterPanel, setShowFilterPanel] = useState<boolean>(true);

  // Load Regions Catalog (Phase 12)
  useEffect(() => {
    api.getRegions()
      .then((data) => {
        setRegions(data);
      })
      .catch((err) => console.warn('[GIS] Failed to load regions:', err));
  }, []);

  const currentRegion = regions.find((r) => r.id === selectedRegionId) || null;
  const availableDistricts = currentRegion && currentRegion.districts && currentRegion.districts.length > 0
    ? ['ALL', ...currentRegion.districts]
    : DELHI_DISTRICTS;

  const handleRegionChange = (newRegionId: string) => {
    setSelectedRegionId(newRegionId);
    setDistrictFilter('ALL');
    setSelectedClusterId(null);
    setSelectedCluster(null);
    syncParamsToUrl({ region_id: newRegionId, district: 'ALL', cluster: undefined });
  };

  // Complaints & Selection
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [selectedComplaintId, setSelectedComplaintId] = useState<string>(initialCaseParam);
  const [selectedComplaint, setSelectedComplaint] = useState<Complaint | null>(null);

  // Cluster Selection & Route Integration (Phase 3 & 4)
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);
  const [selectedCluster, setSelectedCluster] = useState<HotspotCluster | null>(null);
  const [clusterNotice, setClusterNotice] = useState<string | null>(null);
  const [clusterError, setClusterError] = useState<string | null>(null);

  // Persisted Prediction Intelligence State
  const [currentPrediction, setCurrentPrediction] = useState<Prediction | null>(null);
  const [topLocations, setTopLocations] = useState<PredictionLocationItem[]>([]);
  const [predictionLoading, setPredictionLoading] = useState<boolean>(Boolean(initialCaseParam));
  const [predictionError, setPredictionError] = useState<string | null>(null);
  const [integrityError, setIntegrityError] = useState<string | null>(null);
  const [alertGenerating, setAlertGenerating] = useState<boolean>(false);
  const [alertSuccess, setAlertSuccess] = useState<string | null>(null);

  // Generic GIS Context (Monitored Clusters & Prototype ATMs)
  const [hotspots, setHotspots] = useState<HotspotCluster[]>([]);
  const [activeCandidates, setActiveCandidates] = useState<HotspotCluster[]>([]);
  const [atms, setAtms] = useState<ATMLocationItem[]>([]);
  const [gisSummary, setGisSummary] = useState<any>(null);
  const [gisLoading, setGisLoading] = useState<boolean>(true);
  const [gisApiError, setGisApiError] = useState<string | null>(null);
  const [mapHeight, setMapHeight] = useState<string>('620px');

  useEffect(() => {
    const updateHeight = () => {
      if (typeof window !== 'undefined') {
        if (window.innerWidth < 640) {
          setMapHeight('380px');
        } else if (window.innerWidth < 1024) {
          setMapHeight('460px');
        } else {
          setMapHeight('620px');
        }
      }
    };
    updateHeight();
    window.addEventListener('resize', updateHeight);
    return () => window.removeEventListener('resize', updateHeight);
  }, []);

  // Layer Toggles (In Case Focus mode, all Delhi-wide context defaults to OFF)
  const [showPredictionZones, setShowPredictionZones] = useState<boolean>(true);
  const [showHotspots, setShowHotspots] = useState<boolean>(!initialCaseParam);
  const [showAtms, setShowAtms] = useState<boolean>(false);

  // 1. Initial Load: Fetch Complaints List from Real API
  useEffect(() => {
    const loadComplaints = async () => {
      try {
        const comps = await api.getComplaints({ limit: 100, region_id: selectedRegionId });
        let allComps = [...comps];

        const hasClusterParam = Boolean(searchParams.get('cluster'));
        const paramId = searchParams.get('case') || searchParams.get('complaint');

        if (paramId) {
          const inList = comps.find((c) => c.complaint_number === paramId);
          if (inList) {
            setSelectedComplaintId(paramId);
            setSelectedComplaint(inList);
          } else {
            try {
              const specificComp = await api.getComplaint(paramId);
              if (specificComp && specificComp.complaint_number) {
                allComps = [specificComp, ...comps];
                setSelectedComplaintId(paramId);
                setSelectedComplaint(specificComp);
              } else if (!hasClusterParam && comps.length > 0) {
                const defaultComp = comps[0];
                setSelectedComplaintId(defaultComp.complaint_number);
                setSelectedComplaint(defaultComp);
              }
            } catch {
              if (!hasClusterParam && comps.length > 0) {
                const defaultComp = comps[0];
                setSelectedComplaintId(defaultComp.complaint_number);
                setSelectedComplaint(defaultComp);
              }
            }
          }
        } else if (!hasClusterParam && comps.length > 0) {
          const defaultComp = comps[0];
          setSelectedComplaintId(defaultComp.complaint_number);
          setSelectedComplaint(defaultComp);
        }
        setComplaints(allComps);
      } catch (err) {
        console.error('[GIS] Failed to load complaints list', err);
      }
    };
    loadComplaints();
  }, []);

  // Sync Search Params when filters change
  const syncParamsToUrl = (newParams: Record<string, string | undefined>) => {
    const current: Record<string, string> = {};
    searchParams.forEach((val, key) => {
      current[key] = val;
    });

    Object.entries(newParams).forEach(([k, v]) => {
      if (v && v !== 'ALL' && v !== '') {
        current[k] = v;
      } else {
        delete current[k];
      }
    });

    setSearchParams(current, { replace: true });
  };

  // 2. Fetch GIS Context with Multi-Dimensional Filters
  useEffect(() => {
    // Client-side quick range validation
    if (startTime && endTime) {
      const s = new Date(startTime).getTime();
      const e = new Date(endTime).getTime();
      if (!isNaN(s) && !isNaN(e) && s > e) {
        setFilterValidationError('Reversed time range: Start Time cannot be after End Time.');
        return;
      }
    }
    setFilterValidationError(null);

    const fetchGISContext = async () => {
      setGisLoading(true);
      setGisApiError(null);
      try {
        const queryParams = {
          region_id: selectedRegionId,
          district: districtFilter !== 'ALL' ? districtFilter : undefined,
          risk_level: riskFilter !== 'ALL' ? riskFilter : undefined,
          crime_category: crimeCategory !== 'ALL' ? crimeCategory : undefined,
          time_basis: timeBasis,
          start_time: startTime || undefined,
          end_time: endTime || undefined,
        };

        const data: GISOverviewResponse = await api.getRiskMap(queryParams);
        setHotspots(data.hotspots || []);
        setActiveCandidates(data.active_candidates || data.hotspots?.filter((h) => h.is_active_candidate) || []);
        setAtms(data.atms || []);
        setGisSummary(data.summary || null);

        // Update URL query params
        syncParamsToUrl({
          region_id: selectedRegionId,
          district: districtFilter,
          risk_level: riskFilter,
          crime_category: crimeCategory,
          time_basis: timeBasis !== 'predicted_window' ? timeBasis : undefined,
          start_time: startTime || undefined,
          end_time: endTime || undefined,
        });
      } catch (err: any) {
        console.error('[GIS] Failed to load GIS context', err);
        const detail = err.response?.data?.detail || 'Failed to fetch GIS risk map data.';
        setGisApiError(detail);
      } finally {
        setGisLoading(false);
      }
    };

    fetchGISContext();
  }, [selectedRegionId, districtFilter, riskFilter, crimeCategory, timeBasis, startTime, endTime]);

  // 2b. Cluster URL Parameter Navigation & Validation (Phase 3 & 4)
  useEffect(() => {
    const clusterParam = searchParams.get('cluster');
    if (clusterParam && hotspots.length > 0) {
      const target = hotspots.find(
        (h) => String(h.id) === clusterParam || h.cluster_name.toLowerCase() === clusterParam.toLowerCase()
      );
      if (target) {
        setSelectedClusterId(target.id);
        setSelectedCluster(target);
        setShowHotspots(true);
        setClusterError(null);

        if (target.is_active_candidate && target.linked_complaint_numbers && target.linked_complaint_numbers.length > 0) {
          const firstLinked = target.linked_complaint_numbers[0];
          setSelectedComplaintId(firstLinked);
          setClusterNotice(`Focused on active candidate cluster '${target.cluster_name}' (${target.active_cases} linked case(s)).`);
        } else {
          // Historical baseline: clear selected complaint so we don't silently display an unrelated case!
          setSelectedComplaintId('');
          setSelectedComplaint(null);
          setCurrentPrediction(null);
          setTopLocations([]);
          setPredictionLoading(false);
          setClusterNotice(`Focused on monitored hotspot '${target.cluster_name}' (Historical baseline — no active case prediction).`);
        }
      } else {
        setSelectedClusterId(null);
        setSelectedCluster(null);
        setClusterNotice(null);
        setClusterError(`Requested cluster '${clusterParam}' was not found or is outside authorized officer jurisdiction.`);
      }
    }
  }, [searchParams, hotspots]);

  // 3. Reactive Single Source of Truth: Fetch Persisted Prediction on Complaint Change
  useEffect(() => {
    if (!selectedComplaintId) {
      setPredictionLoading(false);
      return;
    }
    let cancelled = false;

    // Update query param for deep linking / refresh stability
    if (searchParams.get('case') !== selectedComplaintId) {
      syncParamsToUrl({ case: selectedComplaintId });
    }

    const matchedComp = complaints.find((c) => c.complaint_number === selectedComplaintId) || null;
    if (matchedComp) {
      setSelectedComplaint(matchedComp);
    } else {
      api
        .getComplaint(selectedComplaintId)
        .then((comp) => {
          if (!cancelled && comp?.complaint_number) {
            setSelectedComplaint(comp);
            setComplaints((prev) =>
              prev.some((c) => c.complaint_number === comp.complaint_number) ? prev : [comp, ...prev]
            );
          }
        })
        .catch(() => {});
    }

    setPredictionLoading(true);
    setCurrentPrediction(null);
    setTopLocations([]);
    setPredictionError(null);
    setIntegrityError(null);

    const fetchPersistedPrediction = async () => {
      try {
        const pred = await api.getPrediction(selectedComplaintId);
        if (cancelled) return;
        if (!pred) {
          setCurrentPrediction(null);
          setTopLocations([]);
          setPredictionError(
            `No persisted prediction found for ${selectedComplaintId}. This complaint may be outside the model's operational scope or awaiting predictive analysis.`
          );
          return;
        }

        setCurrentPrediction(pred);
        const locs = [...(pred.top_locations || [])].sort((a, b) => a.rank - b.rank).slice(0, 3);
        setTopLocations(locs);

        if (pred.primary_cluster_id != null && locs.length > 0) {
          const rank1Cid = locs[0].cluster_id;
          if (rank1Cid != null && pred.primary_cluster_id !== rank1Cid) {
            const errText = `Data Integrity Alert: Primary cluster ID (${pred.primary_cluster_id}) does not match Rank 1 location cluster ID (${rank1Cid}).`;
            console.error('[GIS]', errText);
            setIntegrityError(errText);
          }
        }
      } catch (err: any) {
        if (cancelled) return;
        if (err?.response?.status === 404) {
          setPredictionError(
            `No persisted prediction found for ${selectedComplaintId}. This complaint may be outside the model's operational scope (Delhi Pilot).`
          );
        } else {
          setPredictionError(`Unable to retrieve prediction for ${selectedComplaintId}.`);
        }
        setCurrentPrediction(null);
        setTopLocations([]);
      } finally {
        if (!cancelled) setPredictionLoading(false);
      }
    };

    fetchPersistedPrediction();
    return () => {
      cancelled = true;
    };
  }, [selectedComplaintId]);

  // Quick Preset Helper Handlers
  const handleQuickPreset = (preset: 'next2h' | 'next6h' | 'today' | 'all') => {
    const now = new Date();
    if (preset === 'next2h') {
      const start = new Date(now.getTime());
      const end = new Date(now.getTime() + 2 * 60 * 60 * 1000);
      setStartTime(start.toISOString().slice(0, 16));
      setEndTime(end.toISOString().slice(0, 16));
      setTimeBasis('predicted_window');
    } else if (preset === 'next6h') {
      const start = new Date(now.getTime());
      const end = new Date(now.getTime() + 6 * 60 * 60 * 1000);
      setStartTime(start.toISOString().slice(0, 16));
      setEndTime(end.toISOString().slice(0, 16));
      setTimeBasis('predicted_window');
    } else if (preset === 'today') {
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
      const end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);
      setStartTime(start.toISOString().slice(0, 16));
      setEndTime(end.toISOString().slice(0, 16));
    } else if (preset === 'all') {
      setStartTime('');
      setEndTime('');
    }
  };

  const handleResetFilters = () => {
    setTimeBasis('predicted_window');
    setStartTime('');
    setEndTime('');
    setCrimeCategory('ALL');
    setDistrictFilter('ALL');
    setRiskFilter('ALL');
    setFilterValidationError(null);
    setGisApiError(null);
    setSearchParams(selectedComplaintId ? { case: selectedComplaintId } : {}, { replace: true });
  };

  const handleGenerateAlertFromMap = async () => {
    if (!currentPrediction?.prediction_id) return;
    setAlertGenerating(true);
    try {
      const created = await api.createAlertForPrediction(currentPrediction.prediction_id);
      setAlertSuccess(`Alert #${created.id} active for Prediction #${created.prediction_id}`);
      setTimeout(() => setAlertSuccess(null), 4000);
    } catch (err: any) {
      console.error('Error generating alert from map', err);
      setAlertSuccess(err?.response?.data?.detail || 'Failed to generate alert');
      setTimeout(() => setAlertSuccess(null), 4000);
    } finally {
      setAlertGenerating(false);
    }
  };

  const isTrained = currentPrediction?.prediction_mode === 'trained_ml';
  const highlightClusterName = topLocations.length > 0 ? topLocations[0].location_name : undefined;

  const isFilterActive =
    districtFilter !== 'ALL' ||
    riskFilter !== 'ALL' ||
    crimeCategory !== 'ALL' ||
    timeBasis !== 'predicted_window' ||
    Boolean(startTime) ||
    Boolean(endTime);

  return (
    <div className="space-y-6 pb-12">
      {/* GIS Header & Complaint Selector Bar */}
      <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <Compass className="w-5 h-5 text-blue-600 shrink-0" />
            <h1 className="text-lg font-bold text-[#173A63] font-sans">
              Geospatial Predictive Cash-Out Intelligence (GIS)
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5 font-sans">
            Multi-Dimensional Cash-Out Surveillance, Time-Window Overlap & Interception Routing
          </p>
        </div>

        {/* Dynamic Selectors */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Geographic Region Selector (Phase 12) */}
          <div className="flex items-center space-x-2 bg-[#F6F8FC] px-3 py-1.5 rounded-md border border-[#DCE5F0] w-full sm:w-auto">
            <span className="text-xs text-blue-700 font-semibold shrink-0">Region:</span>
            <select
              value={selectedRegionId}
              onChange={(e) => handleRegionChange(e.target.value)}
              className="bg-transparent text-xs text-slate-800 focus:outline-none cursor-pointer font-medium w-full sm:max-w-[210px]"
            >
              {regions.length === 0 ? (
                <option value="delhi">National Capital Territory of Delhi</option>
              ) : (
                regions.map((r) => (
                  <option key={r.id} value={r.id} className="bg-white text-slate-800">
                    {r.name} {r.is_synthetic ? '(Synthetic)' : ''}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Dynamic Complaint Selector */}
          <div className="flex items-center space-x-2 bg-[#F6F8FC] px-3 py-1.5 rounded-md border border-[#DCE5F0] w-full sm:w-auto">
            <span className="text-xs text-blue-700 font-semibold shrink-0">Active Case:</span>
            <select
              value={selectedComplaintId}
              onChange={(e) => {
                const val = e.target.value;
                setSelectedComplaintId(val);
                if (val) {
                  setShowHotspots(false);
                  setShowAtms(false);
                  setShowPredictionZones(true);
                } else {
                  setShowHotspots(true);
                  setShowAtms(false);
                }
              }}
              className="bg-transparent text-xs text-slate-800 focus:outline-none cursor-pointer font-medium w-full sm:max-w-[220px]"
            >
              <option value="" className="bg-white text-slate-500">-- Overview (No Single Case) --</option>
              {selectedComplaintId && !complaints.some((c) => c.complaint_number === selectedComplaintId) && (
                <option value={selectedComplaintId} className="bg-white text-slate-800">
                  {selectedComplaint
                    ? `${selectedComplaint.complaint_number} (${selectedComplaint.district || selectedComplaint.state}) - ₹${Number(selectedComplaint.amount || 0).toLocaleString('en-IN')}`
                    : selectedComplaintId}
                </option>
              )}
              {complaints.map((c) => (
                <option key={c.complaint_number} value={c.complaint_number} className="bg-white text-slate-800">
                  {c.complaint_number} ({c.district || c.state}) - ₹{Number(c.amount || 0).toLocaleString('en-IN')}
                </option>
              ))}
            </select>
          </div>

          {/* Quick Context Layer Toggles */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setShowPredictionZones(!showPredictionZones)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors border ${
                showPredictionZones
                  ? 'bg-blue-50 text-blue-700 border-blue-300 font-semibold'
                  : 'bg-white text-slate-600 border-[#DCE5F0] hover:bg-slate-50'
              }`}
            >
              Top-3 Predictions
            </button>
            <button
              onClick={() => setShowHotspots(!showHotspots)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors border ${
                showHotspots
                  ? 'bg-blue-50 text-blue-700 border-blue-300 font-semibold'
                  : 'bg-white text-slate-600 border-[#DCE5F0] hover:bg-slate-50'
              }`}
            >
              Hotspot Clusters ({hotspots.length})
            </button>
            <button
              onClick={() => setShowAtms(!showAtms)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors border ${
                showAtms
                  ? 'bg-blue-50 text-blue-700 border-blue-300 font-semibold'
                  : 'bg-white text-slate-600 border-[#DCE5F0] hover:bg-slate-50'
              }`}
            >
              Prototype ATMs ({atms.length})
            </button>
          </div>
        </div>
      </div>

      {/* Region Operational Scope & Validation Status Banner (Phase 12) */}
      {currentRegion && (
        <div
          className={`p-3.5 rounded-lg border text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs ${
            currentRegion.model_support_status === 'MODEL_SUPPORTED'
              ? 'bg-blue-50/80 border-blue-200 text-blue-900'
              : currentRegion.model_support_status === 'VALIDATION_PENDING'
              ? 'bg-amber-50 border-amber-300 text-amber-900'
              : 'bg-red-50 border-red-200 text-red-900'
          }`}
        >
          <div className="flex items-start sm:items-center space-x-2.5">
            {currentRegion.model_support_status === 'MODEL_SUPPORTED' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5 sm:mt-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5 sm:mt-0" />
            )}
            <div>
              <span className="font-bold">
                {currentRegion.name} ({currentRegion.catalog_version}):{' '}
              </span>
              <span>
                {currentRegion.model_support_status === 'MODEL_SUPPORTED'
                  ? `Production Qualified (${currentRegion.supported_model_version}). 100% operational prediction support.`
                  : currentRegion.model_support_status === 'VALIDATION_PENDING'
                  ? `Geographic Validation Pending (${currentRegion.is_synthetic ? 'Synthetic MMR Fixture' : 'Catalog Fixture'}). Operational predictions disabled until ground-truth dataset and promotion gates pass.`
                  : 'Predictions unsupported for this region.'}
              </span>
            </div>
          </div>
          <div className="text-[11px] text-slate-500 shrink-0 font-mono">
            {currentRegion.total_clusters} Clusters | {currentRegion.total_atms} Reference ATMs | Radius: {currentRegion.cluster_radius_km}km
          </div>
        </div>
      )}

      {/* Multi-Dimensional Filter Control Bar (Phase 4) */}
      <div className="p-4 bg-white rounded-lg border border-[#DCE5F0] shadow-xs space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <SlidersHorizontal className="w-4 h-4 text-blue-600" />
            <h2 className="text-xs font-bold text-[#173A63] uppercase tracking-wider">
              Surveillance Filters & Time Basis
            </h2>
            {isFilterActive && (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-800 border border-blue-200">
                Filters Active
              </span>
            )}
          </div>
          <div className="flex items-center space-x-2">
            {isFilterActive && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="px-2.5 py-1 text-xs font-medium text-slate-600 hover:text-red-600 hover:bg-red-50 rounded border border-[#DCE5F0] transition-colors flex items-center space-x-1 cursor-pointer"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset Filters</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => setShowFilterPanel(!showFilterPanel)}
              className="p-1 text-slate-400 hover:text-slate-600 rounded"
            >
              {showFilterPanel ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {showFilterPanel && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-3 pt-2 border-t border-[#DCE5F0] text-xs">
            {/* 1. Time Basis Filter */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-700 flex items-center space-x-1">
                <Clock className="w-3 h-3 text-blue-600" />
                <span>Time Basis:</span>
              </label>
              <select
                value={timeBasis}
                onChange={(e) => setTimeBasis(e.target.value)}
                className="w-full bg-[#F6F8FC] border border-[#DCE5F0] rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-blue-500 font-medium"
              >
                <option value="predicted_window">Predicted Window (Default)</option>
                <option value="complaint_time">Complaint Ingest Time</option>
                <option value="incident_time">Incident Occurred Time</option>
              </select>
            </div>

            {/* 2. Start Time */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-700 flex items-center space-x-1">
                <Calendar className="w-3 h-3 text-blue-600" />
                <span>From (IST / ISO):</span>
              </label>
              <input
                type="datetime-local"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="w-full bg-[#F6F8FC] border border-[#DCE5F0] rounded px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>

            {/* 3. End Time */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-700 flex items-center space-x-1">
                <Calendar className="w-3 h-3 text-blue-600" />
                <span>To (IST / ISO):</span>
              </label>
              <input
                type="datetime-local"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className="w-full bg-[#F6F8FC] border border-[#DCE5F0] rounded px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>

            {/* 4. Crime Category */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-700 flex items-center space-x-1">
                <Shield className="w-3 h-3 text-blue-600" />
                <span>Crime Category:</span>
              </label>
              <select
                value={crimeCategory}
                onChange={(e) => setCrimeCategory(e.target.value)}
                className="w-full bg-[#F6F8FC] border border-[#DCE5F0] rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
              >
                {CRIME_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            {/* 5. District Filter */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-700 flex items-center space-x-1">
                <MapPin className="w-3 h-3 text-blue-600" />
                <span>District:</span>
              </label>
              <select
                value={districtFilter}
                onChange={(e) => setDistrictFilter(e.target.value)}
                className="w-full bg-[#F6F8FC] border border-[#DCE5F0] rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
              >
                {availableDistricts.map((dist) => (
                  <option key={dist} value={dist}>
                    {dist === 'ALL' ? 'All Districts' : dist}
                  </option>
                ))}
              </select>
            </div>

            {/* 6. Risk Level */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-700 flex items-center space-x-1">
                <AlertTriangle className="w-3 h-3 text-blue-600" />
                <span>Risk Level:</span>
              </label>
              <select
                value={riskFilter}
                onChange={(e) => setRiskFilter(e.target.value)}
                className="w-full bg-[#F6F8FC] border border-[#DCE5F0] rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
              >
                <option value="ALL">All Risk Levels</option>
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>
            </div>
          </div>
        )}

        {/* Quick Time Window Presets Bar */}
        {showFilterPanel && (
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100 text-[11px]">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-slate-500 font-medium">Quick Time Windows:</span>
              <button
                type="button"
                onClick={() => handleQuickPreset('next2h')}
                className="px-2 py-0.5 bg-slate-100 hover:bg-blue-50 hover:text-blue-700 border border-slate-200 rounded text-slate-700 font-medium transition-colors"
              >
                Next 2 Hours
              </button>
              <button
                type="button"
                onClick={() => handleQuickPreset('next6h')}
                className="px-2 py-0.5 bg-slate-100 hover:bg-blue-50 hover:text-blue-700 border border-slate-200 rounded text-slate-700 font-medium transition-colors"
              >
                Next 6 Hours
              </button>
              <button
                type="button"
                onClick={() => handleQuickPreset('today')}
                className="px-2 py-0.5 bg-slate-100 hover:bg-blue-50 hover:text-blue-700 border border-slate-200 rounded text-slate-700 font-medium transition-colors"
              >
                Today (24h)
              </button>
              <button
                type="button"
                onClick={() => handleQuickPreset('all')}
                className="px-2 py-0.5 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded text-slate-700 font-medium transition-colors"
              >
                All Windows
              </button>
            </div>

            <div className="text-slate-400 italic">
              Basis: <strong className="text-slate-700 not-italic">{timeBasis === 'predicted_window' ? 'Predicted Window Overlap (Default)' : timeBasis === 'complaint_time' ? 'Complaint Reporting Time' : 'Incident Occurrence Time'}</strong>
            </div>
          </div>
        )}

        {/* Validation or API Error Alerts */}
        {filterValidationError && (
          <div className="p-2.5 bg-red-50 border border-red-200 rounded text-xs text-red-700 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{filterValidationError}</span>
          </div>
        )}

        {gisApiError && (
          <div className="p-2.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600" />
            <span>{gisApiError}</span>
          </div>
        )}
      </div>

      {/* Global Deduplicated GIS KPI Stats Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <div className="text-[10px] uppercase font-bold text-slate-500">Active Candidate Clusters</div>
          <div className="text-xl font-bold text-amber-600 mt-0.5">
            {gisSummary?.total_active_candidates ?? activeCandidates.length}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">With active case routing</div>
        </div>

        <div className="p-3 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <div className="text-[10px] uppercase font-bold text-slate-500">Total Monitored Hotspots</div>
          <div className="text-xl font-bold text-[#173A63] mt-0.5">
            {gisSummary?.total_hotspots ?? hotspots.length}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {gisSummary?.total_historical_hotspots ?? hotspots.filter((h) => !h.is_active_candidate).length} baseline
          </div>
        </div>

        <div className="p-3 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <div className="text-[10px] uppercase font-bold text-slate-500">Unique Active Cases</div>
          <div className="text-xl font-bold text-blue-600 mt-0.5">
            {gisSummary?.total_unique_active_cases ?? '—'}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Globally deduplicated</div>
        </div>

        <div className="p-3 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
          <div className="text-[10px] uppercase font-bold text-slate-500">Associated Active Exposure</div>
          <div className="text-xl font-bold text-red-600 mt-0.5">
            ₹{Number(gisSummary?.total_associated_amount || 0).toLocaleString('en-IN')}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Deduplicated complaint sums</div>
        </div>
      </div>

      {/* Cluster Navigation Feedback Alerts */}
      {clusterNotice && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Info className="w-4 h-4 text-blue-600 shrink-0" />
            <span>{clusterNotice}</span>
          </div>
          <button
            type="button"
            onClick={() => setClusterNotice(null)}
            className="text-blue-600 hover:text-blue-800 font-bold ml-2 text-sm leading-none cursor-pointer"
          >
            ×
          </button>
        </div>
      )}

      {clusterError && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>{clusterError}</span>
          </div>
          <button
            type="button"
            onClick={() => setClusterError(null)}
            className="text-amber-600 hover:text-amber-800 font-bold ml-2 text-sm leading-none cursor-pointer"
          >
            ×
          </button>
        </div>
      )}

      {/* Main Map + Selected Prediction Intelligence Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Full GIS Map Canvas */}
        <div className="lg:col-span-8 bg-white rounded-lg border border-[#DCE5F0] p-4 shadow-xs">
          <CashOutRiskMap
            hotspots={showHotspots ? hotspots : []}
            atms={showAtms ? atms : []}
            topLocations={showPredictionZones ? topLocations : []}
            complaint={selectedComplaint}
            prediction={currentPrediction}
            height={mapHeight}
            highlightCluster={selectedCluster?.cluster_name || highlightClusterName}
            selectedClusterId={selectedClusterId}
            regionCenter={currentRegion?.center}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between text-[11px] text-slate-500 px-2">
            <span>
              Numbered markers show this case's top 3 locations. Concentric Rings:{' '}
              <strong className="text-blue-700">1km / 2.5km / 5km</strong> (Tactical search radii; not confidence intervals)
            </span>
            <span>
              Single Source of Truth:{' '}
              <strong className="text-emerald-700">Persisted Prediction API (Read-Only)</strong>
            </span>
          </div>
        </div>

        {/* Selected Prediction Intelligence Panel */}
        <div className="lg:col-span-4 space-y-4">
          <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs">
            {/* Panel Header */}
            <div className="flex items-center justify-between pb-3 border-b border-[#DCE5F0] mb-4">
              <div className="flex items-center space-x-2">
                <Shield className="w-4 h-4 text-blue-600" />
                <h3 className="text-sm font-bold text-[#173A63] uppercase">
                  Prediction Intelligence
                </h3>
              </div>
              {currentPrediction && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold border border-blue-200">
                  ID #{currentPrediction.prediction_id}
                </span>
              )}
            </div>

            {/* Invariant Failure Warning */}
            {integrityError && (
              <div className="p-3 mb-4 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-start space-x-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-red-600" />
                <span>{integrityError}</span>
              </div>
            )}

            {/* Loading State */}
            {predictionLoading ? (
              <div className="text-center py-12 space-y-2">
                <Activity className="w-6 h-6 text-blue-600 animate-spin mx-auto" />
                <div className="text-xs text-slate-500">Loading persisted prediction...</div>
              </div>
            ) : currentPrediction ? (
              /* Success State: Render Persisted Prediction Details */
              <div className="space-y-4">
                {/* Provenance Header */}
                <div className="p-3 bg-[#F6F8FC] rounded-lg border border-[#DCE5F0] space-y-2 text-xs">
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider pb-1 border-b border-[#DCE5F0]">
                    Prediction Metadata
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Complaint:</span>
                    <strong className="text-slate-900 font-semibold">{currentPrediction.complaint_number}</strong>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Prediction:</span>
                    <span className="text-blue-700 font-bold">#{currentPrediction.prediction_id}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Mode:</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        isTrained
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-purple-50 text-purple-700 border border-purple-200'
                      }`}
                    >
                      {isTrained ? 'Trained ML' : currentPrediction.prediction_mode}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Location Model:</span>
                    <span className="text-slate-700 font-mono">{currentPrediction.model_version || 'unavailable'}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Time Model:</span>
                    <span className="text-slate-700 font-mono">
                      {currentPrediction.time_prediction?.model_version || (currentPrediction as any).time_model_version || 'unavailable'}
                    </span>
                  </div>
                  <div className="pt-2 border-t border-[#DCE5F0]">
                    <div className="text-slate-500 mb-1">Predicted time window</div>
                    <PredictionTiming prediction={currentPrediction} />
                  </div>
                </div>

                {/* Top-3 Locations Breakdown */}
                <div className="space-y-2.5">
                  <div>
                    <h4 className="text-xs font-bold text-slate-700 uppercase">
                      Ranked Cash-Out Zones
                    </h4>
                    <p className="text-[11px] text-slate-500 leading-relaxed mt-1">
                      Scores are relative model ranking scores used to compare candidate cash-out zones. They are not literal probabilities of withdrawal and do not need to sum to 100%.
                    </p>
                  </div>

                  {topLocations.map((loc) => {
                    const isRank1 = loc.rank === 1;
                    const rankLabel = isRank1 ? '#1 PRIMARY' : loc.rank === 2 ? '#2 SECONDARY' : '#3 TERTIARY';
                    const activeModel = currentPrediction.model_version || 'Location V7-compat';

                    return (
                      <div
                        key={loc.rank}
                        className={`p-3 rounded-lg border transition-all text-xs ${
                          isRank1
                            ? 'bg-blue-50/50 border-blue-200 border-l-4 border-l-blue-600'
                            : loc.rank === 2
                            ? 'bg-slate-50 border-[#DCE5F0] border-l-4 border-l-slate-400'
                            : 'bg-white border-[#DCE5F0] border-l-4 border-l-slate-300'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center space-x-2">
                            <span
                              className={`px-1.5 py-0.5 rounded flex items-center justify-center font-bold text-[10px] ${
                                isRank1
                                  ? 'bg-blue-600 text-white'
                                  : loc.rank === 2
                                  ? 'bg-slate-700 text-white'
                                  : 'bg-slate-200 text-slate-700'
                              }`}
                            >
                              {rankLabel}
                            </span>
                            <span className="font-bold text-slate-900 text-xs truncate max-w-[150px]">
                              {loc.location_name}
                            </span>
                          </div>
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                              loc.risk_level === 'CRITICAL'
                                ? 'bg-red-50 text-red-700 border border-red-200'
                                : 'bg-amber-50 text-amber-700 border border-amber-200'
                            }`}
                          >
                            {loc.risk_level}
                          </span>
                        </div>

                        {loc.zone && (
                          <div className="flex justify-between items-center text-slate-500 text-[11px] mt-0.5">
                            <span>Zone / District:</span>
                            <span className="text-slate-800 font-medium">{loc.zone}</span>
                          </div>
                        )}

                        <div className="flex justify-between items-center text-slate-500 text-[11px] mt-0.5">
                          <span
                            className="flex items-center space-x-1 cursor-help"
                            title="Relative ranking score generated by the trained ML model. Higher values indicate stronger ranking compared with other candidate zones for this complaint."
                          >
                            <span>Model ranking score:</span>
                            <Info className="w-3 h-3 text-slate-400" />
                          </span>
                          <strong className="text-blue-700 font-mono">{modelScore(loc)}</strong>
                        </div>

                        <div className="flex justify-between items-center text-slate-500 text-[11px] mt-0.5">
                          <span>Operational Priority:</span>
                          <span className="text-slate-700 font-semibold">
                            {loc.risk_level || (isRank1 ? 'HIGH' : loc.rank === 2 ? 'MEDIUM' : 'LOW')}
                          </span>
                        </div>

                        <div className="text-[10px] text-slate-500 italic mt-1 pt-1 border-t border-slate-200/60">
                          Ranked #{loc.rank} by {activeModel} for the current complaint context.
                        </div>

                        <p className="text-[11px] text-slate-600 mt-1.5 leading-relaxed">{loc.reasoning}</p>

                        <div className="flex justify-between items-center text-slate-400 text-[10px] mt-1">
                          <span>Cluster ID: {loc.cluster_id || 'N/A'}</span>
                          <span>Distance: {loc.distance_km} km</span>
                        </div>
                      </div>
                    );
                  })}

                  <div className="p-2.5 bg-slate-50 rounded border border-slate-200 text-[10px] text-slate-500 flex items-start space-x-1.5 mt-2">
                    <Info className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                    <span>These scores rank candidate locations and are not verified real-world probabilities.</span>
                  </div>
                </div>

                {/* Direct Action Links */}
                <div className="pt-3 border-t border-[#DCE5F0] space-y-2">
                  <button
                    onClick={handleGenerateAlertFromMap}
                    disabled={alertGenerating || !currentPrediction.prediction_id}
                    className="w-full py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-md text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 shadow-xs cursor-pointer"
                  >
                    <BellRing className="w-3.5 h-3.5" />
                    <span>
                      {alertGenerating
                        ? 'DISPATCHING ALERT...'
                        : `TRIGGER ALERT (PREDICTION #${currentPrediction.prediction_id})`}
                    </span>
                  </button>

                  {alertSuccess && (
                    <div className="p-2 bg-emerald-50 border border-emerald-200 rounded-md text-[11px] text-emerald-700 font-medium text-center">
                      {alertSuccess}
                    </div>
                  )}

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => navigate(`/cases/${selectedComplaintId}`)}
                      className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 shadow-xs"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>CASE INTELLIGENCE</span>
                    </button>
                    <button
                      onClick={() => navigate(`/network/${selectedComplaintId}`)}
                      className="flex-1 py-2 bg-white hover:bg-blue-50 border border-[#DCE5F0] text-blue-700 rounded-md text-xs font-semibold transition-colors shadow-xs"
                    >
                      MULE GRAPH
                    </button>
                  </div>
                </div>
              </div>
            ) : selectedCluster && !selectedComplaintId ? (
              /* Cluster Focus Panel */
              <div className="space-y-4">
                <div className="p-3 bg-[#F6F8FC] rounded-lg border border-[#DCE5F0]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase">
                      Cluster Focus
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        selectedCluster.is_active_candidate
                          ? 'bg-amber-100 text-amber-800 border border-amber-300'
                          : 'bg-slate-200 text-slate-700'
                      }`}
                    >
                      {selectedCluster.is_active_candidate ? 'Active Interception Zone' : 'Historical Hotspot'}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-900">{selectedCluster.cluster_name}</h3>
                  <div className="mt-1 text-xs text-slate-600">
                    Radius: {selectedCluster.radius_km || 2.0} km • ATMs: {selectedCluster.atm_count || 0}
                  </div>
                </div>

                {/* Historical Baseline vs Active Data */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="text-[10px] text-slate-500 uppercase font-semibold">Historical Risk</div>
                    <div className="text-base font-bold text-slate-800 mt-0.5">
                      {selectedCluster.historical_risk != null ? `${Math.round(selectedCluster.historical_risk * 100)}%` : 'Baseline'}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">Baseline density</div>
                  </div>
                  <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="text-[10px] text-slate-500 uppercase font-semibold">Active Cases</div>
                    <div className="text-base font-bold text-slate-800 mt-0.5">
                      {selectedCluster.active_cases || 0}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {selectedCluster.is_active_candidate ? 'Eligible predictions' : 'None eligible'}
                    </div>
                  </div>
                </div>

                {selectedCluster.is_active_candidate ? (
                  <div className="space-y-3">
                    <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs space-y-1">
                      <div className="font-semibold text-amber-900 flex items-center justify-between">
                        <span>Operational Priority:</span>
                        <span className="font-bold uppercase text-amber-800">{selectedCluster.operational_priority || 'Standard'}</span>
                      </div>
                      <div className="text-amber-700 text-[11px]">
                        Associated Amount: ₹{(selectedCluster.associated_complaint_amount || 0).toLocaleString('en-IN')}
                      </div>
                      {selectedCluster.window_status && (
                        <div className="text-amber-700 text-[11px]">
                          Window Status: <span className="font-semibold">{selectedCluster.window_status}</span>
                        </div>
                      )}
                    </div>

                    {selectedCluster.linked_complaint_numbers && selectedCluster.linked_complaint_numbers.length > 0 && (
                      <div className="space-y-1.5">
                        <div className="text-[11px] font-semibold text-slate-700">Linked Complaints:</div>
                        <div className="flex flex-wrap gap-1.5">
                          {selectedCluster.linked_complaint_numbers.map((cNum) => (
                            <button
                              key={cNum}
                              onClick={() => {
                                setSelectedComplaintId(cNum);
                              }}
                              className="px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded text-xs font-mono font-medium transition-colors"
                            >
                              {cNum} →
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600 space-y-2">
                    <div className="font-medium text-slate-800 flex items-center gap-1.5">
                      <Shield className="w-3.5 h-3.5 text-slate-500" />
                      <span>Historical Baseline Zone</span>
                    </div>
                    <p className="text-[11px] text-slate-500 leading-relaxed">
                      This cluster is an ATM cash-out concentration zone derived from historical cybercrime patterns. There are currently no active case predictions routed here.
                    </p>
                    <p className="text-[10px] text-slate-500 italic">
                      Select an active complaint from the dropdown or dashboard to render tactical interception rings and model provenance.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              /* Outside Scope / Overview State */
              <div className="py-8 px-4 text-center space-y-3">
                <Compass className="w-8 h-8 text-blue-500 mx-auto" />
                <h4 className="text-sm font-bold text-slate-900">
                  {selectedComplaintId ? 'Prediction Unavailable' : 'Surveillance Overview'}
                </h4>
                <div className="text-xs text-slate-500 leading-relaxed">
                  {selectedComplaintId
                    ? predictionError || 'No persisted prediction found for this complaint.'
                    : 'Select a case from the top selector or click an active candidate cluster below to focus tactical intelligence.'}
                </div>
                {selectedComplaintId && (
                  <button
                    onClick={() => navigate(`/cases/${selectedComplaintId}`)}
                    className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold"
                  >
                    Open Case Intelligence
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Active Interception Clusters Table (Phase 4) */}
      <div className="p-5 bg-white rounded-lg border border-[#DCE5F0] shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#DCE5F0]">
          <div>
            <h3 className="text-sm font-bold text-[#173A63] flex items-center gap-2">
              <Shield className="w-4 h-4 text-blue-600" />
              <span>Surveillance Clusters ({hotspots.length} Scoped Results)</span>
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Filtered by: {timeBasis} • Category: {crimeCategory} • District: {districtFilter}
            </p>
          </div>
          <div className="text-xs text-slate-500">
            Showing <strong className="text-amber-600">{activeCandidates.length} Active Candidates</strong> and{' '}
            <strong className="text-slate-700">{hotspots.length - activeCandidates.length} Baseline Hotspots</strong>
          </div>
        </div>

        {gisLoading ? (
          <div className="text-center py-8">
            <Activity className="w-6 h-6 text-blue-600 animate-spin mx-auto mb-2" />
            <span className="text-xs text-slate-500">Updating geospatial clusters...</span>
          </div>
        ) : hotspots.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-xs">
            No clusters match the current filter criteria. Try expanding the time window or resetting filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600 border-collapse">
              <thead>
                <tr className="bg-[#F6F8FC] border-b border-[#DCE5F0] text-[11px] font-bold text-slate-700 uppercase">
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Cluster Name</th>
                  <th className="py-2.5 px-3">District</th>
                  <th className="py-2.5 px-3">Risk Level</th>
                  <th className="py-2.5 px-3">Priority</th>
                  <th className="py-2.5 px-3 text-right">Active Cases</th>
                  <th className="py-2.5 px-3 text-right">Exposure (₹)</th>
                  <th className="py-2.5 px-3">Interception Window (IST)</th>
                  <th className="py-2.5 px-3">Linked Cases</th>
                  <th className="py-2.5 px-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {hotspots.map((cluster) => {
                  const isSelected = selectedClusterId === cluster.id;
                  return (
                    <tr
                      key={cluster.id}
                      className={`hover:bg-slate-50/80 transition-colors ${
                        isSelected ? 'bg-blue-50/60 font-medium' : ''
                      }`}
                    >
                      <td className="py-2 px-3">
                        <span
                          className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                            cluster.is_active_candidate
                              ? 'bg-amber-100 text-amber-800 border border-amber-300'
                              : 'bg-slate-100 text-slate-600 border border-slate-200'
                          }`}
                        >
                          {cluster.is_active_candidate ? 'Active' : 'Baseline'}
                        </span>
                      </td>
                      <td className="py-2 px-3 font-semibold text-slate-900">
                        {cluster.cluster_name}
                      </td>
                      <td className="py-2 px-3 text-slate-600">{cluster.district}</td>
                      <td className="py-2 px-3">
                        <span
                          className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                            cluster.risk_level === 'CRITICAL'
                              ? 'bg-red-50 text-red-700 border border-red-200'
                              : cluster.risk_level === 'HIGH'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-blue-50 text-blue-700 border border-blue-200'
                          }`}
                        >
                          {cluster.risk_level}
                        </span>
                      </td>
                      <td className="py-2 px-3 font-semibold text-slate-700">
                        {cluster.operational_priority || 'STANDARD'}
                      </td>
                      <td className="py-2 px-3 text-right font-bold text-slate-800">
                        {cluster.active_cases || 0}
                      </td>
                      <td className="py-2 px-3 text-right font-bold text-red-600">
                        ₹{Number(cluster.associated_complaint_amount || 0).toLocaleString('en-IN')}
                      </td>
                      <td className="py-2 px-3 text-[11px] text-slate-600">
                        {cluster.expected_window || 'Baseline surveillance'}
                      </td>
                      <td className="py-2 px-3">
                        {cluster.linked_complaint_numbers && cluster.linked_complaint_numbers.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {cluster.linked_complaint_numbers.slice(0, 3).map((cNum) => (
                              <button
                                key={cNum}
                                onClick={() => setSelectedComplaintId(cNum)}
                                className="px-1.5 py-0.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded text-[10px] font-mono border border-blue-200"
                              >
                                {cNum}
                              </button>
                            ))}
                            {cluster.linked_complaint_numbers.length > 3 && (
                              <span className="text-[10px] text-slate-400">
                                +{cluster.linked_complaint_numbers.length - 3} more
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-center">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedClusterId(cluster.id);
                            setSelectedCluster(cluster);
                            if (cluster.linked_complaint_numbers && cluster.linked_complaint_numbers.length > 0) {
                              setSelectedComplaintId(cluster.linked_complaint_numbers[0]);
                            } else {
                              setSelectedComplaintId('');
                              setSelectedComplaint(null);
                            }
                            syncParamsToUrl({ cluster: String(cluster.id) });
                          }}
                          className="px-2 py-1 bg-white hover:bg-blue-50 text-blue-700 border border-[#DCE5F0] rounded text-xs font-semibold transition-colors"
                        >
                          Focus
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
