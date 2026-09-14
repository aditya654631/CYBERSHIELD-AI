'use strict';

const { EVENT_TYPES, BANK_MSPS, AUTHORITY_MSPS } = require('./constants');
const { partitionSignalsByWindow } = require('./temporal-window');

function countType(signals, eventType) {
    return signals.filter(s => s.event_type === eventType).length;
}

function getDistinctOrgs(signals) {
    const orgs = new Set();
    for (const s of signals) {
        if (s.organization_msp) {
            orgs.add(s.organization_msp);
        }
    }
    return orgs;
}

function getDistinctBanks(signals) {
    const banks = new Set();
    for (const s of signals) {
        if (s.organization_msp && BANK_MSPS.includes(s.organization_msp)) {
            banks.add(s.organization_msp);
        }
    }
    return banks;
}

function computeConfidenceStats(signals) {
    if (!signals || signals.length === 0) {
        return { mean: 0.0, max: 0.0 };
    }
    let sum = 0.0;
    let max = 0.0;
    for (const s of signals) {
        const c = s.confidence !== undefined ? s.confidence : 0.0;
        sum += c;
        if (c > max) max = c;
    }
    const mean = Number((sum / signals.length).toFixed(4));
    return { mean, max: Number(max.toFixed(4)) };
}

function computeAgeMinutes(signals, refTimeMs, eventTypeFilter = null) {
    let filtered = signals;
    if (eventTypeFilter) {
        if (Array.isArray(eventTypeFilter)) {
            filtered = signals.filter(s => eventTypeFilter.includes(s.event_type));
        } else {
            filtered = signals.filter(s => s.event_type === eventTypeFilter);
        }
    }
    if (filtered.length === 0) {
        return -1; // Explicit documented sentinel for no event
    }
    let minAgeMs = Infinity;
    for (const s of filtered) {
        const ageMs = refTimeMs - s.eventTimeMs;
        if (ageMs >= 0 && ageMs < minAgeMs) {
            minAgeMs = ageMs;
        }
    }
    if (minAgeMs === Infinity) {
        return -1;
    }
    return Number((minAgeMs / (60 * 1000)).toFixed(2));
}

function countActiveDays(signals) {
    const days = new Set();
    for (const s of signals) {
        const dayKey = new Date(s.eventTimeMs).toISOString().split('T')[0];
        days.add(dayKey);
    }
    return days.size;
}

/**
 * Builds the complete deterministic numeric feature vector for a candidate cluster.
 * 
 * @param {object} params
 * @param {number} params.clusterId
 * @param {number} params.refTimeMs
 * @param {Array} params.activeClusterSignals
 * @param {Array} params.allClusterSignalsAtRef
 * @param {Array} [params.subjectSignals]
 * @param {string|null} [params.opaqueSubjectRef]
 * @returns {object} Raw numeric feature dictionary
 */
function buildClusterFeatureVector({
    clusterId,
    refTimeMs,
    activeClusterSignals,
    allClusterSignalsAtRef,
    subjectSignals = [],
    opaqueSubjectRef = null
}) {
    const byWin = partitionSignalsByWindow(activeClusterSignals, refTimeMs);

    // 1. Core Temporal Counts
    const verified_cashouts_1h = countType(byWin['1h'], EVENT_TYPES.ATM_WITHDRAWAL_CONFIRMED);
    const verified_cashouts_6h = countType(byWin['6h'], EVENT_TYPES.ATM_WITHDRAWAL_CONFIRMED);
    const verified_cashouts_24h = countType(byWin['24h'], EVENT_TYPES.ATM_WITHDRAWAL_CONFIRMED);

    const withdrawal_attempts_1h = countType(byWin['1h'], EVENT_TYPES.ATM_WITHDRAWAL_ATTEMPT);
    const withdrawal_attempts_6h = countType(byWin['6h'], EVENT_TYPES.ATM_WITHDRAWAL_ATTEMPT);
    const withdrawal_attempts_24h = countType(byWin['24h'], EVENT_TYPES.ATM_WITHDRAWAL_ATTEMPT);

    const branch_cashouts_6h = countType(byWin['6h'], EVENT_TYPES.BRANCH_CASHOUT_CONFIRMED);
    const branch_cashouts_24h = countType(byWin['24h'], EVENT_TYPES.BRANCH_CASHOUT_CONFIRMED);

    const mule_activity_6h = countType(byWin['6h'], EVENT_TYPES.MULE_ACCOUNT_ACTIVITY);
    const mule_activity_24h = countType(byWin['24h'], EVENT_TYPES.MULE_ACCOUNT_ACTIVITY);

    const lea_confirmations_6h = countType(byWin['6h'], EVENT_TYPES.LEA_CONFIRMED_CLUSTER);
    const lea_confirmations_24h = countType(byWin['24h'], EVENT_TYPES.LEA_CONFIRMED_CLUSTER);

    // 2. Source Diversity
    const distinct_orgs_1h = getDistinctOrgs(byWin['1h']).size;
    const distinct_orgs_6h = getDistinctOrgs(byWin['6h']).size;
    const distinct_orgs_24h = getDistinctOrgs(byWin['24h']).size;

    const distinct_banks_1h = getDistinctBanks(byWin['1h']).size;
    const distinct_banks_6h = getDistinctBanks(byWin['6h']).size;
    const distinct_banks_24h = getDistinctBanks(byWin['24h']).size;

    // 3. Multi-Org Attestation
    const multi_org_attestation_1h = distinct_orgs_1h;
    const multi_org_attestation_6h = distinct_orgs_6h;
    const multi_org_attestation_24h = distinct_orgs_24h;

    const has_multi_org_attestation_1h = distinct_orgs_1h >= 2 ? 1 : 0;
    const has_multi_org_attestation_6h = distinct_orgs_6h >= 2 ? 1 : 0;
    const has_multi_org_attestation_24h = distinct_orgs_24h >= 2 ? 1 : 0;

    // 4. Confidence Features
    const conf1h = computeConfidenceStats(byWin['1h']);
    const conf6h = computeConfidenceStats(byWin['6h']);
    const conf24h = computeConfidenceStats(byWin['24h']);

    const mean_signal_confidence_1h = conf1h.mean;
    const mean_signal_confidence_6h = conf6h.mean;
    const mean_signal_confidence_24h = conf24h.mean;

    const max_signal_confidence_1h = conf1h.max;
    const max_signal_confidence_6h = conf6h.max;
    const max_signal_confidence_24h = conf24h.max;

    // 5. Recency Features (age in minutes, sentinel -1 if none)
    const latest_signal_age_minutes = computeAgeMinutes(activeClusterSignals, refTimeMs);
    const latest_verified_cashout_age_minutes = computeAgeMinutes(activeClusterSignals, refTimeMs, EVENT_TYPES.ATM_WITHDRAWAL_CONFIRMED);
    const latest_attempt_age_minutes = computeAgeMinutes(activeClusterSignals, refTimeMs, EVENT_TYPES.ATM_WITHDRAWAL_ATTEMPT);
    const latest_lea_confirmation_age_minutes = computeAgeMinutes(activeClusterSignals, refTimeMs, EVENT_TYPES.LEA_CONFIRMED_CLUSTER);

    // 6. Recurrence Features
    const cluster_signal_count_7d = byWin['7d'].length;
    const cluster_signal_count_30d = byWin['30d'].length;

    const cluster_active_days_7d = countActiveDays(byWin['7d']);
    const cluster_active_days_30d = countActiveDays(byWin['30d']);

    const cluster_recurrence_rate_7d = Number((cluster_active_days_7d / 7.0).toFixed(4));
    const cluster_recurrence_rate_30d = Number((cluster_active_days_30d / 30.0).toFixed(4));

    // 7. Metadata Quality / Correction & Revocation Features (computed from allSignalsAtRef)
    const all24h = partitionSignalsByWindow(allClusterSignalsAtRef, refTimeMs)['24h'];
    const correction_count_24h = all24h.filter(s => s.event_type === EVENT_TYPES.SIGNAL_CORRECTION || s.status === 'CORRECTED').length;
    const revocation_count_24h = all24h.filter(s => s.event_type === EVENT_TYPES.SIGNAL_REVOKED || s.status === 'REVOKED').length;
    const total_signals_24h = all24h.length;
    const active_signal_ratio_24h = total_signals_24h > 0
        ? Number((byWin['24h'].length / total_signals_24h).toFixed(4))
        : 1.0;

    // 8. Subject-Linked Features
    let subject_features_available = 0;
    let subject_signal_count_1h = 0;
    let subject_signal_count_6h = 0;
    let subject_signal_count_24h = 0;
    let subject_distinct_clusters_24h = 0;
    let subject_distinct_orgs_24h = 0;

    if (opaqueSubjectRef && subjectSignals.length > 0) {
        subject_features_available = 1;
        const subjWin = partitionSignalsByWindow(subjectSignals, refTimeMs);
        subject_signal_count_1h = subjWin['1h'].length;
        subject_signal_count_6h = subjWin['6h'].length;
        subject_signal_count_24h = subjWin['24h'].length;

        const distinctClusters = new Set();
        const distinctOrgs = new Set();
        for (const s of subjWin['24h']) {
            if (s.cluster_id !== null && s.cluster_id !== undefined) distinctClusters.add(s.cluster_id);
            if (s.organization_msp) distinctOrgs.add(s.organization_msp);
        }
        subject_distinct_clusters_24h = distinctClusters.size;
        subject_distinct_orgs_24h = distinctOrgs.size;
    }

    return {
        // Core Temporal
        verified_cashouts_1h,
        verified_cashouts_6h,
        verified_cashouts_24h,
        withdrawal_attempts_1h,
        withdrawal_attempts_6h,
        withdrawal_attempts_24h,
        branch_cashouts_6h,
        branch_cashouts_24h,
        mule_activity_6h,
        mule_activity_24h,
        lea_confirmations_6h,
        lea_confirmations_24h,

        // Source Diversity
        distinct_orgs_1h,
        distinct_orgs_6h,
        distinct_orgs_24h,
        distinct_banks_1h,
        distinct_banks_6h,
        distinct_banks_24h,

        // Multi-Org Attestation
        multi_org_attestation_1h,
        multi_org_attestation_6h,
        multi_org_attestation_24h,
        has_multi_org_attestation_1h,
        has_multi_org_attestation_6h,
        has_multi_org_attestation_24h,

        // Confidence
        mean_signal_confidence_1h,
        mean_signal_confidence_6h,
        mean_signal_confidence_24h,
        max_signal_confidence_1h,
        max_signal_confidence_6h,
        max_signal_confidence_24h,

        // Recency
        latest_signal_age_minutes,
        latest_verified_cashout_age_minutes,
        latest_attempt_age_minutes,
        latest_lea_confirmation_age_minutes,

        // Recurrence
        cluster_signal_count_7d,
        cluster_signal_count_30d,
        cluster_active_days_7d,
        cluster_active_days_30d,
        cluster_recurrence_rate_7d,
        cluster_recurrence_rate_30d,

        // Quality & Governance
        correction_count_24h,
        revocation_count_24h,
        active_signal_ratio_24h,

        // Subject-Linked
        subject_features_available,
        subject_signal_count_1h,
        subject_signal_count_6h,
        subject_signal_count_24h,
        subject_distinct_clusters_24h,
        subject_distinct_orgs_24h
    };
}

module.exports = {
    buildClusterFeatureVector
};
