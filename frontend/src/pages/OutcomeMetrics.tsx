/**
 * CyberShield AI — Phase 09: Outcome Metrics Dashboard
 *
 * Displays verified operational outcomes with honest denominators.
 * - Measured / unknown / excluded / synthetic cohorts are always visible.
 * - Verified held amounts and actual recovered amounts are reported separately.
 * - Financial totals carry a disclaimer: "not presented as independently saved money".
 * - Prediction linkage policy is disclosed (LAST_OPERATIONAL_BEFORE_EVENT).
 */

import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import type { OutcomeMetrics as OutcomeMetricsType } from '../types';

const fmt = (n: number | null | undefined, decimals = 2): string => {
  if (n === null || n === undefined) return '—';
  return n.toFixed(decimals);
};

const fmtINR = (n: number | null | undefined): string => {
  if (n === null || n === undefined) return '—';
  return '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
};

const fmtPct = (rate: number | null | undefined): string => {
  if (rate === null || rate === undefined) return '—';
  return (rate * 100).toFixed(1) + '%';
};

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  color?: string;
  warn?: boolean;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, sub, color = '#06b6d4', warn }) => (
  <div style={{
    background: 'rgba(15,23,42,0.7)',
    border: `1px solid ${warn ? '#f59e0b44' : '#1e293b'}`,
    borderRadius: 12,
    padding: '20px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    minWidth: 0,
  }}>
    <div style={{ fontSize: 12, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
    <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color: '#64748b' }}>{sub}</div>}
  </div>
);

const SectionHeader: React.FC<{ title: string; sub?: string }> = ({ title, sub }) => (
  <div style={{ marginBottom: 16, marginTop: 32 }}>
    <div style={{ fontSize: 15, fontWeight: 700, color: '#e2e8f0', borderLeft: '3px solid #06b6d4', paddingLeft: 12 }}>{title}</div>
    {sub && <div style={{ fontSize: 11, color: '#64748b', marginTop: 4, paddingLeft: 15 }}>{sub}</div>}
  </div>
);

const Disclaimer: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{
    background: 'rgba(245,158,11,0.08)',
    border: '1px solid rgba(245,158,11,0.25)',
    borderRadius: 8,
    padding: '12px 16px',
    fontSize: 11,
    color: '#fbbf24',
    lineHeight: 1.6,
    marginTop: 12,
  }}>
    ⚠ {children}
  </div>
);

const DenominatorBadge: React.FC<{ label: string; count: number; color?: string }> = ({ label, count, color = '#64748b' }) => (
  <span style={{
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    background: 'rgba(15,23,42,0.6)',
    border: `1px solid ${color}44`,
    borderRadius: 20,
    padding: '4px 12px',
    fontSize: 11,
    color,
    fontWeight: 600,
    margin: '0 6px 6px 0',
  }}>
    <span style={{ fontSize: 16, fontWeight: 700 }}>{count}</span> {label}
  </span>
);

export const OutcomeMetrics: React.FC = () => {
  const [metrics, setMetrics] = useState<OutcomeMetricsType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getOutcomeMetrics();
      setMetrics(data);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        || (e as { message?: string })?.message
        || 'Failed to load metrics';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1100, margin: '0 auto', fontFamily: "'Inter', sans-serif" }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 id="outcome-metrics-title" style={{ fontSize: 22, fontWeight: 800, color: '#e2e8f0', margin: 0 }}>
              📊 Verified Outcome Metrics
            </h1>
            <p style={{ fontSize: 12, color: '#64748b', margin: '6px 0 0 0' }}>
              Operational measurements from real verified outcomes. Synthetic and excluded cohorts are separated.
            </p>
          </div>
          <button
            id="btn-refresh-metrics"
            onClick={load}
            disabled={loading}
            style={{
              background: loading ? '#1e293b' : 'rgba(6,182,212,0.15)',
              border: '1px solid rgba(6,182,212,0.3)',
              color: '#06b6d4',
              borderRadius: 8,
              padding: '8px 18px',
              fontSize: 12,
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600,
            }}
          >
            {loading ? 'Loading…' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 8,
          padding: '12px 16px',
          color: '#f87171',
          fontSize: 13,
          marginBottom: 24,
        }}>
          {error}
        </div>
      )}

      {loading && !metrics && (
        <div style={{ color: '#64748b', fontSize: 14, padding: 40, textAlign: 'center' }}>
          Loading metrics…
        </div>
      )}

      {metrics && (
        <>
          {/* ── Denominator panel ─────────────────────────────────────────── */}
          <SectionHeader
            title="Cohort Denominators"
            sub="All denominators are always shown so that unknown and excluded cohorts are visible."
          />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 0, marginBottom: 8 }}>
            <DenominatorBadge label="Measured (success/failure)" count={metrics.denominator_measured} color="#06b6d4" />
            <DenominatorBadge label="Cashout events" count={metrics.denominator_cashout} color="#8b5cf6" />
            <DenominatorBadge label="Unknown (excluded from rates)" count={metrics.denominator_unknown} color="#f59e0b" />
            <DenominatorBadge label="Explicitly excluded" count={metrics.denominator_excluded} color="#ef4444" />
            <DenominatorBadge label="Synthetic / demo" count={metrics.denominator_synthetic} color="#64748b" />
            <DenominatorBadge label="Total active records" count={metrics.denominator_total_active} color="#94a3b8" />
          </div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>
            Unknown outcomes are excluded from success/failure denominators and displayed separately above.
            Synthetic outcomes never enter real metrics.
          </div>

          {/* ── Location accuracy ────────────────────────────────────────── */}
          <SectionHeader
            title="Location Accuracy"
            sub="Computed from CONFIRMED_CASHOUT and MULTIPLE_CASHOUT outcomes with a linked prediction."
          />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
            <StatCard
              label="Rank-1 Accuracy"
              value={fmtPct(metrics.rank1_accuracy_rate)}
              sub={`${metrics.rank1_count} / ${metrics.denominator_cashout} cashouts matched rank 1`}
              color="#06b6d4"
            />
            <StatCard
              label="Top-K Accuracy"
              value={fmtPct(metrics.topk_accuracy_rate)}
              sub={`${metrics.topk_count} / ${metrics.denominator_cashout} matched any predicted location (≤10 km)`}
              color="#8b5cf6"
            />
            <StatCard
              label="Mean Distance Error"
              value={metrics.mean_distance_error_km !== null ? fmt(metrics.mean_distance_error_km, 1) + ' km' : '—'}
              sub="Haversine: rank-1 cluster centroid vs actual cashout"
              color="#34d399"
            />
          </div>
          {metrics.denominator_cashout === 0 && (
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 8 }}>
              No cashout outcomes with observed location recorded yet. Accuracy metrics will appear once verified cashouts are ingested.
            </div>
          )}

          {/* ── Timing metrics ───────────────────────────────────────────── */}
          <SectionHeader
            title="Timing & Latency Metrics"
            sub="Lead times are from OPERATIONAL prediction or alert creation to observed event time."
          />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
            <StatCard
              label="Prediction Lead Time"
              value={metrics.mean_prediction_lead_time_minutes !== null
                ? fmt(metrics.mean_prediction_lead_time_minutes, 0) + ' min'
                : '—'}
              sub="Avg minutes from prediction created_at to cashout event"
              color="#06b6d4"
            />
            <StatCard
              label="Alert Lead Time"
              value={metrics.mean_alert_lead_time_minutes !== null
                ? fmt(metrics.mean_alert_lead_time_minutes, 0) + ' min'
                : '—'}
              sub="Avg minutes from alert issued to cashout event"
              color="#8b5cf6"
            />
            <StatCard
              label="Acknowledgement Latency"
              value={metrics.mean_alert_acknowledgement_latency_minutes !== null
                ? fmt(metrics.mean_alert_acknowledgement_latency_minutes, 0) + ' min'
                : '—'}
              sub="Avg minutes from alert created to acknowledged"
              color="#f59e0b"
            />
            <StatCard
              label="Bank Response Latency"
              value={metrics.mean_bank_response_latency_minutes !== null
                ? fmt(metrics.mean_bank_response_latency_minutes, 0) + ' min'
                : '—'}
              sub="Avg minutes from freeze requested to hold confirmed"
              color="#34d399"
            />
          </div>

          {/* ── Financial figures ────────────────────────────────────────── */}
          <SectionHeader
            title="Financial Figures (Reported Separately)"
            sub="Verified held amounts and actual recovered amounts are shown independently — their sum is NOT presented as savings."
          />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
            <StatCard
              label="Verified Held"
              value={fmtINR(metrics.total_verified_held_inr)}
              sub="Sum of confirmed bank hold amounts across CONFIRMED_HOLD / PARTIAL_HOLD actions"
              color="#06b6d4"
            />
            <StatCard
              label="Verified Released"
              value={fmtINR(metrics.total_verified_released_inr)}
              sub="Funds unfrozen post-investigation"
              color="#f59e0b"
              warn
            />
            <StatCard
              label="Actual Recovered"
              value={fmtINR(metrics.total_actual_recovered_inr)}
              sub="Funds returned to victim / seized (separate from held)"
              color="#34d399"
            />
          </div>
          <Disclaimer>
            {metrics.financial_note}
          </Disclaimer>

          {/* ── Alert workload ───────────────────────────────────────────── */}
          <SectionHeader
            title="Alert Workload"
            sub="False-alert count = NO_OBSERVED_CASHOUT outcomes that had an alert linked."
          />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
            <StatCard
              label="False-Alert Workload"
              value={String(metrics.false_alert_count)}
              sub="Alerts dispatched for cases where no cashout was subsequently observed"
              color={metrics.false_alert_count > 0 ? '#f59e0b' : '#34d399'}
              warn={metrics.false_alert_count > 0}
            />
          </div>

          {/* ── Policy disclosure ────────────────────────────────────────── */}
          <SectionHeader title="Prediction Evaluation Policy" />
          <div style={{
            background: 'rgba(15,23,42,0.6)',
            border: '1px solid #1e293b',
            borderRadius: 10,
            padding: '14px 18px',
            fontSize: 11,
            color: '#94a3b8',
            lineHeight: 1.8,
          }}>
            <div style={{ color: '#06b6d4', fontWeight: 700, marginBottom: 6, fontSize: 12 }}>
              Policy: {metrics.prediction_selection_policy}
            </div>
            {metrics.policy_description}
          </div>

          <div style={{ height: 40 }} />
        </>
      )}
    </div>
  );
};
