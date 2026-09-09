import React, { useEffect, useRef, useState } from 'react';
import { setOptions, importLibrary } from '@googlemaps/js-api-loader';
import { HotspotCluster, ATMLocationItem, PredictionLocationItem, Complaint } from '../types';
import { DARK_GEOINT_STYLE } from './googleMapsStyle';
import { LeafletFallbackMap } from './LeafletFallbackMap';
import {
  Layers,
  Map as MapIcon,
  ZoomIn,
  Compass,
  AlertTriangle,
  RotateCcw,
  Eye,
  Check
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export interface UnifiedRiskMapProps {
  hotspots?: HotspotCluster[];
  atms?: ATMLocationItem[];
  topLocations?: PredictionLocationItem[];
  complaint?: Complaint | null;
  prediction?: any;
  highlightCluster?: string;
  height?: string;
  showControls?: boolean;
}

export const UnifiedRiskMap: React.FC<UnifiedRiskMapProps> = ({
  hotspots = [],
  atms = [],
  topLocations = [],
  complaint,
  prediction,
  highlightCluster,
  height = '480px',
  showControls = true,
}) => {
  const navigate = useNavigate();
  const mapDivRef = useRef<HTMLDivElement>(null);
  const googleMapRef = useRef<google.maps.Map | null>(null);

  // References to rendered overlays for clean updates
  const overlaysRef = useRef<{
    markers: google.maps.Marker[];
    circles: google.maps.Circle[];
    infoWindow: google.maps.InfoWindow | null;
  }>({
    markers: [],
    circles: [],
    infoWindow: null,
  });

  // State
  const [provider, setProvider] = useState<'google' | 'leaflet'>('google');
  const [googleLoadStatus, setGoogleLoadStatus] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Map Controls State
  const [mapTypeId, setMapTypeId] = useState<google.maps.MapTypeId | 'roadmap' | 'satellite'>('roadmap');
  const [layerPredictionZones, setLayerPredictionZones] = useState(true);
  const [layerHotspots, setLayerHotspots] = useState(true);
  const [layerAtms, setLayerAtms] = useState(true);
  const [layerOrigin, setLayerOrigin] = useState(true);
  const [selectedClusterData, setSelectedClusterData] = useState<any | null>(null);

  const googleApiKey = (import.meta as any).env?.VITE_GOOGLE_MAPS_API_KEY || '';

  // 1. Initialize Google Maps via modern functional loader API
  useEffect(() => {
    // If user explicitly forced fallback or no API key, skip immediately
    if (!googleApiKey || googleApiKey.trim() === '' || googleApiKey.includes('your_google_maps_api_key_here')) {
      setGoogleLoadStatus('failed');
      setErrorMessage('Google Maps API key not configured — using fallback map.');
      setProvider('leaflet');
      return;
    }

    if (provider === 'leaflet') {
      return;
    }

    let isMounted = true;
    try {
      setOptions({
        key: googleApiKey,
        v: 'weekly',
      });

      Promise.all([
        importLibrary('maps'),
        importLibrary('geometry')
      ])
        .then(() => {
          if (!isMounted) return;
          setGoogleLoadStatus('ready');
          setErrorMessage(null);
        })
        .catch((err) => {
          if (!isMounted) return;
          console.warn('[UnifiedRiskMap] Google Maps failed to load:', err);
          setGoogleLoadStatus('failed');
          setErrorMessage('Google Maps unavailable — using fallback map.');
          setProvider('leaflet');
        });
    } catch (err) {
      if (isMounted) {
        setGoogleLoadStatus('failed');
        setErrorMessage('Google Maps unavailable — using fallback map.');
        setProvider('leaflet');
      }
    }

    return () => {
      isMounted = false;
    };
  }, [googleApiKey, provider]);

  // 2. Initialize and Mount Google Map Instance
  useEffect(() => {
    if (provider !== 'google' || googleLoadStatus !== 'ready' || !mapDivRef.current) return;

    if (!googleMapRef.current) {
      // Default to central Madhya Pradesh corridor (Indore)
      const defaultCenter = { lat: 22.74, lng: 75.88 };

      const map = new google.maps.Map(mapDivRef.current, {
        center: defaultCenter,
        zoom: 11,
        styles: DARK_GEOINT_STYLE,
        disableDefaultUI: true,
        zoomControl: true,
        mapTypeControl: false,
        fullscreenControl: false,
        streetViewControl: false,
        backgroundColor: '#070c18',
      });

      googleMapRef.current = map;
      overlaysRef.current.infoWindow = new google.maps.InfoWindow();

      // Listen to auth failure
      (window as any).gm_authFailure = () => {
        console.warn('[UnifiedRiskMap] Google Maps authentication failure detected.');
        setGoogleLoadStatus('failed');
        setErrorMessage('Google Maps authentication failed — using fallback map.');
        setProvider('leaflet');
      };
    }
  }, [provider, googleLoadStatus]);

  // 3. Update Map Type (Roadmap vs Satellite)
  useEffect(() => {
    if (googleMapRef.current) {
      googleMapRef.current.setMapTypeId(mapTypeId);
      // Re-apply dark styling only if roadmap
      if (mapTypeId === 'roadmap') {
        googleMapRef.current.setOptions({ styles: DARK_GEOINT_STYLE });
      } else {
        googleMapRef.current.setOptions({ styles: null });
      }
    }
  }, [mapTypeId]);

  // 4. Render Layers on Google Map (Predicted Clusters, Hotspots, ATMs, Complaint Origin)
  useEffect(() => {
    if (provider !== 'google' || googleLoadStatus !== 'ready' || !googleMapRef.current) return;

    const map = googleMapRef.current;
    const bounds = new google.maps.LatLngBounds();
    let hasValidPoints = false;

    // Clear previous overlays
    overlaysRef.current.markers.forEach((m) => m.setMap(null));
    overlaysRef.current.circles.forEach((c) => c.setMap(null));
    overlaysRef.current.markers = [];
    overlaysRef.current.circles = [];

    const infoWindow = overlaysRef.current.infoWindow || new google.maps.InfoWindow();
    overlaysRef.current.infoWindow = infoWindow;

    // Layer E: Complaint Origin
    if (layerOrigin && complaint?.victim_location) {
      const isBhopal = complaint.victim_location.toLowerCase().includes('bhopal');
      const isIndore = complaint.victim_location.toLowerCase().includes('indore');
      const originLat = isBhopal ? 23.2332 : (isIndore ? 22.7533 : 22.75);
      const originLon = isBhopal ? 77.4343 : (isIndore ? 75.8937 : 75.89);

      const originMarker = new google.maps.Marker({
        position: { lat: originLat, lng: originLon },
        map,
        title: `Complaint Origin: ${complaint.victim_location}`,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: '#10b981',
          fillOpacity: 1,
          strokeColor: '#ffffff',
          strokeWeight: 2,
        },
      });

      originMarker.addListener('click', () => {
        infoWindow.setContent(`
          <div style="background:#0b1326; color:#f1f5f9; padding:10px; border-radius:6px; font-family:monospace; font-size:11px;">
            <div style="color:#10b981; font-weight:bold; margin-bottom:4px;">COMPLAINT ORIGIN</div>
            <div>${complaint.victim_location}</div>
            <div style="color:#94a3b8; font-size:10px; margin-top:4px;">Complaint #${complaint.complaint_number}</div>
          </div>
        `);
        infoWindow.open(map, originMarker);
      });

      overlaysRef.current.markers.push(originMarker);
      bounds.extend({ lat: originLat, lng: originLon });
      hasValidPoints = true;
    }

    // Layer A & B: Top 3 Predicted Cash-Out Clusters
    if (layerPredictionZones && topLocations.length > 0) {
      topLocations.forEach((loc) => {
        if (!loc.latitude || !loc.longitude || isNaN(loc.latitude) || isNaN(loc.longitude)) return;

        const isTop1 = loc.rank === 1;
        const color = isTop1 ? '#06b6d4' : (loc.rank === 2 ? '#3b82f6' : '#94a3b8');
        const radiusMeters = 2500; // Verified 2.5 km operational search zone

        // Operational circle
        const circle = new google.maps.Circle({
          map,
          center: { lat: loc.latitude, lng: loc.longitude },
          radius: radiusMeters,
          strokeColor: color,
          strokeOpacity: isTop1 ? 0.9 : 0.6,
          strokeWeight: isTop1 ? 2.5 : 1.5,
          fillColor: color,
          fillOpacity: isTop1 ? 0.22 : 0.12,
        });

        // Rank Marker
        const marker = new google.maps.Marker({
          position: { lat: loc.latitude, lng: loc.longitude },
          map,
          title: `Rank #${loc.rank}: ${loc.location_name}`,
          label: {
            text: `#${loc.rank}`,
            color: '#060a15',
            fontWeight: 'bold',
            fontSize: '11px',
            fontFamily: 'monospace',
          },
          icon: {
            path: 'M -12,-12 L 12,-12 L 12,12 L -12,12 Z',
            fillColor: color,
            fillOpacity: 1,
            strokeColor: '#ffffff',
            strokeWeight: 1.5,
            scale: 1,
          },
        });

        // Info popup
        const predMode = prediction?.prediction_mode || 'trained_ml';
        const modelVer = prediction?.model_version || (predMode === 'deterministic_demo' ? 'demo-provider-v1' : 'cashout-location-xgb-v2');

        const content = `
          <div style="background:#0b1326; color:#f1f5f9; padding:12px; border-radius:8px; font-family:monospace; font-size:11px; max-width:260px; line-height:1.4;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e293b; padding-bottom:6px; margin-bottom:8px;">
              <span style="font-weight:bold; color:#f8fafc; font-size:12px;">Predicted Cash-Out Zone</span>
              <span style="background:rgba(6,182,212,0.2); color:#22d3ee; font-size:10px; padding:2px 6px; border-radius:4px; font-weight:bold;">Rank #${loc.rank}</span>
            </div>
            <div style="color:#ffffff; font-weight:bold; margin-bottom:4px;">${loc.location_name}</div>
            <div style="display:flex; justify-content:space-between; margin-top:2px;">
              <span style="color:#94a3b8;">Candidate Likelihood:</span>
              <span style="color:#22d3ee; font-weight:bold;">${Math.round(loc.probability * 100)}%</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:2px;">
              <span style="color:#94a3b8;">Threat Level:</span>
              <span style="color:${loc.risk_level === 'CRITICAL' ? '#f87171' : '#fbbf24'}; font-weight:bold;">${loc.risk_level}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:2px;">
              <span style="color:#94a3b8;">Distance from Origin:</span>
              <span>${loc.distance_km} km</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:2px;">
              <span style="color:#94a3b8;">Operational Radius:</span>
              <span style="color:#e2e8f0;">2.5 km search zone</span>
            </div>
            <div style="color:#94a3b8; font-size:10px; margin-top:6px; padding-top:6px; border-top:1px solid #1e293b;">
              ${loc.reasoning || 'Evaluated via syndicate banking corridor & topological affinity'}
            </div>
            <div style="color:#64748b; font-size:9px; margin-top:6px;">
              Provenance: ${predMode === 'deterministic_demo' ? 'Deterministic Demo / demo-provider-v1' : `Trained ML / ${modelVer}`}
            </div>
          </div>
        `;

        marker.addListener('click', () => {
          infoWindow.setContent(content);
          infoWindow.open(map, marker);
        });

        circle.addListener('click', () => {
          infoWindow.setContent(content);
          infoWindow.open(map, marker);
        });

        overlaysRef.current.markers.push(marker);
        overlaysRef.current.circles.push(circle);
        bounds.extend({ lat: loc.latitude, lng: loc.longitude });
        hasValidPoints = true;
      });
    }

    // Layer C: Monitored Risk Clusters (Hotspots)
    if (layerHotspots && hotspots.length > 0) {
      hotspots.forEach((cluster) => {
        if (!cluster.latitude || !cluster.longitude) return;

        const isCritical = cluster.risk_level === 'CRITICAL';
        const isHighlighted = highlightCluster && cluster.cluster_name.toLowerCase().includes(highlightCluster.toLowerCase());
        const color = isHighlighted ? '#06b6d4' : (isCritical ? '#ef4444' : (cluster.risk_level === 'HIGH' ? '#f59e0b' : '#3b82f6'));
        const radiusMeters = (cluster.radius_km || 2.5) * 1000;

        // Radius circle
        const circle = new google.maps.Circle({
          map,
          center: { lat: cluster.latitude, lng: cluster.longitude },
          radius: radiusMeters,
          strokeColor: color,
          strokeOpacity: isHighlighted ? 0.9 : 0.5,
          strokeWeight: isHighlighted ? 2.5 : 1.2,
          fillColor: color,
          fillOpacity: isCritical ? 0.16 : 0.08,
        });

        // Center marker
        const marker = new google.maps.Marker({
          position: { lat: cluster.latitude, lng: cluster.longitude },
          map,
          title: `${cluster.cluster_name} (${cluster.risk_level})`,
          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            scale: isHighlighted ? 8 : 6,
            fillColor: color,
            fillOpacity: 0.9,
            strokeColor: '#ffffff',
            strokeWeight: 1.5,
          },
        });

        const riskFormatted = cluster.risk_score !== null && cluster.risk_score !== undefined
          ? `${Math.round(cluster.risk_score * 100)}%`
          : 'Risk unavailable';

        const content = `
          <div style="background:#0b1326; color:#f1f5f9; padding:12px; border-radius:8px; font-family:monospace; font-size:11px; max-width:250px;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e293b; padding-bottom:4px; margin-bottom:6px;">
              <strong style="color:#ffffff;">${cluster.cluster_name}</strong>
              <span style="color:${isCritical ? '#f87171' : '#fbbf24'}; font-weight:bold;">${cluster.risk_level} (${riskFormatted})</span>
            </div>
            <div style="color:#94a3b8;">Window: <strong style="color:#22d3ee;">${cluster.expected_window}</strong></div>
            <div style="color:#94a3b8;">Amount at Risk: <strong style="color:#34d399;">₹${(cluster.amount_at_risk || 0).toLocaleString('en-IN')}</strong></div>
            <div style="color:#94a3b8;">Terminals: ${cluster.atm_count || 6} ATMs in ${cluster.radius_km || 2.5} km</div>
            <div style="color:#64748b; font-size:9px; margin-top:6px; border-top:1px solid #1e293b; padding-top:4px;">
              Monitored Geographic Risk Cluster
            </div>
          </div>
        `;

        marker.addListener('click', () => {
          infoWindow.setContent(content);
          infoWindow.open(map, marker);
          setSelectedClusterData(cluster);
        });

        circle.addListener('click', () => {
          infoWindow.setContent(content);
          infoWindow.open(map, marker);
          setSelectedClusterData(cluster);
        });

        overlaysRef.current.markers.push(marker);
        overlaysRef.current.circles.push(circle);

        // Only extend bounds if top predictions aren't already setting bounds
        if (topLocations.length === 0) {
          bounds.extend({ lat: cluster.latitude, lng: cluster.longitude });
          hasValidPoints = true;
        }
      });
    }

    // Layer D: ATM Locations
    if (layerAtms && atms.length > 0) {
      atms.forEach((atm) => {
        if (!atm.latitude || !atm.longitude) return;

        const marker = new google.maps.Marker({
          position: { lat: atm.latitude, lng: atm.longitude },
          map,
          title: `ATM: ${atm.bank_name}`,
          icon: {
            path: 'M -4,-4 L 4,-4 L 4,4 L -4,4 Z',
            fillColor: '#38bdf8',
            fillOpacity: 0.8,
            strokeColor: '#ffffff',
            strokeWeight: 1,
            scale: 1,
          },
        });

        marker.addListener('click', () => {
          infoWindow.setContent(`
            <div style="background:#0b1326; color:#f1f5f9; padding:8px; border-radius:6px; font-family:monospace; font-size:11px;">
              <div style="color:#38bdf8; font-weight:bold;">ATM Node</div>
              <div style="color:#ffffff; font-weight:bold;">${atm.bank_name}</div>
              <div style="color:#94a3b8; font-size:10px;">${atm.address}</div>
              <div style="color:#64748b; font-size:9px; margin-top:4px;">Code: ${atm.atm_code} | Cash: ${atm.cash_available ? 'Available' : 'Unavailable'}</div>
            </div>
          `);
          infoWindow.open(map, marker);
        });

        overlaysRef.current.markers.push(marker);
      });
    }

    // Fit map bounds cleanly if valid points exist
    if (hasValidPoints) {
      if (topLocations.length > 0) {
        // Fit precisely around top predictions + complaint origin
        map.fitBounds(bounds, { top: 40, bottom: 40, left: 40, right: 40 });
        const listener = google.maps.event.addListener(map, 'idle', () => {
          if (map.getZoom()! > 13) map.setZoom(13);
          google.maps.event.removeListener(listener);
        });
      } else if (bounds.isEmpty() === false) {
        map.fitBounds(bounds);
        const listener = google.maps.event.addListener(map, 'idle', () => {
          if (map.getZoom()! > 12) map.setZoom(12);
          google.maps.event.removeListener(listener);
        });
      }
    }
  }, [
    provider,
    googleLoadStatus,
    hotspots,
    atms,
    topLocations,
    complaint,
    prediction,
    highlightCluster,
    layerPredictionZones,
    layerHotspots,
    layerAtms,
    layerOrigin,
  ]);

  // Quick Focus Helpers
  const handleZoomToIndia = () => {
    if (googleMapRef.current) {
      googleMapRef.current.setCenter({ lat: 21.7679, lng: 78.8718 });
      googleMapRef.current.setZoom(5);
    }
  };

  const handleZoomToComplaint = () => {
    if (googleMapRef.current && complaint?.victim_location) {
      const isBhopal = complaint.victim_location.toLowerCase().includes('bhopal');
      const isIndore = complaint.victim_location.toLowerCase().includes('indore');
      const lat = isBhopal ? 23.2332 : (isIndore ? 22.7533 : 22.75);
      const lng = isBhopal ? 77.4343 : (isIndore ? 75.8937 : 75.89);
      googleMapRef.current.setCenter({ lat, lng });
      googleMapRef.current.setZoom(13);
    }
  };

  const handleZoomToTop1 = () => {
    if (googleMapRef.current && topLocations.length > 0 && topLocations[0].latitude) {
      googleMapRef.current.setCenter({
        lat: topLocations[0].latitude,
        lng: topLocations[0].longitude,
      });
      googleMapRef.current.setZoom(13);
    } else if (googleMapRef.current && hotspots.length > 0) {
      googleMapRef.current.setCenter({
        lat: hotspots[0].latitude,
        lng: hotspots[0].longitude,
      });
      googleMapRef.current.setZoom(13);
    }
  };

  // If fallback is selected or google maps failed, render LeafletFallbackMap
  if (provider === 'leaflet') {
    return (
      <div className="relative">
        {errorMessage && (
          <div className="mb-2 px-3 py-1.5 bg-[#0f172a] border border-amber-500/30 rounded-lg flex items-center justify-between text-xs font-mono text-amber-300">
            <span className="flex items-center space-x-1.5">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              <span>{errorMessage}</span>
            </span>
            {googleApiKey && (
              <button
                onClick={() => {
                  setProvider('google');
                  setGoogleLoadStatus('loading');
                }}
                className="underline hover:text-white ml-2 text-[11px]"
              >
                Retry Google Maps
              </button>
            )}
          </div>
        )}

        <LeafletFallbackMap
          hotspots={hotspots}
          atms={atms}
          topLocations={topLocations}
          complaint={complaint}
          prediction={prediction}
          highlightCluster={highlightCluster}
          height={height}
          showPredictionZones={layerPredictionZones}
          showHotspots={layerHotspots}
          showAtms={layerAtms}
          showComplaintOrigin={layerOrigin}
        />
      </div>
    );
  }

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-[#162544] shadow-2xl bg-[#070c18]">
      {/* Top Map Control Bar */}
      {showControls && (
        <div className="absolute top-3 left-3 right-3 z-20 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
          {/* Provider & Map Type Switcher */}
          <div className="flex items-center space-x-1.5 bg-[#090f1d]/90 backdrop-blur-md p-1 rounded-lg border border-[#1a2b4c] pointer-events-auto shadow-lg text-xs font-mono">
            <button
              onClick={() => setMapTypeId('roadmap')}
              className={`px-2.5 py-1 rounded transition-all font-semibold ${
                mapTypeId === 'roadmap' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Roadmap
            </button>
            <button
              onClick={() => setMapTypeId('satellite')}
              className={`px-2.5 py-1 rounded transition-all font-semibold ${
                mapTypeId === 'satellite' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Satellite
            </button>
            <button
              onClick={() => setProvider('leaflet')}
              className="px-2.5 py-1 rounded text-slate-400 hover:text-slate-200 transition-all text-[11px]"
              title="Switch to Leaflet OpenStreetMap fallback"
            >
              Fallback
            </button>
          </div>

          {/* Layer Toggles */}
          <div className="flex items-center space-x-1 bg-[#090f1d]/90 backdrop-blur-md px-2 py-1 rounded-lg border border-[#1a2b4c] pointer-events-auto shadow-lg text-[11px] font-mono">
            {topLocations.length > 0 && (
              <label className="flex items-center space-x-1 cursor-pointer px-1.5 py-0.5 rounded hover:bg-slate-800/40">
                <input
                  type="checkbox"
                  checked={layerPredictionZones}
                  onChange={(e) => setLayerPredictionZones(e.target.checked)}
                  className="rounded border-slate-700 text-cyan-500 focus:ring-0 w-3 h-3 bg-slate-900"
                />
                <span className="text-cyan-300">Predictions</span>
              </label>
            )}

            <label className="flex items-center space-x-1 cursor-pointer px-1.5 py-0.5 rounded hover:bg-slate-800/40">
              <input
                type="checkbox"
                checked={layerHotspots}
                onChange={(e) => setLayerHotspots(e.target.checked)}
                className="rounded border-slate-700 text-red-500 focus:ring-0 w-3 h-3 bg-slate-900"
              />
              <span className="text-slate-300">Hotspots</span>
            </label>

            <label className="flex items-center space-x-1 cursor-pointer px-1.5 py-0.5 rounded hover:bg-slate-800/40">
              <input
                type="checkbox"
                checked={layerAtms}
                onChange={(e) => setLayerAtms(e.target.checked)}
                className="rounded border-slate-700 text-sky-400 focus:ring-0 w-3 h-3 bg-slate-900"
              />
              <span className="text-slate-300">ATMs</span>
            </label>

            {complaint && (
              <label className="flex items-center space-x-1 cursor-pointer px-1.5 py-0.5 rounded hover:bg-slate-800/40">
                <input
                  type="checkbox"
                  checked={layerOrigin}
                  onChange={(e) => setLayerOrigin(e.target.checked)}
                  className="rounded border-slate-700 text-emerald-400 focus:ring-0 w-3 h-3 bg-slate-900"
                />
                <span className="text-emerald-300">Origin</span>
              </label>
            )}
          </div>

          {/* Focus Shortcuts */}
          <div className="flex items-center space-x-1 bg-[#090f1d]/90 backdrop-blur-md px-1.5 py-1 rounded-lg border border-[#1a2b4c] pointer-events-auto shadow-lg text-xs font-mono">
            <button
              onClick={handleZoomToTop1}
              className="px-2 py-0.5 rounded bg-[#13223f] hover:bg-[#1c325e] text-cyan-300 text-[11px] font-semibold flex items-center space-x-1"
              title="Focus on primary predicted cluster"
            >
              <Compass className="w-3 h-3" />
              <span>Top-1</span>
            </button>
            {complaint && (
              <button
                onClick={handleZoomToComplaint}
                className="px-2 py-0.5 rounded bg-[#13223f] hover:bg-[#1c325e] text-emerald-300 text-[11px] font-semibold"
                title="Focus on complaint origin"
              >
                Origin
              </button>
            )}
            <button
              onClick={handleZoomToIndia}
              className="px-2 py-0.5 rounded hover:bg-[#13223f] text-slate-300 text-[11px]"
              title="Zoom out to national view"
            >
              India
            </button>
          </div>
        </div>
      )}

      {/* Google Maps Container */}
      <div ref={mapDivRef} style={{ height, width: '100%' }} />

      {/* Status Overlay if Loading */}
      {googleLoadStatus === 'loading' && (
        <div className="absolute inset-0 bg-[#070c18]/80 backdrop-blur-sm flex items-center justify-center text-xs font-mono text-slate-300">
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
            <span>Loading Google Maps Geospatial Canvas...</span>
          </div>
        </div>
      )}

      {/* Subtle Legend / Operational Scope Footer */}
      <div className="absolute bottom-2 left-3 z-10 pointer-events-none bg-[#090f1d]/85 backdrop-blur-sm px-2.5 py-1 rounded border border-[#1a2b4c] text-[10px] font-mono text-slate-400 flex items-center space-x-3">
        <span className="flex items-center space-x-1">
          <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block"></span>
          <span>Predicted Zone (2.5 km)</span>
        </span>
        <span className="flex items-center space-x-1">
          <span className="w-2 h-2 rounded-full bg-red-500 inline-block"></span>
          <span>Critical Hotspot</span>
        </span>
        <span className="flex items-center space-x-1">
          <span className="w-2 h-2 bg-sky-400 inline-block"></span>
          <span>ATM Terminal</span>
        </span>
        <span className="text-slate-500">Provider: Google Maps (Restrained Dark GeoINT)</span>
      </div>
    </div>
  );
};
