'use strict';

const GeoIntelligenceService = require('../src/services/geo-intelligence-service');

async function main() {
    console.log('=== BankA Simulated Gateway Submitter ===');
    const service = new GeoIntelligenceService('BankA');

    const demoSignal = {
        event_id: process.env.EVENT_ID || 'EVT-GATEWAY-BANKA-001',
        event_type: 'ATM_WITHDRAWAL_ATTEMPT',
        opaque_subject_ref: 'opaque-gateway-demo-001',
        cluster_id: 7,
        district: 'NEW_DELHI',
        event_timestamp: new Date().toISOString(),
        confidence: 0.84,
        source_reference_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    };

    try {
        console.log(`Submitting signal ${demoSignal.event_id} via Fabric Gateway SDK...`);
        const result = await service.submitSignal(demoSignal, 'BankA');
        console.log('--- Submission Succeeded ---');
        console.log('Transaction ID:', result.txId);
        console.log('Commit Status: ', result.status);
        console.log('Latency:       ', `${result.latencyMs}ms`);
        console.log('Committed Signal:', JSON.stringify(result.result, null, 2));
    } catch (err) {
        console.error('Submission Failed:', err.message);
        process.exit(1);
    } finally {
        await service.closeAll();
    }
}

if (require.main === module) {
    main();
}

module.exports = main;
