import React, { useEffect, useRef, useState } from 'react';
import { setOptions, importLibrary } from '@googlemaps/js-api-loader';
import { HotspotCluster, ATMLocationItem, PredictionLocationItem, Complaint } from '../types';
import { LeafletFallbackMap } from './LeafletFallbackMap';
import {
  Compass,
  AlertTriangle,
  RotateCcw,
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

const DELHI_CENTER = { lat: 28.6139, lng: 77.2090 };

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

  // References to rendered overlays for clean updates without map recreation
  const overlaysRef = useRef<{
    markers: google.maps.Marker[];
    circles: google.maps.Circle[];
    infoWindow: google.maps.InfoWindow | null;
  }>({
    markers: [],
    circles: [],
    infoWindow: null,
  });

  // Provider State
  const [provider, setProvider] = useState<'google' | 'leaflet'>('google');
  const [googleLoadStatus, setGoogleLoadStatus] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Map Controls State
  const [mapTypeId, setMapTypeId] = useState<google.maps.MapTypeId | 'roadmap' | 'satellite'>('roadmap');
  const [layerPredictionZones, setLayerPredictionZones] = useState(true);
  const [layerHotspots, setLayerHotspots] = useState(true);
  const [layerAtms, setLayerAtms] = useState(true);
  const [layerOrigin, setLayerOrigin] = useState(true);

  const googleApiKey = (import.meta as any).env?.VITE_GOOGLE_MAPS_API_KEY || '';

  // 1. Initialize Google Maps via modern functional loader API
  useEffect(() => {
    // If API key is missing or is placeholder, immediately use Leaflet fallback
    if (
      !googleApiKey ||
      googleApiKey.trim() === '' ||
      googleApiKey.includes('your_google_maps_api_key_here') ||
      googleApiKey.includes('YOUR_GOOGLE_MAPS_KEY')
    ) {
      setGoogleLoadStatus('failed');
      setErrorMessage('Google Maps API key not configured — displaying fallback map.');
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
        importLibrary('geometry'),
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
          setErrorMessage('Google Maps unavailable — displaying fallback map.');
          setProvider('leaflet');
        });
    } catch (err) {
      if (isMounted) {
        setGoogleLoadStatus('failed');
        setErrorMessage('Google Maps unavailable — displaying fallback map.');
        setProvider('leaflet');
      }
    }

    return () => {
      isMounted = false;
    };
  }, [googleApiKey, provider]);

  // 2. Initialize and Mount Google Map Instance (Standard Roadmap Cartography)
  useEffect(() => {
    if (provider !== 'google' || googleLoadStatus !== 'ready' || !mapDivRef.current) return;

    if (!googleMapRef.current) {
      const map = new google.maps.Map(mapDivRef.current, {
        center: DELHI_CENTER,
        zoom: 11,
        mapTypeId: 'roadmap',
        disableDefaultUI: false,
        zoomControl: true,
        mapTypeControl: false,
        fullscreenControl: false,
        streetViewControl: false,
        backgroundColor: '#F6F8FC',
      });

      googleMapRef.current = map;
      overlaysRef.current.infoWindow = new google.maps.InfoWindow();

      // Listen to runtime authentication failures (e.g. invalid key or domain restriction)
      (window as any).gm_authFailure = () => {
        console.warn('[UnifiedRiskMap] Google Maps authentication failure detected.');
        setGoogleLoadStatus('failed');
        setErrorMessage('Google Maps authentication failed — displaying fallback map.');
        setProvider('leaflet');
      };
    }
  }, [provider, googleLoadStatus]);

  // 3. Update Map Type (Roadmap vs Satellite)
  useEffect(() => {
    if (googleMapRef.current) {
      googleMapRef.current.setMapTypeId(mapTypeId);
    }
  }, [mapTypeId]);

  // 4. Render Layers on Google Map (Top-3 Predictions, Operational Rings, Delhi ATMs, Complaint Origin)
  useEffect(() => {
    if (provider !== 'google' || googleLoadStatus !== 'ready' || !googleMapRef.current) return;

    const map = googleMapRef.current;
    const bounds = new google.maps.LatLngBounds();
    let hasValidPoints = false;

    // Clear previous overlays cleanly without destroying the map instance
    overlaysRef.current.markers.forEach((m) => m.setMap(null));
    overlaysRef.current.circles.forEach((c) => c.setMap(null));
    overlaysRef.current.markers = [];
    overlaysRef.current.circles = [];

    const infoWindow = overlaysRef.current.infoWindow || new google.maps.InfoWindow();
    overlaysRef.current.infoWindow = infoWindow;

    // Layer 1: Complaint Origin Marker (Strict coordinate validation — NO fabrication)
    const hasValidComplaintCoords =
      complaint?.victim_lat != null &&
      complaint?.victim_lon != null &&
      !isNaN(Number(complaint.victim_lat)) &&
      !isNaN(Number(complaint.victim_lon));

    if (layerOrigin && hasValidComplaintCoords) {
      const originLat = Number(complaint!.victim_lat);
      const originLon = Number(complaint!.victim_lon);

      const originMarker = new google.maps.Marker({
        position: { lat: originLat, lng: originLon },
        map,
        title: `Complaint Origin: ${complaint!.victim_location || 'Incident Location'}`,
        label: {
          text: 'O',
          color: '#FFFFFF',
          fontWeight: 'bold',
          fontSize: '11px',
          fontFamily: 'monospace',
        },
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 10,
          fillColor: '#10B981',
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2,
        },
        zIndex: 999,
      });

      originMarker.addListener('click', () => {
        infoWindow.setContent(`
          <div style="background:#FFFFFF; color:#1E293B; padding:12px; border-radius:8px; font-family:system-ui, -apple-system, sans-serif; font-size:12px; max-width:240px; border:1px solid #DCE5F0; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
            <div style="color:#059669; font-weight:700; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Complaint Origin</div>
            <div style="font-weight:600; color:#0F172A; font-size:13px;">${complaint!.victim_location || 'Reported Location'}</div>
            <div style="color:#64748B; font-size:11px; margin-top:4px;">Complaint #${complaint!.complaint_number}</div>
            <div style="color:#94A3B8; font-size:10px; margin-top:2px;">Coords: (${originLat.toFixed(4)}, ${originLon.toFixed(4)})</div>
          </div>
        `);
        infoWindow.open(map, originMarker);
      });

      overlaysRef.current.markers.push(originMarker);
      bounds.extend({ lat: originLat, lng: originLon });
      hasValidPoints = true;
    }

    // Layer 2: Top-3 Predicted Cash-Out Zones & Rank #1 Concentric Operational Rings
    if (layerPredictionZones && topLocations.length > 0) {
      topLocations.forEach((loc) => {
        if (loc.latitude == null || loc.longitude == null || isNaN(Number(loc.latitude)) || isNaN(Number(loc.longitude))) {
          return;
        }

        const lat = Number(loc.latitude);
        const lng = Number(loc.longitude);
        const isTop1 = loc.rank === 1;

        // Rank #1: Exactly three concentric geographic operational bands
        // 0–1 km: Critical operational proximity
        // 1–2.5 km: High-priority surrounding zone
        // 2.5–5 km: Context zone
        // Rank #2 & Rank #3: Numbered marker ONLY (Correction 1 — zero circles)
        if (isTop1) {
          // Band 1: 0–1 km Critical operational proximity
          const circle1km = new google.maps.Circle({
            map,
            center: { lat, lng },
            radius: 1000,
            strokeColor: '#2563EB',
            strokeOpacity: 0.9,
            strokeWeight: 2,
            fillColor: '#3B82F6',
            fillOpacity: 0.18,
          });

          // Band 2: 1–2.5 km High-priority surrounding zone
          const circle2_5km = new google.maps.Circle({
            map,
            center: { lat, lng },
            radius: 2500,
            strokeColor: '#0284C7',
            strokeOpacity: 0.8,
            strokeWeight: 1.8,
            fillColor: '#38BDF8',
            fillOpacity: 0.10,
          });

          // Band 3: 2.5–5 km Context zone
          const circle5km = new google.maps.Circle({
            map,
            center: { lat, lng },
            radius: 5000,
            strokeColor: '#64748B',
            strokeOpacity: 0.6,
            strokeWeight: 1.2,
            fillColor: '#94A3B8',
            fillOpacity: 0.04,
          });

          overlaysRef.current.circles.push(circle1km, circle2_5km, circle5km);
        }

        // Distinct visual styling for Top-3 prediction markers
        const markerBgColor = isTop1 ? '#2563EB' : (loc.rank === 2 ? '#3B82F6' : '#64748B');
        const markerScale = isTop1 ? 1.2 : (loc.rank === 2 ? 1.05 : 0.95);

        const marker = new google.maps.Marker({
          position: { lat, lng },
          map,
          title: `Rank #${loc.rank}: ${loc.location_name}`,
          label: {
            text: `${loc.rank}`,
            color: '#FFFFFF',
            fontWeight: 'bold',
            fontSize: isTop1 ? '13px' : '11px',
            fontFamily: 'monospace',
          },
          icon: {
            path: 'M -13,-13 L 13,-13 L 13,13 L -13,13 Z',
            fillColor: markerBgColor,
            fillOpacity: 1,
            strokeColor: '#FFFFFF',
            strokeWeight: 2,
            scale: markerScale,
            anchor: new google.maps.Point(0, 0),
            labelOrigin: new google.maps.Point(0, 0),
          },
          zIndex: isTop1 ? 1000 : (loc.rank === 2 ? 900 : 800),
        });

        // Operational InfoWindow — Strict operational fields; NO raw ML percentages, NO accuracy scores
        const infoContent = `
          <div style="background:#FFFFFF; color:#1E293B; padding:12px; border-radius:8px; font-family:system-ui, -apple-system, sans-serif; font-size:12px; max-width:270px; line-height:1.4; box-shadow:0 2px 8px rgba(0,0,0,0.12); border:1px solid #DCE5F0;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #E2E8F0; padding-bottom:6px; margin-bottom:8px;">
              <span style="font-weight:700; color:#173A63; font-size:12px;">Predicted Cash-Out Zone</span>
              <span style="background:${isTop1 ? '#EFF6FF' : '#F1F5F9'}; color:${isTop1 ? '#2563EB' : '#475569'}; font-size:10px; padding:2px 6px; border-radius:4px; font-weight:700; border:1px solid ${isTop1 ? '#BFDBFE' : '#CBD5E1'};">
                ${isTop1 ? '#1 PRIMARY' : (loc.rank === 2 ? '#2 SECONDARY' : '#3 TERTIARY')}
              </span>
            </div>
            <div style="color:#0F172A; font-weight:700; font-size:13px; margin-bottom:4px;">${loc.location_name}</div>
            ${loc.zone ? `<div style="display:flex; justify-content:space-between; margin-top:2px;"><span style="color:#64748B;">District:</span><span style="font-weight:500; color:#1E293B;">${loc.zone}</span></div>` : ''}
            <div style="display:flex; justify-content:space-between; margin-top:2px;">
              <span style="color:#64748B;">Operational Priority:</span>
              <span style="color:${loc.risk_level === 'CRITICAL' ? '#DC2626' : (loc.risk_level === 'HIGH' ? '#D97706' : '#2563EB')}; font-weight:700;">${loc.risk_level || 'HIGH'}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:2px;">
              <span style="color:#64748B;">Distance from Origin:</span>
              <span style="font-weight:500; color:#1E293B;">${loc.distance_km ?? '0.0'} km</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:2px;">
              <span style="color:#64748B;">Operational Window:</span>
              <span style="font-weight:600; color:#D97706;">${prediction?.when_window || 'Next 2–4 Hours'}</span>
            </div>
            ${isTop1 ? `
            <div style="margin-top:6px; padding-top:4px; border-top:1px solid #E2E8F0; font-size:10px; color:#2563EB; font-weight:500;">
              Tactical bands: 1 km critical / 2.5 km priority / 5 km context
            </div>
            ` : ''}
            <div style="color:#64748B; font-size:10px; margin-top:6px; padding-top:4px; border-top:1px solid #F1F5F9;">
              ${loc.reasoning || 'Ranked candidate cluster node'}
            </div>
          </div>
        `;

        marker.addListener('click', () => {
          infoWindow.setContent(infoContent);
          infoWindow.open(map, marker);
        });

        overlaysRef.current.markers.push(marker);
        bounds.extend({ lat, lng });
        hasValidPoints = true;
      });
    }

    // Layer 3: Monitored Risk Hotspot Clusters (Delhi Context)
    if (layerHotspots && hotspots.length > 0) {
      hotspots.forEach((cluster) => {
        if (!cluster.latitude || !cluster.longitude) return;

        const isCritical = cluster.risk_level === 'CRITICAL';
        const isHighlighted = highlightCluster && cluster.cluster_name.toLowerCase().includes(highlightCluster.toLowerCase());
        const color = isHighlighted ? '#2563EB' : (isCritical ? '#EF4444' : (cluster.risk_level === 'HIGH' ? '#F59E0B' : '#3B82F6'));
        const radiusMeters = (cluster.radius_km || 2.5) * 1000;

        const circle = new google.maps.Circle({
          map,
          center: { lat: cluster.latitude, lng: cluster.longitude },
          radius: radiusMeters,
          strokeColor: color,
          strokeOpacity: isHighlighted ? 0.9 : 0.45,
          strokeWeight: isHighlighted ? 2 : 1.2,
          fillColor: color,
          fillOpacity: isCritical ? 0.12 : 0.06,
        });

        const marker = new google.maps.Marker({
          position: { lat: cluster.latitude, lng: cluster.longitude },
          map,
          title: `${cluster.cluster_name} (${cluster.risk_level})`,
          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            scale: isHighlighted ? 7 : 5,
            fillColor: color,
            fillOpacity: 0.9,
            strokeColor: '#FFFFFF',
            strokeWeight: 1.5,
          },
        });

        const content = `
          <div style="background:#FFFFFF; color:#1E293B; padding:12px; border-radius:8px; font-family:system-ui, -apple-system, sans-serif; font-size:12px; max-width:250px; border:1px solid #DCE5F0; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #E2E8F0; padding-bottom:4px; margin-bottom:6px;">
              <strong style="color:#0F172A; font-size:12px;">${cluster.cluster_name}</strong>
              <span style="color:${isCritical ? '#DC2626' : '#D97706'}; font-weight:700; font-size:10px;">${cluster.risk_level}</span>
            </div>
            <div style="color:#64748B; font-size:11px; margin-top:2px;">Context Window: <strong style="color:#0284C7;">${cluster.expected_window}</strong></div>
            <div style="color:#64748B; font-size:11px; margin-top:2px;">Amount at Risk: <strong style="color:#059669;">₹${(cluster.amount_at_risk || 0).toLocaleString('en-IN')}</strong></div>
            <div style="color:#64748B; font-size:11px; margin-top:2px;">Surrounding Terminals: ${cluster.atm_count || 6} ATMs in ${cluster.radius_km || 2.5} km</div>
            <div style="color:#94A3B8; font-size:9px; margin-top:6px; border-top:1px solid #F1F5F9; padding-top:4px;">
              Monitored Geographic Risk Cluster
            </div>
          </div>
        `;

        marker.addListener('click', () => {
          infoWindow.setContent(content);
          infoWindow.open(map, marker);
        });

        overlaysRef.current.markers.push(marker);
        overlaysRef.current.circles.push(circle);

        if (topLocations.length === 0) {
          bounds.extend({ lat: cluster.latitude, lng: cluster.longitude });
          hasValidPoints = true;
        }
      });
    }

    // Layer 4: Existing 240 Delhi Reference ATM Nodes (Secondary Geographic Context)
    if (layerAtms && atms.length > 0) {
      atms.forEach((atm) => {
        if (!atm.latitude || !atm.longitude) return;

        const marker = new google.maps.Marker({
          position: { lat: atm.latitude, lng: atm.longitude },
          map,
          title: `ATM: ${atm.bank_name}`,
          icon: {
            path: 'M -4,-4 L 4,-4 L 4,4 L -4,4 Z',
            fillColor: '#0EA5E9',
            fillOpacity: 0.8,
            strokeColor: '#FFFFFF',
            strokeWeight: 1,
            scale: 1,
          },
          zIndex: 50,
        });

        marker.addListener('click', () => {
          infoWindow.setContent(`
            <div style="background:#FFFFFF; color:#1E293B; padding:10px; border-radius:6px; font-family:system-ui, -apple-system, sans-serif; font-size:11px; max-width:230px; border:1px solid #DCE5F0; box-shadow:0 2px 6px rgba(0,0,0,0.08);">
              <div style="color:#0284C7; font-weight:700; font-size:10px; text-transform:uppercase; letter-spacing:0.5px;">ATM Context Node</div>
              <div style="color:#0F172A; font-weight:700; margin-top:2px;">${atm.bank_name}</div>
              <div style="color:#64748B; font-size:10px; margin-top:2px;">${atm.address}</div>
              <div style="color:#94A3B8; font-size:9px; margin-top:4px; border-top:1px solid #F1F5F9; padding-top:3px;">
                Terminal Code: ${atm.atm_code || 'N/A'}${atm.district ? ` • ${atm.district}` : ''}
              </div>
              <div style="color:#94A3B8; font-size:9px; font-style:italic; margin-top:2px;">
                Geographic context node only
              </div>
            </div>
          `);
          infoWindow.open(map, marker);
        });

        overlaysRef.current.markers.push(marker);
      });
    }

    // Dynamic Map Bounds Handling (Section 13 & 15)
    if (hasValidPoints) {
      if (topLocations.length > 0) {
        // Fit bounds precisely around top prediction zones + complaint origin
        map.fitBounds(bounds, { top: 45, bottom: 45, left: 45, right: 45 });
        const listener = google.maps.event.addListener(map, 'idle', () => {
          if (map.getZoom()! > 13) map.setZoom(13);
          google.maps.event.removeListener(listener);
        });
      } else if (!bounds.isEmpty()) {
        map.fitBounds(bounds);
        const listener = google.maps.event.addListener(map, 'idle', () => {
          if (map.getZoom()! > 12) map.setZoom(12);
          google.maps.event.removeListener(listener);
        });
      }
    } else {
      // Default to Delhi Center when no prediction coordinates are selected
      map.setCenter(DELHI_CENTER);
      map.setZoom(11);
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
  const handleZoomToDelhi = () => {
    if (googleMapRef.current) {
      googleMapRef.current.setCenter(DELHI_CENTER);
      googleMapRef.current.setZoom(11);
    }
  };

  const handleZoomToComplaint = () => {
    if (
      googleMapRef.current &&
      complaint?.victim_lat != null &&
      complaint?.victim_lon != null &&
      !isNaN(Number(complaint.victim_lat)) &&
      !isNaN(Number(complaint.victim_lon))
    ) {
      googleMapRef.current.setCenter({
        lat: Number(complaint.victim_lat),
        lng: Number(complaint.victim_lon),
      });
      googleMapRef.current.setZoom(13);
    }
  };

  const handleZoomToTop1 = () => {
    if (googleMapRef.current && topLocations.length > 0 && topLocations[0].latitude) {
      googleMapRef.current.setCenter({
        lat: Number(topLocations[0].latitude),
        lng: Number(topLocations[0].longitude),
      });
      googleMapRef.current.setZoom(13);
    } else if (googleMapRef.current && hotspots.length > 0) {
      googleMapRef.current.setCenter({
        lat: Number(hotspots[0].latitude),
        lng: Number(hotspots[0].longitude),
      });
      googleMapRef.current.setZoom(13);
    }
  };

  // If fallback is active or Google Maps failed, render LeafletFallbackMap
  if (provider === 'leaflet') {
    return (
      <div className="relative">
        {errorMessage && (
          <div className="mb-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-between text-xs font-sans text-blue-900 shadow-xs">
            <span className="flex items-center space-x-1.5">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-blue-600" />
              <span>{errorMessage}</span>
            </span>
            {googleApiKey && (
              <button
                onClick={() => {
                  setProvider('google');
                  setGoogleLoadStatus('loading');
                }}
                className="underline hover:text-blue-950 ml-2 text-[11px] font-semibold cursor-pointer"
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

  const hasValidComplaint =
    complaint?.victim_lat != null &&
    complaint?.victim_lon != null &&
    !isNaN(Number(complaint.victim_lat)) &&
    !isNaN(Number(complaint.victim_lon));

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-[#DCE5F0] shadow-xs bg-[#F6F8FC]">
      {/* Top Map Control Bar */}
      {showControls && (
        <div className="absolute top-2 sm:top-3 left-2 sm:left-3 right-2 sm:right-3 z-20 flex flex-wrap items-center justify-between gap-1.5 sm:gap-2 pointer-events-none">
          {/* Provider & Map Type Switcher */}
          <div className="flex items-center space-x-1 sm:space-x-1.5 bg-white/95 backdrop-blur-md p-1 rounded-lg border border-[#DCE5F0] pointer-events-auto shadow-xs text-xs font-sans">
            <button
              onClick={() => setMapTypeId('roadmap')}
              className={`px-2 sm:px-2.5 py-1 rounded transition-all font-semibold cursor-pointer ${
                mapTypeId === 'roadmap' ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Roadmap
            </button>
            <button
              onClick={() => setMapTypeId('satellite')}
              className={`px-2 sm:px-2.5 py-1 rounded transition-all font-semibold cursor-pointer ${
                mapTypeId === 'satellite' ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Satellite
            </button>
            <button
              onClick={() => setProvider('leaflet')}
              className="px-2 sm:px-2.5 py-1 rounded text-slate-500 hover:text-slate-800 transition-all text-[11px] cursor-pointer"
              title="Switch to Leaflet OpenStreetMap fallback"
            >
              Fallback
            </button>
          </div>

          {/* Layer Toggles */}
          <div className="flex items-center space-x-1 sm:space-x-1.5 bg-white/95 backdrop-blur-md px-2 sm:px-2.5 py-1 rounded-lg border border-[#DCE5F0] pointer-events-auto shadow-xs text-xs font-sans">
            {topLocations.length > 0 && (
              <label className="flex items-center space-x-1.5 cursor-pointer px-1 py-0.5 rounded hover:bg-slate-100/80">
                <input
                  type="checkbox"
                  checked={layerPredictionZones}
                  onChange={(e) => setLayerPredictionZones(e.target.checked)}
                  className="rounded border-[#DCE5F0] text-blue-600 focus:ring-0 w-3.5 h-3.5 bg-white cursor-pointer"
                />
                <span className="text-blue-700 font-semibold text-[11px]">Predictions</span>
              </label>
            )}

            <label className="flex items-center space-x-1.5 cursor-pointer px-1 py-0.5 rounded hover:bg-slate-100/80">
              <input
                type="checkbox"
                checked={layerHotspots}
                onChange={(e) => setLayerHotspots(e.target.checked)}
                className="rounded border-[#DCE5F0] text-red-600 focus:ring-0 w-3.5 h-3.5 bg-white cursor-pointer"
              />
              <span className="text-slate-700 font-medium text-[11px]">Hotspots</span>
            </label>

            <label className="flex items-center space-x-1.5 cursor-pointer px-1 py-0.5 rounded hover:bg-slate-100/80">
              <input
                type="checkbox"
                checked={layerAtms}
                onChange={(e) => setLayerAtms(e.target.checked)}
                className="rounded border-[#DCE5F0] text-sky-600 focus:ring-0 w-3.5 h-3.5 bg-white cursor-pointer"
              />
              <span className="text-slate-700 font-medium text-[11px]">ATMs</span>
            </label>

            {hasValidComplaint && (
              <label className="flex items-center space-x-1.5 cursor-pointer px-1 py-0.5 rounded hover:bg-slate-100/80">
                <input
                  type="checkbox"
                  checked={layerOrigin}
                  onChange={(e) => setLayerOrigin(e.target.checked)}
                  className="rounded border-[#DCE5F0] text-emerald-600 focus:ring-0 w-3.5 h-3.5 bg-white cursor-pointer"
                />
                <span className="text-emerald-700 font-semibold text-[11px]">Origin</span>
              </label>
            )}
          </div>

          {/* Focus Shortcuts */}
          <div className="flex items-center space-x-1 bg-white/95 backdrop-blur-md px-1.5 py-1 rounded-lg border border-[#DCE5F0] pointer-events-auto shadow-xs text-xs font-sans">
            <button
              onClick={handleZoomToTop1}
              className="px-2 py-0.5 rounded bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 text-[11px] font-semibold flex items-center space-x-1 cursor-pointer"
              title="Focus on primary predicted cluster"
            >
              <Compass className="w-3 h-3" />
              <span>Top-1</span>
            </button>
            {hasValidComplaint && (
              <button
                onClick={handleZoomToComplaint}
                className="px-2 py-0.5 rounded bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-[11px] font-semibold cursor-pointer"
                title="Focus on complaint origin"
              >
                Origin
              </button>
            )}
            <button
              onClick={handleZoomToDelhi}
              className="px-2 py-0.5 rounded hover:bg-slate-100 text-slate-600 text-[11px] cursor-pointer"
              title="Reset to Delhi NCR view"
            >
              Delhi
            </button>
          </div>
        </div>
      )}

      {/* Google Maps Container */}
      <div ref={mapDivRef} style={{ height, width: '100%' }} />

      {/* Status Overlay while Loading */}
      {googleLoadStatus === 'loading' && (
        <div className="absolute inset-0 bg-white/80 backdrop-blur-xs flex items-center justify-center text-xs font-sans text-slate-700">
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
            <span>Loading Google Maps Geospatial Canvas...</span>
          </div>
        </div>
      )}

      {/* Map Legend Footer */}
      <div className="absolute bottom-2 left-2 sm:left-3 right-2 sm:right-auto max-w-[calc(100%-1rem)] sm:max-w-none z-10 pointer-events-none bg-white/95 backdrop-blur-xs px-2 sm:px-3 py-1 rounded-md border border-[#DCE5F0] text-[9px] sm:text-[10px] font-sans text-slate-600 shadow-xs flex flex-wrap items-center gap-x-2.5 sm:gap-x-3 gap-y-0.5">
        <span className="flex items-center space-x-1">
          <span className="w-2.5 h-2.5 rounded-sm bg-blue-600 inline-block shrink-0"></span>
          <span className="font-semibold text-slate-700">Predicted Zone (#1 Tactical Rings)</span>
        </span>
        <span className="flex items-center space-x-1">
          <span className="w-2 h-2 rounded-full bg-red-500 inline-block shrink-0"></span>
          <span>Hotspot Cluster</span>
        </span>
        <span className="flex items-center space-x-1">
          <span className="w-2 h-2 bg-sky-500 inline-block shrink-0"></span>
          <span>ATM Context Node</span>
        </span>
        <span className="text-slate-400 hidden sm:inline">Provider: Google Maps (Roadmap)</span>
      </div>
    </div>
  );
};
