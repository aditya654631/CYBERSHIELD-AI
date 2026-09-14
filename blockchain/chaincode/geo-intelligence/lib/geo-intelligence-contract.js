'use strict';

const { Contract } = require('fabric-contract-api');

const SCHEMA_VERSION = 'geo-intelligence-v1';

const ALLOWED_EVENT_TYPES = [
    'ATM_WITHDRAWAL_CONFIRMED',
    'ATM_WITHDRAWAL_ATTEMPT',
    'BRANCH_CASHOUT_CONFIRMED',
    'MULE_ACCOUNT_ACTIVITY',
    'LEA_CONFIRMED_CLUSTER',
    'SIGNAL_CORRECTION',
    'SIGNAL_REVOKED'
];

const BANK_MSPS = ['BankAMSP', 'BankBMSP', 'BankCMSP'];
const I4C_MSP = 'I4CMSP';
const LEA_MSP = 'LEAMSP';
const KNOWN_MSPS = [...BANK_MSPS, I4C_MSP, LEA_MSP];

const BANK_ALLOWED_TYPES = [
    'ATM_WITHDRAWAL_CONFIRMED',
    'ATM_WITHDRAWAL_ATTEMPT',
    'BRANCH_CASHOUT_CONFIRMED',
    'MULE_ACCOUNT_ACTIVITY'
];

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

class GeoIntelligenceContract extends Contract {

    constructor() {
        super('GeoIntelligenceContract');
    }

    /**
     * Initialize the ledger with contract metadata
     */
    async InitLedger(ctx) {
        const metadata = {
            contract: 'GeoIntelligenceContract',
            schema_version: SCHEMA_VERSION,
            initialized_at: this._getTxTimestampISO(ctx),
            tx_id: ctx.stub.getTxID(),
            status: 'INITIALIZED'
        };
        await ctx.stub.putState('CONTRACT_METADATA', Buffer.from(JSON.stringify(metadata)));
        return JSON.stringify(metadata);
    }

    /**
     * Submit a new verified intelligence signal
     */
    async SubmitSignal(ctx, signalJson) {
        const rawPayload = this._parseJson(signalJson, 'signalJson');
        this._validatePIISafety(rawPayload);

        const clientMsp = this._getClientMsp(ctx);
        this._validateSubmitPermissions(clientMsp, rawPayload.event_type);
        this._validateSignalFields(rawPayload, false);

        const eventId = rawPayload.event_id;
        const key = this._getSignalKey(eventId);

        // Check idempotency
        const existingBytes = await ctx.stub.getState(key);
        if (existingBytes && existingBytes.length > 0) {
            const existingSignal = JSON.parse(existingBytes.toString());
            if (this._isPayloadIdentical(existingSignal, rawPayload)) {
                return JSON.stringify({
                    ...existingSignal,
                    _idempotent_replay: true
                });
            }
            throw new Error(`Idempotency conflict: Event ID '${eventId}' already exists with different payload.`);
        }

        const txTimestamp = this._getTxTimestampISO(ctx);
        const txId = ctx.stub.getTxID();

        const signalRecord = {
            event_id: eventId,
            event_type: rawPayload.event_type,
            organization_msp: clientMsp,
            opaque_subject_ref: rawPayload.opaque_subject_ref,
            cluster_id: rawPayload.cluster_id !== undefined && rawPayload.cluster_id !== null ? Number(rawPayload.cluster_id) : null,
            district: rawPayload.district ? String(rawPayload.district).trim().toUpperCase() : null,
            event_timestamp: rawPayload.event_timestamp,
            submitted_at: txTimestamp,
            verification_status: rawPayload.verification_status || 'VERIFIED',
            confidence: rawPayload.confidence !== undefined && rawPayload.confidence !== null ? Number(rawPayload.confidence) : 1.0,
            source_reference_hash: rawPayload.source_reference_hash || null,
            status: 'ACTIVE',
            created_tx_id: txId,
            created_by_msp: clientMsp,
            corrected_by_event_id: null,
            revoked_by_event_id: null,
            schema_version: SCHEMA_VERSION
        };

        // Write primary state
        await ctx.stub.putState(key, Buffer.from(JSON.stringify(signalRecord)));

        // Create composite keys for efficient indexed queries
        await this._writeCompositeKeys(ctx, signalRecord);

        // Emit Fabric chaincode event (privacy-safe metadata only)
        const eventPayload = {
            event_id: signalRecord.event_id,
            event_type: signalRecord.event_type,
            organization_msp: signalRecord.organization_msp,
            cluster_id: signalRecord.cluster_id,
            district: signalRecord.district,
            status: signalRecord.status,
            tx_id: txId
        };
        ctx.stub.setEvent('SignalSubmitted', Buffer.from(JSON.stringify(eventPayload)));

        return JSON.stringify(signalRecord);
    }

    /**
     * Retrieve a signal by event_id
     */
    async GetSignal(ctx, event_id) {
        if (!event_id) {
            throw new Error('event_id is required');
        }
        const key = this._getSignalKey(event_id);
        const signalBytes = await ctx.stub.getState(key);
        if (!signalBytes || signalBytes.length === 0) {
            throw new Error(`Signal '${event_id}' does not exist on the ledger.`);
        }
        return signalBytes.toString();
    }

    /**
     * Check if a signal exists on the ledger
     */
    async SignalExists(ctx, event_id) {
        if (!event_id) {
            return JSON.stringify({ exists: false });
        }
        const key = this._getSignalKey(event_id);
        const signalBytes = await ctx.stub.getState(key);
        const exists = !!(signalBytes && signalBytes.length > 0);
        return JSON.stringify({ event_id, exists });
    }

    /**
     * Get current state of a signal (including status)
     */
    async GetCurrentSignalState(ctx, event_id) {
        const signalStr = await this.GetSignal(ctx, event_id);
        const signal = JSON.parse(signalStr);
        return JSON.stringify({
            event_id: signal.event_id,
            status: signal.status,
            event_type: signal.event_type,
            cluster_id: signal.cluster_id,
            district: signal.district,
            corrected_by_event_id: signal.corrected_by_event_id,
            revoked_by_event_id: signal.revoked_by_event_id,
            organization_msp: signal.organization_msp,
            submitted_at: signal.submitted_at
        });
    }

    /**
     * Correct an existing signal.
     * Creates a new immutable SIGNAL_CORRECTION record and updates target signal status to CORRECTED.
     */
    async CorrectSignal(ctx, target_event_id, correctionSignalJson) {
        if (!target_event_id) {
            throw new Error('target_event_id is required');
        }
        const rawCorrection = this._parseJson(correctionSignalJson, 'correctionSignalJson');
        this._validatePIISafety(rawCorrection);

        const targetKey = this._getSignalKey(target_event_id);
        const targetBytes = await ctx.stub.getState(targetKey);
        if (!targetBytes || targetBytes.length === 0) {
            throw new Error(`Target signal '${target_event_id}' does not exist for correction.`);
        }
        const targetSignal = JSON.parse(targetBytes.toString());

        if (targetSignal.status === 'REVOKED') {
            throw new Error(`Cannot correct a REVOKED signal '${target_event_id}'.`);
        }

        const clientMsp = this._getClientMsp(ctx);
        this._validateModifyPermissions(clientMsp, targetSignal);

        const correctionEventId = rawCorrection.event_id || `CORR_${target_event_id}_${ctx.stub.getTxID().substring(0, 8)}`;
        const corrKey = this._getSignalKey(correctionEventId);
        const corrExists = await ctx.stub.getState(corrKey);
        if (corrExists && corrExists.length > 0) {
            throw new Error(`Correction event ID '${correctionEventId}' already exists.`);
        }

        const txTimestamp = this._getTxTimestampISO(ctx);
        const txId = ctx.stub.getTxID();

        // Update target signal record
        targetSignal.status = 'CORRECTED';
        targetSignal.corrected_by_event_id = correctionEventId;
        await ctx.stub.putState(targetKey, Buffer.from(JSON.stringify(targetSignal)));

        // Create new SIGNAL_CORRECTION record
        const correctionRecord = {
            event_id: correctionEventId,
            event_type: 'SIGNAL_CORRECTION',
            organization_msp: clientMsp,
            opaque_subject_ref: rawCorrection.opaque_subject_ref || targetSignal.opaque_subject_ref,
            cluster_id: rawCorrection.cluster_id !== undefined ? Number(rawCorrection.cluster_id) : targetSignal.cluster_id,
            district: rawCorrection.district ? String(rawCorrection.district).trim().toUpperCase() : targetSignal.district,
            event_timestamp: rawCorrection.event_timestamp || txTimestamp,
            submitted_at: txTimestamp,
            verification_status: rawCorrection.verification_status || 'CORRECTED',
            confidence: rawCorrection.confidence !== undefined ? Number(rawCorrection.confidence) : targetSignal.confidence,
            source_reference_hash: rawCorrection.source_reference_hash || targetSignal.source_reference_hash,
            status: 'ACTIVE',
            created_tx_id: txId,
            created_by_msp: clientMsp,
            target_event_id: target_event_id,
            corrected_by_event_id: null,
            revoked_by_event_id: null,
            schema_version: SCHEMA_VERSION
        };

        await ctx.stub.putState(corrKey, Buffer.from(JSON.stringify(correctionRecord)));
        await this._writeCompositeKeys(ctx, correctionRecord);

        // Emit event
        const eventPayload = {
            event_id: correctionEventId,
            target_event_id: target_event_id,
            corrected_by_msp: clientMsp,
            tx_id: txId
        };
        ctx.stub.setEvent('SignalCorrected', Buffer.from(JSON.stringify(eventPayload)));

        return JSON.stringify({
            message: `Signal '${target_event_id}' corrected successfully.`,
            target_event: targetSignal,
            correction_event: correctionRecord
        });
    }

    /**
     * Revoke an existing signal.
     * Creates a new immutable SIGNAL_REVOKED record and updates target signal status to REVOKED.
     */
    async RevokeSignal(ctx, target_event_id, revocationPayloadJson) {
        if (!target_event_id) {
            throw new Error('target_event_id is required');
        }
        let rawRevocation = {};
        if (revocationPayloadJson) {
            rawRevocation = this._parseJson(revocationPayloadJson, 'revocationPayloadJson');
            this._validatePIISafety(rawRevocation);
        }

        const targetKey = this._getSignalKey(target_event_id);
        const targetBytes = await ctx.stub.getState(targetKey);
        if (!targetBytes || targetBytes.length === 0) {
            throw new Error(`Target signal '${target_event_id}' does not exist for revocation.`);
        }
        const targetSignal = JSON.parse(targetBytes.toString());

        const clientMsp = this._getClientMsp(ctx);
        this._validateModifyPermissions(clientMsp, targetSignal);

        const revocationEventId = rawRevocation.event_id || `REV_${target_event_id}_${ctx.stub.getTxID().substring(0, 8)}`;
        const revKey = this._getSignalKey(revocationEventId);

        const txTimestamp = this._getTxTimestampISO(ctx);
        const txId = ctx.stub.getTxID();

        // Update target signal record
        targetSignal.status = 'REVOKED';
        targetSignal.revoked_by_event_id = revocationEventId;
        await ctx.stub.putState(targetKey, Buffer.from(JSON.stringify(targetSignal)));

        // Create new SIGNAL_REVOKED record
        const revocationRecord = {
            event_id: revocationEventId,
            event_type: 'SIGNAL_REVOKED',
            organization_msp: clientMsp,
            opaque_subject_ref: targetSignal.opaque_subject_ref,
            cluster_id: targetSignal.cluster_id,
            district: targetSignal.district,
            event_timestamp: txTimestamp,
            submitted_at: txTimestamp,
            verification_status: 'REVOKED',
            confidence: 0.0,
            source_reference_hash: rawRevocation.source_reference_hash || null,
            status: 'REVOKED',
            created_tx_id: txId,
            created_by_msp: clientMsp,
            target_event_id: target_event_id,
            reason: rawRevocation.reason || 'Consortium revocation',
            schema_version: SCHEMA_VERSION
        };

        await ctx.stub.putState(revKey, Buffer.from(JSON.stringify(revocationRecord)));
        await this._writeCompositeKeys(ctx, revocationRecord);

        // Emit event
        const eventPayload = {
            event_id: revocationEventId,
            target_event_id: target_event_id,
            revoked_by_msp: clientMsp,
            tx_id: txId
        };
        ctx.stub.setEvent('SignalRevoked', Buffer.from(JSON.stringify(eventPayload)));

        return JSON.stringify({
            message: `Signal '${target_event_id}' revoked successfully.`,
            target_event: targetSignal,
            revocation_event: revocationRecord
        });
    }

    /**
     * Query signals for a given cluster_id
     * include_inactive: boolean or string ('true'/'false'), defaults to false
     */
    async QuerySignalsByCluster(ctx, cluster_id, include_inactive) {
        if (cluster_id === undefined || cluster_id === null || cluster_id === '') {
            throw new Error('cluster_id is required');
        }
        const showInactive = this._parseBoolean(include_inactive, false);
        const clusterStr = String(cluster_id);

        const iterator = await ctx.stub.getStateByPartialCompositeKey('cluster~timestamp~event', [clusterStr]);
        const results = await this._resolveCompositeKeyResults(ctx, iterator, showInactive);
        return JSON.stringify(results);
    }

    /**
     * Query signals by time window (ISO-8601 start_time to end_time)
     * include_inactive: boolean or string ('true'/'false'), defaults to false
     */
    async QuerySignalsByTimeWindow(ctx, start_time, end_time, include_inactive) {
        if (!start_time || !end_time) {
            throw new Error('Both start_time and end_time are required (ISO-8601 format).');
        }
        const startTimeMs = Date.parse(start_time);
        const endTimeMs = Date.parse(end_time);
        if (isNaN(startTimeMs) || isNaN(endTimeMs)) {
            throw new Error('Invalid ISO-8601 date string provided for time window query.');
        }
        if (startTimeMs > endTimeMs) {
            throw new Error('start_time must be less than or equal to end_time.');
        }

        const showInactive = this._parseBoolean(include_inactive, false);

        // Query all signals range
        const iterator = await ctx.stub.getStateByRange('SIGNAL_', 'SIGNAL_\uffff');
        const results = [];

        let res = await iterator.next();
        while (!res.done) {
            if (res.value && res.value.value.toString()) {
                try {
                    const signal = JSON.parse(res.value.value.toString());
                    const eventTimeMs = Date.parse(signal.event_timestamp);
                    if (!isNaN(eventTimeMs) && eventTimeMs >= startTimeMs && eventTimeMs <= endTimeMs) {
                        if (showInactive || signal.status === 'ACTIVE') {
                            results.push(signal);
                        }
                    }
                } catch (e) {
                    // Ignore non-signal keys
                }
            }
            res = await iterator.next();
        }
        await iterator.close();

        return JSON.stringify(results);
    }

    /**
     * Query signals by opaque_subject_ref
     * include_inactive: boolean or string ('true'/'false'), defaults to false
     */
    async QuerySignalsByOpaqueSubject(ctx, opaque_subject_ref, include_inactive) {
        if (!opaque_subject_ref) {
            throw new Error('opaque_subject_ref is required');
        }
        const showInactive = this._parseBoolean(include_inactive, false);

        const iterator = await ctx.stub.getStateByPartialCompositeKey('subject~timestamp~event', [opaque_subject_ref]);
        const results = await this._resolveCompositeKeyResults(ctx, iterator, showInactive);
        return JSON.stringify(results);
    }

    /**
     * Retrieve full immutable transaction history for a signal
     */
    async GetSignalHistory(ctx, event_id) {
        if (!event_id) {
            throw new Error('event_id is required');
        }
        const key = this._getSignalKey(event_id);
        const iterator = await ctx.stub.getHistoryForKey(key);
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

    _getSignalKey(eventId) {
        return `SIGNAL_${eventId}`;
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

    _parseBoolean(input, defaultValue = false) {
        if (input === undefined || input === null) return defaultValue;
        if (typeof input === 'boolean') return input;
        if (typeof input === 'string') {
            const s = input.toLowerCase().trim();
            if (s === 'true' || s === '1') return true;
            if (s === 'false' || s === '0') return false;
        }
        return defaultValue;
    }

    _validatePIISafety(payload) {
        if (!payload || typeof payload !== 'object') return;
        const keys = Object.keys(payload);
        for (const key of keys) {
            const normalized = key.toLowerCase().replace(/[^a-z0-9_]/g, '');
            for (const prohibited of PROHIBITED_PII_FIELDS) {
                if (normalized === prohibited || normalized.includes(prohibited)) {
                    throw new Error(`PII Security Violation: Prohibited field '${key}' is rejected by geo-intelligence chaincode schema enforcement.`);
                }
            }
            // Check nested objects if any
            if (typeof payload[key] === 'object' && payload[key] !== null) {
                this._validatePIISafety(payload[key]);
            }
        }
    }

    _validateSubmitPermissions(clientMsp, eventType) {
        if (!KNOWN_MSPS.includes(clientMsp)) {
            throw new Error(`Unauthorized MSP: '${clientMsp}' is not a recognized consortium member.`);
        }

        if (BANK_MSPS.includes(clientMsp)) {
            if (!BANK_ALLOWED_TYPES.includes(eventType)) {
                throw new Error(`Permission Denied: Bank organizations (${clientMsp}) may only submit cash-out & mule events (${BANK_ALLOWED_TYPES.join(', ')}). Received: '${eventType}'.`);
            }
        } else if (clientMsp === LEA_MSP) {
            if (eventType !== 'LEA_CONFIRMED_CLUSTER') {
                throw new Error(`Permission Denied: LEA (${clientMsp}) may only submit 'LEA_CONFIRMED_CLUSTER' signals. Received: '${eventType}'.`);
            }
        } else if (clientMsp === I4C_MSP) {
            // I4C can submit any authorized event
            if (!ALLOWED_EVENT_TYPES.includes(eventType)) {
                throw new Error(`Invalid event_type: '${eventType}'.`);
            }
        }
    }

    _validateModifyPermissions(clientMsp, targetSignal) {
        if (!KNOWN_MSPS.includes(clientMsp)) {
            throw new Error(`Unauthorized MSP: '${clientMsp}' is not a recognized consortium member.`);
        }

        // I4C has consortium-wide correction & revocation authority
        if (clientMsp === I4C_MSP) {
            return;
        }

        // Original submitting organization may modify its own signals
        if (clientMsp === targetSignal.created_by_msp) {
            return;
        }

        // LEA can modify LEA-originated intelligence
        if (clientMsp === LEA_MSP && targetSignal.created_by_msp === LEA_MSP) {
            return;
        }

        // Banks cannot modify signals belonging to another bank or authority
        throw new Error(`Permission Denied: Organization '${clientMsp}' is not authorized to modify signal owned by '${targetSignal.created_by_msp}'.`);
    }

    _validateSignalFields(payload, isCorrectionOrRevocation = false) {
        if (!payload.event_id || typeof payload.event_id !== 'string' || payload.event_id.trim().length === 0) {
            throw new Error('event_id is required, non-empty string.');
        }
        if (!/^[A-Za-z0-9_-]{3,128}$/.test(payload.event_id.trim())) {
            throw new Error(`event_id '${payload.event_id}' has invalid format. Must be 3-128 alphanumeric, underscore, or hyphen characters.`);
        }

        if (!payload.event_type || !ALLOWED_EVENT_TYPES.includes(payload.event_type)) {
            throw new Error(`event_type '${payload.event_type}' is not allowed. Must be one of: ${ALLOWED_EVENT_TYPES.join(', ')}`);
        }

        if (!payload.opaque_subject_ref || typeof payload.opaque_subject_ref !== 'string' || payload.opaque_subject_ref.trim().length === 0) {
            throw new Error('opaque_subject_ref is required and must be a non-empty tokenized string.');
        }

        // Geographic events require cluster_id and district
        const geoRequired = ['ATM_WITHDRAWAL_CONFIRMED', 'ATM_WITHDRAWAL_ATTEMPT', 'BRANCH_CASHOUT_CONFIRMED', 'LEA_CONFIRMED_CLUSTER'];
        if (geoRequired.includes(payload.event_type)) {
            if (payload.cluster_id === undefined || payload.cluster_id === null || isNaN(Number(payload.cluster_id))) {
                throw new Error(`cluster_id is required for event type '${payload.event_type}'.`);
            }
            if (!payload.district || typeof payload.district !== 'string' || payload.district.trim().length === 0) {
                throw new Error(`district is required for event type '${payload.event_type}'.`);
            }
        }

        if (!payload.event_timestamp || isNaN(Date.parse(payload.event_timestamp))) {
            throw new Error(`event_timestamp '${payload.event_timestamp}' must be a valid ISO-8601 date string.`);
        }

        if (payload.confidence !== undefined && payload.confidence !== null) {
            const conf = Number(payload.confidence);
            if (isNaN(conf) || conf < 0.0 || conf > 1.0) {
                throw new Error(`confidence must be a number between 0.0 and 1.0. Received: ${payload.confidence}`);
            }
        }

        if (payload.source_reference_hash) {
            if (!/^[a-fA-F0-9]{64}$/.test(payload.source_reference_hash)) {
                throw new Error(`source_reference_hash must be a 64-character hex SHA-256 string. Received: ${payload.source_reference_hash}`);
            }
        }
    }

    _isPayloadIdentical(existingSignal, newPayload) {
        // Compare semantic fields
        if (existingSignal.event_type !== newPayload.event_type) return false;
        if (existingSignal.opaque_subject_ref !== newPayload.opaque_subject_ref) return false;
        if (newPayload.cluster_id !== undefined && existingSignal.cluster_id !== Number(newPayload.cluster_id)) return false;
        if (newPayload.district && existingSignal.district !== String(newPayload.district).trim().toUpperCase()) return false;
        if (existingSignal.event_timestamp !== newPayload.event_timestamp) return false;
        if (newPayload.confidence !== undefined && existingSignal.confidence !== Number(newPayload.confidence)) return false;
        if (newPayload.source_reference_hash && existingSignal.source_reference_hash !== newPayload.source_reference_hash) return false;
        return true;
    }

    async _writeCompositeKeys(ctx, record) {
        const clusterVal = record.cluster_id !== null ? String(record.cluster_id) : 'NONE';
        const clusterCompKey = ctx.stub.createCompositeKey('cluster~timestamp~event', [clusterVal, record.event_timestamp, record.event_id]);
        await ctx.stub.putState(clusterCompKey, Buffer.from('\u0000'));

        const subjectCompKey = ctx.stub.createCompositeKey('subject~timestamp~event', [record.opaque_subject_ref, record.event_timestamp, record.event_id]);
        await ctx.stub.putState(subjectCompKey, Buffer.from('\u0000'));

        const orgCompKey = ctx.stub.createCompositeKey('org~timestamp~event', [record.organization_msp, record.event_timestamp, record.event_id]);
        await ctx.stub.putState(orgCompKey, Buffer.from('\u0000'));

        const typeCompKey = ctx.stub.createCompositeKey('type~timestamp~event', [record.event_type, record.event_timestamp, record.event_id]);
        await ctx.stub.putState(typeCompKey, Buffer.from('\u0000'));
    }

    async _resolveCompositeKeyResults(ctx, iterator, showInactive) {
        const results = [];
        let res = await iterator.next();
        while (!res.done) {
            if (res.value && res.value.key) {
                const splitKey = ctx.stub.splitCompositeKey(res.value.key);
                const eventId = splitKey.attributes[splitKey.attributes.length - 1];
                if (eventId) {
                    const signalKey = this._getSignalKey(eventId);
                    const signalBytes = await ctx.stub.getState(signalKey);
                    if (signalBytes && signalBytes.length > 0) {
                        try {
                            const signal = JSON.parse(signalBytes.toString());
                            if (showInactive || signal.status === 'ACTIVE') {
                                results.push(signal);
                            }
                        } catch (e) {
                            // ignore parse errors
                        }
                    }
                }
            }
            res = await iterator.next();
        }
        await iterator.close();
        return results;
    }
}

module.exports = GeoIntelligenceContract;
