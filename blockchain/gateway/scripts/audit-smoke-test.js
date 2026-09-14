'use strict';

const PredictionAuditService = require('../src/services/prediction-audit-service');
const {
    canonicalizePredictionAuditPayload,
    computePredictionHash,
    buildAnchorPayload,
    computeComplaintReference
} = require('../../prediction-audit/hasher');

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

async function runAuditSmokeTest() {
    console.log('===============================================================');
    console.log('PHASE B.5 — PREDICTION AUDIT & TAMPER VERIFICATION SUITE');
    console.log('===============================================================\n');

    const results = {};
    const anchorLatencies = [];
    const verifyLatencies = [];
    const hashLatencies = [];

    const auditServiceI4C = new PredictionAuditService('I4C', 'I4C');
    const auditServiceLEA = new PredictionAuditService('LEA', 'LEA');
    const auditServiceBankA = new PredictionAuditService('BankA', 'BankA');

    const testRunId = Date.now().toString().slice(-6);
    const syntheticPredId = Number(`88${testRunId}`);
    const syntheticComplaint = `CMP-TEST-${testRunId}`;

    const syntheticPrediction = {
        prediction_id: syntheticPredId,
        complaint_number: syntheticComplaint,
        prediction_mode: 'trained_ml',
        model_version: 'cashout-location-xgb-v7-compat',
        time_model_version: 'cashout-time-xgb-v3',
        created_at: new Date().toISOString(),
        predicted_window_start: new Date(Date.now() + 900000).toISOString(),
        predicted_window_end: new Date(Date.now() + 2700000).toISOString(),
        window_label: 'Next 2–4 Hours (operational estimate window)',
        top_locations: [
            { rank: 1, cluster_id: 12, ml_probability: 0.845123, location_name: 'Connaught Place' },
            { rank: 2, cluster_id: 45, ml_probability: 0.654321, location_name: 'Karol Bagh' },
            { rank: 3, cluster_id: 9, ml_probability: 0.432109, location_name: 'Lajpat Nagar' }
        ]
    };

    try {
        // -------------------------------------------------------------
        // STEP 1: Canonicalization & Hash Determinism
        // -------------------------------------------------------------
        console.log('[1] Testing Canonicalization & Deterministic Hash...');
        const hStart = process.hrtime.bigint();
        const { anchorPayload, canonicalPayload, predictionHash } = buildAnchorPayload(syntheticPrediction);
        const hEnd = process.hrtime.bigint();
        const hashDurMs = Number(hEnd - hStart) / 1000000;
        hashLatencies.push(hashDurMs);

        const repeatCanonical = canonicalizePredictionAuditPayload(syntheticPrediction);
        const repeatHash = computePredictionHash(repeatCanonical);
        const isDeterministic = (repeatHash === predictionHash);
        results.canonicalization = 'PASS';
        results.deterministicRepeat = isDeterministic ? 'PASS' : 'FAIL';
        console.log(`  -> Hash: ${predictionHash} (computed in ${hashDurMs.toFixed(3)}ms)`);
        console.log(`  -> Deterministic repeat: ${results.deterministicRepeat}`);

        // -------------------------------------------------------------
        // STEP 2: Top-3 Order Sensitivity
        // -------------------------------------------------------------
        console.log('\n[2] Testing Top-3 Order Sensitivity...');
        const swappedTop3 = [
            syntheticPrediction.top_locations[1], // Karol Bagh rank 2 swapped to 1
            syntheticPrediction.top_locations[0], // Connaught Place rank 1 swapped to 2
            syntheticPrediction.top_locations[2]
        ].map((loc, idx) => ({ ...loc, rank: idx + 1 }));

        const swappedPred = { ...syntheticPrediction, top_locations: swappedTop3 };
        const swappedCanonical = canonicalizePredictionAuditPayload(swappedPred);
        const swappedHash = computePredictionHash(swappedCanonical);

        const orderSensitive = (swappedHash !== predictionHash);
        results.orderSensitivity = orderSensitive ? 'PASS' : 'FAIL';
        console.log(`  -> Swapped hash: ${swappedHash}`);
        console.log(`  -> Order sensitivity: ${results.orderSensitivity}`);

        // -------------------------------------------------------------
        // STEP 3: Unauthorized MSP Anchor Rejection
        // -------------------------------------------------------------
        console.log('\n[3] Testing Unauthorized MSP (BankA) Anchoring Rejection...');
        let bankARejected = false;
        try {
            await auditServiceBankA.anchorPrediction(syntheticPrediction, 'BankA');
        } catch (err) {
            bankARejected = true;
            console.log(`  -> BankA anchor correctly rejected: ${err.message}`);
        }
        results.unauthorizedRejection = bankARejected ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 4: I4C Authorized Anchor Submission
        // -------------------------------------------------------------
        console.log('\n[4] Anchoring Synthetic Prediction via I4C Gateway Client...');
        const aStart = Date.now();
        const anchorRes = await auditServiceI4C.anchorPrediction(syntheticPrediction, 'I4C');
        const aLatency = Date.now() - aStart;
        anchorLatencies.push(aLatency);

        results.i4cAnchor = anchorRes.status === 'COMMITTED' ? 'PASS' : 'FAIL';
        results.fabricTxId = anchorRes.txId;
        console.log(`  -> Anchored successfully! TxID: ${anchorRes.txId}, Status: ${anchorRes.status}, Latency: ${aLatency}ms`);

        // -------------------------------------------------------------
        // STEP 5: Cross-Org Read (LEA querying anchor)
        // -------------------------------------------------------------
        console.log('\n[5] Cross-Org Read: LEA reading prediction anchor from ledger...');
        const vStart = Date.now();
        const leaAnchor = await auditServiceLEA.getPredictionAnchor(syntheticPredId, 'LEA');
        const vLatency = Date.now() - vStart;
        verifyLatencies.push(vLatency);

        const parsedLea = typeof leaAnchor === 'string' ? JSON.parse(leaAnchor) : leaAnchor;
        results.crossOrgRead = (parsedLea.prediction_hash === predictionHash) ? 'PASS' : 'FAIL';
        console.log(`  -> LEA retrieved anchor: prediction_id=${parsedLea.prediction_id}, hash=${parsedLea.prediction_hash} (Latency: ${vLatency}ms)`);

        // -------------------------------------------------------------
        // STEP 6: Ledger Hash Verification (Matching)
        // -------------------------------------------------------------
        console.log('\n[6] Verifying Unaltered Prediction against Ledger Anchor...');
        const verifyRes = await auditServiceLEA.verifyPredictionHash(syntheticPredId, predictionHash, 'LEA');
        results.verificationMatch = (verifyRes.verified === true && verifyRes.status === 'VERIFIED') ? 'PASS' : 'FAIL';
        console.log(`  -> Verification Status: ${verifyRes.status}, Verified: ${verifyRes.verified}`);

        // -------------------------------------------------------------
        // STEP 7: Idempotent Replay
        // -------------------------------------------------------------
        console.log('\n[7] Testing Idempotent Replay (Re-anchoring identical prediction)...');
        const replayRes = await auditServiceI4C.anchorPrediction(syntheticPrediction, 'I4C');
        const isIdempotent = replayRes.anchored_record && (replayRes.anchored_record.idempotent === true || replayRes.anchored_record.prediction_hash === predictionHash);
        results.idempotentReplay = isIdempotent ? 'PASS' : 'FAIL';
        console.log(`  -> Replay result: ${results.idempotentReplay} (idempotent=${isIdempotent})`);

        // -------------------------------------------------------------
        // STEP 8: Changed-Hash Rejection (Tamper Attempt on Anchor)
        // -------------------------------------------------------------
        console.log('\n[8] Testing Changed-Hash Conflict Rejection (Tamper Re-anchor)...');
        const tamperedAnchorPred = {
            ...syntheticPrediction,
            model_version: 'cashout-location-xgb-v4' // altered model
        };
        let tamperRejectionPass = false;
        try {
            await auditServiceI4C.anchorPrediction(tamperedAnchorPred, 'I4C');
        } catch (err) {
            tamperRejectionPass = err.message.includes('Tamper Conflict');
            console.log(`  -> Re-anchor with changed hash correctly rejected: ${err.message}`);
        }
        results.changedHashRejection = tamperRejectionPass ? 'PASS' : 'FAIL';

        // -------------------------------------------------------------
        // STEP 9: Tamper Detection on Read (Altered Payload Fails Verification)
        // -------------------------------------------------------------
        console.log('\n[9] Testing Tamper Detection on Persisted Prediction Verification...');
        const tamperedLocalPred = JSON.parse(JSON.stringify(syntheticPrediction));
        // Tamper: change Rank 1 probability slightly
        tamperedLocalPred.top_locations[0].ml_probability = 0.999999;

        const tamperedCanonical = canonicalizePredictionAuditPayload(tamperedLocalPred);
        const tamperedHash = computePredictionHash(tamperedCanonical);
        console.log(`  -> Original Hash: ${predictionHash}`);
        console.log(`  -> Tampered Hash: ${tamperedHash}`);

        const tamperVerifyRes = await auditServiceLEA.verifyPredictionHash(syntheticPredId, tamperedHash, 'LEA');
        results.tamperDetection = (tamperVerifyRes.verified === false && tamperVerifyRes.status === 'HASH_MISMATCH') ? 'PASS' : 'FAIL';
        console.log(`  -> Tamper Verification Status: ${tamperVerifyRes.status}, Verified: ${tamperVerifyRes.verified}`);

        // -------------------------------------------------------------
        // STEP 10: Anchor History
        // -------------------------------------------------------------
        console.log('\n[10] Retrieving Ledger History for Anchor...');
        const history = await auditServiceLEA.getAnchorHistory(syntheticPredId, 'LEA');
        results.historyCheck = (Array.isArray(history) && history.length >= 1) ? 'PASS' : 'FAIL';
        console.log(`  -> History entries count: ${Array.isArray(history) ? history.length : 0}`);

        // -------------------------------------------------------------
        // STEP 11: Latency Metrics
        // -------------------------------------------------------------
        const anchorMetrics = computePercentiles(anchorLatencies);
        const verifyMetrics = computePercentiles(verifyLatencies);

        console.log('\n===============================================================');
        console.log('SUMMARY RESULTS:');
        console.log(JSON.stringify(results, null, 2));
        console.log(`\nMetrics:`);
        console.log(`- Hash computation: ${hashLatencies[0].toFixed(3)}ms`);
        console.log(`- Anchor median: ${anchorMetrics.median}ms, p95: ${anchorMetrics.p95}ms`);
        console.log(`- Verification median: ${verifyMetrics.median}ms, p95: ${verifyMetrics.p95}ms`);
        console.log('===============================================================');

        return {
            results,
            predictionHash,
            syntheticPredId,
            anchorMetrics,
            verifyMetrics,
            hashDuration: hashLatencies[0]
        };

    } finally {
        await auditServiceI4C.closeAll();
        await auditServiceLEA.closeAll();
        await auditServiceBankA.closeAll();
    }
}

if (require.main === module) {
    runAuditSmokeTest()
        .then(() => process.exit(0))
        .catch(err => {
            console.error('Audit Smoke Test Failed:', err);
            process.exit(1);
        });
}

module.exports = runAuditSmokeTest;
