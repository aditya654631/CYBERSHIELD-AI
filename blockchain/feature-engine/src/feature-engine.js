'use strict';

const path = require('path');
const { SCHEMA_VERSION } = require('./constants');
const { validateFeatureRequest, FabricUnavailableError } = require('./validation');
const { normalizeSignalsAtReference } = require('./signal-normalizer');
const { buildClusterFeatureVector } = require('./cluster-feature-builder');

class FeatureEngine {
    /**
     * @param {object} [options]
     * @param {object} [options.geoService] Existing GeoIntelligenceService instance
     * @param {string} [options.gatewayOrg='I4C'] Organization to use for intelligence retrieval
     */
    constructor(options = {}) {
        this.gatewayOrg = options.gatewayOrg || 'I4C';
        this.geoService = options.geoService || null;

        // Lazy load GeoIntelligenceService from B.3 if not passed
        if (!this.geoService) {
            try {
                const GeoIntelligenceService = require('../../gateway/src/services/geo-intelligence-service');
                this.geoService = new GeoIntelligenceService(this.gatewayOrg);
                this._ownsGeoService = true;
            } catch (err) {
                this.geoService = null;
                this._ownsGeoService = false;
            }
        } else {
            this._ownsGeoService = false;
        }
    }

    async close() {
        if (this._ownsGeoService && this.geoService && typeof this.geoService.closeAll === 'function') {
            await this.geoService.closeAll();
        }
    }

    /**
     * Builds leakage-safe deterministic features for a single candidate cluster.
     * 
     * @param {object} input
     * @param {number|string} input.clusterId
     * @param {string} input.referenceTimestamp - ISO-8601 reference time
     * @param {string} [input.opaqueSubjectRef] - Optional opaque subject reference
     * @returns {Promise<object>} Versioned feature package
     */
    async buildClusterFeatures(input) {
        const validated = validateFeatureRequest(input);
        const { clusterId, referenceTimestamp, refTimeMs, opaqueSubjectRef } = validated;

        if (!this.geoService) {
            throw new FabricUnavailableError("Fabric Gateway service is not initialized or unreachable.");
        }

        const genTimeISO = new Date().toISOString();

        try {
            // 1. Query raw signals for the cluster (include inactive to capture historical state)
            const rawClusterSignals = await this.geoService.querySignalsByCluster(clusterId, true, this.gatewayOrg);

            // 2. Query subject signals if opaqueSubjectRef is provided
            let rawSubjectSignals = [];
            if (opaqueSubjectRef) {
                rawSubjectSignals = await this.geoService.querySignalsByOpaqueSubject(opaqueSubjectRef, true, this.gatewayOrg);
            }

            // 3. Normalize signals as of reference timestamp (anti-leakage + status resolution)
            const normalizedCluster = normalizeSignalsAtReference(rawClusterSignals, refTimeMs);
            const normalizedSubject = normalizeSignalsAtReference(rawSubjectSignals, refTimeMs);

            // 4. Build feature vector
            const features = buildClusterFeatureVector({
                clusterId,
                refTimeMs,
                activeClusterSignals: normalizedCluster.activeSignals,
                allClusterSignalsAtRef: normalizedCluster.allSignalsAtRef,
                subjectSignals: normalizedSubject.activeSignals,
                opaqueSubjectRef
            });

            return {
                schema_version: SCHEMA_VERSION,
                cluster_id: clusterId,
                reference_timestamp: referenceTimestamp,
                feature_generated_at: genTimeISO,
                source: 'hyperledger_fabric',
                channel: 'cyber-intelligence',
                chaincode: 'geo-intelligence',
                fabric_available: true,
                provenance: {
                    fabric_channel: 'cyber-intelligence',
                    chaincode_name: 'geo-intelligence',
                    feature_schema_version: SCHEMA_VERSION,
                    reference_timestamp: referenceTimestamp,
                    queried_event_count: Array.isArray(rawClusterSignals) ? rawClusterSignals.length : 0,
                    active_event_count: normalizedCluster.activeSignals.length,
                    excluded_future_count: normalizedCluster.futureExcludedCount,
                    excluded_revoked_count: normalizedCluster.revokedExcludedCount
                },
                features
            };
        } catch (err) {
            // If Fabric or Gateway fails, return truthful failure without fabricating data
            if (err.name === 'FabricUnavailableError' || err.code === 'FABRIC_UNAVAILABLE' || err.statusCode === 503) {
                throw new FabricUnavailableError(`Fabric service unavailable during feature generation: ${err.message}`, err);
            }
            throw err;
        }
    }

    /**
     * Builds leakage-safe candidate feature matrix for Top-25 or multiple clusters.
     * Preserves exact input candidate order.
     * 
     * @param {object} input
     * @param {Array<number|string>} input.clusterIds
     * @param {string} input.referenceTimestamp
     * @param {string} [input.opaqueSubjectRef]
     * @returns {Promise<object>} Batch feature matrix
     */
    async buildCandidateFeatureMatrix(input) {
        const { clusterIds, referenceTimestamp, opaqueSubjectRef } = input || {};
        if (!Array.isArray(clusterIds) || clusterIds.length === 0) {
            throw new Error("clusterIds must be a non-empty array of cluster identifiers.");
        }

        const results = [];
        // Sequential or bounded resolution preserving exact input order
        for (const cid of clusterIds) {
            const row = await this.buildClusterFeatures({
                clusterId: cid,
                referenceTimestamp,
                opaqueSubjectRef
            });
            results.push(row);
        }

        return {
            schema_version: SCHEMA_VERSION,
            reference_timestamp: referenceTimestamp,
            candidate_count: results.length,
            matrix: results
        };
    }
}

module.exports = FeatureEngine;
