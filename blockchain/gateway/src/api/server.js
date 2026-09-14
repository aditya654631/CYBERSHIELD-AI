'use strict';

require('dotenv').config();
const express = require('express');
const GeoIntelligenceService = require('../services/geo-intelligence-service');
const PredictionAuditService = require('../services/prediction-audit-service');
const createRouter = require('./routes');
const { GatewayError } = require('../utils/errors');

const app = express();
app.use(express.json());

const geoService = new GeoIntelligenceService('I4C');
const auditService = new PredictionAuditService('I4C', 'LEA');

// Root process health check
app.get('/health', (req, res) => {
    res.json({
        status: 'UP',
        service: 'CyberShield AI Fabric Gateway',
        timestamp: new Date().toISOString()
    });
});

// Service token authentication middleware
const authenticateService = (req, res, next) => {
    const requiredToken = process.env.GATEWAY_AUTH_TOKEN;
    // If no token is configured in environment, allow (dev mode)
    if (!requiredToken || requiredToken.trim() === '') {
        return next();
    }

    // Public health checks
    const p = req.path;
    if (p === '/health' || p.endsWith('/health')) {
        return next();
    }

    // Check X-API-Key or Authorization Bearer header
    const apiKey = req.headers['x-api-key'];
    let bearerToken = null;
    const authHeader = req.headers['authorization'];
    if (authHeader && authHeader.startsWith('Bearer ')) {
        bearerToken = authHeader.substring(7).trim();
    }

    const suppliedToken = apiKey || bearerToken;
    if (!suppliedToken || suppliedToken !== requiredToken) {
        return res.status(401).json({
            success: false,
            error: {
                code: 'UNAUTHORIZED',
                message: 'Invalid or missing Gateway service authentication token'
            }
        });
    }

    next();
};

app.use(authenticateService);

// Mount routes
const gatewayRouter = createRouter(geoService, auditService);
app.use('/api/v1/gateway', gatewayRouter);
app.use('/api/v1', gatewayRouter);

// Centralized error handling
app.use((err, req, res, next) => {
    console.error('[Gateway Error]', err);
    const statusCode = err.statusCode || 500;
    const code = err.code || 'INTERNAL_SERVER_ERROR';

    res.status(statusCode).json({
        success: false,
        error: {
            code,
            message: err.message,
            details: err.details || null
        }
    });
});

const PORT = process.env.GATEWAY_PORT || 4000;
const HOST = process.env.GATEWAY_HOST || '0.0.0.0';

let server = null;
if (require.main === module) {
    server = app.listen(PORT, HOST, () => {
        console.log(`[CyberShield Fabric Gateway] Service listening on http://${HOST}:${PORT}`);
    });

    const shutdown = async () => {
        console.log('[CyberShield Fabric Gateway] Shutting down...');
        await geoService.closeAll();
        await auditService.closeAll();
        if (server) {
            server.close(() => process.exit(0));
        } else {
            process.exit(0);
        }
    };

    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
}

module.exports = {
    app,
    geoService,
    auditService
};
