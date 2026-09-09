import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  MapPin,
  Filter,
  Layers,
  Search,
  ShieldAlert,
  Clock,
  DollarSign,
  AlertTriangle,
  ArrowRight,
  Eye,
  SlidersHorizontal,
  Compass
} from 'lucide-react';
import { api } from '../services/api';
import { HotspotCluster, ATMLocationItem } from '../types';
import { CashOutRiskMap } from '../maps/CashOutRiskMap';

export const RiskMap: React.FC = () => {
  const navigate = useNavigate();
  const [hotspots, setHotspots] = useState<HotspotCluster[]>([]);
  const [atms, setAtms] = useState<ATMLocationItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [districtFilter, setDistrictFilter] = useState('ALL');
  const [riskFilter, setRiskFilter] = useState('ALL');
  const [fraudTypeFilter, setFraudTypeFilter] = useState('ALL');
  const [selectedCluster, setSelectedCluster] = useState<HotspotCluster | null>(null);

  useEffect(() => {
    const fetchGIS = async () => {
      setLoading(true);
      try {
        const data = await api.getRiskMap({
          district: districtFilter !== 'ALL' ? districtFilter : undefined,
          risk_level: riskFilter !== 'ALL' ? riskFilter : undefined,
        });
        setHotspots(data.hotspots);
        setAtms(data.atms);
        if (data.hotspots.length > 0) {
          setSelectedCluster(data.hotspots[0]);
        }
      } catch (err) {
        console.error('Failed to load GIS data', err);
      } finally {
        setLoading(false);
      }
    };
    fetchGIS();
  }, [districtFilter, riskFilter]);

  return (
    <div className="space-y-6 pb-12">
      {/* GIS Control Header */}
      <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <Compass className="w-5 h-5 text-cyan-400" />
            <h1 className="text-xl font-bold text-white font-['JetBrains_Mono',monospace]">
              Geospatial Predictive Cash-Out Intelligence (GIS)
            </h1>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Real-time clustering & ATM terminal vulnerability surveillance
          </p>
        </div>

        {/* Filter Bar */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-2 bg-[#070c18] px-3 py-1.5 rounded-lg border border-[#162544]">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={districtFilter}
              onChange={(e) => setDistrictFilter(e.target.value)}
              className="bg-transparent text-xs text-slate-200 focus:outline-none font-mono cursor-pointer"
            >
              <option value="ALL">All Districts</option>
              <option value="Indore">Indore</option>
              <option value="Bhopal">Bhopal</option>
              <option value="Ujjain">Ujjain</option>
            </select>
          </div>

          <div className="flex items-center space-x-2 bg-[#070c18] px-3 py-1.5 rounded-lg border border-[#162544]">
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="bg-transparent text-xs text-slate-200 focus:outline-none font-mono cursor-pointer"
            >
              <option value="ALL">All Threat Levels</option>
              <option value="CRITICAL">Critical (&gt;80%)</option>
              <option value="HIGH">High (60-80%)</option>
              <option value="MEDIUM">Medium (&lt;60%)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Map + Selected Hotspot Inspect Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Full GIS Map Canvas */}
        <div className="lg:col-span-8 bg-[#0a1020] rounded-2xl border border-[#162544] p-4 shadow-2xl">
          <CashOutRiskMap
            hotspots={hotspots}
            atms={atms}
            height="580px"
            highlightCluster={selectedCluster?.cluster_name}
          />
        </div>

        {/* Hotspot Cluster Inspector */}
        <div className="lg:col-span-4 space-y-4">
          <div className="p-5 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-[#162544] mb-4">
              <h3 className="text-sm font-bold text-white font-mono uppercase">
                Active Cluster Telemetry
              </h3>
              <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono font-bold">
                {hotspots.length} Monitored
              </span>
            </div>

            {selectedCluster ? (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between">
                    <h4 className="text-base font-bold text-slate-100 font-mono">
                      {selectedCluster.cluster_name}
                    </h4>
                    <span
                      className={`text-xs px-2 py-0.5 rounded font-mono font-bold ${
                        selectedCluster.risk_level === 'CRITICAL'
                          ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                          : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                      }`}
                    >
                      {selectedCluster.risk_level} ({Math.round(selectedCluster.risk_score * 100)}%)
                    </span>
                  </div>
                  <span className="text-xs text-slate-400 font-mono">
                    {selectedCluster.district}, {selectedCluster.state}
                  </span>
                </div>

                <div className="space-y-2.5 text-xs font-mono">
                  <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] flex items-center justify-between">
                    <span className="text-slate-400">Expected Time Window:</span>
                    <span className="text-cyan-300 font-bold">{selectedCluster.expected_window}</span>
                  </div>

                  <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] flex items-center justify-between">
                    <span className="text-slate-400">Amount At Risk:</span>
                    <span className="text-emerald-400 font-bold">
                      ₹{selectedCluster.amount_at_risk.toLocaleString('en-IN')}
                    </span>
                  </div>

                  <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] flex items-center justify-between">
                    <span className="text-slate-400">Active Tied Cases:</span>
                    <span className="text-white font-bold">{selectedCluster.active_cases} Complaints</span>
                  </div>

                  <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] flex items-center justify-between">
                    <span className="text-slate-400">Terminals Monitored:</span>
                    <span className="text-slate-200">{selectedCluster.atm_count} ATMs in {selectedCluster.radius_km}km</span>
                  </div>

                  <div className="p-3 bg-[#070c18] rounded-lg border border-[#162544] flex items-center justify-between">
                    <span className="text-slate-400">Primary Modus:</span>
                    <span className="text-purple-300 font-semibold">{selectedCluster.fraud_type}</span>
                  </div>
                </div>

                {/* Direct Actions */}
                <div className="pt-3 border-t border-[#162544] space-y-2">
                  <button
                    onClick={() => navigate('/cases/CMP-1042')}
                    className="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-mono font-bold transition-all flex items-center justify-center space-x-2 shadow-lg"
                  >
                    <Eye className="w-4 h-4" />
                    <span>VIEW CASES IN THIS CLUSTER</span>
                  </button>

                  <button
                    onClick={() => navigate('/network/CMP-1042')}
                    className="w-full py-2.5 bg-[#0e1933] hover:bg-[#15254d] border border-cyan-500/40 text-cyan-300 rounded-lg text-xs font-mono font-bold transition-all"
                  >
                    VIEW MULE NETWORK FLOW
                  </button>

                  <button
                    onClick={() => navigate('/alerts')}
                    className="w-full py-2.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-mono font-bold transition-all flex items-center justify-center space-x-2 shadow-[0_0_15px_rgba(239,68,68,0.3)]"
                  >
                    <AlertTriangle className="w-4 h-4" />
                    <span>GENERATE CLUSTER INTERCEPT ALERT</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-xs text-slate-400 font-mono">
                Select a cluster marker from the map to inspect telemetry
              </div>
            )}
          </div>

          {/* Quick Hotspot Selector List */}
          <div className="p-4 bg-[#0a1020] rounded-2xl border border-[#162544] shadow-2xl">
            <h4 className="text-xs font-bold text-slate-300 font-mono uppercase mb-3">
              Monitored Hotspots (Click to focus)
            </h4>
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {hotspots.map((h) => (
                <div
                  key={h.id}
                  onClick={() => setSelectedCluster(h)}
                  className={`p-2.5 rounded-lg text-xs font-mono cursor-pointer transition-all flex items-center justify-between border ${
                    selectedCluster?.id === h.id
                      ? 'bg-[#101e3b] border-cyan-500/60 text-white'
                      : 'bg-[#070c18] border-[#162544] text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <span className="truncate">{h.cluster_name}</span>
                  <span className="text-red-400 font-bold">{Math.round(h.risk_score * 100)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
