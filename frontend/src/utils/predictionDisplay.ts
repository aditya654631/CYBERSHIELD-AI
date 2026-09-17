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
  delayHours?: number | null,
  rank?: number | null,
  backendReason?: string | null
): string => {
  if (backendReason && backendReason.trim()) {
    return backendReason.trim();
  }

  const level = (riskLevel || 'MEDIUM').toUpperCase();
  const amtStr = amount != null ? `₹${Number(amount).toLocaleString('en-IN')}` : 'reported loss';

  if (rank === 1) {
    switch (level) {
      case 'CRITICAL':
        return `Rank #1 Primary: CRITICAL (loss band >= ₹5L or >= ₹1.5L with cash-out urgency <= 90 min and intake delay <= 4 hrs). Associated amount: ${amtStr}.`;
      case 'HIGH':
        return `Rank #1 Primary: HIGH (loss band >= ₹75k or >= ₹30k with cash-out urgency <= 90 min). Associated amount: ${amtStr}.`;
      case 'MEDIUM':
        return `Rank #1 Primary: MEDIUM (loss band >= ₹20k or window urgency <= 90 min). Associated amount: ${amtStr}.`;
      case 'LOW':
        return `Rank #1 Primary: LOW (routine observation for loss band < ₹20k without immediate window urgency).`;
      default:
        return `Rank #1 Primary: ${level}`;
    }
  } else if (rank === 2) {
    switch (level) {
      case 'HIGH':
        return `Rank #2 Secondary: HIGH (loss band >= ₹5L with immediate window urgency <= 90 min). Associated amount: ${amtStr}.`;
      case 'MEDIUM':
        return `Rank #2 Secondary: MEDIUM (loss band >= ₹100k or >= ₹40k with window urgency <= 90 min). Associated amount: ${amtStr}.`;
      case 'LOW':
        return `Rank #2 Secondary: LOW (routine observation).`;
      default:
        return `Rank #2 Secondary: ${level}`;
    }
  } else if (rank && rank >= 3) {
    switch (level) {
      case 'MEDIUM':
        return `Rank #${rank} Candidate: MEDIUM (loss band >= ₹5L with urgency <= 90 min and intake delay <= 4 hrs). Associated amount: ${amtStr}.`;
      case 'LOW':
        return `Rank #${rank} Candidate: LOW (routine observation).`;
      default:
        return `Rank #${rank} Candidate: ${level}`;
    }
  }

  switch (level) {
    case 'CRITICAL':
      return `Operational Priority: CRITICAL (loss band >= ₹5L or compound risk with cash-out urgency <= 90 min and intake delay <= 4 hrs). Associated amount: ${amtStr}.`;
    case 'HIGH':
      return `Operational Priority: HIGH (loss band >= ₹75k or urgency <= 90 min). Associated amount: ${amtStr}.`;
    case 'MEDIUM':
      return `Operational Priority: MEDIUM (loss band >= ₹20k or immediate window urgency). Associated amount: ${amtStr}.`;
    case 'LOW':
      return `Operational Priority: LOW (routine observation).`;
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
