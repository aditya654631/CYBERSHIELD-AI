import React from 'react';
import { Prediction } from '../types';
import { formatIST, parseApiDate, predictionWindow } from '../utils/predictionDisplay';

export const PredictionTiming: React.FC<{ prediction: Prediction }> = ({ prediction }) => {
  const time = prediction.time_prediction;
  const windowEnd = parseApiDate(time?.window_end);
  const expired = windowEnd != null && windowEnd.getTime() < Date.now();
  return (
    <div className="space-y-2 text-xs">
      <div className="font-bold text-[#173A63] leading-relaxed">{predictionWindow(prediction)}</div>
      {time?.prediction_reference_time && (
        <div className="text-slate-600">
          Reference (complaint reported): <strong>{formatIST(time.prediction_reference_time)}</strong>
        </div>
      )}
      {time?.predicted_minutes_to_cashout != null && Number.isFinite(time.predicted_minutes_to_cashout) && (
        <div className="text-slate-600">
          Central estimate: <strong>~{Math.round(time.predicted_minutes_to_cashout)} minutes after the reference</strong>
          {time.predicted_cashout_at ? ` (${formatIST(time.predicted_cashout_at)})` : ''}.
        </div>
      )}
      {expired && <p className="font-medium text-amber-800">This estimated window has passed. Review transaction evidence before taking action.</p>}
      <p className="text-[11px] text-slate-500">
        Estimated from prototype patterns; the same case-level time window applies to all three locations. This is not a calibrated confidence interval.
      </p>
    </div>
  );
};
