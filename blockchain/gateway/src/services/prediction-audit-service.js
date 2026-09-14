'use strict';

const { connectGateway } = require('../fabric/gateway-client');
const ContractClient = require('../fabric/contract-client');
const {
    canonicalizePredictionAuditPayload,
    computePredictionHash,
    buildAnchorPayload,
    SCHEMA_VERSION
} = require('../../../prediction-audit/hasher');
const { FabricUnavailableError } = require('../utils/errors');

class PredictionAuditService {
    /**
     * @param {string} [defaultAnchorOrg='I4C'] Organization to use for anchoring (I4CMSP authorized)
     * @param {string} [defaultQueryOrg='LEA'] Organization to use for reads/verification
     */
    constructor(defaultAnchorOrg = 'I4C', defaultQueryOrg = 'LEA') {
        this.defaultAnchorOrg = defaultAnchorOrg;
        this.defaultQueryOrg = defaultQueryOrg;
        this.chaincodeName = 'prediction-audit';
        this._gatewayConnections = new Map();
    }

    /**
     * Gets or creates a reusable ContractClient for prediction-audit chaincode.
     * @param {string} orgIdentifier
     * @returns {Promise<ContractClient>}
     */
    async getContractClient(orgIdentifier) {
        const org = orgIdentifier || this.defaultAnchorOrg;
        const cacheKey = `${org}:${this.chaincodeName}`;
        if (!this._gatewayConnections.has(cacheKey)) {
            const conn = await connectGateway(org, { chaincodeName: this.chaincodeName });
            const contract = conn.getContract();
            const client = new ContractClient(contract, conn.orgConfig.mspId);
            this._gatewayConnections.set(cacheKey, { conn, client });
        }
        return this._gatewayConnections.get(cacheKey).client;
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
     * Anchors a prediction to the immutable Fabric ledger.
     * @param {object} predictionData Raw prediction output from persistence/inference
     * @param {string} [anchorOrg='I4C'] MSP identity
     * @returns {Promise<object>} Anchor result including txId and hash
     */
    async anchorPrediction(predictionData, anchorOrg = null) {
        const org = anchorOrg || this.defaultAnchorOrg;
        let anchorPayload;
        let predictionHash;
        let predictionId;

        if (predictionData && predictionData.prediction_hash && Array.isArray(predictionData.top3_cluster_ids)) {
            anchorPayload = predictionData;
            predictionHash = predictionData.prediction_hash;
            predictionId = predictionData.prediction_id;
        } else {
            const built = buildAnchorPayload(predictionData);
            anchorPayload = built.anchorPayload;
            predictionHash = built.predictionHash;
            predictionId = built.canonicalPayload.prediction_id;
        }

        const client = await this.getContractClient(org);

        const startTime = Date.now();
        const res = await client.submit('AnchorPrediction', JSON.stringify(anchorPayload));
        const latencyMs = Date.now() - startTime;

        return {
            success: true,
            txId: res.txId,
            status: res.status,
            blockNumber: res.blockNumber,
            prediction_id: predictionId,
            prediction_hash: predictionHash,
            anchored_record: res.result,
            latencyMs
        };
    }

    /**
     * Retrieves an anchor by prediction ID.
     * @param {number|string} predictionId
     * @param {string} [queryOrg='LEA']
     */
    async getPredictionAnchor(predictionId, queryOrg = null) {
        if (!predictionId) {
            throw new Error('predictionId is required.');
        }
        const org = queryOrg || this.defaultQueryOrg;
        const client = await this.getContractClient(org);
        return await client.evaluate('GetPredictionAnchor', String(predictionId));
    }

    /**
     * Checks whether an anchor exists on ledger.
     * @param {number|string} predictionId
     * @param {string} [queryOrg='LEA']
     */
    async predictionAnchorExists(predictionId, queryOrg = null) {
        const org = queryOrg || this.defaultQueryOrg;
        const client = await this.getContractClient(org);
        return await client.evaluate('PredictionAnchorExists', String(predictionId));
    }

    /**
     * Verifies if a given prediction_id and candidate prediction_hash match the ledger anchor.
     * @param {number|string} predictionId
     * @param {string} candidateHash
     * @param {string} [queryOrg='LEA']
     */
    async verifyPredictionHash(predictionId, candidateHash, queryOrg = null) {
        if (!predictionId || !candidateHash) {
            throw new Error('Both predictionId and candidateHash are required.');
        }
        const org = queryOrg || this.defaultQueryOrg;
        const client = await this.getContractClient(org);
        return await client.evaluate('VerifyPredictionHash', String(predictionId), String(candidateHash).trim().toLowerCase());
    }

    /**
     * End-to-end verification: takes raw prediction data, computes canonical hash, and verifies against ledger.
     * @param {object} predictionData
     * @param {string} [queryOrg='LEA']
     */
    async verifyPersistedPrediction(predictionData, queryOrg = null) {
        const canonical = canonicalizePredictionAuditPayload(predictionData);
        const computedHash = computePredictionHash(canonical);
        const verification = await this.verifyPredictionHash(canonical.prediction_id, computedHash, queryOrg);
        return {
            ...verification,
            recomputed_hash: computedHash,
            canonical_payload: canonical
        };
    }

    /**
     * Retrieves full immutable transaction history for an anchor.
     * @param {number|string} predictionId
     * @param {string} [queryOrg='LEA']
     */
    async getAnchorHistory(predictionId, queryOrg = null) {
        if (!predictionId) {
            throw new Error('predictionId is required.');
        }
        const org = queryOrg || this.defaultQueryOrg;
        const client = await this.getContractClient(org);
        return await client.evaluate('GetAnchorHistory', String(predictionId));
    }

    /**
     * Health check for prediction-audit chaincode.
     * @param {string} [queryOrg='I4C']
     */
    async checkHealth(queryOrg = null) {
        const org = queryOrg || this.defaultQueryOrg;
        try {
            const client = await this.getContractClient(org);
            const res = await client.evaluate('PredictionAnchorExists', '0');
            return {
                gateway: 'UP',
                peer: 'REACHABLE',
                channel: 'cyber-intelligence',
                chaincode: this.chaincodeName,
                ledger: 'ACCESSIBLE',
                identity: client.orgMsp || org
            };
        } catch (err) {
            return {
                gateway: 'UP',
                peer: 'UNREACHABLE',
                channel: 'cyber-intelligence',
                chaincode: this.chaincodeName,
                ledger: 'FAIL',
                error: err.message
            };
        }
    }
}

module.exports = PredictionAuditService;
