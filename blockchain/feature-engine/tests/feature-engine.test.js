'use strict';

const { expect } = require('chai');
const sinon = require('sinon');
const { validateFeatureRequest, InputValidationError, FabricUnavailableError } = require('../src/validation');
const { normalizeSignalsAtReference } = require('../src/signal-normalizer');
const { partitionSignalsByWindow } = require('../src/temporal-window');
const { buildClusterFeatureVector } = require('../src/cluster-feature-builder');
const FeatureEngine = require('../src/feature-engine');

describe('CyberShield Blockchain Feature Engine — Unit Test Suite', () => {

    const T_REF_STR = '2026-09-14T12:00:00.000Z';
    const T_REF = Date.parse(T_REF_STR);

    describe('1. Input Contract & Anti-PII Validation', () => {
        it('should accept valid cluster, reference timestamp, and opaque subject', () => {
            const input = {
                clusterId: 7,
                referenceTimestamp: T_REF_STR,
                opaqueSubjectRef: 'opaque-subj-001'
            };
            const validated = validateFeatureRequest(input);
            expect(validated.clusterId).to.equal(7);
            expect(validated.refTimeMs).to.equal(T_REF);
            expect(validated.opaqueSubjectRef).to.equal('opaque-subj-001');
        });

        it('should throw InputValidationError if clusterId is missing', () => {
            expect(() => validateFeatureRequest({ referenceTimestamp: T_REF_STR }))
                .to.throw(InputValidationError, /clusterId is required/);
        });

        it('should throw InputValidationError if referenceTimestamp is invalid', () => {
            expect(() => validateFeatureRequest({ clusterId: 7, referenceTimestamp: 'not-a-date' }))
                .to.throw(InputValidationError, /valid ISO-8601/);
        });

        it('should reject prohibited PII in opaqueSubjectRef (e.g. phone, upi, account)', () => {
            expect(() => validateFeatureRequest({
                clusterId: 7,
                referenceTimestamp: T_REF_STR,
                opaqueSubjectRef: 'victim_phone_9876543210'
            })).to.throw(InputValidationError, /PII Defense Violation/);
        });
    });

    describe('2. Anti-Leakage & Temporal Filtering', () => {
        it('should exclude future signals where event_timestamp > referenceTimestamp', () => {
            const rawSignals = [
                {
                    event_id: 'EVT-PAST-1',
                    event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                    event_timestamp: new Date(T_REF - 1800000).toISOString(), // 30 min ago
                    status: 'ACTIVE'
                },
                {
                    event_id: 'EVT-FUTURE-1',
                    event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                    event_timestamp: new Date(T_REF + 3600000).toISOString(), // 1 hour in future
                    status: 'ACTIVE'
                }
            ];

            const res = normalizeSignalsAtReference(rawSignals, T_REF);
            expect(res.futureExcludedCount).to.equal(1);
            expect(res.activeSignals).to.have.length(1);
            expect(res.activeSignals[0].event_id).to.equal('EVT-PAST-1');
        });

        it('should partition signals strictly into lookback windows (1h, 6h, 24h, 7d, 30d)', () => {
            const signals = [
                { event_id: 'S-30m', eventTimeMs: T_REF - (30 * 60 * 1000) },
                { event_id: 'S-3h',  eventTimeMs: T_REF - (3 * 60 * 60 * 1000) },
                { event_id: 'S-12h', eventTimeMs: T_REF - (12 * 60 * 60 * 1000) },
                { event_id: 'S-3d',  eventTimeMs: T_REF - (3 * 24 * 60 * 60 * 1000) },
                { event_id: 'S-15d', eventTimeMs: T_REF - (15 * 24 * 60 * 60 * 1000) }
            ];

            const win = partitionSignalsByWindow(signals, T_REF);
            expect(win['1h'].map(s => s.event_id)).to.deep.equal(['S-30m']);
            expect(win['6h'].map(s => s.event_id)).to.deep.equal(['S-30m', 'S-3h']);
            expect(win['24h'].map(s => s.event_id)).to.deep.equal(['S-30m', 'S-3h', 'S-12h']);
            expect(win['7d'].map(s => s.event_id)).to.deep.equal(['S-30m', 'S-3h', 'S-12h', 'S-3d']);
            expect(win['30d'].map(s => s.event_id)).to.deep.equal(['S-30m', 'S-3h', 'S-12h', 'S-3d', 'S-15d']);
        });
    });

    describe('3. Historical As-Of State Resolution (Revocation & Correction)', () => {
        it('should treat a signal revoked in the future as ACTIVE at an earlier reference time', () => {
            const tSignal = T_REF - 3600000; // 1 hour ago
            const tRevocation = T_REF + 1800000; // 30 min in future

            const rawSignals = [
                {
                    event_id: 'EVT-REV-LATER',
                    event_type: 'ATM_WITHDRAWAL_ATTEMPT',
                    event_timestamp: new Date(tSignal).toISOString(),
                    submitted_at: new Date(tSignal).toISOString(),
                    status: 'REVOKED',
                    revoked_by_event_id: 'REV-EVENT-1'
                },
                {
                    event_id: 'REV-EVENT-1',
                    event_type: 'SIGNAL_REVOKED',
                    event_timestamp: new Date(tRevocation).toISOString(),
                    submitted_at: new Date(tRevocation).toISOString(),
                    status: 'REVOKED'
                }
            ];

            const res = normalizeSignalsAtReference(rawSignals, T_REF);
            // REV-EVENT-1 is excluded because it is in the future
            expect(res.futureExcludedCount).to.equal(1);
            // At T_REF, EVT-REV-LATER had not yet been revoked!
            expect(res.activeSignals).to.have.length(1);
            expect(res.activeSignals[0].event_id).to.equal('EVT-REV-LATER');
            expect(res.activeSignals[0].status).to.equal('ACTIVE');
        });

        it('should exclude a signal if revoked before the reference time', () => {
            const tSignal = T_REF - (3 * 3600000); // 3 hours ago
            const tRevocation = T_REF - (1 * 3600000); // 1 hour ago

            const rawSignals = [
                {
                    event_id: 'EVT-REV-PAST',
                    event_type: 'ATM_WITHDRAWAL_ATTEMPT',
                    event_timestamp: new Date(tSignal).toISOString(),
                    submitted_at: new Date(tSignal).toISOString(),
                    status: 'REVOKED',
                    revoked_by_event_id: 'REV-EVENT-PAST'
                },
                {
                    event_id: 'REV-EVENT-PAST',
                    event_type: 'SIGNAL_REVOKED',
                    event_timestamp: new Date(tRevocation).toISOString(),
                    submitted_at: new Date(tRevocation).toISOString(),
                    status: 'REVOKED'
                }
            ];

            const res = normalizeSignalsAtReference(rawSignals, T_REF);
            expect(res.futureExcludedCount).to.equal(0);
            expect(res.activeSignals).to.have.length(0); // Excluded from active intelligence
            expect(res.revokedExcludedCount).to.be.greaterThan(0);
        });
    });

    describe('4. Feature Builder Computations & Multi-Org Attestation', () => {
        it('should correctly compute distinct orgs, distinct banks, and multi-org attestation', () => {
            const activeSignals = [
                {
                    event_id: 'E1',
                    event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                    organization_msp: 'BankAMSP',
                    eventTimeMs: T_REF - 1800000, // 30 min ago
                    confidence: 0.80
                },
                {
                    event_id: 'E2',
                    event_type: 'ATM_WITHDRAWAL_ATTEMPT',
                    organization_msp: 'BankBMSP',
                    eventTimeMs: T_REF - 900000, // 15 min ago
                    confidence: 0.90
                },
                {
                    event_id: 'E3',
                    event_type: 'LEA_CONFIRMED_CLUSTER',
                    organization_msp: 'LEAMSP',
                    eventTimeMs: T_REF - 300000, // 5 min ago
                    confidence: 1.00
                }
            ];

            const features = buildClusterFeatureVector({
                clusterId: 7,
                refTimeMs: T_REF,
                activeClusterSignals: activeSignals,
                allClusterSignalsAtRef: activeSignals
            });

            expect(features.verified_cashouts_1h).to.equal(1);
            expect(features.withdrawal_attempts_1h).to.equal(1);
            expect(features.lea_confirmations_6h).to.equal(1);

            // 3 distinct orgs: BankA, BankB, LEA
            expect(features.distinct_orgs_1h).to.equal(3);
            // 2 distinct banks: BankA, BankB (LEA is not a bank)
            expect(features.distinct_banks_1h).to.equal(2);

            // Multi-org attestation >= 2 orgs
            expect(features.multi_org_attestation_1h).to.equal(3);
            expect(features.has_multi_org_attestation_1h).to.equal(1);

            // Confidence
            expect(features.mean_signal_confidence_1h).to.equal(0.90);
            expect(features.max_signal_confidence_1h).to.equal(1.00);

            // Recency (latest is E3, 5 minutes ago)
            expect(features.latest_signal_age_minutes).to.equal(5.0);
            expect(features.latest_lea_confirmation_age_minutes).to.equal(5.0);
            expect(features.latest_verified_cashout_age_minutes).to.equal(30.0);
        });

        it('should return sentinel -1 for missing recency events and 0 for missing counts', () => {
            const features = buildClusterFeatureVector({
                clusterId: 99,
                refTimeMs: T_REF,
                activeClusterSignals: [],
                allClusterSignalsAtRef: []
            });

            expect(features.verified_cashouts_1h).to.equal(0);
            expect(features.distinct_orgs_1h).to.equal(0);
            expect(features.has_multi_org_attestation_1h).to.equal(0);
            expect(features.mean_signal_confidence_1h).to.equal(0.0);
            expect(features.latest_signal_age_minutes).to.equal(-1);
            expect(features.latest_verified_cashout_age_minutes).to.equal(-1);
            expect(features.latest_lea_confirmation_age_minutes).to.equal(-1);
            expect(features.subject_features_available).to.equal(0);
        });
    });

    describe('5. FeatureEngine API & Determinism', () => {
        it('should produce identical feature vectors given identical input and mock ledger state', async () => {
            const mockGeoService = {
                querySignalsByCluster: sinon.stub().resolves([
                    {
                        event_id: 'EVT-DET-1',
                        event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                        organization_msp: 'BankAMSP',
                        cluster_id: 7,
                        event_timestamp: new Date(T_REF - 1800000).toISOString(),
                        confidence: 0.85,
                        status: 'ACTIVE'
                    }
                ]),
                querySignalsByOpaqueSubject: sinon.stub().resolves([])
            };

            const engine = new FeatureEngine({ geoService: mockGeoService });

            const res1 = await engine.buildClusterFeatures({ clusterId: 7, referenceTimestamp: T_REF_STR });
            const res2 = await engine.buildClusterFeatures({ clusterId: 7, referenceTimestamp: T_REF_STR });

            expect(res1.features).to.deep.equal(res2.features);
            expect(res1.features.verified_cashouts_1h).to.equal(1);
            expect(res1.provenance.active_event_count).to.equal(1);
        });

        it('should preserve candidate ordering in buildCandidateFeatureMatrix', async () => {
            const mockGeoService = {
                querySignalsByCluster: sinon.stub().callsFake(async (cid) => [
                    {
                        event_id: `EVT-${cid}`,
                        event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                        organization_msp: 'BankAMSP',
                        cluster_id: Number(cid),
                        event_timestamp: new Date(T_REF - 1800000).toISOString(),
                        confidence: 0.85,
                        status: 'ACTIVE'
                    }
                ]),
                querySignalsByOpaqueSubject: sinon.stub().resolves([])
            };

            const engine = new FeatureEngine({ geoService: mockGeoService });
            const candidateIds = [7, 2, 14, 25, 1, 9];

            const batch = await engine.buildCandidateFeatureMatrix({
                clusterIds: candidateIds,
                referenceTimestamp: T_REF_STR
            });

            expect(batch.candidate_count).to.equal(6);
            const returnedOrder = batch.matrix.map(m => m.cluster_id);
            expect(returnedOrder).to.deep.equal(candidateIds);
        });

        it('should throw FabricUnavailableError truthfully when gateway fails', async () => {
            const mockGeoService = {
                querySignalsByCluster: sinon.stub().rejects({
                    name: 'FabricUnavailableError',
                    code: 'FABRIC_UNAVAILABLE',
                    statusCode: 503,
                    message: 'Connect ECONNREFUSED'
                })
            };

            const engine = new FeatureEngine({ geoService: mockGeoService });

            try {
                await engine.buildClusterFeatures({ clusterId: 7, referenceTimestamp: T_REF_STR });
                expect.fail('Should have thrown FabricUnavailableError');
            } catch (err) {
                expect(err.code).to.equal('FABRIC_UNAVAILABLE');
                expect(err.statusCode).to.equal(503);
            }
        });
    });
});
