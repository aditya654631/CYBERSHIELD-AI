'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert');
const {
    canonicalizePredictionAuditPayload,
    computePredictionHash,
    buildAnchorPayload,
    computeComplaintReference,
    normalizeTimestamp,
    normalizeFloat,
    SCHEMA_VERSION
} = require('../hasher');

describe('Prediction Audit Hasher & Canonicalization', () => {

    const samplePrediction = {
        prediction_id: 107,
        complaint_number: 'CMP-NEW-000063',
        prediction_mode: 'trained_ml',
        model_version: 'cashout-location-xgb-v7-compat',
        time_model_version: 'cashout-time-xgb-v3',
        created_at: '2026-09-14T06:00:00Z',
        predicted_window_start: '2026-09-14T06:15:00Z',
        predicted_window_end: '2026-09-14T06:45:00Z',
        window_label: 'Next 2–4 Hours (operational estimate window)',
        top_locations: [
            { rank: 1, cluster_id: 12, ml_probability: 0.845123, location_name: 'Connaught Place' },
            { rank: 2, cluster_id: 45, ml_probability: 0.654321, location_name: 'Karol Bagh' },
            { rank: 3, cluster_id: 9, ml_probability: 0.432109, location_name: 'Lajpat Nagar' }
        ]
    };

    test('1. Deterministic Canonicalization: repeated calls generate identical output', () => {
        const canonical1 = canonicalizePredictionAuditPayload(samplePrediction);
        const canonical2 = canonicalizePredictionAuditPayload(samplePrediction);
        assert.deepStrictEqual(canonical1, canonical2);
        assert.strictEqual(JSON.stringify(canonical1), JSON.stringify(canonical2));
    });

    test('2. Deterministic Hash: repeated calls generate identical SHA-256 hex string', () => {
        const canonical = canonicalizePredictionAuditPayload(samplePrediction);
        const hash1 = computePredictionHash(canonical);
        const hash2 = computePredictionHash(canonical);
        assert.strictEqual(hash1, hash2);
        assert.strictEqual(hash1.length, 64);
        assert.match(hash1, /^[a-f0-9]{64}$/);
    });

    test('3. Privacy-Safe Complaint Reference: does not leak plain complaint number', () => {
        const ref = computeComplaintReference('CMP-NEW-000063');
        assert.strictEqual(ref.length, 64);
        assert.doesNotMatch(ref, /CMP-NEW-000063/);
        assert.match(ref, /^[a-f0-9]{64}$/);
    });

    test('4. Order Sensitivity: Swapping Top-3 order produces a DIFFERENT hash', () => {
        const canonicalOriginal = canonicalizePredictionAuditPayload(samplePrediction);
        const originalHash = computePredictionHash(canonicalOriginal);

        // Perturb ranks: cluster 45 is rank 1, cluster 12 is rank 2
        const swappedPrediction = {
            ...samplePrediction,
            top_locations: [
                { rank: 1, cluster_id: 45, ml_probability: 0.845123, location_name: 'Karol Bagh' },
                { rank: 2, cluster_id: 12, ml_probability: 0.654321, location_name: 'Connaught Place' },
                { rank: 3, cluster_id: 9, ml_probability: 0.432109, location_name: 'Lajpat Nagar' }
            ]
        };

        const canonicalSwapped = canonicalizePredictionAuditPayload(swappedPrediction);
        const swappedHash = computePredictionHash(canonicalSwapped);

        assert.notStrictEqual(originalHash, swappedHash, 'Swapping cluster rank order must alter the hash!');
    });

    test('5. Single Field Tamper Sensitivity: changing probability alters hash', () => {
        const canonicalOriginal = canonicalizePredictionAuditPayload(samplePrediction);
        const originalHash = computePredictionHash(canonicalOriginal);

        const tamperedPrediction = JSON.parse(JSON.stringify(samplePrediction));
        tamperedPrediction.top_locations[0].ml_probability = 0.845124; // 1 micro difference

        const canonicalTampered = canonicalizePredictionAuditPayload(tamperedPrediction);
        const tamperedHash = computePredictionHash(canonicalTampered);

        assert.notStrictEqual(originalHash, tamperedHash, 'Changing probability must alter the hash!');
    });

    test('6. Single Field Tamper Sensitivity: changing model version alters hash', () => {
        const canonicalOriginal = canonicalizePredictionAuditPayload(samplePrediction);
        const originalHash = computePredictionHash(canonicalOriginal);

        const tamperedPrediction = {
            ...samplePrediction,
            model_version: 'cashout-location-xgb-v4'
        };

        const canonicalTampered = canonicalizePredictionAuditPayload(tamperedPrediction);
        const tamperedHash = computePredictionHash(canonicalTampered);

        assert.notStrictEqual(originalHash, tamperedHash, 'Changing model version must alter the hash!');
    });

    test('7. Anchor Payload Builder includes required ledger fields', () => {
        const { anchorPayload, canonicalPayload, predictionHash } = buildAnchorPayload(samplePrediction);
        assert.strictEqual(anchorPayload.prediction_id, 107);
        assert.strictEqual(anchorPayload.prediction_hash, predictionHash);
        assert.strictEqual(anchorPayload.schema_version, 'prediction-audit-v1');
        assert.deepStrictEqual(anchorPayload.top3_cluster_ids, [12, 45, 9]);
        assert.strictEqual(anchorPayload.location_model_version, 'cashout-location-xgb-v7-compat');
        assert.strictEqual(anchorPayload.time_model_version, 'cashout-time-xgb-v3');
    });

    test('8. Rejects invalid top_locations count', () => {
        const invalidPred = {
            ...samplePrediction,
            top_locations: [
                { rank: 1, cluster_id: 12, ml_probability: 0.845123 }
            ]
        };
        assert.throws(() => {
            canonicalizePredictionAuditPayload(invalidPred);
        }, /must contain exactly 3 locations/);
    });

    test('9. Rejects invalid rank ordering (e.g. ranks 1, 1, 3)', () => {
        const invalidPred = {
            ...samplePrediction,
            top_locations: [
                { rank: 1, cluster_id: 12, ml_probability: 0.845123 },
                { rank: 1, cluster_id: 45, ml_probability: 0.654321 },
                { rank: 3, cluster_id: 9, ml_probability: 0.432109 }
            ]
        };
        assert.throws(() => {
            canonicalizePredictionAuditPayload(invalidPred);
        }, /ranks must be strictly/);
    });
});
