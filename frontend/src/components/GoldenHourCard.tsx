import React, { useEffect, useState } from 'react';
import { Clock, Info, CheckCircle2, AlertTriangle, ShieldAlert } from 'lucide-react';
import { api } from '../services/api';
import { GoldenHourResponse } from '../types';

interface GoldenHourCardProps {
  predictionId: number;
}

export const GoldenHourCard: React.FC<GoldenHourCardProps> = ({ predictionId }) => {
  const [data, setData] = useState<GoldenHourResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState<number>(Date.now());
  const [showTooltip, setShowTooltip] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    api.getGoldenHour(predictionId)
      .then((res) => {
        if (isMounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err?.response?.data?.detail || 'Failed to load Golden-Hour data');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [predictionId]);

  // Client-side local timer tick every 1000ms (Requirement 9: zero polling to backend)
  useEffect(() => {
    const timer = setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  if (loading) {
    return (
      <div className="bg-[#10192C]/80 border border-slate-700/60 rounded-xl p-5 shadow-lg animate-pulse">
        <div className="h-5 bg-slate-700/50 rounded w-1/3 mb-4"></div>
        <div className="h-10 bg-slate-700/30 rounded mb-3"></div>
        <div className="h-16 bg-slate-700/20 rounded"></div>
      </div>
    );
  }

  if (error || !data || data.status === 'GOLDEN_HOUR_UNAVAILABLE' || !data.window.start || !data.window.end) {
    return (
      <div className="bg-[#10192C] border border-slate-800 rounded-xl p-5 shadow-lg text-slate-300">
        <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <Clock className="w-5 h-5 text-amber-400" />
            <span className="font-semibold text-white tracking-wide text-sm uppercase">Golden-Hour Intervention Window</span>
          </div>
          <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">UNAVAILABLE</span>
        </div>
        <p className="text-sm text-slate-400">
          Operational time window unavailable for this prediction.
        </p>
      </div>
    );
  }

  const startMs = new Date(data.window.start).getTime();
  const endMs = new Date(data.window.end).getTime();

  // Dynamic countdown logic based on current clock vs stored window
  let dynamicStatus = data.status;
  let dynamicStatusDisplay = data.status_display;
  let countdownText = '';
  let subCountdownText = '';

  const msToStart = startMs - nowMs;
  const msToEnd = endMs - nowMs;

  if (nowMs > endMs) {
    dynamicStatus = 'WINDOW_PASSED';
    dynamicStatusDisplay = 'WINDOW PASSED';
    const passedMins = Math.max(1, Math.floor((nowMs - endMs) / 60000));
    countdownText = `Window ended ${passedMins}m ago`;
    subCountdownText = 'Review Case / Reassess';
  } else if (nowMs >= startMs && nowMs <= endMs) {
    dynamicStatus = 'WINDOW_ACTIVE';
    dynamicStatusDisplay = 'WINDOW ACTIVE';
    const totalSecs = Math.max(0, Math.floor(msToEnd / 1000));
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    countdownText = `Time remaining: ${mins}m ${secs.toString().padStart(2, '0')}s`;
    subCountdownText = 'Window is currently active';
  } else {
    // nowMs < startMs
    const minsUntil = Math.floor(msToStart / 60000);
    if (minsUntil <= 30) {
      dynamicStatus = 'HIGH_URGENCY';
      dynamicStatusDisplay = 'HIGH URGENCY';
    } else if (minsUntil <= 60) {
      dynamicStatus = 'ELEVATED';
      dynamicStatusDisplay = 'ELEVATED';
    } else {
      dynamicStatus = 'PLANNING';
      dynamicStatusDisplay = 'PLANNING';
    }
    const totalSecs = Math.max(0, Math.floor(msToStart / 1000));
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    countdownText = `Window opens in: ${mins}m ${secs.toString().padStart(2, '0')}s`;
    subCountdownText = `Urgency: ${dynamicStatusDisplay}`;
  }

  // Visual status pill classes
  const getStatusBadgeClass = (st: string) => {
    switch (st) {
      case 'HIGH_URGENCY':
        return 'bg-red-500/20 text-red-300 border-red-500/40 ring-1 ring-red-500/30';
      case 'WINDOW_ACTIVE':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 ring-1 ring-emerald-500/30 animate-pulse';
      case 'ELEVATED':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40 ring-1 ring-amber-500/30';
      case 'PLANNING':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/40 ring-1 ring-blue-500/30';
      case 'WINDOW_PASSED':
      default:
        return 'bg-slate-700/40 text-slate-400 border-slate-600/40';
    }
  };

  return (
    <div className="bg-[#0b1329] border border-cyan-900/40 rounded-xl p-5 shadow-2xl relative text-slate-200">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2.5">
          <Clock className="w-5 h-5 text-cyan-400" />
          <h3 className="text-sm font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
            Golden-Hour Intervention Window
          </h3>
          <div className="relative inline-block">
            <button
              type="button"
              onClick={() => setShowTooltip(!showTooltip)}
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
              className="text-slate-400 hover:text-cyan-300 focus:outline-none transition-colors"
              aria-label="Golden-Hour Operational Information"
            >
              <Info className="w-4 h-4" />
            </button>
            {showTooltip && (
              <div className="absolute z-50 left-6 top-0 w-72 bg-slate-900 border border-cyan-700/50 p-3 rounded-lg shadow-xl text-xs text-slate-300 leading-relaxed pointer-events-none backdrop-blur-sm">
                Golden-Hour shows the operational time window derived from the persisted cash-out time prediction. Countdown and urgency labels support response planning and are not independent probability estimates.
              </div>
            )}
          </div>
        </div>

        <span
          className={`px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase border ${getStatusBadgeClass(
            dynamicStatus
          )}`}
        >
          {dynamicStatusDisplay}
        </span>
      </div>

      {/* Grid: Timing & Operational Window */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
        <div className="bg-[#121c38] border border-slate-800 p-3.5 rounded-lg">
          <span className="text-xs text-slate-400 uppercase tracking-wide block mb-1">Expected Cash-Out Window</span>
          <div className="text-base font-semibold text-white tracking-tight">
            {data.window.start_time_ist || 'N/A'} – {data.window.end_time_ist || 'N/A'}
          </div>
          <span className="text-[11px] text-cyan-400/80 font-mono mt-0.5 block">
            {data.window.start_ist?.split(',')[0] || 'IST'}
          </span>
        </div>

        <div className="bg-[#121c38] border border-slate-800 p-3.5 rounded-lg">
          <span className="text-xs text-slate-400 uppercase tracking-wide block mb-1">Time Remaining / Status</span>
          <div className="text-base font-bold text-cyan-300 tracking-tight font-mono">
            {countdownText}
          </div>
          <span className="text-[11px] text-slate-400 mt-0.5 block">
            {subCountdownText}
          </span>
        </div>

        <div className="bg-[#121c38] border border-slate-800 p-3.5 rounded-lg">
          <span className="text-xs text-slate-400 uppercase tracking-wide block mb-1">Source Intelligence</span>
          <div className="text-sm font-medium text-slate-200 truncate">
            {data.source.model_version}
          </div>
          <span className="text-[11px] text-emerald-400 mt-0.5 block">
            ✓ Persisted Prediction Record
          </span>
        </div>
      </div>

      {/* Operational Response Timeline */}
      {data.timeline && data.timeline.length > 0 && (
        <div className="bg-[#121c38]/60 border border-slate-800/80 rounded-lg p-3.5 mt-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
            <span>Response Timeline (IST)</span>
          </div>
          <div className="flex flex-col md:flex-row md:items-center justify-between relative gap-3">
            {data.timeline.map((item, idx) => (
              <div key={idx} className="flex md:flex-col items-start md:items-center text-left md:text-center flex-1 relative">
                <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 ring-4 ring-cyan-950 mb-1.5 mr-2 md:mr-0"></div>
                <div className="text-[11px] font-semibold text-slate-200">{item.step}</div>
                <div className="text-[10px] text-cyan-400 font-mono mt-0.5">
                  {item.timestamp_ist ? item.timestamp_ist.split(',')[1]?.trim() || item.timestamp_ist : '—'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
