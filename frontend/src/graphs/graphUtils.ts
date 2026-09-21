/**
 * Pure graph utility functions for Phase 6
 * Safe label formatting, bounded edge styling, and color/shape mapping
 */

/**
 * Cleanly format multi-line node display labels
 * Neutralizes guilt-implying words per neutral language policy and appends masked IDs.
 */
export const formatSafeDisplayLabel = (
  rawLabel?: string | null,
  nodeType?: string,
  isSource?: boolean,
  maskedId?: string | null,
  isPotentialMuleIndicator?: boolean
): string => {
  let mainLabel = '';

  if (nodeType === 'atm') {
    mainLabel = rawLabel || 'Cash-Out Terminal';
  } else if (nodeType === 'cluster') {
    mainLabel = rawLabel ? `PREDICTED ZONE: ${rawLabel}` : 'PREDICTED CASH-OUT ZONE';
  } else if (isPotentialMuleIndicator) {
    mainLabel = 'Potential Mule Indicator / Under Review';
  } else if (!rawLabel || rawLabel.trim() === '') {
    if (isSource || nodeType === 'victim') {
      mainLabel = 'Victim Account';
    } else if (nodeType === 'intermediary') {
      mainLabel = 'Intermediary Account';
    } else if (nodeType === 'account') {
      mainLabel = 'Account';
    } else {
      mainLabel = 'Beneficiary Account';
    }
  } else {
    const trimmed = rawLabel.trim();
    const lower = trimmed.toLowerCase();

    // Neutralize labels with guilt-implying or mule strings
    if (
      lower.includes('mule.recipient') ||
      lower.includes('mule.receiver') ||
      lower.includes('confirmed mule') ||
      lower === 'mule' ||
      lower === 'suspected mule'
    ) {
      mainLabel = 'Potential Mule Indicator / Under Review';
    } else if (lower.includes('(terminal mule)')) {
      mainLabel = trimmed.replace(/\(terminal mule\)/i, '(Potential Mule Indicator / Under Review)');
    } else if (lower.includes('(known atm cashier)')) {
      mainLabel = trimmed.replace(/\(known atm cashier\)/i, '(Cashier / Under Review)');
    } else {
      mainLabel = trimmed;
    }
  }

  // Append masked account/terminal ID on a second line so identically named nodes remain distinguishable
  if (maskedId && maskedId.trim() !== '') {
    return `${mainLabel}\n${maskedId.trim()}`;
  }
  return mainLabel;
};

/**
 * Computes a visually bounded edge width (between 2.0px and 5.5px) based on transaction volume.
 */
export const computeBoundedEdgeWidth = (amount: number): number => {
  if (!amount || amount <= 1000) return 2.0;
  if (amount >= 1000000) return 5.5;
  // Scale logarithmically between ₹1,000 (2.0px) and ₹1,000,000 (5.5px)
  const logAmt = Math.log10(amount);
  const width = 2.0 + ((logAmt - 3.0) / 3.0) * 3.5;
  return Math.round(Math.max(2.0, Math.min(5.5, width)) * 10) / 10;
};
