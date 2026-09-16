import { Prediction, PredictionLocationItem } from '../types';

// datetime-local expects wall-clock time, whereas toISOString() always returns UTC.
export const toLocalDateTimeInput = (date = new Date()): string =>
  new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

export const parseApiDate = (value?: string | null): Date | null => {
  if (!value || typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed === 'None' || trimmed === 'null') return null;
  // Normalize space separator between date and time to ISO 'T'
  const normalized = trimmed.replace(' ', 'T');
  // If timezone offset or 'Z' is missing, under legacy database compatibility policy it represents UTC.
  const isoString = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}Z`;
  const date = new Date(isoString);
  return Number.isFinite(date.getTime()) ? date : null;
};

export const formatIST = (value?: string | null): string => {
  const date = parseApiDate(value);
  if (!date) return 'Not available';
  return `${date.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })} IST`;
};

export const formatWindowIST = (startVal?: string | null, endVal?: string | null): string => {
  const startDate = parseApiDate(startVal);
  const endDate = parseApiDate(endVal);
  if (!startDate && !endDate) return 'Time estimate unavailable';
  if (!startDate && endDate) return `Until ${formatIST(endVal)}`;
  if (startDate && !endDate) return `From ${formatIST(startVal)}`;

  const fmt = (d: Date, opts: Intl.DateTimeFormatOptions) =>
    d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', ...opts });

  const startDateStr = fmt(startDate!, { day: '2-digit', month: 'short', year: 'numeric' });
  const endDateStr = fmt(endDate!, { day: '2-digit', month: 'short', year: 'numeric' });
  const startTimeStr = fmt(startDate!, { hour: '2-digit', minute: '2-digit', hour12: false });
  const endTimeStr = fmt(endDate!, { hour: '2-digit', minute: '2-digit', hour12: false });

  if (startDateStr === endDateStr) {
    return `${startDateStr}, ${startTimeStr} – ${endTimeStr} IST`;
  }
  // Midnight-crossing window: show full date/time for both bounds explicitly
  return `${startDateStr}, ${startTimeStr} IST – ${endDateStr}, ${endTimeStr} IST`;
};

export const hasCoordinates = (latitude: unknown, longitude: unknown): boolean =>
  latitude != null && longitude != null && latitude !== '' && longitude !== '' &&
  Number.isFinite(Number(latitude)) && Number.isFinite(Number(longitude)) &&
  Math.abs(Number(latitude)) <= 90 && Math.abs(Number(longitude)) <= 180;

export const modelScore = (location: PredictionLocationItem): string => {
  const value = location.ml_probability ?? location.probability;
  if (value == null || !Number.isFinite(value) || value < 0 || value > 1) return 'Unavailable';
  return `${(value * 100).toFixed(1)}%`;
};

export const predictionScoreNote = (prediction: Prediction): string =>
  prediction.prediction_mode === 'deterministic_demo'
    ? 'Demo scores are preset scenario values, not a measured chance of cash-out.'
    : 'Scores are relative model ranking scores used to compare candidate cash-out zones. This is not model accuracy or a verified real-world probability of withdrawal.';

export const explainOperationalPriority = (
  riskLevel?: string | null,
  amount?: number | null,
  urgencyMinutes?: number | null,
  delayHours?: number | null
): string => {
  const level = (riskLevel || 'MEDIUM').toUpperCase();
  const amtStr = amount != null ? `₹${Number(amount).toLocaleString('en-IN')}` : 'reported loss';
  switch (level) {
    case 'CRITICAL':
      return `Operational Priority: CRITICAL (loss band >= ₹5L or >= ₹1.5L with cash-out urgency <= 90 min and intake delay <= 4 hrs). Amount at risk: ${amtStr}.`;
    case 'HIGH':
      return `Operational Priority: HIGH (loss band >= ₹75k or >= ₹30k with window urgency <= 90 min). Amount at risk: ${amtStr}.`;
    case 'MEDIUM':
      return `Operational Priority: MEDIUM (loss band >= ₹20k or window urgency). Amount at risk: ${amtStr}.`;
    case 'LOW':
      return `Operational Priority: LOW (routine observation for loss band < ₹20k without immediate window urgency).`;
    default:
      return `Operational Priority: ${level}`;
  }
};

export const predictionWindow = (prediction?: Prediction | null): string => {
  if (!prediction) return 'Time estimate unavailable';
  const time = prediction.time_prediction;
  if (time?.window_start && time?.window_end) {
    return formatWindowIST(time.window_start, time.window_end);
  }
  return time?.operational_window || prediction.when_window || 'Time estimate unavailable';
};

export const apiErrorMessage = (error: any, fallback: string): string => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || 'Invalid input').join('; ');
  return fallback;
};

export const escapeMapText = (value: unknown): string => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]!));
