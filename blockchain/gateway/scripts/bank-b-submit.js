'use strict';

const GeoIntelligenceService = require('../src/services/geo-intelligence-service');

async function main() {
    console.log('=== BankB Simulated Gateway Submitter ===');
    const service = new GeoIntelligenceService('BankB');

    const demoSignal = {
        event_id: process.env.EVENT_ID || 'EVT-GATEWAY-BANKB-001',
        event_type: 'ATM_WITHDRAWAL_CONFIRMED',
        opaque_subject_ref: 'opaque-gateway-demo-002',
        cluster_id: 7,
        district: 'NEW_DELHI',
        event_timestamp: new Date().toISOString(),
        confidence: 0.88,
        source_reference_hash: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90'
    };

    try {
        console.log(`Submitting signal ${demoSignal.event_id} via Fabric Gateway SDK as BankB...`);
        const result = await service.submitSignal(demoSignal, 'BankB');
        console.log('--- BankB Submission Succeeded ---');
        console.log('Transaction ID:', result.txId);
        console.log('Commit Status: ', result.status);
        console.log('Latency:       ', `${result.latencyMs}ms`);
        console.log('Committed Signal:', JSON.stringify(result.result, null, 2));
        return result;
    } catch (err) {
        console.error('BankB Submission Failed:', err.message);
        throw err;
    } finally {
        await service.closeAll();
    }
}

if (require.main === module) {
    main().catch(() => process.exit(1));
}

module.exports = main;
