import { Prediction, PredictionLocationItem } from '../types';

// datetime-local expects wall-clock time, whereas toISOString() always returns UTC.
export const toLocalDateTimeInput = (date = new Date()): string =>
  new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

export const parseApiDate = (value?: string | null): Date | null => {
  if (!value) return null;
  // Legacy database timestamps are UTC but were serialized without a timezone.
  const normalized = value.trim().replace(' ', 'T');
  const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}Z`);
  return Number.isFinite(date.getTime()) ? date : null;
};

export const formatIST = (value?: string | null): string => {
  const date = parseApiDate(value);
  if (!date) return 'Not available';
  return `${date.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })} IST`;
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
    : prediction.score_note || 'Scores come from a model trained on synthetic Delhi data. They rank candidate locations, are not verified real-world probabilities, and need not sum to 100%.';

export const predictionWindow = (prediction?: Prediction | null): string => {
  if (!prediction) return 'Time estimate unavailable';
  const time = prediction.time_prediction;
  if (time?.window_start && time?.window_end) {
    return `${formatIST(time.window_start)} – ${formatIST(time.window_end)}`;
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
