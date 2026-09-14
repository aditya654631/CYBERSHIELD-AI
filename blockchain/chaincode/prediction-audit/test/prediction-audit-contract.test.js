'use strict';

const chai = require('chai');
const chaiAsPromised = require('chai-as-promised');
const sinon = require('sinon');
const sinonChai = require('sinon-chai');

chai.should();
chai.use(chaiAsPromised);
chai.use(sinonChai);
const expect = chai.expect;

const PredictionAuditContract = require('../lib/prediction-audit-contract');

describe('PredictionAuditContract Unit Tests', () => {
    let contract;
    let ctx;
    let stub;
    let clientIdentity;
    let mockState;

    const SAMPLE_HASH = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
    const SAMPLE_COMPLAINT_REF = 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90';

    beforeEach(() => {
        contract = new PredictionAuditContract();
        mockState = new Map();

        stub = {
            getState: sinon.stub().callsFake(async (key) => mockState.get(key) || null),
            putState: sinon.stub().callsFake(async (key, value) => {
                mockState.set(key, value);
            }),
            createCompositeKey: sinon.stub().callsFake((objectType, attributes) => {
                return `\u0000${objectType}\u0000${attributes.join('\u0000')}\u0000`;
            }),
            setEvent: sinon.stub(),
            getTxID: sinon.stub().returns('mock-tx-12345'),
            getTxTimestamp: sinon.stub().returns({ seconds: 1773720000, nanos: 0 }),
            getHistoryForKey: sinon.stub().callsFake(async (key) => {
                const val = mockState.get(key);
                const items = val ? [{ txId: 'mock-tx-12345', timestamp: { seconds: 1773720000, nanos: 0 }, isDelete: false, value: val }] : [];
                let idx = 0;
                return {
                    next: async () => {
                        if (idx < items.length) return { value: items[idx++], done: false };
                        return { done: true };
                    },
                    close: async () => {}
                };
            })
        };

        clientIdentity = {
            getMSPID: sinon.stub().returns('I4CMSP')
        };

        ctx = {
            stub,
            clientIdentity
        };
    });

    it('should initialize the ledger metadata in InitLedger', async () => {
        const resStr = await contract.InitLedger(ctx);
        const res = JSON.parse(resStr);
        expect(res.contract_name).to.equal('prediction-audit');
        expect(res.schema_version).to.equal('prediction-audit-v1');
    });

    it('should anchor a valid prediction as I4CMSP', async () => {
        const payload = {
            prediction_id: 101,
            complaint_reference_hash: SAMPLE_COMPLAINT_REF,
            prediction_hash: SAMPLE_HASH,
            prediction_mode: 'trained_ml',
            location_model_version: 'cashout-location-xgb-v7-compat',
            time_model_version: 'cashout-time-xgb-v3',
            top3_cluster_ids: [7, 8, 12]
        };

        const resStr = await contract.AnchorPrediction(ctx, JSON.stringify(payload));
        const res = JSON.parse(resStr);

        expect(res.prediction_id).to.equal(101);
        expect(res.prediction_hash).to.equal(SAMPLE_HASH);
        expect(res.status).to.equal('ANCHORED');
        expect(res.anchored_by_msp).to.equal('I4CMSP');
        expect(stub.setEvent).to.have.been.calledWith('PredictionAnchored');
    });

    it('should reject anchoring from non-authorized MSP (e.g. BankAMSP)', async () => {
        clientIdentity.getMSPID.returns('BankAMSP');

        const payload = {
            prediction_id: 102,
            complaint_reference_hash: SAMPLE_COMPLAINT_REF,
            prediction_hash: SAMPLE_HASH,
            location_model_version: 'cashout-location-xgb-v7-compat',
            top3_cluster_ids: [7, 8, 12]
        };

        await expect(contract.AnchorPrediction(ctx, JSON.stringify(payload)))
            .to.be.rejectedWith(/Permission Denied: Organization 'BankAMSP' is not authorized/);
    });

    it('should reject payload containing prohibited PII fields', async () => {
        const payload = {
            prediction_id: 103,
            victim_name: 'Aditya Sharma',
            complaint_reference_hash: SAMPLE_COMPLAINT_REF,
            prediction_hash: SAMPLE_HASH,
            location_model_version: 'cashout-location-xgb-v7-compat',
            top3_cluster_ids: [7, 8, 12]
        };

        await expect(contract.AnchorPrediction(ctx, JSON.stringify(payload)))
            .to.be.rejectedWith(/PII Security Violation/);
    });

    it('should reject invalid SHA-256 prediction hash', async () => {
        const payload = {
            prediction_id: 104,
            complaint_reference_hash: SAMPLE_COMPLAINT_REF,
            prediction_hash: 'not-a-valid-sha256',
            location_model_version: 'cashout-location-xgb-v7-compat',
            top3_cluster_ids: [7, 8, 12]
        };

        await expect(contract.AnchorPrediction(ctx, JSON.stringify(payload)))
            .to.be.rejectedWith(/must be a valid 64-character lowercase hexadecimal SHA-256 string/);
    });

    it('should handle identical replay idempotently without creating new anchor', async () => {
        const payload = {
            prediction_id: 105,
            complaint_reference_hash: SAMPLE_COMPLAINT_REF,
            prediction_hash: SAMPLE_HASH,
            location_model_version: 'cashout-location-xgb-v7-compat',
            top3_cluster_ids: [7, 8, 12]
        };

        await contract.AnchorPrediction(ctx, JSON.stringify(payload));
        const replayStr = await contract.AnchorPrediction(ctx, JSON.stringify(payload));
        const replay = JSON.parse(replayStr);

        expect(replay.idempotent).to.equal(true);
        expect(replay.anchor.prediction_hash).to.equal(SAMPLE_HASH);
    });

    it('should reject duplicate anchoring with DIFFERENT hash (tamper protection)', async () => {
        const payload1 = {
            prediction_id: 106,
            complaint_reference_hash: SAMPLE_COMPLAINT_REF,
            prediction_hash: SAMPLE_HASH,
            location_model_version: 'cashout-location-xgb-v7-compat',
            top3_cluster_ids: [7, 8, 12]
        };
        const payload2 = {
            ...payload1,
            prediction_hash: 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        };

        await contract.AnchorPrediction(ctx, JSON.stringify(payload1));
        await expect(contract.AnchorPrediction(ctx, JSON.stringify(payload2)))
            .to.be.rejectedWith(/Tamper Conflict: Prediction '106' is already anchored/);
    });

    it('should verify matching prediction hash correctly in VerifyPredictionHash', async () => {
        const payload = {
            prediction_id: 107,
            complaint_reference_hash: SAMPLE_COMPLAINT_REF,
            prediction_hash: SAMPLE_HASH,
            location_model_version: 'cashout-location-xgb-v7-compat',
            top3_cluster_ids: [7, 8, 12]
        };
        await contract.AnchorPrediction(ctx, JSON.stringify(payload));

        const resStr = await contract.VerifyPredictionHash(ctx, 107, SAMPLE_HASH);
        const res = JSON.parse(resStr);

        expect(res.verified).to.equal(true);
        expect(res.status).to.equal('VERIFIED');
    });

    it('should detect hash mismatch in VerifyPredictionHash when payload has been tampered', async () => {
        const payload = {
            prediction_id: 108,
            complaint_reference_hash: SAMPLE_COMPLAINT_REF,
            prediction_hash: SAMPLE_HASH,
            location_model_version: 'cashout-location-xgb-v7-compat',
            top3_cluster_ids: [7, 8, 12]
        };
        await contract.AnchorPrediction(ctx, JSON.stringify(payload));

        const tamperedHash = '1111111111111111111111111111111111111111111111111111111111111111';
        const resStr = await contract.VerifyPredictionHash(ctx, 108, tamperedHash);
        const res = JSON.parse(resStr);

        expect(res.verified).to.equal(false);
        expect(res.status).to.equal('HASH_MISMATCH');
    });

    it('should return ANCHOR_NOT_FOUND if prediction was never anchored', async () => {
        const resStr = await contract.VerifyPredictionHash(ctx, 9999, SAMPLE_HASH);
        const res = JSON.parse(resStr);

        expect(res.verified).to.equal(false);
        expect(res.status).to.equal('ANCHOR_NOT_FOUND');
    });
});
