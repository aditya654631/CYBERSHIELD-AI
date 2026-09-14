'use strict';

const { PROHIBITED_PII_FIELDS } = require('./constants');

class FeatureEngineError extends Error {
    constructor(message, code = 'FEATURE_ENGINE_ERROR', statusCode = 500, details = null) {
        super(message);
        this.name = this.constructor.name;
        this.code = code;
        this.statusCode = statusCode;
        this.details = details;
    }
}

class InputValidationError extends FeatureEngineError {
    constructor(message, details = null) {
        super(message, 'INPUT_VALIDATION_ERROR', 400, details);
    }
}

class FabricUnavailableError extends FeatureEngineError {
    constructor(message, details = null) {
        super(message, 'FABRIC_UNAVAILABLE', 503, details);
    }
}

/**
 * Validates input contract for feature generation.
 */
function validateFeatureRequest({ clusterId, referenceTimestamp, opaqueSubjectRef }) {
    if (clusterId === undefined || clusterId === null || clusterId === '') {
        throw new InputValidationError("clusterId is required (e.g. integer or string identifier).");
    }

    const numCluster = Number(clusterId);
    if (isNaN(numCluster)) {
        throw new InputValidationError(`clusterId must be a valid numeric identifier, received: '${clusterId}'`);
    }

    if (!referenceTimestamp) {
        throw new InputValidationError("referenceTimestamp is required for leakage-safe feature computation.");
    }

    const refTimeMs = Date.parse(referenceTimestamp);
    if (isNaN(refTimeMs)) {
        throw new InputValidationError(`referenceTimestamp must be a valid ISO-8601 string, received: '${referenceTimestamp}'`);
    }

    if (opaqueSubjectRef !== undefined && opaqueSubjectRef !== null) {
        if (typeof opaqueSubjectRef !== 'string' || opaqueSubjectRef.trim().length === 0) {
            throw new InputValidationError("opaqueSubjectRef must be a non-empty string if provided.");
        }
        // Validate against PII fields
        for (const prohibited of PROHIBITED_PII_FIELDS) {
            const lower = opaqueSubjectRef.toLowerCase();
            if (lower.includes(prohibited)) {
                throw new InputValidationError(`PII Defense Violation: opaqueSubjectRef contains prohibited field indicator '${prohibited}'`);
            }
        }
    }

    return {
        clusterId: numCluster,
        referenceTimestamp: new Date(refTimeMs).toISOString(),
        refTimeMs,
        opaqueSubjectRef: opaqueSubjectRef ? opaqueSubjectRef.trim() : null
    };
}

module.exports = {
    FeatureEngineError,
    InputValidationError,
    FabricUnavailableError,
    validateFeatureRequest
};
