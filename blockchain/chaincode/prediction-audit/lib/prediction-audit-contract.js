'use strict';

const { Contract } = require('fabric-contract-api');

const SCHEMA_VERSION = 'prediction-audit-v1';

const AUTHORIZED_ANCHOR_MSPS = ['I4CMSP'];
const KNOWN_CONSORTIUM_MSPS = ['BankAMSP', 'BankBMSP', 'BankCMSP', 'I4CMSP', 'LEAMSP'];

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
    'raw_complaint',
    'description'
];

class PredictionAuditContract extends Contract {

    constructor() {
        super('PredictionAuditContract');
    }

    /**
     * Initialize the ledger for prediction audit
     */
    async InitLedger(ctx) {
        console.info('=== Initializing CyberShield Prediction Audit Ledger ===');
        const initMetadata = {
            contract_name: 'prediction-audit',
            schema_version: SCHEMA_VERSION,
            initialized_at: this._getTxTimestampISO(ctx),
            network: 'cyber-intelligence',
            policy: 'Tamper-Evident Prediction Audit Anchoring'
        };
        await ctx.stub.putState('AUDIT_CONTRACT_METADATA', Buffer.from(JSON.stringify(initMetadata)));
        return JSON.stringify(initMetadata);
    }

    /**
     * Anchors a prediction hash to the immutable ledger.
     * 
     * @param {Context} ctx
     * @param {string} anchorPayloadJson
     * @returns {string} JSON representation of the anchored record
     */
    async AnchorPrediction(ctx, anchorPayloadJson) {
        const clientMsp = this._getClientMsp(ctx);
        if (!AUTHORIZED_ANCHOR_MSPS.includes(clientMsp)) {
            throw new Error(`Permission Denied: Organization '${clientMsp}' is not authorized to create prediction audit anchors. Only ${AUTHORIZED_ANCHOR_MSPS.join(', ')} may anchor predictions.`);
        }

        const payload = this._parseJson(anchorPayloadJson, 'anchorPayloadJson');
        this._validatePIISafety(payload);
        this._validateAnchorFields(payload);

        const predictionIdStr = String(payload.prediction_id);
        const anchorKey = this._getAnchorKey(predictionIdStr);

        const existingBytes = await ctx.stub.getState(anchorKey);
        if (existingBytes && existingBytes.length > 0) {
            const existing = JSON.parse(existingBytes.toString());
            // Idempotency check: Same prediction_id + same prediction_hash => IDEMPOTENT return
            if (existing.prediction_hash === payload.prediction_hash) {
                return JSON.stringify({
                    message: 'Idempotent replay: prediction already anchored with identical hash.',
                    anchor: existing,
                    idempotent: true
                });
            } else {
                // Same prediction_id + DIFFERENT hash => TAMPER CONFLICT REJECT
                throw new Error(`Tamper Conflict: Prediction '${predictionIdStr}' is already anchored with hash '${existing.prediction_hash}'. Cannot overwrite with different hash '${payload.prediction_hash}'.`);
            }
        }

        const txId = ctx.stub.getTxID();
        const anchoredAt = this._getTxTimestampISO(ctx);

        const anchorRecord = {
            anchor_id: `ANCHOR_${predictionIdStr}`,
            prediction_id: Number(payload.prediction_id),
            complaint_reference_hash: payload.complaint_reference_hash,
            prediction_hash: payload.prediction_hash.toLowerCase(),
            prediction_mode: payload.prediction_mode || 'trained_ml',
            location_model_version: payload.location_model_version,
            time_model_version: payload.time_model_version || null,
            top3_cluster_ids: payload.top3_cluster_ids || [],
            prediction_created_at: payload.prediction_created_at || anchoredAt,
            anchored_at: anchoredAt,
            anchored_by_msp: clientMsp,
            schema_version: SCHEMA_VERSION,
            fabric_tx_id: txId,
            status: 'ANCHORED'
        };

        // Write primary anchor state
        await ctx.stub.putState(anchorKey, Buffer.from(JSON.stringify(anchorRecord)));

        // Write composite index for lookup by hash
        const hashCompKey = ctx.stub.createCompositeKey('hash~prediction', [anchorRecord.prediction_hash, predictionIdStr]);
        await ctx.stub.putState(hashCompKey, Buffer.from('\u0000'));

        // Emit Fabric Event
        const eventPayload = {
            prediction_id: anchorRecord.prediction_id,
            prediction_hash: anchorRecord.prediction_hash,
            schema_version: SCHEMA_VERSION,
            anchored_by_msp: clientMsp,
            tx_id: txId
        };
        ctx.stub.setEvent('PredictionAnchored', Buffer.from(JSON.stringify(eventPayload)));

        return JSON.stringify(anchorRecord);
    }

    /**
     * Retrieves an anchor by prediction ID.
     */
    async GetPredictionAnchor(ctx, prediction_id) {
        if (!prediction_id) {
            throw new Error('prediction_id is required');
        }
        const clientMsp = this._getClientMsp(ctx);
        if (!KNOWN_CONSORTIUM_MSPS.includes(clientMsp)) {
            throw new Error(`Unauthorized MSP: '${clientMsp}' is not a recognized consortium member.`);
        }

        const anchorKey = this._getAnchorKey(String(prediction_id));
        const bytes = await ctx.stub.getState(anchorKey);
        if (!bytes || bytes.length === 0) {
            throw new Error(`Prediction anchor for ID '${prediction_id}' does not exist on the ledger.`);
        }
        return bytes.toString();
    }

    /**
     * Checks if an anchor exists for a prediction ID.
     */
    async PredictionAnchorExists(ctx, prediction_id) {
        if (!prediction_id) {
            return JSON.stringify({ exists: false });
        }
        const anchorKey = this._getAnchorKey(String(prediction_id));
        const bytes = await ctx.stub.getState(anchorKey);
        const exists = !!(bytes && bytes.length > 0);
        return JSON.stringify({ prediction_id: Number(prediction_id), exists });
    }

    /**
     * Verifies if a given prediction_id and candidate prediction_hash match the ledger anchor.
     * 
     * @param {Context} ctx
     * @param {string|number} prediction_id
     * @param {string} candidate_prediction_hash
     * @returns {string} JSON verification outcome
     */
    async VerifyPredictionHash(ctx, prediction_id, candidate_prediction_hash) {
        if (!prediction_id || !candidate_prediction_hash) {
            throw new Error('Both prediction_id and candidate_prediction_hash are required for verification.');
        }
        const clientMsp = this._getClientMsp(ctx);
        if (!KNOWN_CONSORTIUM_MSPS.includes(clientMsp)) {
            throw new Error(`Unauthorized MSP: '${clientMsp}' is not a recognized consortium member.`);
        }

        const anchorKey = this._getAnchorKey(String(prediction_id));
        const bytes = await ctx.stub.getState(anchorKey);
        if (!bytes || bytes.length === 0) {
            return JSON.stringify({
                prediction_id: Number(prediction_id),
                verified: false,
                status: 'ANCHOR_NOT_FOUND',
                message: `No anchor found for prediction ID '${prediction_id}' on the ledger.`
            });
        }

        const anchor = JSON.parse(bytes.toString());
        const normalizedCandidate = String(candidate_prediction_hash).trim().toLowerCase();
        const match = anchor.prediction_hash === normalizedCandidate;

        return JSON.stringify({
            prediction_id: Number(prediction_id),
            verified: match,
            status: match ? 'VERIFIED' : 'HASH_MISMATCH',
            ledger_hash: anchor.prediction_hash,
            candidate_hash: normalizedCandidate,
            anchored_at: anchor.anchored_at,
            fabric_tx_id: anchor.fabric_tx_id,
            anchored_by_msp: anchor.anchored_by_msp
        });
    }

    /**
     * Retrieves full immutable transaction history for an anchor.
     */
    async GetAnchorHistory(ctx, prediction_id) {
        if (!prediction_id) {
            throw new Error('prediction_id is required');
        }
        const clientMsp = this._getClientMsp(ctx);
        if (!KNOWN_CONSORTIUM_MSPS.includes(clientMsp)) {
            throw new Error(`Unauthorized MSP: '${clientMsp}' is not a recognized consortium member.`);
        }

        const anchorKey = this._getAnchorKey(String(prediction_id));
        const iterator = await ctx.stub.getHistoryForKey(anchorKey);
        const history = [];

        let res = await iterator.next();
        while (!res.done) {
            if (res.value) {
                let tsIso = null;
                if (res.value.timestamp) {
                    try {
                        const secRaw = res.value.timestamp.seconds;
                        const sec = typeof secRaw === 'object' && secRaw !== null ? Number(secRaw.low || secRaw.high || 0) : Number(secRaw);
                        const nanos = Number(res.value.timestamp.nanos || 0);
                        if (!isNaN(sec) && sec > 0) {
                            tsIso = new Date((sec * 1000) + Math.floor(nanos / 1000000)).toISOString();
                        }
                    } catch (e) {
                        tsIso = null;
                    }
                }

                const item = {
                    tx_id: res.value.txId,
                    timestamp: tsIso,
                    is_delete: res.value.isDelete,
                    value: null
                };
                if (!res.value.isDelete && res.value.value && res.value.value.length > 0) {
                    try {
                        item.value = JSON.parse(res.value.value.toString());
                    } catch (e) {
                        item.value = res.value.value.toString();
                    }
                }
                history.push(item);
            }
            res = await iterator.next();
        }
        await iterator.close();

        return JSON.stringify(history);
    }

    // =========================================================================
    // INTERNAL HELPERS & VALIDATION
    // =========================================================================

    _getAnchorKey(predictionId) {
        return `PRED_ANCHOR_${predictionId}`;
    }

    _getClientMsp(ctx) {
        try {
            return ctx.clientIdentity.getMSPID();
        } catch (e) {
            throw new Error(`Failed to retrieve client MSP ID: ${e.message}`);
        }
    }

    _getTxTimestampISO(ctx) {
        try {
            const timestamp = ctx.stub.getTxTimestamp();
            if (timestamp && timestamp.seconds) {
                const ms = (Number(timestamp.seconds.low || timestamp.seconds) * 1000) +
                           Math.floor((Number(timestamp.nanos || 0)) / 1000000);
                return new Date(ms).toISOString();
            }
        } catch (e) {
            // fallback
        }
        return new Date(0).toISOString();
    }

    _parseJson(input, paramName) {
        if (typeof input === 'object' && input !== null) {
            return input;
        }
        if (typeof input === 'string') {
            try {
                return JSON.parse(input);
            } catch (err) {
                throw new Error(`Parameter '${paramName}' must be valid JSON: ${err.message}`);
            }
        }
        throw new Error(`Parameter '${paramName}' must be a JSON string or object.`);
    }

    _validatePIISafety(payload) {
        if (!payload || typeof payload !== 'object') return;
        const keys = Object.keys(payload);
        for (const key of keys) {
            const normalized = key.toLowerCase().replace(/[^a-z0-9_]/g, '');
            for (const prohibited of PROHIBITED_PII_FIELDS) {
                if (normalized === prohibited || normalized.includes(prohibited)) {
                    throw new Error(`PII Security Violation: Prohibited field '${key}' is rejected by prediction-audit chaincode schema enforcement.`);
                }
            }
            if (typeof payload[key] === 'object' && payload[key] !== null) {
                this._validatePIISafety(payload[key]);
            }
        }
    }

    _validateAnchorFields(payload) {
        if (payload.prediction_id === undefined || payload.prediction_id === null || payload.prediction_id === '') {
            throw new Error('prediction_id is required, numeric identifier.');
        }
        if (isNaN(Number(payload.prediction_id))) {
            throw new Error(`prediction_id '${payload.prediction_id}' must be a valid number.`);
        }

        if (!payload.prediction_hash || typeof payload.prediction_hash !== 'string') {
            throw new Error('prediction_hash is required, 64-character hex string.');
        }
        const cleanHash = payload.prediction_hash.trim().toLowerCase();
        if (!/^[a-f0-9]{64}$/.test(cleanHash)) {
            throw new Error(`prediction_hash '${payload.prediction_hash}' must be a valid 64-character lowercase hexadecimal SHA-256 string.`);
        }

        if (!payload.complaint_reference_hash || typeof payload.complaint_reference_hash !== 'string') {
            throw new Error('complaint_reference_hash is required, 64-character hex string.');
        }
        const cleanRef = payload.complaint_reference_hash.trim().toLowerCase();
        if (!/^[a-f0-9]{64}$/.test(cleanRef)) {
            throw new Error(`complaint_reference_hash '${payload.complaint_reference_hash}' must be a valid 64-character hexadecimal string.`);
        }

        if (!payload.location_model_version || typeof payload.location_model_version !== 'string') {
            throw new Error('location_model_version is required.');
        }

        if (!Array.isArray(payload.top3_cluster_ids) || payload.top3_cluster_ids.length !== 3) {
            throw new Error('top3_cluster_ids must be an array of exactly 3 cluster IDs.');
        }
    }
}

module.exports = PredictionAuditContract;
