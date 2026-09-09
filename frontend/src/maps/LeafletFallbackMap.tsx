import React from 'react';
import { MapContainer, TileLayer, Circle, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { HotspotCluster, ATMLocationItem, PredictionLocationItem, Complaint } from '../types';
import { ShieldAlert, ArrowRight, Eye, AlertTriangle, MapPin } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const createClusterIcon = (riskLevel: string, isPulsing: boolean) => {
  const color = riskLevel === 'CRITICAL' ? '#ef4444' : riskLevel === 'HIGH' ? '#f59e0b' : '#3b82f6';
  const pulseHtml = isPulsing
    ? `<div style="position:absolute; width:34px; height:34px; border-radius:50%; background:${color}; opacity:0.25; animation:ping 2.5s cubic-bezier(0,0,0.2,1) infinite; top:-5px; left:-5px;"></div>`
    : '';

  return L.divIcon({
    className: 'custom-risk-icon',
    html: `
      <div style="position:relative; width:24px; height:24px; display:flex; align-items:center; justify-content:center;">
        ${pulseHtml}
        <div style="width:20px; height:20px; border-radius:50%; background:${color}; border:2px solid #ffffff; box-shadow:0 0 10px ${color}; display:flex; align-items:center; justify-content:center; color:#fff; font-size:10px; font-weight:bold;">
          !
        </div>
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
};

const createPredictionIcon = (rank: number) => {
  const bg = rank === 1 ? '#06b6d4' : rank === 2 ? '#3b82f6' : '#64748b';
  const border = rank === 1 ? '#ffffff' : '#cbd5e1';
  return L.divIcon({
    className: 'custom-pred-icon',
    html: `
      <div style="position:relative; width:28px; height:28px; display:flex; align-items:center; justify-content:center;">
        <div style="width:24px; height:24px; border-radius:6px; background:${bg}; border:2px solid ${border}; box-shadow:0 0 12px rgba(6,182,212,0.6); display:flex; align-items:center; justify-content:center; color:#060a15; font-size:11px; font-weight:bold; font-family:monospace;">
          #${rank}
        </div>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
};

const createOriginIcon = () => {
  return L.divIcon({
    className: 'custom-origin-icon',
    html: `
      <div style="width:20px; height:20px; border-radius:50%; background:#10b981; border:2px solid #ffffff; box-shadow:0 0 10px #10b981; display:flex; align-items:center; justify-content:center; color:#fff; font-size:10px; font-weight:bold;">
        O
      </div>
    `,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
};

const createAtmIcon = () => {
  return L.divIcon({
    className: 'custom-atm-icon',
    html: `
      <div style="width:10px; height:10px; border-radius:2px; background:#38bdf8; border:1px solid #ffffff; box-shadow:0 0 5px #38bdf8;"></div>
    `,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
  });
};

export interface LeafletFallbackMapProps {
  hotspots: HotspotCluster[];
  atms?: ATMLocationItem[];
  topLocations?: PredictionLocationItem[];
  complaint?: Complaint | null;
  prediction?: any;
  highlightCluster?: string;
  height?: string;
  showPredictionZones?: boolean;
  showHotspots?: boolean;
  showAtms?: boolean;
  showComplaintOrigin?: boolean;
  focusTarget?: 'india' | 'complaint' | 'top1' | null;
}

export const LeafletFallbackMap: React.FC<LeafletFallbackMapProps> = ({
  hotspots,
  atms = [],
  topLocations = [],
  complaint,
  prediction,
  highlightCluster,
  height = '480px',
  showPredictionZones = true,
  showHotspots = true,
  showAtms = true,
  showComplaintOrigin = true,
}) => {
  const navigate = useNavigate();

  // Determine initial center: top prediction, or highlighted cluster, or default MP corridor
  let centerLat = 22.74;
  let centerLon = 75.88;
  let zoom = 11;

  if (topLocations.length > 0 && topLocations[0].latitude && topLocations[0].longitude) {
    centerLat = topLocations[0].latitude;
    centerLon = topLocations[0].longitude;
    zoom = 12;
  } else if (highlightCluster) {
    const matched = hotspots.find(h => h.cluster_name.toLowerCase().includes(highlightCluster.toLowerCase()));
    if (matched) {
      centerLat = matched.latitude;
      centerLon = matched.longitude;
      zoom = 12;
    }
  }

  // Victim coordinates if complaint available
  const hasVictimCoords = complaint?.victim_location && (
    complaint.victim_location.toLowerCase().includes('bhopal') ? { lat: 23.2332, lon: 77.4343 } :
    complaint.victim_location.toLowerCase().includes('indore') ? { lat: 22.7533, lon: 75.8937 } :
    null
  );

  return (
    <div style={{ height, width: '100%' }} className="rounded-xl overflow-hidden border border-[#162544] relative z-10 shadow-2xl">
      <MapContainer
        center={[centerLat, centerLon]}
        zoom={zoom}
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%', backgroundColor: '#070c18' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Complaint Origin Pin */}
        {showComplaintOrigin && hasVictimCoords && (
          <Marker position={[hasVictimCoords.lat, hasVictimCoords.lon]} icon={createOriginIcon()}>
            <Popup>
              <div className="bg-[#0b1326] text-slate-100 p-2 text-xs font-mono">
                <div className="font-bold text-emerald-400">Complaint Origin</div>
                <div className="text-slate-200">{complaint?.victim_location}</div>
                <div className="text-[10px] text-slate-400 mt-1">Ref: {complaint?.complaint_number}</div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Render Top Predicted Locations if provided */}
        {showPredictionZones && topLocations.map((loc) => {
          if (!loc.latitude || !loc.longitude) return null;
          const isTop1 = loc.rank === 1;
          const strokeColor = isTop1 ? '#06b6d4' : loc.rank === 2 ? '#3b82f6' : '#94a3b8';

          return (
            <React.Fragment key={`pred-${loc.rank}-${loc.location_name}`}>
              <Circle
                center={[loc.latitude, loc.longitude]}
                radius={2500} // 2.5 km operational search radius
                pathOptions={{
                  color: strokeColor,
                  fillColor: strokeColor,
                  fillOpacity: isTop1 ? 0.22 : 0.12,
                  weight: isTop1 ? 2.5 : 1.5,
                  dashArray: isTop1 ? '5, 5' : undefined
                }}
              />
              <Marker position={[loc.latitude, loc.longitude]} icon={createPredictionIcon(loc.rank)}>
                <Popup>
                  <div className="bg-[#0b1326] text-slate-100 p-3 rounded-lg border border-[#1b2b4d] font-sans w-64">
                    <div className="flex items-center justify-between pb-1.5 border-b border-[#1b2b4d] mb-2">
                      <span className="font-bold text-xs text-slate-100">Predicted Cash-Out Zone</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded font-mono font-bold bg-cyan-500/20 text-cyan-300">
                        Rank #{loc.rank}
                      </span>
                    </div>
                    <div className="space-y-1 text-xs font-mono text-slate-300">
                      <div><strong className="text-white">{loc.location_name}</strong></div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Candidate Likelihood:</span>
                        <span className="text-cyan-300 font-bold">{Math.round(loc.probability * 100)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Threat Level:</span>
                        <span className={loc.risk_level === 'CRITICAL' ? 'text-red-400 font-bold' : 'text-amber-400 font-bold'}>{loc.risk_level}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Distance from Origin:</span>
                        <span>{loc.distance_km} km</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Operational Radius:</span>
                        <span className="text-slate-300">2.5 km search zone</span>
                      </div>
                      <div className="text-[10px] text-slate-400 pt-1 border-t border-[#1b2b4d]/50">
                        {loc.reasoning}
                      </div>
                    </div>
                  </div>
                </Popup>
              </Marker>
            </React.Fragment>
          );
        })}

        {/* Render Hotspot Clusters */}
        {showHotspots && hotspots.map((cluster) => {
          const isCritical = cluster.risk_level === 'CRITICAL';
          const isHighlighted = highlightCluster && cluster.cluster_name.toLowerCase().includes(highlightCluster.toLowerCase());
          const circleColor = isCritical ? '#ef4444' : cluster.risk_level === 'HIGH' ? '#f59e0b' : '#3b82f6';
          const radiusMeters = (cluster.radius_km || 2.5) * 1000;

          return (
            <React.Fragment key={cluster.id}>
              <Circle
                center={[cluster.latitude, cluster.longitude]}
                radius={radiusMeters}
                pathOptions={{
                  color: isHighlighted ? '#06b6d4' : circleColor,
                  fillColor: circleColor,
                  fillOpacity: isCritical ? 0.2 : 0.12,
                  weight: isHighlighted ? 2.5 : 1.5,
                  dashArray: isCritical ? '6, 6' : undefined,
                }}
              />
              <Marker
                position={[cluster.latitude, cluster.longitude]}
                icon={createClusterIcon(cluster.risk_level, isCritical || !!isHighlighted)}
              >
                <Popup>
                  <div className="bg-[#0b1326] text-slate-100 p-3 rounded-lg border border-[#1b2b4d] font-sans w-64">
                    <div className="flex items-center justify-between pb-2 border-b border-[#1b2b4d] mb-2">
                      <span className="font-bold text-xs text-slate-100">{cluster.cluster_name}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded font-bold font-mono ${
                          cluster.risk_level === 'CRITICAL'
                            ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                            : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                        }`}
                      >
                        {cluster.risk_level} ({Math.round((cluster.risk_score || 0.5) * 100)}%)
                      </span>
                    </div>

                    <div className="space-y-1.5 text-xs text-slate-300 font-mono">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Time Window:</span>
                        <span className="text-cyan-300 font-bold">{cluster.expected_window}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Amount At Risk:</span>
                        <span className="text-emerald-400 font-bold">₹{(cluster.amount_at_risk || 0).toLocaleString('en-IN')}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Search Radius:</span>
                        <span>{cluster.radius_km || 2.5} km operational zone</span>
                      </div>
                    </div>

                    <div className="mt-3 pt-2 border-t border-[#1b2b4d] flex items-center justify-between gap-1.5">
                      <button
                        onClick={() => navigate('/cases/CMP-1042')}
                        className="flex-1 px-2 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-[11px] font-bold text-center flex items-center justify-center space-x-1"
                      >
                        <Eye className="w-3 h-3" />
                        <span>Case</span>
                      </button>
                      <button
                        onClick={() => navigate('/network/CMP-1042')}
                        className="flex-1 px-2 py-1 bg-[#122040] hover:bg-[#1a2d5a] border border-cyan-500/30 text-cyan-300 rounded text-[11px] font-bold text-center"
                      >
                        Network
                      </button>
                    </div>
                  </div>
                </Popup>
              </Marker>
            </React.Fragment>
          );
        })}

        {/* Render ATMs */}
        {showAtms && atms.map((atm) => (
          <Marker
            key={atm.id}
            position={[atm.latitude, atm.longitude]}
            icon={createAtmIcon()}
          >
            <Popup>
              <div className="bg-[#0b1326] text-slate-100 p-2 text-xs font-mono">
                <div className="font-bold text-cyan-300">ATM Node</div>
                <div className="text-slate-200 text-[11px] font-semibold">{atm.bank_name}</div>
                <div className="text-slate-400 text-[10px]">{atm.address}</div>
                <div className="text-[10px] text-slate-500 mt-1">Code: {atm.atm_code} | Cash: {atm.cash_available ? 'Available' : 'Unavailable'}</div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
};
