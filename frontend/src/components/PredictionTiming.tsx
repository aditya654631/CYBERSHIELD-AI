import React from 'react';
import { Prediction } from '../types';
import { formatIST, parseApiDate, predictionWindow } from '../utils/predictionDisplay';

export const PredictionTiming: React.FC<{ prediction: Prediction }> = ({ prediction }) => {
  const time = prediction.time_prediction;
  const windowEnd = parseApiDate(time?.window_end);
  const expired = windowEnd != null && windowEnd.getTime() <= Date.now();
  return (
    <div className="space-y-2 text-xs">
      <div className="font-bold text-[#031926] leading-relaxed">{predictionWindow(prediction)}</div>
      {time?.prediction_reference_time && (
        <div className="text-slate-600">
          Reference (complaint reported): <strong className="text-[#031926]">{formatIST(time.prediction_reference_time)}</strong>
        </div>
      )}
      {time?.predicted_minutes_to_cashout != null && Number.isFinite(time.predicted_minutes_to_cashout) && (
        <div className="text-slate-600">
          Central estimate: <strong className="text-[#031926]">~{Math.round(time.predicted_minutes_to_cashout)} minutes after the reference</strong>
          {time.predicted_cashout_at ? ` (${formatIST(time.predicted_cashout_at)})` : ''}.
        </div>
      )}
      {expired && (
        <div className="p-2 rounded bg-[#FDFBF7] border border-[#F4E9CD] text-[#78350F] font-medium">
          Estimated cash-out window has expired ({formatIST(time?.window_end)}). Review transaction evidence before taking field action.
        </div>
      )}
      <p className="text-[11px] text-slate-500">
        Estimated from prototype patterns; the same case-level time window applies to all three locations. This is not a calibrated confidence interval.
      </p>
    </div>
  );
};
