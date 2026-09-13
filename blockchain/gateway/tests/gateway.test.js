'use strict';

const { expect } = require('chai');
const sinon = require('sinon');
const request = require('supertest');

const { getOrgConfig, listKnownOrgs } = require('../src/config/organizations');
const { validatePIISafety, validateSignalPayload } = require('../src/utils/validation');
const {
    GatewayError,
    ValidationError,
    AuthorizationError,
    NotFoundError,
    FabricUnavailableError
} = require('../src/utils/errors');
const createRouter = require('../src/api/routes');
const express = require('express');

describe('CyberShield Fabric Gateway Test Suite', () => {

    describe('1. Organization Configuration', () => {
        it('should list all 5 consortium organizations', () => {
            const orgs = listKnownOrgs();
            expect(orgs).to.have.members(['BankA', 'BankB', 'BankC', 'I4C', 'LEA']);
        });

        it('should properly configure BankA with MSP, peer endpoint, and TLS certs', () => {
            const config = getOrgConfig('BankA');
            expect(config.mspId).to.equal('BankAMSP');
            expect(config.peerEndpoint).to.include('7051');
            expect(config.peerHostAlias).to.equal('peer0.banka.cybershield.net');
            expect(config.tlsCaPath).to.be.a('string');
            expect(config.certPath).to.be.a('string');
            expect(config.keyPath).to.be.a('string');
        });

        it('should properly configure I4C with MSP, peer endpoint, and TLS certs', () => {
            const config = getOrgConfig('I4C');
            expect(config.mspId).to.equal('I4CMSP');
            expect(config.peerEndpoint).to.include('10051');
            expect(config.peerHostAlias).to.equal('peer0.i4c.cybershield.net');
        });

        it('should throw error when requesting unknown organization', () => {
            expect(() => getOrgConfig('UnknownOrg')).to.throw(/Unknown organization/);
        });
    });

    describe('2. PII Validation & Defense-in-Depth', () => {
        it('should accept privacy-safe signal payload', () => {
            const validPayload = {
                event_id: 'EVT-VALID-001',
                event_type: 'ATM_WITHDRAWAL_CONFIRMED',
                opaque_subject_ref: 'sub-001',
                cluster_id: 7,
                district: 'NEW_DELHI',
                confidence: 0.85
            };
            expect(() => validatePIISafety(validPayload)).to.not.throw();
            expect(() => validateSignalPayload(validPayload)).to.not.throw();
        });

        it('should reject prohibited PII field: victim_name', () => {
            const piiPayload = {
                event_id: 'EVT-PII-001',
                victim_name: 'Aditya Sharma',
                cluster_id: 7
            };
            expect(() => validatePIISafety(piiPayload)).to.throw(ValidationError, /Prohibited field 'victim_name'/);
        });

        it('should reject prohibited PII field: account_number', () => {
            const piiPayload = {
                event_id: 'EVT-PII-002',
                account_number: '123456789012'
            };
            expect(() => validatePIISafety(piiPayload)).to.throw(ValidationError, /Prohibited field 'account_number'/);
        });

        it('should reject prohibited PII field: upi_id', () => {
            const piiPayload = {
                event_id: 'EVT-PII-003',
                upi_id: 'target@okhdfcbank'
            };
            expect(() => validatePIISafety(piiPayload)).to.throw(ValidationError, /Prohibited field 'upi_id'/);
        });

        it('should reject prohibited PII field: aadhaar or pan', () => {
            expect(() => validatePIISafety({ aadhaar: '123412341234' })).to.throw(ValidationError);
            expect(() => validatePIISafety({ pan: 'ABCDE1234F' })).to.throw(ValidationError);
        });

        it('should reject nested PII fields', () => {
            const nestedPayload = {
                event_id: 'EVT-NESTED-001',
                metadata: {
                    user: {
                        phone: '9876543210'
                    }
                }
            };
            expect(() => validatePIISafety(nestedPayload)).to.throw(ValidationError, /Prohibited field 'phone'/);
        });
    });

    describe('3. Error Mapping & Hierarchy', () => {
        it('should properly instantiate structured error types', () => {
            const authErr = new AuthorizationError('Permission denied');
            expect(authErr).to.be.instanceOf(GatewayError);
            expect(authErr.statusCode).to.equal(403);
            expect(authErr.code).to.equal('PERMISSION_DENIED');

            const valErr = new ValidationError('Bad field');
            expect(valErr.statusCode).to.equal(400);

            const notFoundErr = new NotFoundError('Signal not found');
            expect(notFoundErr.statusCode).to.equal(404);

            const unavailErr = new FabricUnavailableError('Peer down');
            expect(unavailErr.statusCode).to.equal(503);
            expect(unavailErr.code).to.equal('FABRIC_UNAVAILABLE');
        });
    });

    describe('4. Express API Routes & Error Handling', () => {
        let app;
        let mockGeoService;

        beforeEach(() => {
            mockGeoService = {
                checkHealth: sinon.stub(),
                querySignalsByTimeWindow: sinon.stub(),
                querySignalsByCluster: sinon.stub(),
                querySignalsByOpaqueSubject: sinon.stub(),
                getCurrentSignalState: sinon.stub(),
                getSignalHistory: sinon.stub(),
                getSignal: sinon.stub()
            };

            app = express();
            app.use(express.json());
            const router = createRouter(mockGeoService);
            app.use('/api/v1/gateway', router);
            app.use('/api/v1', router);

            // Error handler
            app.use((err, req, res, next) => {
                const statusCode = err.statusCode || 500;
                res.status(statusCode).json({
                    success: false,
                    error: {
                        code: err.code || 'INTERNAL_ERROR',
                        message: err.message
                    }
                });
            });
        });

        it('GET /api/v1/gateway/health should return 200 when ledger accessible', async () => {
            mockGeoService.checkHealth.resolves({
                service: 'UP',
                peer: 'REACHABLE',
                channel: 'cyber-intelligence',
                chaincode: 'geo-intelligence',
                ledger: 'ACCESSIBLE',
                identity: 'I4CMSP'
            });

            const res = await request(app).get('/api/v1/gateway/health');
            expect(res.status).to.equal(200);
            expect(res.body.ledger).to.equal('ACCESSIBLE');
            expect(res.body.peer).to.equal('REACHABLE');
        });

        it('GET /api/v1/gateway/health should return 503 when ledger inaccessible', async () => {
            mockGeoService.checkHealth.resolves({
                service: 'DEGRADED',
                peer: 'UNREACHABLE',
                channel: 'cyber-intelligence',
                chaincode: 'geo-intelligence',
                ledger: 'FAIL',
                identity: 'I4CMSP'
            });

            const res = await request(app).get('/api/v1/gateway/health');
            expect(res.status).to.equal(503);
            expect(res.body.ledger).to.equal('FAIL');
        });

        it('GET /api/v1/signals/:eventId should return 200 and signal payload', async () => {
            mockGeoService.getSignal.withArgs('EVT-100').resolves({
                event_id: 'EVT-100',
                cluster_id: 7,
                status: 'ACTIVE'
            });

            const res = await request(app).get('/api/v1/signals/EVT-100');
            expect(res.status).to.equal(200);
            expect(res.body.signal.event_id).to.equal('EVT-100');
        });

        it('GET /api/v1/signals/:eventId should return 404 when signal not found', async () => {
            mockGeoService.getSignal.withArgs('EVT-NONEXISTENT').rejects(new NotFoundError('Signal not found'));

            const res = await request(app).get('/api/v1/signals/EVT-NONEXISTENT');
            expect(res.status).to.equal(404);
            expect(res.body.error.code).to.equal('NOT_FOUND');
        });

        it('GET /api/v1/signals/cluster/:clusterId should return list of signals', async () => {
            mockGeoService.querySignalsByCluster.withArgs('7', false).resolves([
                { event_id: 'EVT-1', cluster_id: 7 },
                { event_id: 'EVT-2', cluster_id: 7 }
            ]);

            const res = await request(app).get('/api/v1/signals/cluster/7');
            expect(res.status).to.equal(200);
            expect(res.body.count).to.equal(2);
            expect(res.body.signals).to.have.length(2);
        });

        it('GET /api/v1/signals/subject/:ref should return matching signals', async () => {
            mockGeoService.querySignalsByOpaqueSubject.withArgs('sub-abc', false).resolves([
                { event_id: 'EVT-1', opaque_subject_ref: 'sub-abc' }
            ]);

            const res = await request(app).get('/api/v1/signals/subject/sub-abc');
            expect(res.status).to.equal(200);
            expect(res.body.signals[0].event_id).to.equal('EVT-1');
        });

        it('GET /api/v1/signals/:eventId/history should return transaction history', async () => {
            mockGeoService.getSignalHistory.withArgs('EVT-1').resolves([
                { tx_id: 'tx1', timestamp: '2026-09-14T00:00:00Z', is_delete: false },
                { tx_id: 'tx2', timestamp: '2026-09-14T01:00:00Z', is_delete: false }
            ]);

            const res = await request(app).get('/api/v1/signals/EVT-1/history');
            expect(res.status).to.equal(200);
            expect(res.body.history).to.have.length(2);
        });
    });
});
