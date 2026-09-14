'use strict';

const GeoIntelligenceService = require('../src/services/geo-intelligence-service');

async function main() {
    console.log('=== I4C Simulated Gateway Intelligence Consumer ===');
    const service = new GeoIntelligenceService('I4C');

    try {
        const targetEventId = process.env.EVENT_ID || 'EVT-GATEWAY-BANKA-001';
        console.log(`\n[1] Querying signal ${targetEventId} as I4CMSP...`);
        const signal = await service.getSignal(targetEventId, 'I4C');
        console.log('Result:', JSON.stringify(signal, null, 2));

        console.log(`\n[2] Querying cluster 7 signals as I4CMSP...`);
        const clusterSignals = await service.querySignalsByCluster(7, 'I4C');
        console.log(`Found ${clusterSignals.length} signals for cluster 7.`);
        clusterSignals.forEach(s => {
            console.log(` - ID: ${s.event_id}, Org: ${s.organization_msp}, Type: ${s.event_type}, Status: ${s.status}`);
        });

        console.log(`\n[3] Checking ledger health as I4CMSP...`);
        const health = await service.checkHealth('I4C');
        console.log('Health check:', JSON.stringify(health, null, 2));

        return { signal, clusterSignals, health };
    } catch (err) {
        console.error('I4C Query Failed:', err.message);
        throw err;
    } finally {
        await service.closeAll();
    }
}

if (require.main === module) {
    main().catch(() => process.exit(1));
}

module.exports = main;
