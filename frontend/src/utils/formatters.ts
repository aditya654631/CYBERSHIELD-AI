/**
 * Format risk score or percentage for display.
 * Numeric risk is only shown when explicitly supplied/calculated by backend.
 * If both fields are missing, invalid, non-numeric, NaN, or non-finite, returns "Risk unavailable".
 * Does NOT silently convert missing risk to zero.
 */
export function formatRisk(
  riskScore?: number | null,
  riskPercentage?: number | null
): string {
  if (
    typeof riskPercentage === 'number' &&
    Number.isFinite(riskPercentage) &&
    !Number.isNaN(riskPercentage)
  ) {
    return `${Math.round(riskPercentage)}%`;
  }

  if (
    typeof riskScore === 'number' &&
    Number.isFinite(riskScore) &&
    !Number.isNaN(riskScore)
  ) {
    // If riskScore is between 0 and 1 (standard normalized float), scale by 100
    const val = riskScore <= 1 && riskScore >= 0 ? riskScore * 100 : riskScore;
    return `${Math.round(val)}%`;
  }

  return 'Risk unavailable';
}

const inrFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0
});

/**
 * Format currency strictly in Indian Rupees (INR) format (e.g., ₹15,200, ₹85,000).
 * Never prepends a dollar sign. Handles null, undefined, strings, and non-finite inputs gracefully.
 */
export function formatINR(amount?: number | string | null): string {
  if (amount === null || amount === undefined || amount === '') {
    return '₹0';
  }
  const val = typeof amount === 'number' ? amount : Number(amount);
  if (!Number.isFinite(val) || Number.isNaN(val)) {
    return '₹0';
  }
  return inrFormatter.format(val);
}
