import React from 'react';
import { UnifiedRiskMap } from './UnifiedRiskMap';
import { HotspotCluster, ATMLocationItem, PredictionLocationItem, Complaint } from '../types';

export interface CashOutRiskMapProps {
  hotspots?: HotspotCluster[];
  atms?: ATMLocationItem[];
  topLocations?: PredictionLocationItem[];
  complaint?: Complaint | null;
  prediction?: any;
  highlightCluster?: string;
  height?: string;
  showControls?: boolean;
  priorityHotspotIds?: number[];
  selectedClusterId?: number | null;
  regionCenter?: { lat: number; lon: number };
}

export const CashOutRiskMap: React.FC<CashOutRiskMapProps> = (props) => {
  return <UnifiedRiskMap {...props} />;
};
