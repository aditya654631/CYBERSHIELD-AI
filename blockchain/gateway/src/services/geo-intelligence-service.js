'use strict';

const { connectGateway } = require('../fabric/gateway-client');
const ContractClient = require('../fabric/contract-client');
const { validateSignalPayload, validatePIISafety } = require('../utils/validation');
const { FabricUnavailableError } = require('../utils/errors');

class GeoIntelligenceService {
    /**
     * @param {string} [defaultOrg='I4C'] Organization to use for queries
     */
    constructor(defaultOrg = 'I4C') {
        this.defaultOrg = defaultOrg;
        this._gatewayConnections = new Map();
    }

    /**
     * Gets or creates a reusable ContractClient for an organization.
     * @param {string} [orgIdentifier]
     * @returns {Promise<ContractClient>}
     */
    async getContractClient(orgIdentifier = null) {
        const org = orgIdentifier || this.defaultOrg;
        if (!this._gatewayConnections.has(org)) {
            const conn = await connectGateway(org);
            const contract = conn.getContract();
            const client = new ContractClient(contract, conn.orgConfig.mspId);
            this._gatewayConnections.set(org, { conn, client });
        }
        return this._gatewayConnections.get(org).client;
    }

    /**
     * Closes all active gateway connections.
     */
    async closeAll() {
        for (const { conn } of this._gatewayConnections.values()) {
            conn.close();
        }
        this._gatewayConnections.clear();
    }

    /**
     * Submits a verified intelligence signal.
     */
    async submitSignal(signalPayload, submitterOrg = null) {
        validateSignalPayload(signalPayload);
        const org = submitterOrg || this.defaultOrg;
        const client = await this.getContractClient(org);

        const startTime = Date.now();
        const res = await client.submit('SubmitSignal', JSON.stringify(signalPayload));
        const latencyMs = Date.now() - startTime;

        return {
            ...res,
            latencyMs
        };
    }

    /**
     * Retrieves a single signal by event ID.
     */
    async getSignal(eventId, queryOrg = null) {
        if (!eventId) {
            throw new Error('eventId is required.');
        }
        const client = await this.getContractClient(queryOrg);
        return await client.evaluate('GetSignal', eventId);
    }

    /**
     * Checks if a signal exists on the ledger.
     */
    async signalExists(eventId, queryOrg = null) {
        const client = await this.getContractClient(queryOrg);
        return await client.evaluate('SignalExists', eventId);
    }

    /**
     * Gets current signal state (status, references).
     */
    async getCurrentSignalState(eventId, queryOrg = null) {
        if (!eventId) {
            throw new Error('eventId is required.');
        }
        const client = await this.getContractClient(queryOrg);
        return await client.evaluate('GetCurrentSignalState', eventId);
    }

    /**
     * Corrects an existing signal.
     */
    async correctSignal(targetEventId, correctionPayload, modifierOrg = null) {
        if (!targetEventId) {
            throw new Error('targetEventId is required.');
        }
        validatePIISafety(correctionPayload);
        const client = await this.getContractClient(modifierOrg);

        const startTime = Date.now();
        const res = await client.submit('CorrectSignal', targetEventId, JSON.stringify(correctionPayload));
        return {
            ...res,
            latencyMs: Date.now() - startTime
        };
    }

    /**
     * Revokes an existing signal.
     */
    async revokeSignal(targetEventId, revocationPayload = {}, revokerOrg = null) {
        if (!targetEventId) {
            throw new Error('targetEventId is required.');
        }
        validatePIISafety(revocationPayload);
        const client = await this.getContractClient(revokerOrg);

        const startTime = Date.now();
        const res = await client.submit('RevokeSignal', targetEventId, JSON.stringify(revocationPayload));
        return {
            ...res,
            latencyMs: Date.now() - startTime
        };
    }

    /**
     * Queries signals for a given cluster_id.
     */
    async querySignalsByCluster(clusterId, includeInactive = false, queryOrg = null) {
        if (clusterId === undefined || clusterId === null || clusterId === '') {
            throw new Error('clusterId is required.');
        }
        const client = await this.getContractClient(queryOrg);
        return await client.evaluate('QuerySignalsByCluster', String(clusterId), String(includeInactive));
    }

    /**
     * Queries signals by ISO-8601 time window.
     */
    async querySignalsByTimeWindow(startTime, endTime, includeInactive = false, queryOrg = null) {
        if (!startTime || !endTime) {
            throw new Error('Both startTime and endTime are required.');
        }
        const client = await this.getContractClient(queryOrg);
        return await client.evaluate('QuerySignalsByTimeWindow', startTime, endTime, String(includeInactive));
    }

    /**
     * Queries signals by opaque subject reference.
     */
    async querySignalsByOpaqueSubject(opaqueSubjectRef, includeInactive = false, queryOrg = null) {
        if (!opaqueSubjectRef) {
            throw new Error('opaqueSubjectRef is required.');
        }
        const client = await this.getContractClient(queryOrg);
        return await client.evaluate('QuerySignalsByOpaqueSubject', opaqueSubjectRef, String(includeInactive));
    }

    /**
     * Retrieves the complete transaction history for a signal.
     */
    async getSignalHistory(eventId, queryOrg = null) {
        if (!eventId) {
            throw new Error('eventId is required.');
        }
        const client = await this.getContractClient(queryOrg);
        return await client.evaluate('GetSignalHistory', eventId);
    }

    /**
     * Verifies actual ledger connectivity and health.
     */
    async checkHealth(queryOrg = null) {
        const org = queryOrg || this.defaultOrg;
        try {
            const client = await this.getContractClient(org);
            // Evaluate lightweight query
            const existsCheck = await client.evaluate('SignalExists', 'HEALTH_PROBE');
            return {
                gateway: 'UP',
                peer: 'REACHABLE',
                channel: 'cyber-intelligence',
                chaincode: 'geo-intelligence',
                ledger: 'ACCESSIBLE',
                identity: client.orgMsp || org
            };
        } catch (err) {
            return {
                gateway: 'UP',
                peer: 'UNREACHABLE',
                channel: 'cyber-intelligence',
                chaincode: 'geo-intelligence',
                ledger: 'FAIL',
                error: err.message
            };
        }
    }
}

module.exports = GeoIntelligenceService;
