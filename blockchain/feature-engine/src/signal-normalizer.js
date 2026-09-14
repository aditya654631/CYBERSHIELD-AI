'use strict';

const { EVENT_TYPES, BANK_MSPS, AUTHORITY_MSPS } = require('./constants');

/**
 * Resolves the historical state of a signal as it existed at referenceTimestamp.
 * 
 * Rules:
 * 1. Anti-leakage: event_timestamp <= refTimeMs AND (if submitted_at present) submitted_at <= refTimeMs.
 *    Signals created after referenceTimestamp are completely excluded from that point in time.
 * 2. State at reference time:
 *    - If a signal was revoked at or before referenceTimestamp, its status at that time was REVOKED.
 *    - If a signal was revoked AFTER referenceTimestamp, at referenceTimestamp it had not yet been revoked,
 *      so it was still ACTIVE.
 *    - If a signal was corrected AFTER referenceTimestamp, at referenceTimestamp it had not yet been corrected.
 *    - If a signal was corrected at or before referenceTimestamp, targetSignal is CORRECTED and the
 *      correction record (SIGNAL_CORRECTION) is the active superseding record.
 * 
 * @param {Array} rawSignals - Raw signal objects from the ledger
 * @param {number} refTimeMs - Epoch milliseconds for reference_timestamp
 * @param {Map<string, Array>} [historyMap] - Optional map of eventId -> array of history records
 * @returns {object} { activeSignals, allSignalsAtRef, futureExcludedCount, revokedExcludedCount }
 */
function normalizeSignalsAtReference(rawSignals, refTimeMs, historyMap = new Map()) {
    if (!Array.isArray(rawSignals)) {
        return {
            activeSignals: [],
            allSignalsAtRef: [],
            futureExcludedCount: 0,
            revokedExcludedCount: 0
        };
    }

    let futureExcludedCount = 0;
    let revokedExcludedCount = 0;
    const allSignalsAtRef = [];

    // Map by event_id for quick lookups
    const signalById = new Map();
    for (const s of rawSignals) {
        if (s && s.event_id) {
            signalById.set(s.event_id, s);
        }
    }

    for (const s of rawSignals) {
        if (!s || !s.event_id) continue;

        const eventTimeMs = Date.parse(s.event_timestamp);
        const submittedAtMs = s.submitted_at ? Date.parse(s.submitted_at) : eventTimeMs;

        // Anti-leakage rule: Cannot use future events
        if (eventTimeMs > refTimeMs || submittedAtMs > refTimeMs) {
            futureExcludedCount++;
            continue;
        }

        // Determine status as of refTimeMs
        let effectiveStatus = s.status || 'ACTIVE';
        let effectiveConfidence = s.confidence !== undefined ? Number(s.confidence) : 1.0;
        let effectiveType = s.event_type;

        // Check if history is available for granular point-in-time reconstruction
        const history = historyMap.get(s.event_id);
        if (Array.isArray(history) && history.length > 0) {
            // Traverse history entries up to refTimeMs in chronological order
            let latestValueAtRef = null;
            for (const h of history) {
                const hTimeMs = h.timestamp ? Date.parse(h.timestamp) : 0;
                if (hTimeMs <= refTimeMs) {
                    if (h.value && typeof h.value === 'object') {
                        latestValueAtRef = h.value;
                    }
                }
            }
            if (latestValueAtRef) {
                effectiveStatus = latestValueAtRef.status || effectiveStatus;
                effectiveConfidence = latestValueAtRef.confidence !== undefined ? Number(latestValueAtRef.confidence) : effectiveConfidence;
                effectiveType = latestValueAtRef.event_type || effectiveType;
            }
        } else {
            // Deduce from current state and referenced events
            // If current status is REVOKED:
            if (s.status === 'REVOKED') {
                if (s.revoked_by_event_id && signalById.has(s.revoked_by_event_id)) {
                    const revEvent = signalById.get(s.revoked_by_event_id);
                    const revTimeMs = revEvent.submitted_at ? Date.parse(revEvent.submitted_at) : Date.parse(revEvent.event_timestamp);
                    if (revTimeMs <= refTimeMs) {
                        // Revocation already happened at or before refTime
                        effectiveStatus = 'REVOKED';
                    } else {
                        // Revocation happened in the future relative to refTime! At refTime it was ACTIVE
                        effectiveStatus = 'ACTIVE';
                    }
                } else if (s.event_type === 'SIGNAL_REVOKED') {
                    effectiveStatus = 'REVOKED';
                }
            }

            // If current status is CORRECTED:
            if (s.status === 'CORRECTED') {
                if (s.corrected_by_event_id && signalById.has(s.corrected_by_event_id)) {
                    const corrEvent = signalById.get(s.corrected_by_event_id);
                    const corrTimeMs = corrEvent.submitted_at ? Date.parse(corrEvent.submitted_at) : Date.parse(corrEvent.event_timestamp);
                    if (corrTimeMs <= refTimeMs) {
                        effectiveStatus = 'CORRECTED';
                    } else {
                        // Correction happened in the future relative to refTime!
                        effectiveStatus = 'ACTIVE';
                    }
                }
            }
        }

        const normalized = {
            event_id: s.event_id,
            event_type: effectiveType,
            organization_msp: s.organization_msp || s.created_by_msp || 'UNKNOWN',
            cluster_id: s.cluster_id !== undefined && s.cluster_id !== null ? Number(s.cluster_id) : null,
            district: s.district || null,
            event_timestamp: s.event_timestamp,
            eventTimeMs,
            submitted_at: s.submitted_at,
            confidence: isNaN(effectiveConfidence) ? 0.0 : effectiveConfidence,
            status: effectiveStatus,
            source_reference_hash: s.source_reference_hash || null,
            opaque_subject_ref: s.opaque_subject_ref || null
        };

        allSignalsAtRef.push(normalized);
    }

    // Active signals for intelligence computation (exclude REVOKED and superseded CORRECTED)
    const activeSignals = [];
    for (const sig of allSignalsAtRef) {
        if (sig.status === 'REVOKED' || sig.event_type === 'SIGNAL_REVOKED') {
            revokedExcludedCount++;
            continue;
        }
        if (sig.status === 'CORRECTED') {
            // Exclude superseded base signals if already replaced by an active correction record
            continue;
        }
        activeSignals.push(sig);
    }

    return {
        activeSignals,
        allSignalsAtRef,
        futureExcludedCount,
        revokedExcludedCount
    };
}

module.exports = {
    normalizeSignalsAtReference
};
