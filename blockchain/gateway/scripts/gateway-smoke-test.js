'use strict';

const GeoIntelligenceService = require('../src/services/geo-intelligence-service');

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function computePercentiles(arr) {
    if (arr.length === 0) return { median: 0, p95: 0 };
    const sorted = [...arr].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length * 0.5)];
    const p95 = sorted[Math.floor(sorted.length * 0.95)];
    return { median, p95 };
}

async function runSmokeTest() {
    console.log('===============================================================');
    console.log('PHASE B.3 — COMPREHENSIVE FABRIC GATEWAY VERIFICATION SUITE');
    console.log('===============================================================\n');

    const results = {};
    const readLatencies = [];
    const writeLatencies = [];

    const serviceBankA = new GeoIntelligenceService('BankA');
    const serviceBankB = new GeoIntelligenceService('BankB');
    const serviceBankC = new GeoIntelligenceService('BankC');
    const serviceLEA = new GeoIntelligenceService('LEA');
    const serviceI4C = new GeoIntelligenceService('I4C');

    const testRunId = Date.now().toString().slice(-6);
    const evtBankA = `EVT-B3-BANKA-${testRunId}`;
    const evtBankB = `EVT-B3-BANKB-${testRunId}`;
    const evtLEA = `EVT-B3-LEA-${testRunId}`;
    const evtRevoke = `EVT-B3-REV-${testRunId}`;
    const targetCluster = 7;
    const opaqueSubject = `subject-smoke-${testRunId}`;

    try {
        // -------------------------------------------------------------
        // STEP 1: BankA Gateway Submit
        // -------------------------------------------------------------
        console.log(`[1] Testing BankA Gateway Submit (${evtBankA})...`);
        const signalA = {
            event_id: evtBankA,
            event_type: 'ATM_WITHDRAWAL_ATTEMPT',
            opaque_subject_ref: opaqueSubject,
            cluster_id: targetCluster,
            district: 'NEW_DELHI',
            event_timestamp: new Date().toISOString(),
            confidence: 0.85,
            source_reference_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
        };

        const resA = await serviceBankA.submitSignal(signalA, 'BankA');
        writeLatencies.push(resA.latencyMs);
        console.log(`  -> BankA submitted successfully. TxId: ${resA.txId}, Status: ${resA.status}, Latency: ${resA.latencyMs}ms`);
        results.bankASubmit = resA.status === 'COMMITTED' ? 'PASS' : 'FAIL';
        results.transactionCommitted = resA.status === 'COMMITTED' ? 'YES' : 'NO';

        // -------------------------------------------------------------
        // STEP 2: Cross-Org Query via I4C Gateway
        // -------------------------------------------------------------
        console.log(`\n[2] Testing Cross-Org Query via I4C Gateway (${evtBankA})...`);
        const tStartRead1 = Date.now();
        const readA = await serviceI4C.getSignal(evtBankA, 'I4C');
        const tRead1 = Date.now() - tStartRead1;
        readLatencies.push(tRead1);

        console.log(`  -> I4C read successfully: ID=${readA.event_id}, Origin=${readA.organization_msp}, Status=${readA.status}, Latency=${tRead1}ms`);
        results.i4cRead = (readA.event_id === evtBankA && readA.organization_msp === 'BankAMSP' && readA.status === 'ACTIVE') ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 3: BankB Corroboration Submission
        // -------------------------------------------------------------
        console.log(`\n[3] Testing BankB Gateway Submit (${evtBankB}) for Cluster ${targetCluster}...`);
        const signalB = {
            event_id: evtBankB,
            event_type: 'ATM_WITHDRAWAL_CONFIRMED',
            opaque_subject_ref: `subject-bankb-${testRunId}`,
            cluster_id: targetCluster,
            district: 'NEW_DELHI',
            event_timestamp: new Date().toISOString(),
            confidence: 0.89,
            source_reference_hash: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90'
        };

        const resB = await serviceBankB.submitSignal(signalB, 'BankB');
        writeLatencies.push(resB.latencyMs);
        console.log(`  -> BankB submitted successfully. TxId: ${resB.txId}, Status: ${resB.status}, Latency: ${resB.latencyMs}ms`);
        results.bankBSubmit = resB.status === 'COMMITTED' ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 4: Cluster Query via I4C Gateway
        // -------------------------------------------------------------
        console.log(`\n[4] Querying Cluster ${targetCluster} signals via I4C Gateway...`);
        const tStartCluster = Date.now();
        const clusterSignals = await serviceI4C.querySignalsByCluster(targetCluster, false, 'I4C');
        const tCluster = Date.now() - tStartCluster;
        readLatencies.push(tCluster);

        const foundA = clusterSignals.find(s => s.event_id === evtBankA);
        const foundB = clusterSignals.find(s => s.event_id === evtBankB);
        console.log(`  -> Cluster query found ${clusterSignals.length} items. BankA found: ${Boolean(foundA)}, BankB found: ${Boolean(foundB)}, Latency: ${tCluster}ms`);
        results.clusterQuery = (foundA && foundB) ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 5: LEA Gateway Submission
        // -------------------------------------------------------------
        console.log(`\n[5] Testing LEA Gateway Submit (${evtLEA})...`);
        const signalLEA = {
            event_id: evtLEA,
            event_type: 'LEA_CONFIRMED_CLUSTER',
            opaque_subject_ref: `subject-lea-${testRunId}`,
            cluster_id: targetCluster,
            district: 'NEW_DELHI',
            event_timestamp: new Date().toISOString(),
            confidence: 0.96,
            source_reference_hash: '9f8e7d6c5b4a392817162534435261709f8e7d6c5b4a39281716253443526170'
        };

        const resLEA = await serviceLEA.submitSignal(signalLEA, 'LEA');
        writeLatencies.push(resLEA.latencyMs);
        console.log(`  -> LEA submitted successfully. TxId: ${resLEA.txId}, Status: ${resLEA.status}, Latency: ${resLEA.latencyMs}ms`);
        results.leaSubmit = resLEA.status === 'COMMITTED' ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 6: Authorization Enforcement: BankC attempts CorrectSignal on BankA signal
        // -------------------------------------------------------------
        console.log(`\n[6] Testing Chaincode Authorization Enforcement (BankC modifying BankA signal)...`);
        const unauthorizedCorrection = {
            event_id: `CORR-${evtBankA}`,
            opaque_subject_ref: opaqueSubject,
            cluster_id: targetCluster,
            district: 'NEW_DELHI',
            event_timestamp: new Date().toISOString(),
            confidence: 0.90,
            source_reference_hash: '1111111111111111111111111111111111111111111111111111111111111111'
        };

        let authRejected = false;
        let chaincodeEnforced = false;
        try {
            await serviceBankC.correctSignal(evtBankA, unauthorizedCorrection, 'BankC');
        } catch (err) {
            console.log(`  -> Rejection captured: [${err.name}] ${err.message}`);
            authRejected = true;
            if (err.message.includes('not authorized') || err.message.includes('BankAMSP') || err.message.includes('Permission Denied')) {
                chaincodeEnforced = true;
            }
        }
        // Verify original state preserved
        const checkStateA = await serviceI4C.getSignal(evtBankA, 'I4C');
        const statePreserved = checkStateA.status === 'ACTIVE';

        results.bankCUnauthorized = authRejected ? 'REJECTED' : 'FAIL';
        results.chaincodeEnforced = chaincodeEnforced ? 'YES' : 'NO';
        results.statePreserved = statePreserved ? 'YES' : 'NO';

        // -------------------------------------------------------------
        // STEP 7: Idempotency Verification
        // -------------------------------------------------------------
        console.log(`\n[7] Testing Idempotency (Replaying BankA identical signal)...`);
        const replayRes = await serviceBankA.submitSignal(signalA, 'BankA');
        console.log(`  -> Replay result: TxId: ${replayRes.txId}, Status: ${replayRes.status}`);
        const replaySignal = await serviceI4C.getSignal(evtBankA, 'I4C');
        const idempotent = (replaySignal.event_id === evtBankA && replaySignal.status === 'ACTIVE');
        results.identicalReplay = idempotent ? 'IDEMPOTENT' : 'FAIL';

        console.log(`  -> Testing Modified Duplicate Rejection...`);
        const modifiedSignalA = { ...signalA, confidence: 0.12 };
        let modRejected = false;
        try {
            await serviceBankA.submitSignal(modifiedSignalA, 'BankA');
        } catch (err) {
            console.log(`  -> Modified duplicate correctly rejected: ${err.message}`);
            modRejected = true;
        }
        results.modifiedDuplicate = modRejected ? 'REJECTED' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 8: Authorized Correction
        // -------------------------------------------------------------
        console.log(`\n[8] Testing Authorized Correction by BankA...`);
        const authorizedCorrection = {
            event_id: `CORR-AUTH-${evtBankA}`,
            opaque_subject_ref: opaqueSubject,
            cluster_id: targetCluster,
            district: 'NEW_DELHI',
            event_timestamp: new Date().toISOString(),
            confidence: 0.92,
            source_reference_hash: '2222222222222222222222222222222222222222222222222222222222222222'
        };

        const resCorr = await serviceBankA.correctSignal(evtBankA, authorizedCorrection, 'BankA');
        writeLatencies.push(resCorr.latencyMs);
        console.log(`  -> Correction committed: TxId: ${resCorr.txId}`);

        const signalAfterCorr = await serviceI4C.getSignal(evtBankA, 'I4C');
        const corrSignalQuery = await serviceI4C.getSignal(`CORR-AUTH-${evtBankA}`, 'I4C');
        const corrSuccess = (signalAfterCorr.status === 'CORRECTED' && corrSignalQuery.event_id === `CORR-AUTH-${evtBankA}`);
        results.correction = corrSuccess ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 9: Authorized Revocation
        // -------------------------------------------------------------
        console.log(`\n[9] Testing Authorized Revocation...`);
        const signalToRevoke = {
            event_id: evtRevoke,
            event_type: 'ATM_WITHDRAWAL_ATTEMPT',
            opaque_subject_ref: `subject-rev-${testRunId}`,
            cluster_id: 8,
            district: 'CENTRAL_DELHI',
            event_timestamp: new Date().toISOString(),
            confidence: 0.75,
            source_reference_hash: '3333333333333333333333333333333333333333333333333333333333333333'
        };
        await serviceBankA.submitSignal(signalToRevoke, 'BankA');
        const resRev = await serviceBankA.revokeSignal(evtRevoke, { reason: 'Test revocation via B.3 Gateway' }, 'BankA');
        writeLatencies.push(resRev.latencyMs);

        const stateAfterRev = await serviceI4C.getSignal(evtRevoke, 'I4C');
        const cluster8Signals = await serviceI4C.querySignalsByCluster(8, false, 'I4C');
        const revokedExcludedFromCluster = !cluster8Signals.some(s => s.event_id === evtRevoke);
        const revocationSuccess = (stateAfterRev.status === 'REVOKED' && revokedExcludedFromCluster);
        results.revocation = revocationSuccess ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 10: Time-Window Query
        // -------------------------------------------------------------
        console.log(`\n[10] Testing QuerySignalsByTimeWindow...`);
        const startTime = new Date(Date.now() - 3600000).toISOString();
        const endTime = new Date(Date.now() + 3600000).toISOString();
        const tStartTimeWin = Date.now();
        const timeWindowSignals = await serviceI4C.querySignalsByTimeWindow(startTime, endTime, false, 'I4C');
        const tTimeWin = Date.now() - tStartTimeWin;
        readLatencies.push(tTimeWin);

        console.log(`  -> Time-window query found ${timeWindowSignals.length} records. Latency: ${tTimeWin}ms`);
        results.timeWindowQuery = (Array.isArray(timeWindowSignals) && timeWindowSignals.length > 0) ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 11: Opaque Subject Query
        // -------------------------------------------------------------
        console.log(`\n[11] Testing QuerySignalsByOpaqueSubject (${opaqueSubject})...`);
        const tStartSubj = Date.now();
        const subjectSignals = await serviceI4C.querySignalsByOpaqueSubject(opaqueSubject, true, 'I4C');
        const tSubj = Date.now() - tStartSubj;
        readLatencies.push(tSubj);

        console.log(`  -> Subject query returned ${subjectSignals.length} records. Latency: ${tSubj}ms`);
        const foundSubjectSignal = subjectSignals.find(s => s.event_id === evtBankA || s.event_id === `CORR-AUTH-${evtBankA}`);
        results.opaqueSubjectQuery = (Array.isArray(subjectSignals) && Boolean(foundSubjectSignal)) ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 12: History Query
        // -------------------------------------------------------------
        console.log(`\n[12] Testing GetSignalHistory (${evtBankA})...`);
        const tStartHist = Date.now();
        const historyEntries = await serviceI4C.getSignalHistory(evtBankA, 'I4C');
        const tHist = Date.now() - tStartHist;
        readLatencies.push(tHist);

        console.log(`  -> History entries count: ${historyEntries.length}. Latency: ${tHist}ms`);
        results.history = (Array.isArray(historyEntries) && historyEntries.length >= 2) ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // Performance Baseline
        // -------------------------------------------------------------
        const readStats = computePercentiles(readLatencies);
        const writeStats = computePercentiles(writeLatencies);

        results.medianReadLatency = `${readStats.median}ms`;
        results.p95ReadLatency = `${readStats.p95}ms`;
        results.medianWriteLatency = `${writeStats.median}ms`;
        results.p95WriteLatency = `${writeStats.p95}ms`;

        console.log('\n---------------------------------------------------------------');
        console.log('SUMMARY OF SMOKE TEST RESULTS:');
        console.log(JSON.stringify(results, null, 2));
        console.log('---------------------------------------------------------------\n');

        return results;

    } finally {
        await Promise.all([
            serviceBankA.closeAll(),
            serviceBankB.closeAll(),
            serviceBankC.closeAll(),
            serviceLEA.closeAll(),
            serviceI4C.closeAll()
        ]);
    }
}

if (require.main === module) {
    runSmokeTest()
        .then(() => process.exit(0))
        .catch(err => {
            console.error('Smoke test aborted with error:', err);
            process.exit(1);
        });
}

module.exports = runSmokeTest;
