'use strict';

const GeoIntelligenceService = require('../src/services/geo-intelligence-service');

async function main() {
    console.log('=== LEA Simulated Gateway Submitter ===');
    const service = new GeoIntelligenceService('LEA');

    const demoSignal = {
        event_id: process.env.EVENT_ID || 'EVT-GATEWAY-LEA-001',
        event_type: 'LEA_CONFIRMED_CLUSTER',
        opaque_subject_ref: 'opaque-gateway-demo-003',
        cluster_id: 7,
        district: 'NEW_DELHI',
        event_timestamp: new Date().toISOString(),
        confidence: 0.95,
        source_reference_hash: '9f8e7d6c5b4a392817162534435261709f8e7d6c5b4a39281716253443526170'
    };

    try {
        console.log(`Submitting signal ${demoSignal.event_id} via Fabric Gateway SDK as LEA...`);
        const result = await service.submitSignal(demoSignal, 'LEA');
        console.log('--- LEA Submission Succeeded ---');
        console.log('Transaction ID:', result.txId);
        console.log('Commit Status: ', result.status);
        console.log('Latency:       ', `${result.latencyMs}ms`);
        console.log('Committed Signal:', JSON.stringify(result.result, null, 2));
        return result;
    } catch (err) {
        console.error('LEA Submission Failed:', err.message);
        throw err;
    } finally {
        await service.closeAll();
    }
}

if (require.main === module) {
    main().catch(() => process.exit(1));
}

module.exports = main;
