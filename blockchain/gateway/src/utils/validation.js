'use strict';

const { ValidationError } = require('./errors');

const PROHIBITED_PII_FIELDS = [
    'victim_name',
    'victim_phone',
    'phone',
    'phone_number',
    'mobile',
    'account_number',
    'raw_account_number',
    'bank_account',
    'upi_id',
    'vpa',
    'aadhaar',
    'pan',
    'email',
    'password',
    'jwt',
    'token',
    'raw_transaction_history',
    'complaint_text',
    'raw_complaint'
];

/**
 * Validates payload to ensure no sensitive PII fields are included.
 * @param {object} payload
 */
function validatePIISafety(payload) {
    if (!payload || typeof payload !== 'object') {
        return;
    }

    for (const key of Object.keys(payload)) {
        const normalized = key.toLowerCase().replace(/[^a-z0-9_]/g, '');
        for (const prohibited of PROHIBITED_PII_FIELDS) {
            if (normalized === prohibited || normalized.includes(prohibited)) {
                throw new ValidationError(`PII Defense Violation: Prohibited field '${key}' cannot be submitted to the consortium ledger.`);
            }
        }
        if (typeof payload[key] === 'object' && payload[key] !== null) {
            validatePIISafety(payload[key]);
        }
    }
}

/**
 * Validates signal submission payload before Gateway dispatch.
 * @param {object} signal
 */
function validateSignalPayload(signal) {
    if (!signal || typeof signal !== 'object') {
        throw new ValidationError('Signal payload must be a non-null object.');
    }

    validatePIISafety(signal);

    if (!signal.event_id || typeof signal.event_id !== 'string' || signal.event_id.trim().length === 0) {
        throw new ValidationError('event_id is required and must be a non-empty string.');
    }

    if (!signal.event_type || typeof signal.event_type !== 'string') {
        throw new ValidationError('event_type is required.');
    }

    if (!signal.opaque_subject_ref || typeof signal.opaque_subject_ref !== 'string') {
        throw new ValidationError('opaque_subject_ref is required (tokenized/hashed subject identifier).');
    }

    if (signal.confidence !== undefined && signal.confidence !== null) {
        const conf = Number(signal.confidence);
        if (isNaN(conf) || conf < 0.0 || conf > 1.0) {
            throw new ValidationError(`confidence must be between 0.0 and 1.0. Received: ${signal.confidence}`);
        }
    }

    if (signal.source_reference_hash) {
        if (!/^[a-fA-F0-9]{64}$/.test(signal.source_reference_hash)) {
            throw new ValidationError('source_reference_hash must be a 64-character SHA-256 hex string.');
        }
    }
}

module.exports = {
    PROHIBITED_PII_FIELDS,
    validatePIISafety,
    validateSignalPayload
};
