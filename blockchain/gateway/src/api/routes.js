'use strict';

const express = require('express');

function createRouter(geoService, auditService = null) {
    const router = express.Router();

    // Health endpoint (Fabric-verified)
    router.get('/health', async (req, res, next) => {
        try {
            const health = await geoService.checkHealth();
            const statusCode = health.ledger === 'ACCESSIBLE' ? 200 : 503;
            res.status(statusCode).json(health);
        } catch (err) {
            next(err);
        }
    });

    // Query signals by time window
    router.get('/signals/time-window', async (req, res, next) => {
        try {
            const { start, end, include_inactive } = req.query;
            const includeInactive = include_inactive === 'true' || include_inactive === true;
            const signals = await geoService.querySignalsByTimeWindow(start, end, includeInactive);
            res.json({
                success: true,
                count: Array.isArray(signals) ? signals.length : 0,
                signals
            });
        } catch (err) {
            next(err);
        }
    });

    // Query signals by cluster ID
    router.get('/signals/cluster/:clusterId', async (req, res, next) => {
        try {
            const { clusterId } = req.params;
            const includeInactive = req.query.include_inactive === 'true';
            const signals = await geoService.querySignalsByCluster(clusterId, includeInactive);
            res.json({
                success: true,
                cluster_id: Number(clusterId),
                count: Array.isArray(signals) ? signals.length : 0,
                signals
            });
        } catch (err) {
            next(err);
        }
    });

    // Query signals by opaque subject reference
    router.get('/signals/subject/:opaqueSubjectRef', async (req, res, next) => {
        try {
            const { opaqueSubjectRef } = req.params;
            const includeInactive = req.query.include_inactive === 'true';
            const signals = await geoService.querySignalsByOpaqueSubject(opaqueSubjectRef, includeInactive);
            res.json({
                success: true,
                opaque_subject_ref: opaqueSubjectRef,
                count: Array.isArray(signals) ? signals.length : 0,
                signals
            });
        } catch (err) {
            next(err);
        }
    });

    // Get current state of a signal
    router.get('/signals/:eventId/state', async (req, res, next) => {
        try {
            const { eventId } = req.params;
            const state = await geoService.getCurrentSignalState(eventId);
            res.json({
                success: true,
                state
            });
        } catch (err) {
            next(err);
        }
    });

    // Get complete signal history
    router.get('/signals/:eventId/history', async (req, res, next) => {
        try {
            const { eventId } = req.params;
            const history = await geoService.getSignalHistory(eventId);
            res.json({
                success: true,
                event_id: eventId,
                history
            });
        } catch (err) {
            next(err);
        }
    });

    // Get signal by event ID
    router.get('/signals/:eventId', async (req, res, next) => {
        try {
            const { eventId } = req.params;
            const signal = await geoService.getSignal(eventId);
            res.json({
                success: true,
                signal
            });
        } catch (err) {
            next(err);
        }
    });

    // =========================================================================
    // PREDICTION AUDIT ENDPOINTS
    // =========================================================================

    // Anchor a prediction
    router.post('/prediction-audit/anchor', async (req, res, next) => {
        try {
            if (!auditService) {
                return res.status(501).json({ success: false, error: 'Prediction audit service not configured' });
            }
            const result = await auditService.anchorPrediction(req.body);
            res.json({
                success: true,
                ...result
            });
        } catch (err) {
            next(err);
        }
    });

    // Get anchor by prediction ID
    router.get('/prediction-audit/:predictionId', async (req, res, next) => {
        try {
            if (!auditService) {
                return res.status(501).json({ success: false, error: 'Prediction audit service not configured' });
            }
            const { predictionId } = req.params;
            const anchor = await auditService.getPredictionAnchor(predictionId);
            res.json({
                success: true,
                anchor
            });
        } catch (err) {
            next(err);
        }
    });

    // Verify a candidate hash against ledger
    router.post('/prediction-audit/:predictionId/verify-hash', async (req, res, next) => {
        try {
            if (!auditService) {
                return res.status(501).json({ success: false, error: 'Prediction audit service not configured' });
            }
            const { predictionId } = req.params;
            const { candidate_hash } = req.body;
            const verification = await auditService.verifyPredictionHash(predictionId, candidate_hash);
            res.json({
                success: true,
                ...verification
            });
        } catch (err) {
            next(err);
        }
    });

    // Full verification from raw prediction data
    router.post('/prediction-audit/verify-prediction', async (req, res, next) => {
        try {
            if (!auditService) {
                return res.status(501).json({ success: false, error: 'Prediction audit service not configured' });
            }
            const verification = await auditService.verifyPersistedPrediction(req.body);
            res.json({
                success: true,
                ...verification
            });
        } catch (err) {
            next(err);
        }
    });

    // History for prediction anchor
    router.get('/prediction-audit/:predictionId/history', async (req, res, next) => {
        try {
            if (!auditService) {
                return res.status(501).json({ success: false, error: 'Prediction audit service not configured' });
            }
            const { predictionId } = req.params;
            const history = await auditService.getAnchorHistory(predictionId);
            res.json({
                success: true,
                prediction_id: Number(predictionId),
                history
            });
        } catch (err) {
            next(err);
        }
    });

    return router;
}

module.exports = createRouter;
