'use strict';

const crypto = require('crypto');

const SCHEMA_VERSION = 'prediction-audit-v1';

/**
 * Normalizes an ISO-8601 date string to UTC Z format.
 * @param {string|Date} dateInput
 * @returns {string} e.g. "2026-09-14T06:30:00.000Z"
 */
function normalizeTimestamp(dateInput) {
    if (!dateInput) return null;
    const d = new Date(dateInput);
    if (isNaN(d.getTime())) {
        throw new Error(`Invalid timestamp: ${dateInput}`);
    }
    return d.toISOString();
}

/**
 * Normalizes float precision to 6 decimal places to avoid IEEE 754 platform variations.
 * @param {number} val
 * @returns {number}
 */
function normalizeFloat(val) {
    if (val === null || val === undefined || isNaN(val)) return 0.0;
    return Math.round(Number(val) * 1000000) / 1000000;
}

/**
 * Computes privacy-safe complaint reference hash without exposing raw complaint number or PII.
 * @param {string|number} complaintIdentifier
 * @returns {string} 64-char lowercase hex SHA-256
 */
function computeComplaintReference(complaintIdentifier) {
    if (!complaintIdentifier) {
        throw new Error('complaintIdentifier is required for privacy-safe reference.');
    }
    return crypto.createHash('sha256')
        .update(`COMPLAINT_REF:${String(complaintIdentifier).trim()}`, 'utf8')
        .digest('hex')
        .toLowerCase();
}

/**
 * Recursively sorts object keys lexicographically.
 * @param {any} obj
 * @returns {any}
 */
function sortKeysRecursively(obj) {
    if (obj === null || typeof obj !== 'object') {
        return obj;
    }
    if (Array.isArray(obj)) {
        return obj.map(sortKeysRecursively);
    }
    const sorted = {};
    const keys = Object.keys(obj).sort();
    for (const key of keys) {
        sorted[key] = sortKeysRecursively(obj[key]);
    }
    return sorted;
}

/**
 * Creates a deterministic canonical audit payload from raw prediction data.
 * @param {object} predictionData
 * @returns {object} Canonical payload with sorted keys and normalized types
 */
function canonicalizePredictionAuditPayload(predictionData) {
    if (!predictionData || typeof predictionData !== 'object') {
        throw new Error('predictionData must be an object.');
    }

    const predictionId = Number(predictionData.prediction_id);
    if (isNaN(predictionId)) {
        throw new Error('predictionData.prediction_id must be a valid number.');
    }

    // Complaint reference hash
    let complaintRef = predictionData.complaint_reference_hash;
    if (!complaintRef) {
        const compIdentifier = predictionData.complaint_number || predictionData.complaint_id;
        if (!compIdentifier) {
            throw new Error('complaint_reference_hash or complaint_number/id is required.');
        }
        complaintRef = computeComplaintReference(compIdentifier);
    }
    complaintRef = String(complaintRef).trim().toLowerCase();

    // Top-3 Locations strictly ordered by rank ascending (1, 2, 3)
    const rawLocations = predictionData.top_locations || predictionData.ordered_top3 || [];
    if (!Array.isArray(rawLocations) || rawLocations.length !== 3) {
        throw new Error(`top_locations must contain exactly 3 locations, found ${rawLocations.length}.`);
    }

    const sortedLocations = [...rawLocations].sort((a, b) => Number(a.rank) - Number(b.rank));
    const ranks = sortedLocations.map(l => Number(l.rank));
    if (ranks[0] !== 1 || ranks[1] !== 2 || ranks[2] !== 3) {
        throw new Error(`top_locations ranks must be strictly [1, 2, 3], found [${ranks.join(', ')}].`);
    }

    const orderedTop3 = sortedLocations.map(loc => ({
        cluster_id: Number(loc.cluster_id),
        probability: normalizeFloat(loc.ml_probability !== undefined ? loc.ml_probability : loc.probability),
        rank: Number(loc.rank)
    }));

    // Time window
    const rawTime = predictionData.time_prediction || predictionData.time_window || {};
    const timeWindow = {
        window_end: normalizeTimestamp(rawTime.window_end || predictionData.predicted_window_end),
        window_label: String(rawTime.operational_window || predictionData.window_label || 'Next 2–4 Hours'),
        window_start: normalizeTimestamp(rawTime.window_start || predictionData.predicted_window_start)
    };

    const payload = {
        complaint_reference_hash: complaintRef,
        location_model_version: String(predictionData.model_version || predictionData.location_model_version || 'cashout-location-xgb-v7-compat'),
        ordered_top3: orderedTop3,
        prediction_created_at: normalizeTimestamp(predictionData.created_at || predictionData.prediction_created_at || new Date()),
        prediction_id: predictionId,
        prediction_mode: String(predictionData.prediction_mode || 'trained_ml'),
        time_model_version: predictionData.time_model_version || (rawTime.model_version ? String(rawTime.model_version) : null),
        time_window: timeWindow
    };

    return sortKeysRecursively(payload);
}

/**
 * Computes canonical SHA-256 hash of the prediction audit payload.
 * @param {object} canonicalPayload
 * @returns {string} 64-char lowercase hex
 */
function computePredictionHash(canonicalPayload) {
    const jsonStr = JSON.stringify(canonicalPayload);
    return crypto.createHash('sha256').update(jsonStr, 'utf8').digest('hex').toLowerCase();
}

/**
 * Builds the complete Fabric anchor payload ready for AnchorPrediction transaction.
 * @param {object} predictionData
 * @returns {{ anchorPayload: object, canonicalPayload: object, predictionHash: string }}
 */
function buildAnchorPayload(predictionData) {
    const canonicalPayload = canonicalizePredictionAuditPayload(predictionData);
    const predictionHash = computePredictionHash(canonicalPayload);

    const anchorPayload = {
        prediction_id: canonicalPayload.prediction_id,
        complaint_reference_hash: canonicalPayload.complaint_reference_hash,
        prediction_hash: predictionHash,
        prediction_mode: canonicalPayload.prediction_mode,
        location_model_version: canonicalPayload.location_model_version,
        time_model_version: canonicalPayload.time_model_version,
        top3_cluster_ids: canonicalPayload.ordered_top3.map(l => l.cluster_id),
        prediction_created_at: canonicalPayload.prediction_created_at,
        schema_version: SCHEMA_VERSION
    };

    return {
        anchorPayload,
        canonicalPayload,
        predictionHash
    };
}

module.exports = {
    SCHEMA_VERSION,
    normalizeTimestamp,
    normalizeFloat,
    computeComplaintReference,
    sortKeysRecursively,
    canonicalizePredictionAuditPayload,
    computePredictionHash,
    buildAnchorPayload
};
