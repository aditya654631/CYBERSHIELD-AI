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
  BellRing
} from 'lucide-react';
import { api } from '../services/api';
import { HotspotCluster, ATMLocationItem, Complaint, Prediction, PredictionLocationItem } from '../types';
import { CashOutRiskMap } from '../maps/CashOutRiskMap';

export const RiskMap: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Complaints & Selection
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [selectedComplaintId, setSelectedComplaintId] = useState<string>('');
  const [selectedComplaint, setSelectedComplaint] = useState<Complaint | null>(null);

  // Persisted Prediction Intelligence State
  const [currentPrediction, setCurrentPrediction] = useState<Prediction | null>(null);
  const [topLocations, setTopLocations] = useState<PredictionLocationItem[]>([]);
  const [predictionLoading, setPredictionLoading] = useState<boolean>(false);
  const [predictionError, setPredictionError] = useState<string | null>(null);
  const [integrityError, setIntegrityError] = useState<string | null>(null);
  const [alertGenerating, setAlertGenerating] = useState<boolean>(false);
  const [alertSuccess, setAlertSuccess] = useState<string | null>(null);

  // Generic GIS Context (Monitored Clusters & Prototype ATMs)
  const [hotspots, setHotspots] = useState<HotspotCluster[]>([]);
  const [atms, setAtms] = useState<ATMLocationItem[]>([]);
  const [gisLoading, setGisLoading] = useState<boolean>(true);
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

  // Filters for Generic Hotspots
  const [districtFilter, setDistrictFilter] = useState('ALL');
  const [riskFilter, setRiskFilter] = useState('ALL');

  // Layer Toggles
  const [showPredictionZones, setShowPredictionZones] = useState<boolean>(true);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [showAtms, setShowAtms] = useState<boolean>(false);

  // 1. Initial Load: Fetch Complaints List from Real API (Correction 2)
  useEffect(() => {
    const loadComplaints = async () => {
      try {
        const comps = await api.getComplaints({ limit: 100 });
        setComplaints(comps);

        // Check query param first, otherwise default to CMP-NEW-000002 or first complaint
        const paramId = searchParams.get('case');
        if (paramId && comps.some(c => c.complaint_number === paramId)) {
          setSelectedComplaintId(paramId);
        } else if (comps.length > 0) {
          const defaultComp = comps.find(c => c.complaint_number === 'CMP-NEW-000002') || comps[0];
          setSelectedComplaintId(defaultComp.complaint_number);
        }
      } catch (err) {
        console.error('[GIS] Failed to load complaints list', err);
      }
    };
    loadComplaints();
  }, []);

  // 2. Fetch Generic GIS Context (Clusters & ATMs)
  useEffect(() => {
    const fetchGISContext = async () => {
      setGisLoading(true);
      try {
        const data = await api.getRiskMap({
          district: districtFilter !== 'ALL' ? districtFilter : undefined,
          risk_level: riskFilter !== 'ALL' ? riskFilter : undefined,
        });
        setHotspots(data.hotspots);
        setAtms(data.atms);
      } catch (err) {
        console.error('[GIS] Failed to load generic GIS context', err);
      } finally {
        setGisLoading(false);
      }
    };
    fetchGISContext();
  }, [districtFilter, riskFilter]);

  // 3. Reactive Single Source of Truth: Fetch Persisted Prediction on Complaint Change (Requirement 2 & 19)
  useEffect(() => {
    if (!selectedComplaintId) return;

    // Update query param for deep linking / refresh stability (Requirement 22)
    setSearchParams({ case: selectedComplaintId }, { replace: true });

    const matchedComp = complaints.find(c => c.complaint_number === selectedComplaintId) || null;
    setSelectedComplaint(matchedComp);

    // CRITICAL (Requirement 19): Clear previous prediction markers immediately before new fetch
    setPredictionLoading(true);
    setCurrentPrediction(null);
    setTopLocations([]);
    setPredictionError(null);
    setIntegrityError(null);

    const fetchPersistedPrediction = async () => {
      try {
        // Read-only GET request strictly to Step-10 persisted prediction API
        const pred = await api.getPrediction(selectedComplaintId);
        setCurrentPrediction(pred);
        const locs = pred.top_locations || [];
        setTopLocations(locs);

        // Verify Requirement 9: Prediction.primary_cluster_id == PredictionLocation rank=1 cluster_id
        if (pred.primary_cluster_id != null && locs.length > 0) {
          const rank1Cid = locs[0].cluster_id;
          if (rank1Cid != null && pred.primary_cluster_id !== rank1Cid) {
            const errText = `Data Integrity Alert: Primary cluster ID (${pred.primary_cluster_id}) does not match Rank 1 location cluster ID (${rank1Cid}).`;
            console.error('[GIS]', errText);
            setIntegrityError(errText);
          }
        }
      } catch (err: any) {
        // 404 or Outside Scope Handling (Requirement 17)
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
        setPredictionLoading(false);
      }
    };

    fetchPersistedPrediction();
  }, [selectedComplaintId, complaints]);

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
  const isDemo = currentPrediction?.prediction_mode === 'deterministic_demo';
  const highlightClusterName = topLocations.length > 0 ? topLocations[0].location_name : undefined;

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
            Persisted Top-3 Cash-Out Intelligence & High-Risk Operational Zone Surveillance
          </p>
        </div>

        {/* Dynamic Complaint Selector (Correction 2) */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-2 bg-[#F6F8FC] px-3 py-1.5 rounded-md border border-[#DCE5F0] w-full sm:w-auto">
            <span className="text-xs text-blue-700 font-semibold shrink-0">Case:</span>
            <select
              value={selectedComplaintId}
              onChange={(e) => setSelectedComplaintId(e.target.value)}
              className="bg-transparent text-xs text-slate-800 focus:outline-none cursor-pointer font-medium w-full sm:max-w-[220px]"
            >
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
              Hotspot Clusters
            </button>
            <button
              onClick={() => setShowAtms(!showAtms)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors border ${
                showAtms
                  ? 'bg-blue-50 text-blue-700 border-blue-300 font-semibold'
                  : 'bg-white text-slate-600 border-[#DCE5F0] hover:bg-slate-50'
              }`}
            >
              Prototype ATMs
            </button>
          </div>
        </div>
      </div>

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
            highlightCluster={highlightClusterName}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between text-[11px] text-slate-500 px-2">
            <span>
              Provider: <strong className="text-slate-700">Leaflet OpenStreetMap</strong> | Concentric Rings:{' '}
              <strong className="text-blue-700">1km / 2.5km / 5km</strong> (Tactical search radii; not confidence intervals)
            </span>
            <span>
              Single Source of Truth:{' '}
              <strong className="text-emerald-700">Persisted Prediction API (Read-Only)</strong>
            </span>
          </div>
        </div>

        {/* Selected Prediction Intelligence Panel (Requirement 6) */}
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
                {/* Provenance Header (Section 28) */}
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
                    <span className="text-slate-700">{currentPrediction.model_version || 'Location V3.1'}</span>
                  </div>
                  <div className="flex justify-between items-center pt-1 border-t border-[#DCE5F0]">
                    <span className="text-slate-500">Time Window:</span>
                    <span className="text-amber-800 font-semibold">{currentPrediction.when_window}</span>
                  </div>
                </div>

                {/* Top-3 Locations Breakdown (Section 28) */}
                <div className="space-y-2.5">
                  <h4 className="text-xs font-bold text-slate-700 uppercase">
                    Ranked Cash-Out Zones
                  </h4>

                  {topLocations.map((loc) => {
                    const isRank1 = loc.rank === 1;
                    const rankLabel = isRank1 ? '#1 PRIMARY' : loc.rank === 2 ? '#2 SECONDARY' : '#3 TERTIARY';

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
                          <span>Priority Status:</span>
                          <span className="text-slate-700 font-medium">
                            {isRank1 ? 'Primary Target Zone' : 'Candidate Target Zone'}
                          </span>
                        </div>

                        <div className="flex justify-between items-center text-slate-400 text-[10px] mt-0.5">
                          <span>Cluster ID: {loc.cluster_id || 'N/A'}</span>
                          <span>Distance: {loc.distance_km} km</span>
                        </div>
                      </div>
                    );
                  })}
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
            ) : (
              /* Outside Scope / Unavailable State (Requirement 17) */
              <div className="py-8 px-4 text-center space-y-3">
                <AlertCircle className="w-8 h-8 text-amber-500 mx-auto" />
                <h4 className="text-sm font-bold text-slate-900">Prediction Unavailable</h4>
                <div className="text-xs text-slate-500 leading-relaxed">
                  {predictionError || 'No persisted prediction found for this complaint.'}
                </div>
                <div className="p-3 bg-[#F6F8FC] rounded-lg border border-[#DCE5F0] text-[11px] text-slate-600 text-left space-y-1">
                  <div><strong className="text-slate-800">Operational Jurisdiction:</strong> Delhi Pilot (60 Clusters)</div>
                  {selectedComplaint && (
                    <>
                      <div><strong className="text-slate-800">Reported State:</strong> {selectedComplaint.state || 'Unknown'}</div>
                      <div><strong className="text-slate-800">Reported District:</strong> {selectedComplaint.district || 'Unknown'}</div>
                    </>
                  )}
                  <div className="text-amber-700 text-[10px] pt-1">
                    Zero prediction markers rendered to maintain strict model integrity.
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
