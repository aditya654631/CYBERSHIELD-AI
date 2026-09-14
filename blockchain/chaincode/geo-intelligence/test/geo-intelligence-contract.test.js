'use strict';

const chai = require('chai');
const chaiAsPromised = require('chai-as-promised');
const sinon = require('sinon');
const sinonChai = require('sinon-chai');

chai.should();
chai.use(chaiAsPromised);
chai.use(sinonChai);
const expect = chai.expect;

const GeoIntelligenceContract = require('../lib/geo-intelligence-contract');

describe('GeoIntelligenceContract Unit Tests', () => {
    let contract;
    let ctx;
    let stub;
    let clientIdentity;
    let mockState;

    beforeEach(() => {
        contract = new GeoIntelligenceContract();
        mockState = new Map();

        stub = {
            getState: sinon.stub().callsFake(async (key) => mockState.get(key) || null),
            putState: sinon.stub().callsFake(async (key, value) => {
                mockState.set(key, value);
            }),
            deleteState: sinon.stub().callsFake(async (key) => {
                mockState.delete(key);
            }),
            createCompositeKey: sinon.stub().callsFake((objectType, attributes) => {
                return `\u0000${objectType}\u0000${attributes.join('\u0000')}\u0000`;
            }),
            splitCompositeKey: sinon.stub().callsFake((compositeKey) => {
                const parts = compositeKey.split('\u0000').filter(p => p.length > 0);
                const objectType = parts[0];
                const attributes = parts.slice(1);
                return { objectType, attributes };
            }),
            getStateByPartialCompositeKey: sinon.stub().callsFake(async (objectType, attributes) => {
                const prefix = `\u0000${objectType}\u0000${attributes.join('\u0000')}`;
                const matchedKeys = [];
                for (const k of mockState.keys()) {
                    if (k.startsWith(prefix)) {
                        matchedKeys.push({ key: k, value: mockState.get(k) });
                    }
                }
                let index = 0;
                return {
                    next: async () => {
                        if (index < matchedKeys.length) {
                            return { value: matchedKeys[index++], done: false };
                        }
                        return { done: true };
                    },
                    close: async () => {}
                };
            }),
            getStateByRange: sinon.stub().callsFake(async (startKey, endKey) => {
                const matched = [];
                for (const [k, v] of mockState.entries()) {
                    if (k >= startKey && k <= endKey) {
                        matched.push({ key: k, value: v });
                    }
                }
                let index = 0;
                return {
                    next: async () => {
                        if (index < matched.length) {
                            return { value: matched[index++], done: false };
                        }
                        return { done: true };
                    },
                    close: async () => {}
                };
            }),
            getHistoryForKey: sinon.stub().callsFake(async (key) => {
                const val = mockState.get(key);
                const historyList = [];
                if (val) {
                    historyList.push({
                        txId: 'tx-mock-history-001',
                        timestamp: { seconds: { low: 1726000000 }, nanos: 0 },
                        isDelete: false,
                        value: val
                    });
                }
                let index = 0;
                return {
                    next: async () => {
                        if (index < historyList.length) {
                            return { value: historyList[index++], done: false };
                        }
                        return { done: true };
                    },
                    close: async () => {}
                };
            }),
            getTxTimestamp: sinon.stub().returns({ seconds: { low: 1726000000 }, nanos: 0 }),
            getTxID: sinon.stub().returns('tx-test-00000001'),
            setEvent: sinon.stub()
        };

        clientIdentity = {
            getMSPID: sinon.stub().returns('BankAMSP')
        };

        ctx = {
            stub,
            clientIdentity
        };
    });

    describe('InitLedger', () => {
        it('should initialize contract metadata successfully', async () => {
            const res = await contract.InitLedger(ctx);
            const parsed = JSON.parse(res);
            expect(parsed.contract).to.equal('GeoIntelligenceContract');
            expect(parsed.schema_version).to.equal('geo-intelligence-v1');
            expect(parsed.status).to.equal('INITIALIZED');
            expect(stub.putState).to.have.been.calledWith('CONTRACT_METADATA');
        });
    });

    describe('SubmitSignal', () => {
        it('should submit a valid BankA ATM withdrawal attempt signal', async () => {
            const payload = {
                event_id: 'EVT-BANKA-001',
                event_type: 'ATM_WITHDRAWAL_ATTEMPT',
                opaque_subject_ref: 'opaque-sub-001',
                cluster_id: 7,
                district: 'NEW_DELHI',
                event_timestamp: '2026-09-13T12:00:00.000Z',
                confidence: 0.85,
                source_reference_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
            };

            const resStr = await contract.SubmitSignal(ctx, JSON.stringify(payload));
            const signal = JSON.parse(resStr);

            expect(signal.event_id).to.equal('EVT-BANKA-001');
            expect(signal.event_type).to.equal('ATM_WITHDRAWAL_ATTEMPT');
            expect(signal.organization_msp).to.equal('BankAMSP');
            expect(signal.cluster_id).to.equal(7);
            expect(signal.district).to.equal('NEW_DELHI');
            expect(signal.status).to.equal('ACTIVE');
            expect(stub.setEvent).to.have.been.calledWith('SignalSubmitted');
        });

        it('should submit a valid LEA confirmed cluster signal with LEAMSP identity', async () => {
            clientIdentity.getMSPID.returns('LEAMSP');

            const payload = {
                event_id: 'EVT-LEA-001',
                event_type: 'LEA_CONFIRMED_CLUSTER',
                opaque_subject_ref: 'opaque-sub-lea-01',
                cluster_id: 3,
                district: 'NORTH_DELHI',
                event_timestamp: '2026-09-13T14:30:00.000Z',
                confidence: 0.95
            };

            const resStr = await contract.SubmitSignal(ctx, JSON.stringify(payload));
            const signal = JSON.parse(resStr);

            expect(signal.event_id).to.equal('EVT-LEA-001');
            expect(signal.organization_msp).to.equal('LEAMSP');
            expect(signal.event_type).to.equal('LEA_CONFIRMED_CLUSTER');
        });

        it('should reject invalid event_type', async () => {
            const payload = {
                event_id: 'EVT-INVALID-TYPE',
                event_type: 'UNSUPPORTED_TYPE',
                opaque_subject_ref: 'opaque-sub-001',
                cluster_id: 7,
                district: 'NEW_DELHI',
                event_timestamp: '2026-09-13T12:00:00.000Z'
            };

            await expect(contract.SubmitSignal(ctx, JSON.stringify(payload)))
                .to.be.rejectedWith(/Permission Denied|not allowed/);
        });

        it('should reject invalid confidence value (> 1.0)', async () => {
            const payload = {
                event_id: 'EVT-INVALID-CONF',
                event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                opaque_subject_ref: 'opaque-sub-001',
                cluster_id: 7,
                district: 'NEW_DELHI',
                event_timestamp: '2026-09-13T12:00:00.000Z',
                confidence: 1.5
            };

            await expect(contract.SubmitSignal(ctx, JSON.stringify(payload)))
                .to.be.rejectedWith(/confidence must be a number between 0.0 and 1.0/);
        });

        it('should reject prohibited PII fields (e.g. phone, account_number, upi_id, aadhaar)', async () => {
            const piiPayload = {
                event_id: 'EVT-PII-TEST',
                event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                opaque_subject_ref: 'opaque-sub-001',
                cluster_id: 7,
                district: 'NEW_DELHI',
                event_timestamp: '2026-09-13T12:00:00.000Z',
                phone: '+919999999999'
            };

            await expect(contract.SubmitSignal(ctx, JSON.stringify(piiPayload)))
                .to.be.rejectedWith(/PII Security Violation: Prohibited field 'phone'/);

            const piiPayload2 = {
                event_id: 'EVT-PII-TEST2',
                event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                opaque_subject_ref: 'opaque-sub-001',
                cluster_id: 7,
                district: 'NEW_DELHI',
                event_timestamp: '2026-09-13T12:00:00.000Z',
                account_number: '123456789012'
            };

            await expect(contract.SubmitSignal(ctx, JSON.stringify(piiPayload2)))
                .to.be.rejectedWith(/PII Security Violation: Prohibited field 'account_number'/);
        });

        it('should handle idempotent duplicate submission of exact same payload', async () => {
            const payload = {
                event_id: 'EVT-IDEMPOTENT-001',
                event_type: 'ATM_WITHDRAWAL_ATTEMPT',
                opaque_subject_ref: 'opaque-sub-idem',
                cluster_id: 5,
                district: 'SOUTH_DELHI',
                event_timestamp: '2026-09-13T10:00:00.000Z',
                confidence: 0.90
            };

            const firstRes = await contract.SubmitSignal(ctx, JSON.stringify(payload));
            const secondRes = await contract.SubmitSignal(ctx, JSON.stringify(payload));

            const parsedSecond = JSON.parse(secondRes);
            expect(parsedSecond.event_id).to.equal('EVT-IDEMPOTENT-001');
            expect(parsedSecond._idempotent_replay).to.equal(true);
        });

        it('should reject duplicate event_id when payload is modified', async () => {
            const payload1 = {
                event_id: 'EVT-DUP-CONFLICT',
                event_type: 'ATM_WITHDRAWAL_ATTEMPT',
                opaque_subject_ref: 'opaque-sub-001',
                cluster_id: 5,
                district: 'SOUTH_DELHI',
                event_timestamp: '2026-09-13T10:00:00.000Z'
            };
            const payload2 = {
                event_id: 'EVT-DUP-CONFLICT',
                event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                opaque_subject_ref: 'opaque-sub-001',
                cluster_id: 8,
                district: 'EAST_DELHI',
                event_timestamp: '2026-09-13T10:00:00.000Z'
            };

            await contract.SubmitSignal(ctx, JSON.stringify(payload1));
            await expect(contract.SubmitSignal(ctx, JSON.stringify(payload2)))
                .to.be.rejectedWith(/Idempotency conflict/);
        });

        it('should reject submission from unknown unauthorized MSP', async () => {
            clientIdentity.getMSPID.returns('UnknownHackerMSP');

            const payload = {
                event_id: 'EVT-UNAUTH-001',
                event_type: 'ATM_WITHDRAWAL_ATTEMPT',
                opaque_subject_ref: 'opaque-sub-001',
                cluster_id: 5,
                district: 'SOUTH_DELHI',
                event_timestamp: '2026-09-13T10:00:00.000Z'
            };

            await expect(contract.SubmitSignal(ctx, JSON.stringify(payload)))
                .to.be.rejectedWith(/Unauthorized MSP/);
        });
    });

    describe('Correction & Revocation & Access Control', () => {
        beforeEach(async () => {
            clientIdentity.getMSPID.returns('BankAMSP');
            const signalPayload = {
                event_id: 'EVT-ORIG-BANKA',
                event_type: 'ATM_WITHDRAWAL_ATTEMPT',
                opaque_subject_ref: 'opaque-sub-corr',
                cluster_id: 2,
                district: 'WEST_DELHI',
                event_timestamp: '2026-09-13T09:00:00.000Z',
                confidence: 0.70
            };
            await contract.SubmitSignal(ctx, JSON.stringify(signalPayload));
        });

        it('should reject cross-bank unauthorized correction (BankB trying to correct BankA signal)', async () => {
            clientIdentity.getMSPID.returns('BankBMSP');
            const corrPayload = {
                cluster_id: 4,
                district: 'CENTRAL_DELHI'
            };

            await expect(contract.CorrectSignal(ctx, 'EVT-ORIG-BANKA', JSON.stringify(corrPayload)))
                .to.be.rejectedWith(/Permission Denied: Organization 'BankBMSP' is not authorized to modify signal owned by 'BankAMSP'/);
        });

        it('should allow original submitter (BankA) to correct its signal', async () => {
            clientIdentity.getMSPID.returns('BankAMSP');
            const corrPayload = {
                event_id: 'CORR-BANKA-001',
                cluster_id: 4,
                district: 'CENTRAL_DELHI',
                confidence: 0.92
            };

            const resStr = await contract.CorrectSignal(ctx, 'EVT-ORIG-BANKA', JSON.stringify(corrPayload));
            const res = JSON.parse(resStr);

            expect(res.target_event.status).to.equal('CORRECTED');
            expect(res.target_event.corrected_by_event_id).to.equal('CORR-BANKA-001');
            expect(res.correction_event.cluster_id).to.equal(4);
            expect(stub.setEvent).to.have.been.calledWith('SignalCorrected');

            // Verify target state in ledger
            const updatedTargetStr = await contract.GetSignal(ctx, 'EVT-ORIG-BANKA');
            const updatedTarget = JSON.parse(updatedTargetStr);
            expect(updatedTarget.status).to.equal('CORRECTED');
        });

        it('should allow I4C to revoke a BankA signal', async () => {
            clientIdentity.getMSPID.returns('I4CMSP');
            const revPayload = {
                event_id: 'REV-I4C-001',
                reason: 'False positive confirmed by fraud analysis'
            };

            const resStr = await contract.RevokeSignal(ctx, 'EVT-ORIG-BANKA', JSON.stringify(revPayload));
            const res = JSON.parse(resStr);

            expect(res.target_event.status).to.equal('REVOKED');
            expect(res.target_event.revoked_by_event_id).to.equal('REV-I4C-001');
            expect(stub.setEvent).to.have.been.calledWith('SignalRevoked');

            // Verify state
            const target = JSON.parse(await contract.GetSignal(ctx, 'EVT-ORIG-BANKA'));
            expect(target.status).to.equal('REVOKED');
        });

        it('should reject correction on an already revoked signal', async () => {
            clientIdentity.getMSPID.returns('I4CMSP');
            await contract.RevokeSignal(ctx, 'EVT-ORIG-BANKA', JSON.stringify({ reason: 'Revoked' }));

            clientIdentity.getMSPID.returns('BankAMSP');
            await expect(contract.CorrectSignal(ctx, 'EVT-ORIG-BANKA', JSON.stringify({ cluster_id: 1 })))
                .to.be.rejectedWith(/Cannot correct a REVOKED signal/);
        });
    });

    describe('Queries (Cluster, TimeWindow, OpaqueSubject, History)', () => {
        beforeEach(async () => {
            clientIdentity.getMSPID.returns('BankAMSP');
            await contract.SubmitSignal(ctx, JSON.stringify({
                event_id: 'EVT-Q-001',
                event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                opaque_subject_ref: 'subject-alpha',
                cluster_id: 7,
                district: 'NEW_DELHI',
                event_timestamp: '2026-09-13T10:00:00.000Z'
            }));

            clientIdentity.getMSPID.returns('BankBMSP');
            await contract.SubmitSignal(ctx, JSON.stringify({
                event_id: 'EVT-Q-002',
                event_type: 'BRANCH_CASHOUT_CONFIRMED',
                opaque_subject_ref: 'subject-beta',
                cluster_id: 7,
                district: 'NEW_DELHI',
                event_timestamp: '2026-09-13T11:00:00.000Z'
            }));

            clientIdentity.getMSPID.returns('LEAMSP');
            await contract.SubmitSignal(ctx, JSON.stringify({
                event_id: 'EVT-Q-003',
                event_type: 'LEA_CONFIRMED_CLUSTER',
                opaque_subject_ref: 'subject-alpha',
                cluster_id: 9,
                district: 'EAST_DELHI',
                event_timestamp: '2026-09-13T15:00:00.000Z'
            }));
        });

        it('should query signals by cluster (cross-bank corroboration)', async () => {
            const resStr = await contract.QuerySignalsByCluster(ctx, 7, false);
            const results = JSON.parse(resStr);
            expect(results).to.have.lengthOf(2);
            const ids = results.map(r => r.event_id);
            expect(ids).to.include('EVT-Q-001');
            expect(ids).to.include('EVT-Q-002');
        });

        it('should query signals by time window', async () => {
            const resStr = await contract.QuerySignalsByTimeWindow(ctx, '2026-09-13T09:30:00.000Z', '2026-09-13T11:30:00.000Z', false);
            const results = JSON.parse(resStr);
            expect(results).to.have.lengthOf(2);
            const ids = results.map(r => r.event_id);
            expect(ids).to.include('EVT-Q-001');
            expect(ids).to.include('EVT-Q-002');
            expect(ids).to.not.include('EVT-Q-003');
        });

        it('should query signals by opaque subject ref', async () => {
            const resStr = await contract.QuerySignalsByOpaqueSubject(ctx, 'subject-alpha', false);
            const results = JSON.parse(resStr);
            expect(results).to.have.lengthOf(2);
            const ids = results.map(r => r.event_id);
            expect(ids).to.include('EVT-Q-001');
            expect(ids).to.include('EVT-Q-003');
        });

        it('should retrieve signal history', async () => {
            const histStr = await contract.GetSignalHistory(ctx, 'EVT-Q-001');
            const history = JSON.parse(histStr);
            expect(history).to.be.an('array');
            expect(history.length).to.be.greaterThan(0);
            expect(history[0].tx_id).to.equal('tx-mock-history-001');
        });
    });
});
