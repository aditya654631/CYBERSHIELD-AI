'use strict';

const GeoIntelligenceService = require('../../gateway/src/services/geo-intelligence-service');
const FeatureEngine = require('../src/feature-engine');

async function main() {
    console.log('=== CyberShield Blockchain Feature Engine Demo ===\n');

    const geoService = new GeoIntelligenceService('I4C');
    const engine = new FeatureEngine({ geoService, gatewayOrg: 'I4C' });

    try {
        const clusterId = 7;
        const referenceTimestamp = new Date().toISOString();
        const opaqueSubjectRef = 'opaque-demo-subject-001';

        console.log(`Generating leakage-safe features for Cluster ${clusterId} as-of ${referenceTimestamp}...`);
        const result = await engine.buildClusterFeatures({
            clusterId,
            referenceTimestamp,
            opaqueSubjectRef
        });

        console.log('\n--- Provenance Metadata ---');
        console.log(JSON.stringify(result.provenance, null, 2));

        console.log('\n--- Candidate Cluster Features ---');
        console.log(JSON.stringify(result.features, null, 2));

        console.log('\n--- Batch Top-5 Candidates ---');
        const candidateIds = [7, 8, 12, 1, 2];
        const batch = await engine.buildCandidateFeatureMatrix({
            clusterIds: candidateIds,
            referenceTimestamp,
            opaqueSubjectRef
        });
        console.log(`Computed batch matrix for ${batch.candidate_count} candidates.`);
        batch.matrix.forEach(m => {
            console.log(`Cluster ${m.cluster_id}: active_signals=${m.provenance.active_event_count}, cashouts_1h=${m.features.verified_cashouts_1h}, multi_org=${m.features.has_multi_org_attestation_1h}`);
        });

    } catch (err) {
        console.error('Demo failed:', err);
    } finally {
        await engine.close();
    }
}

if (require.main === module) {
    main();
}

module.exports = main;
