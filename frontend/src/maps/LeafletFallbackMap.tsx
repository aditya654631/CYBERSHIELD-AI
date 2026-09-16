import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Circle, Marker, Popup, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import { HotspotCluster, ATMLocationItem, PredictionLocationItem, Complaint } from '../types';
import { Eye } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { hasCoordinates, modelScore, predictionWindow } from '../utils/predictionDisplay';
import 'leaflet/dist/leaflet.css';

const createClusterIcon = (riskLevel: string, isPulsing: boolean) => {
  const color = riskLevel === 'CRITICAL' ? '#ef4444' : riskLevel === 'HIGH' ? '#f59e0b' : '#3b82f6';
  return L.divIcon({
    className: 'custom-risk-icon',
    html: `
      <div style="position:relative; width:22px; height:22px; display:flex; align-items:center; justify-content:center;">
        <div style="width:18px; height:18px; border-radius:50%; background:${color}; border:2px solid #ffffff; box-shadow:0 0 6px ${color}; display:flex; align-items:center; justify-content:center; color:#fff; font-size:9px; font-weight:bold;">
          !
        </div>
      </div>
    `,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
};

const createHistoricalClusterIcon = () => {
  return L.divIcon({
    className: 'custom-historical-cluster-icon',
    html: `
      <div style="position:relative; width:16px; height:16px; display:flex; align-items:center; justify-content:center;">
        <div style="width:12px; height:12px; border-radius:50%; background:#64748b; border:1.5px solid #ffffff; box-shadow:0 0 4px rgba(0,0,0,0.3);"></div>
      </div>
    `,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
};

const createPredictionIcon = (rank: number) => {
  // Rank 1 visually strongest, Rank 2 and 3 progressively less prominent
  const bg = rank === 1 ? '#06b6d4' : (rank === 2 ? '#2563eb' : '#475569');
  const border = rank === 1 ? '#ffffff' : (rank === 2 ? '#93c5fd' : '#94a3b8');
  const size = rank === 1 ? 30 : (rank === 2 ? 26 : 22);
  const fontSize = rank === 1 ? 12 : (rank === 2 ? 11 : 10);
  const half = Math.round(size / 2);

  return L.divIcon({
    className: 'custom-pred-icon',
    html: `
      <div style="position:relative; width:${size}px; height:${size}px; display:flex; align-items:center; justify-content:center;">
        <div style="width:${size}px; height:${size}px; border-radius:6px; background:${bg}; border:2px solid ${border}; box-shadow:0 0 ${rank === 1 ? '10px' : '4px'} rgba(6,182,212,0.4); display:flex; align-items:center; justify-content:center; color:#ffffff; font-size:${fontSize}px; font-weight:bold; font-family:monospace;">
          #${rank}
        </div>
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [half, half],
  });
};

const createOriginIcon = () => {
  return L.divIcon({
    className: 'custom-origin-icon',
    html: `
      <div style="width:20px; height:20px; border-radius:50%; background:#10b981; border:2px solid #ffffff; box-shadow:0 0 8px #10b981; display:flex; align-items:center; justify-content:center; color:#fff; font-size:10px; font-weight:bold; font-family:monospace;">
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
      <div style="width:8px; height:8px; border-radius:2px; background:#38bdf8; border:1px solid #ffffff; box-shadow:0 0 3px #38bdf8;"></div>
    `,
    iconSize: [8, 8],
    iconAnchor: [4, 4],
  });
};

const createPriorityHotspotIcon = (priorityRank: number, riskLevel: string) => {
  const bg = riskLevel === 'CRITICAL' ? '#ef4444' : riskLevel === 'HIGH' ? '#f59e0b' : '#3b82f6';
  return L.divIcon({
    className: 'custom-priority-hotspot-icon',
    html: `
      <div style="width:24px; height:24px; border-radius:4px; background:${bg}; border:2px solid #ffffff; box-shadow:0 0 8px rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center; color:#ffffff; font-size:10px; font-weight:bold; font-family:monospace;">
        P${priorityRank}
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
};

/**
 * Reactive controller to dynamically fit Leaflet map bounds when topLocations or complaint change.
 */
const MapBoundsController: React.FC<{
  topLocations: PredictionLocationItem[];
  complaint?: Complaint | null;
}> = ({ topLocations, complaint }) => {
  const map = useMap();

  useEffect(() => {
    const points: [number, number][] = [];

    topLocations.forEach((loc) => {
      if (hasCoordinates(loc.latitude, loc.longitude)) {
        points.push([Number(loc.latitude), Number(loc.longitude)]);
      }
    });

    if (
      hasCoordinates(complaint?.victim_lat, complaint?.victim_lon)
    ) {
      points.push([Number(complaint!.victim_lat), Number(complaint!.victim_lon)]);
    }

    if (points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds.pad(0.2), { padding: [40, 40], maxZoom: 12 });
    } else {
      map.setView([28.6139, 77.2090], 11);
    }
  }, [topLocations, complaint, map]);

  useEffect(() => {
    const container = map.getContainer();
    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    observer.observe(container);
    map.invalidateSize();
    return () => observer.disconnect();
  }, [map]);

  return null;
};

const ClusterCenterController: React.FC<{
  selectedClusterId?: number | null;
  hotspots: HotspotCluster[];
}> = ({ selectedClusterId, hotspots }) => {
  const map = useMap();
  useEffect(() => {
    if (selectedClusterId) {
      const target = hotspots.find((h) => h.id === selectedClusterId);
      if (target && hasCoordinates(target.latitude, target.longitude)) {
        map.setView([Number(target.latitude), Number(target.longitude)], 13);
      }
    }
  }, [selectedClusterId, hotspots, map]);
  return null;
};

export interface LeafletFallbackMapProps {
  hotspots?: HotspotCluster[];
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
  priorityHotspotIds?: number[];
  selectedClusterId?: number | null;
}

export const LeafletFallbackMap: React.FC<LeafletFallbackMapProps> = ({
  hotspots = [],
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
  priorityHotspotIds,
  selectedClusterId,
}) => {
  const navigate = useNavigate();

  // Initial center fallback (Delhi Pilot baseline coordinates or MP fallback)
  let centerLat = 28.6315;
  let centerLon = 77.2167;
  let zoom = 11;

  if (topLocations.length > 0 && topLocations[0].latitude && topLocations[0].longitude) {
    centerLat = Number(topLocations[0].latitude);
    centerLon = Number(topLocations[0].longitude);
    zoom = 12;
  } else if (highlightCluster) {
    const matched = hotspots.find(h => h.cluster_name.toLowerCase().includes(highlightCluster.toLowerCase()));
    if (matched) {
      centerLat = matched.latitude;
      centerLon = matched.longitude;
      zoom = 12;
    }
  }

  // Legitimate victim coordinates only (Correction 5: no string matching on "bhopal" or "indore")
  const hasVictimCoords = hasCoordinates(complaint?.victim_lat, complaint?.victim_lon)
    ? { lat: Number(complaint!.victim_lat), lon: Number(complaint!.victim_lon) } : null;

  return (
    <div style={{ height, width: '100%' }} className="rounded-lg overflow-hidden border border-[#DCE5F0] relative z-10 shadow-xs">
      <MapContainer
        center={[centerLat, centerLon]}
        zoom={zoom}
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%', backgroundColor: '#f6f8fc' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Dynamic Bounds Controller */}
        <MapBoundsController topLocations={topLocations} complaint={complaint} />
        <ClusterCenterController selectedClusterId={selectedClusterId} hotspots={hotspots} />

        {/* Complaint Origin Pin: Only rendered when legitimate coordinates exist */}
        {showComplaintOrigin && hasVictimCoords && (
          <Marker position={[hasVictimCoords.lat, hasVictimCoords.lon]} icon={createOriginIcon()}>
            <Popup>
              <div className="bg-white text-slate-800 p-2 text-xs border border-[#DCE5F0] rounded shadow-xs">
                <div className="font-bold text-emerald-700">COMPLAINT ORIGIN</div>
                <div className="text-slate-800 mt-0.5">{complaint?.victim_location || 'Incident Location'}</div>
                <div className="text-[10px] text-slate-500 mt-1">Ref: {complaint?.complaint_number}</div>
                <div className="text-[9px] text-slate-400 mt-0.5">Coordinates: ({hasVictimCoords.lat.toFixed(4)}, {hasVictimCoords.lon.toFixed(4)})</div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Render Top Predicted Locations (Persisted Step-10 Data Only) */}
        {showPredictionZones && topLocations.map((loc) => {
          if (!hasCoordinates(loc.latitude, loc.longitude)) {
            return null;
          }
          const lat = Number(loc.latitude);
          const lon = Number(loc.longitude);
          const isTop1 = loc.rank === 1;

          return (
            <React.Fragment key={`pred-${loc.rank}-${loc.cluster_id || loc.location_name}`}>
              {/* Operational Tactical Rings (Requirement 8): 
                  Concentric search bands around primary predicted location (Rank 1).
                  Explicitly marked as operational search perimeters, not statistical confidence intervals. */}
              {isTop1 ? (
                <>
                  {/* Outer Context Band: 2.5–5 km */}
                  <Circle
                    center={[lat, lon]}
                    radius={5000}
                    pathOptions={{
                      color: '#0891b2',
                      fillColor: '#0891b2',
                      fillOpacity: 0.03,
                      weight: 1,
                      dashArray: '6, 6'
                    }}
                  />
                  {/* High-Risk Operational Search Band: 1–2.5 km */}
                  <Circle
                    center={[lat, lon]}
                    radius={2500}
                    pathOptions={{
                      color: '#06b6d4',
                      fillColor: '#06b6d4',
                      fillOpacity: 0.10,
                      weight: 2,
                    }}
                  />
                  {/* Critical Proximity Band: 0–1 km */}
                  <Circle
                    center={[lat, lon]}
                    radius={1000}
                    pathOptions={{
                      color: '#22d3ee',
                      fillColor: '#22d3ee',
                      fillOpacity: 0.18,
                      weight: 2,
                      dashArray: '4, 4'
                    }}
                  />
                </>
              ) : (
                /* Rank 2 & 3: Single restrained operational search radius (2.5 km) */
                <Circle
                  center={[lat, lon]}
                  radius={2500}
                  pathOptions={{
                    color: loc.rank === 2 ? '#3b82f6' : '#64748b',
                    fillColor: loc.rank === 2 ? '#3b82f6' : '#64748b',
                    fillOpacity: loc.rank === 2 ? 0.08 : 0.04,
                    weight: 1.5,
                  }}
                />
              )}

              {/* Numbered Prediction Marker (#1, #2, #3) */}
              <Marker position={[lat, lon]} icon={createPredictionIcon(loc.rank)} zIndexOffset={1200 - loc.rank * 50}>
                <Tooltip direction="top" offset={[0, -14]} permanent>{`#${loc.rank} ${loc.location_name}`}</Tooltip>
                <Popup>
                  <div className="bg-[#0b1326] text-slate-100 p-3 rounded-lg border border-[#1b2b4d] font-sans w-72">
                    <div className="flex items-center justify-between pb-1.5 border-b border-[#1b2b4d] mb-2">
                      <span className="font-bold text-xs text-slate-100 font-mono">Predicted Cash-Out Cluster</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${
                        isTop1 ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' : 'bg-slate-700 text-slate-200'
                      }`}>
                        {isTop1 ? '#1 PRIMARY' : loc.rank === 2 ? '#2 SECONDARY' : '#3 TERTIARY'}
                      </span>
                    </div>

                    <div className="space-y-1.5 text-xs font-mono text-slate-300">
                      <div>
                        <span className="text-[10px] text-slate-400">Cluster: </span>
                        <strong className="text-white">{loc.location_name}</strong>
                        {loc.cluster_id && <span className="text-[10px] text-slate-500 ml-1">(ID: {loc.cluster_id})</span>}
                      </div>

                      {loc.zone && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Zone / District:</span>
                          <span className="text-slate-200">{loc.zone}</span>
                        </div>
                      )}

                      <div className="flex justify-between">
                        <span className="text-slate-400">Distance from Origin:</span>
                        <span className="text-slate-200">{loc.distance_km == null ? 'Unavailable' : `${loc.distance_km} km`}</span>
                      </div>

                      <div className="flex justify-between">
                        <span className="text-slate-400">Operational Priority:</span>
                        <span className={loc.risk_level === 'CRITICAL' ? 'text-red-400 font-bold' : (loc.risk_level === 'HIGH' ? 'text-amber-400 font-bold' : 'text-blue-300 font-bold')}>
                          {loc.risk_level || 'HIGH'}
                        </span>
                      </div>

                      <div className="flex justify-between">
                        <span className="text-slate-400">Model ranking score:</span>
                        <strong className="text-slate-200 font-mono">{modelScore(loc)}</strong>
                      </div>
                      <div className="space-y-1">
                        <span className="text-slate-400">Operational Window:</span>
                        <div className="text-slate-200">{predictionWindow(prediction)}</div>
                      </div>

                      <div className="text-[10px] text-slate-400 pt-1 border-t border-[#1b2b4d]/50">
                        {loc.reasoning || 'Ranked candidate cluster node'}
                      </div>

                      <div className="text-[9px] text-slate-500 pt-1 border-t border-[#1b2b4d]/30">
                        Provenance: {prediction?.prediction_mode === 'deterministic_demo' ? 'Deterministic Demo' : `Synthetic Delhi ML / ${prediction?.model_version || 'unavailable'}`}
                      </div>

                      {isTop1 && (
                        <div className="text-[9px] text-cyan-400/80 pt-1 italic">
                          Operational visualization rings (1km / 2.5km / 5km tactical radii). Not a statistical confidence interval.
                        </div>
                      )}
                    </div>
                  </div>
                </Popup>
              </Marker>
            </React.Fragment>
          );
        })}

        {/* Render Hotspot Clusters (Active Candidates vs Historical Baseline) */}
        {showHotspots && hotspots.map((cluster) => {
          if (!hasCoordinates(cluster.latitude, cluster.longitude)) return null;
          const isActiveCandidate = cluster.is_active_candidate ?? (cluster.active_cases > 0);
          const isSelected = selectedClusterId != null && cluster.id === selectedClusterId;
          const priorityIndex = priorityHotspotIds?.indexOf(cluster.id);
          const isPriority = priorityIndex != null && priorityIndex >= 0;
          const priorityRank = isPriority ? priorityIndex + 1 : null;

          const priorityLevel = (cluster.operational_priority || cluster.risk_level || 'LOW').toUpperCase();
          const isCritical = priorityLevel === 'CRITICAL';
          const isHigh = priorityLevel === 'HIGH';

          const circleColor = isSelected
            ? '#06b6d4'
            : isActiveCandidate
            ? (isCritical ? '#ef4444' : isHigh ? '#f59e0b' : '#3b82f6')
            : '#64748b';

          const radiusMeters = (cluster.radius_km || 2.5) * 1000;

          return (
            <React.Fragment key={cluster.id}>
              <Circle
                center={[cluster.latitude, cluster.longitude]}
                radius={radiusMeters}
                pathOptions={{
                  color: isSelected ? '#06b6d4' : isPriority ? '#2563eb' : circleColor,
                  fillColor: circleColor,
                  fillOpacity: isSelected ? 0.25 : isActiveCandidate ? (isPriority ? 0.18 : 0.08) : 0.04,
                  weight: isSelected ? 2.5 : isActiveCandidate ? (isPriority ? 2.5 : 1.5) : 1,
                  dashArray: isActiveCandidate && isCritical ? '6, 6' : undefined,
                }}
              />
              <Marker
                position={[cluster.latitude, cluster.longitude]}
                icon={
                  isPriority
                    ? createPriorityHotspotIcon(priorityRank!, priorityLevel)
                    : isActiveCandidate
                    ? createClusterIcon(priorityLevel, isCritical || !!isSelected)
                    : createHistoricalClusterIcon()
                }
              >
                <Popup>
                  <div className="bg-[#0b1326] text-slate-100 p-3 rounded-lg border border-[#1b2b4d] font-sans w-64">
                    <div className="flex items-center justify-between pb-2 border-b border-[#1b2b4d] mb-2">
                      <span className="font-bold text-xs text-slate-100">{cluster.cluster_name}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded font-bold font-mono ${
                          isActiveCandidate
                            ? isCritical
                              ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                              : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                            : 'bg-slate-700/40 text-slate-400 border border-slate-600/40'
                        }`}
                      >
                        {isActiveCandidate ? priorityLevel : 'HISTORICAL'}
                      </span>
                    </div>

                    {isPriority && (
                      <div className="mb-2 pb-1.5 border-b border-[#1b2b4d] flex items-center justify-between">
                        <span className="text-xs font-bold text-blue-400 font-mono">Priority Hotspot #{priorityRank}</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-500/20 text-blue-300 font-mono">P{priorityRank}</span>
                      </div>
                    )}

                    <div className="space-y-1.5 text-xs text-slate-300 font-mono">
                      {isActiveCandidate ? (
                        <>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Active Window:</span>
                            <span className="text-cyan-300 font-bold">{cluster.expected_window}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Candidate Score:</span>
                            <span className="text-slate-200 font-bold">{cluster.candidate_score != null ? `${(cluster.candidate_score * 100).toFixed(1)}%` : 'N/A'}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Associated Amount:</span>
                            <span className="text-emerald-400 font-bold">₹{(cluster.associated_complaint_amount ?? cluster.amount_at_risk ?? 0).toLocaleString('en-IN')}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Active Cases:</span>
                            <span className="text-slate-200">{cluster.active_cases}</span>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Baseline Risk:</span>
                            <span className="text-slate-300 font-bold">{cluster.historical_risk != null ? `${Math.round(cluster.historical_risk * 100)}%` : 'Baseline'}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Active Cases:</span>
                            <span className="text-slate-400">0 (No active prediction)</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Associated Amount:</span>
                            <span className="text-slate-400">₹0</span>
                          </div>
                        </>
                      )}
                      <div className="flex justify-between">
                        <span className="text-slate-400">Context Radius:</span>
                        <span>{cluster.radius_km || 2.5} km</span>
                      </div>
                    </div>

                    {isActiveCandidate && cluster.linked_complaint_numbers && cluster.linked_complaint_numbers.length > 0 && (
                      <div className="mt-3 pt-2 border-t border-[#1b2b4d] flex items-center justify-between gap-1.5">
                        <button
                          onClick={() => navigate(`/cases/${cluster.linked_complaint_numbers![0]}`)}
                          className="flex-1 px-2 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-[11px] font-bold text-center flex items-center justify-center space-x-1"
                        >
                          <Eye className="w-3 h-3" />
                          <span>View {cluster.linked_complaint_numbers[0]}</span>
                        </button>
                      </div>
                    )}
                  </div>
                </Popup>
              </Marker>
            </React.Fragment>
          );
        })}

        {/* Render ATMs: Prototype Context Only (Requirement 11) */}
        {showAtms && atms.filter((atm) => hasCoordinates(atm.latitude, atm.longitude)).map((atm) => (
          <Marker
            key={atm.id}
            position={[atm.latitude, atm.longitude]}
            icon={createAtmIcon()}
          >
            <Popup>
              <div className="bg-[#0b1326] text-slate-100 p-2 text-xs font-mono">
                <div className="font-bold text-cyan-300">PROTOTYPE ATM CONTEXT</div>
                <div className="text-slate-200 text-[11px] font-semibold mt-0.5">{atm.bank_name}</div>
                <div className="text-slate-400 text-[10px]">{atm.address}</div>
                <div className="text-[10px] text-slate-500 mt-1">Code: {atm.atm_code} | Cash: {atm.cash_available ? 'Available' : 'Unavailable'}</div>
                <div className="text-[9px] text-slate-600 mt-1 italic">Reference ATM context from synthetic baseline. Prediction is cluster-level; not an ATM-specific dispatch.</div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Map Legend Footer */}
      <div className="absolute bottom-2 left-2 sm:left-3 right-2 sm:right-auto max-w-[calc(100%-1rem)] sm:max-w-none z-[1000] pointer-events-none bg-[#0b1326]/90 backdrop-blur-xs px-2 sm:px-3 py-1.5 rounded-md border border-[#1b2b4d] text-[9px] sm:text-[10px] font-sans text-slate-300 shadow-xs flex flex-wrap items-center gap-x-2.5 sm:gap-x-3 gap-y-0.5">
        <span className="flex items-center space-x-1">
          <span className="w-2.5 h-2.5 rounded-sm bg-cyan-500 inline-block shrink-0"></span>
          <span className="font-semibold text-slate-200">Predicted Zone (#1 Rings)</span>
        </span>
        <span className="flex items-center space-x-1">
          <span className="w-2 h-2 rounded-full bg-red-500 inline-block shrink-0"></span>
          <span className="font-medium text-slate-200">Active Candidate</span>
        </span>
        <span className="flex items-center space-x-1">
          <span className="w-2 h-2 rounded-full bg-slate-500 inline-block shrink-0"></span>
          <span className="text-slate-400">Historical Hotspot (Baseline)</span>
        </span>
        <span className="flex items-center space-x-1">
          <span className="w-2 h-2 bg-sky-400 inline-block shrink-0"></span>
          <span>ATM Terminal</span>
        </span>
        <span className="text-slate-400 hidden sm:inline">Provider: OpenStreetMap</span>
      </div>
    </div>
  );
};
