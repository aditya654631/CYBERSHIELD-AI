/**
 * CyberShield AI — Phase 6: Outcome Feedback & Model Drift Intelligence
 *
 * Displays verified operational outcomes with honest denominators and strict cohort separation.
 * - Authorized Operational / Controlled Synthetic / Excluded / Unknown cohorts are separated.
 * - Real-world metrics are never displayed without an authorized operational cohort (n = 0 state truthful).
 * - Controlled synthetic outcomes are reported under separate "CONTROLLED SYNTHETIC EVALUATION" heading.
 * - Non-retraining drift monitoring layer tracks distribution shifts against frozen V8 reference metadata.
 * - Verified held amounts and actual recovered amounts are reported separately (never summed as "money saved").
 */

import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import type {
  OutcomeMetrics as OutcomeMetricsType,
  OutcomeMonitoringData,
  DistributionDriftItem,
} from '../types';
import {
  ShieldAlert,
  Info,
  CheckCircle2,
  AlertTriangle,
  Activity,
  Layers,
  TrendingUp,
  Cpu,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';

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

const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  sub,
  color = '#06b6d4',
  warn,
}) => (
  <div
    style={{
      background: 'rgba(15,23,42,0.7)',
      border: `1px solid ${warn ? '#f59e0b44' : '#1e293b'}`,
      borderRadius: 12,
      padding: '20px 24px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      minWidth: 0,
    }}
  >
    <div
      style={{
        fontSize: 12,
        color: '#94a3b8',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: 1,
      }}
    >
      {label}
    </div>
    <div style={{ fontSize: 26, fontWeight: 700, color }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color: '#64748b' }}>{sub}</div>}
  </div>
);

const SectionHeader: React.FC<{
  title: string;
  sub?: string;
  tooltip?: string;
}> = ({ title, sub, tooltip }) => {
  const [showTip, setShowTip] = useState(false);
  return (
    <div style={{ marginBottom: 16, marginTop: 32 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          borderLeft: '3px solid #06b6d4',
          paddingLeft: 12,
        }}
      >
        <span style={{ fontSize: 15, fontWeight: 700, color: '#e2e8f0' }}>
          {title}
        </span>
        {tooltip && (
          <div style={{ position: 'relative', display: 'inline-block' }}>
            <button
              type="button"
              onClick={() => setShowTip(!showTip)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                padding: 0,
                display: 'flex',
                alignItems: 'center',
              }}
              title="Information"
            >
              <Info size={14} />
            </button>
            {showTip && (
              <div
                style={{
                  position: 'absolute',
                  left: 0,
                  top: 20,
                  zIndex: 40,
                  width: 280,
                  padding: 12,
                  background: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: 8,
                  boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
                  fontSize: 11,
                  color: '#cbd5e1',
                  lineHeight: 1.5,
                }}
              >
                {tooltip}
              </div>
            )}
          </div>
        )}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: '#64748b', marginTop: 4, paddingLeft: 15 }}>
          {sub}
        </div>
      )}
    </div>
  );
};

const Disclaimer: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    style={{
      background: 'rgba(245,158,11,0.08)',
      border: '1px solid rgba(245,158,11,0.25)',
      borderRadius: 8,
      padding: '12px 16px',
      fontSize: 11,
      color: '#fbbf24',
      lineHeight: 1.6,
      marginTop: 12,
    }}
  >
    ⚠ {children}
  </div>
);

export const OutcomeMetrics: React.FC = () => {
  const [metrics, setMetrics] = useState<OutcomeMetricsType | null>(null);
  const [monitoring, setMonitoring] = useState<OutcomeMonitoringData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [mMetrics, mMonitoring] = await Promise.all([
        api.getOutcomeMetrics(),
        api.getOutcomeMonitoring(),
      ]);
      setMetrics(mMetrics);
      setMonitoring(mMonitoring);
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ||
        (e as { message?: string })?.message ||
        'Failed to load metrics';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const authOperationalCount =
    monitoring?.cohorts?.AUTHORIZED_OPERATIONAL?.count ?? 0;
  const controlledSyntheticCount =
    monitoring?.cohorts?.CONTROLLED_SYNTHETIC?.count ?? 0;
  const excludedCount = monitoring?.cohorts?.EXCLUDED?.count ?? 0;
  const unknownCount = monitoring?.cohorts?.UNKNOWN?.count ?? 0;

  return (
    <div
      style={{
        padding: '28px 32px',
        maxWidth: 1100,
        margin: '0 auto',
        fontFamily: "'Inter', sans-serif",
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <h1
              id="outcome-metrics-title"
              style={{
                fontSize: 22,
                fontWeight: 800,
                color: '#e2e8f0',
                margin: 0,
              }}
            >
              📊 Verified Outcome & Drift Monitoring
            </h1>
            <p style={{ fontSize: 12, color: '#64748b', margin: '6px 0 0 0' }}>
              Operational evaluation and model drift intelligence. Synthetic,
              operational, excluded, and unknown cohorts are strictly isolated.
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
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <RefreshCw
              size={14}
              style={{
                animation: loading ? 'spin 1s linear infinite' : 'none',
              }}
            />
            <span>{loading ? 'Refreshing…' : 'Refresh Telemetry'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 8,
            padding: '12px 16px',
            color: '#f87171',
            fontSize: 13,
            marginBottom: 24,
          }}
        >
          {error}
        </div>
      )}

      {loading && !metrics && !monitoring && (
        <div
          style={{
            color: '#64748b',
            fontSize: 14,
            padding: 40,
            textAlign: 'center',
          }}
        >
          Loading outcome & drift intelligence…
        </div>
      )}

      {/* ── 1. OUTCOME COHORTS BREAKDOWN ────────────────────────────────────────── */}
      <SectionHeader
        title="Outcome Evaluation Cohorts"
        sub="Every outcome belongs strictly to one cohort. Controlled synthetic scenarios are never combined into real-world accuracy."
        tooltip="Cohort isolation ensures real-world operational evaluation is never contaminated by synthetic test data or unverified claims."
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
          gap: 12,
        }}
      >
        <StatCard
          label="Authorized Operational"
          value={`n = ${authOperationalCount}`}
          sub="Verified field outcomes eligible for real-world metrics"
          color="#10b981"
        />
        <StatCard
          label="Controlled Synthetic"
          value={`n = ${controlledSyntheticCount}`}
          sub="Isolated synthetic scenarios for validation testing"
          color="#a855f7"
        />
        <StatCard
          label="Excluded Outcomes"
          value={`n = ${excludedCount}`}
          sub="Out of scope, test cases, or explicitly excluded"
          color="#ef4444"
          warn={excludedCount > 0}
        />
        <StatCard
          label="Unknown / Pending"
          value={`n = ${unknownCount}`}
          sub="Awaiting field verification by authorized officer"
          color="#f59e0b"
          warn={unknownCount > 0}
        />
      </div>

      {/* ── 2. REAL-WORLD OPERATIONAL EVALUATION METRICS ─────────────────────── */}
      <SectionHeader
        title="Authorized Operational Evaluation"
        sub="Metrics computed exclusively from verified real-world operational outcomes (n > 0 required)."
        tooltip="Operational metrics reflect true field resolution accuracy against historical predictions. Percentages are never displayed from zero or synthetic cohorts."
      />

      {authOperationalCount === 0 ? (
        <div
          style={{
            background: 'rgba(30,41,59,0.5)',
            border: '1px dashed #334155',
            borderRadius: 10,
            padding: '24px 20px',
            textAlign: 'center',
            color: '#94a3b8',
            fontSize: 13,
            lineHeight: 1.6,
          }}
        >
          <div
            style={{
              fontWeight: 700,
              color: '#e2e8f0',
              fontSize: 14,
              marginBottom: 4,
            }}
          >
            No authorized real-world evaluation cohort is available yet.
          </div>
          <p style={{ margin: 0, fontSize: 12, color: '#64748b' }}>
            Real-world Top-1/Top-3 hit rates and spatial error metrics require
            verified operational outcomes from active field operations (n = 0).
            Accuracy is not fabricated from zero or synthetic cohorts.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: 12,
          }}
        >
          <StatCard
            label="Top-1 Operational Hit Rate"
            value={fmtPct(monitoring?.operational_metrics?.top1_hit_rate)}
            sub={`n = ${authOperationalCount} verified cases`}
            color="#06b6d4"
          />
          <StatCard
            label="Top-3 Operational Hit Rate"
            value={fmtPct(monitoring?.operational_metrics?.top3_hit_rate)}
            sub={`n = ${authOperationalCount} verified cases`}
            color="#10b981"
          />
          <StatCard
            label="Median Spatial Error"
            value={
              monitoring?.operational_metrics?.median_spatial_error_km !== null &&
              monitoring?.operational_metrics?.median_spatial_error_km !== undefined
                ? `${fmt(monitoring.operational_metrics.median_spatial_error_km, 1)} km`
                : '—'
            }
            sub="Haversine distance between prediction and actual cashout"
            color="#34d399"
          />
          <StatCard
            label="Median Lead Time"
            value={
              monitoring?.operational_metrics?.median_lead_time_min !== null &&
              monitoring?.operational_metrics?.median_lead_time_min !== undefined
                ? `${fmt(monitoring.operational_metrics.median_lead_time_min, 0)} min`
                : '—'
            }
            sub="Prediction lead time before observed event"
            color="#38bdf8"
          />
        </div>
      )}

      {/* ── 3. CONTROLLED SYNTHETIC EVALUATION ───────────────────────────────── */}
      <SectionHeader
        title="Controlled Synthetic Evaluation"
        sub="Controlled synthetic outcomes evaluated separately for pipeline and calibration validation."
        tooltip="Synthetic evaluation benchmarks pipeline correctness without misrepresenting synthetic performance as real-world field success."
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: 12,
        }}
      >
        <StatCard
          label="Synthetic Top-3 Hit Rate"
          value={fmtPct(monitoring?.synthetic_metrics?.top3_hit_rate)}
          sub={`n = ${controlledSyntheticCount} synthetic cases`}
          color="#a855f7"
        />
        <StatCard
          label="Synthetic Top-1 Hit Rate"
          value={fmtPct(monitoring?.synthetic_metrics?.top1_hit_rate)}
          sub={`n = ${controlledSyntheticCount} synthetic cases`}
          color="#8b5cf6"
        />
        <StatCard
          label="Synthetic Mean Spatial Error"
          value={
            monitoring?.synthetic_metrics?.mean_spatial_error_km !== null &&
            monitoring?.synthetic_metrics?.mean_spatial_error_km !== undefined
              ? `${fmt(monitoring.synthetic_metrics.mean_spatial_error_km, 1)} km`
              : '—'
          }
          sub="Evaluation against synthetic ground-truth coordinates"
          color="#c084fc"
        />
      </div>

      {/* ── 4. MODEL DRIFT MONITORING (NON-TRAINING LAYER) ───────────────────── */}
      <SectionHeader
        title="Model Drift & Distribution Monitoring"
        sub="Distribution stability tracked against approved model reference baseline. Strictly non-training layer."
        tooltip="Drift monitoring checks whether incoming case and prediction distributions are changing relative to an approved reference. It does not automatically retrain or replace the active model."
      />

      <div
        style={{
          background: 'rgba(15,23,42,0.7)',
          border: '1px solid #1e293b',
          borderRadius: 12,
          padding: '20px 24px',
          marginBottom: 16,
        }}
      >
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 12,
            borderBottom: '1px solid #1e293b',
            paddingBottom: 14,
            marginBottom: 14,
          }}
        >
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0' }}>
              Reference Baseline:{' '}
              <span style={{ color: '#06b6d4', fontFamily: 'monospace' }}>
                {monitoring?.reference_model_version || 'cashout-location-xgb-v8-debiased'}
              </span>
            </div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
              Source: {monitoring?.reference_baseline_source || 'model_metadata_v8_debiased.json'}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600 }}>
              Overall Drift Status:
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '4px 10px',
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 700,
                background:
                  monitoring?.overall_drift_status === 'STABLE'
                    ? 'rgba(16,185,129,0.15)'
                    : monitoring?.overall_drift_status === 'SHIFT_OBSERVED'
                    ? 'rgba(239,68,68,0.15)'
                    : monitoring?.overall_drift_status === 'MONITORING'
                    ? 'rgba(6,182,212,0.15)'
                    : 'rgba(245,158,11,0.15)',
                color:
                  monitoring?.overall_drift_status === 'STABLE'
                    ? '#10b981'
                    : monitoring?.overall_drift_status === 'SHIFT_OBSERVED'
                    ? '#f87171'
                    : monitoring?.overall_drift_status === 'MONITORING'
                    ? '#06b6d4'
                    : '#fbbf24',
                border: `1px solid ${
                  monitoring?.overall_drift_status === 'STABLE'
                    ? '#10b98144'
                    : monitoring?.overall_drift_status === 'SHIFT_OBSERVED'
                    ? '#ef444444'
                    : monitoring?.overall_drift_status === 'MONITORING'
                    ? '#06b6d444'
                    : '#f59e0b44'
                }`,
              }}
            >
              {monitoring?.overall_drift_status === 'STABLE' && <CheckCircle2 size={13} />}
              {monitoring?.overall_drift_status === 'SHIFT_OBSERVED' && <AlertTriangle size={13} />}
              {monitoring?.overall_drift_status === 'INSUFFICIENT_DATA' && <Info size={13} />}
              {monitoring?.overall_drift_status === 'MONITORING' && <Activity size={13} />}
              <span>{monitoring?.overall_drift_status?.replace(/_/g, ' ') || 'INSUFFICIENT DATA'}</span>
            </span>
          </div>
        </div>

        {/* Drift Table */}
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: 12,
              color: '#cbd5e1',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8', textAlign: 'left' }}>
                <th style={{ padding: '8px 12px' }}>Distribution Indicator</th>
                <th style={{ padding: '8px 12px' }}>Reference Mean</th>
                <th style={{ padding: '8px 12px' }}>Monitoring Mean</th>
                <th style={{ padding: '8px 12px' }}>Shift Metric</th>
                <th style={{ padding: '8px 12px' }}>Status</th>
                <th style={{ padding: '8px 12px' }}>Notes</th>
              </tr>
            </thead>
            <tbody>
              {monitoring?.drift_indicators && monitoring.drift_indicators.length > 0 ? (
                monitoring.drift_indicators.map((d: DistributionDriftItem, idx: number) => (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: '1px solid #1e293b',
                      background: idx % 2 === 0 ? 'rgba(30,41,59,0.2)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '10px 12px', fontWeight: 600, color: '#e2e8f0' }}>
                      {d.feature_name}
                    </td>
                    <td style={{ padding: '10px 12px', fontFamily: 'monospace' }}>
                      {d.reference_mean !== null ? fmt(d.reference_mean, 3) : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', fontFamily: 'monospace' }}>
                      {d.monitoring_mean !== null ? fmt(d.monitoring_mean, 3) : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: '#06b6d4' }}>
                      {d.shift_metric_value !== null ? fmt(d.shift_metric_value, 4) : '—'} ({d.metric_type})
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 4,
                          background:
                            d.status === 'STABLE'
                              ? 'rgba(16,185,129,0.15)'
                              : d.status === 'SHIFT_OBSERVED'
                              ? 'rgba(239,68,68,0.15)'
                              : 'rgba(148,163,184,0.15)',
                          color:
                            d.status === 'STABLE'
                              ? '#34d399'
                              : d.status === 'SHIFT_OBSERVED'
                              ? '#f87171'
                              : '#94a3b8',
                        }}
                      >
                        {d.status}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px', fontSize: 11, color: '#94a3b8' }}>
                      {d.notes}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} style={{ padding: 16, textAlign: 'center', color: '#64748b' }}>
                    No drift distribution telemetry available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div
          style={{
            marginTop: 14,
            padding: '10px 14px',
            background: 'rgba(30,41,59,0.6)',
            borderRadius: 6,
            fontSize: 11,
            color: '#94a3b8',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>
            🔒 <strong>Retraining Policy:</strong> Automatic retraining is strictly disabled.
            Distribution shifts trigger governance review only. Model artifacts remain frozen.
          </span>
          <span style={{ color: '#10b981', fontWeight: 600 }}>
            Auto-retraining Triggered: {monitoring?.auto_retraining_triggered ? 'YES' : 'NO (FROZEN)'}
          </span>
        </div>
      </div>

      {/* ── 5. FINANCIAL FIGURES (REPORTED SEPARATELY) ────────────────────── */}
      <SectionHeader
        title="Financial Figures (Reported Separately)"
        sub="Verified held amounts and actual recovered amounts are shown independently — their sum is NOT presented as savings."
      />
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: 12,
        }}
      >
        <StatCard
          label="Verified Held"
          value={fmtINR(metrics?.total_verified_held_inr ?? 0)}
          sub="Confirmed bank hold amounts across hold actions"
          color="#06b6d4"
        />
        <StatCard
          label="Verified Released"
          value={fmtINR(metrics?.total_verified_released_inr ?? 0)}
          sub="Funds unfrozen post-investigation"
          color="#f59e0b"
          warn
        />
        <StatCard
          label="Actual Recovered"
          value={fmtINR(metrics?.total_actual_recovered_inr ?? 0)}
          sub="Funds returned to victim / seized (separate from held)"
          color="#34d399"
        />
      </div>
      <Disclaimer>
        {metrics?.financial_note ||
          'Verified held amounts and actual recovered amounts represent distinct operational stages. They are reported separately and must not be summed together as loss prevented.'}
      </Disclaimer>

      {/* ── 6. ALERT WORKLOAD ──────────────────────────────────────────────── */}
      <SectionHeader
        title="Alert Workload"
        sub="False-alert count = NO_OBSERVED_CASHOUT outcomes that had an alert linked."
      />
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: 12,
        }}
      >
        <StatCard
          label="False-Alert Workload"
          value={String(metrics?.false_alert_count ?? 0)}
          sub="Alerts dispatched for cases where no cashout was subsequently observed"
          color={
            metrics && metrics.false_alert_count > 0 ? '#f59e0b' : '#34d399'
          }
          warn={Boolean(metrics && metrics.false_alert_count > 0)}
        />
      </div>

      {/* ── 7. POLICY DISCLOSURE ───────────────────────────────────────────── */}
      <SectionHeader title="Prediction Evaluation Policy" />
      <div
        style={{
          background: 'rgba(15,23,42,0.6)',
          border: '1px solid #1e293b',
          borderRadius: 10,
          padding: '14px 18px',
          fontSize: 11,
          color: '#94a3b8',
          lineHeight: 1.8,
        }}
      >
        <div
          style={{
            color: '#06b6d4',
            fontWeight: 700,
            marginBottom: 6,
            fontSize: 12,
          }}
        >
          Policy: {metrics?.prediction_selection_policy || 'LAST_OPERATIONAL_BEFORE_EVENT'}
        </div>
        {metrics?.policy_description ||
          'Prediction linkage is applied strictly using the LAST_OPERATIONAL_BEFORE_EVENT rule. Predictions generated after an observed event are not evaluated retroactively.'}
      </div>

      <div style={{ height: 40 }} />
    </div>
  );
};
