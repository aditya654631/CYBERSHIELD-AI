'use strict';

require('dotenv').config();
const express = require('express');
const GeoIntelligenceService = require('../services/geo-intelligence-service');
const createRouter = require('./routes');
const { GatewayError } = require('../utils/errors');

const app = express();
app.use(express.json());

const geoService = new GeoIntelligenceService('I4C');

// Root process health check
app.get('/health', (req, res) => {
    res.json({
        status: 'UP',
        service: 'CyberShield AI Fabric Gateway',
        timestamp: new Date().toISOString()
    });
});

// Mount routes
const gatewayRouter = createRouter(geoService);
app.use('/api/v1/gateway', gatewayRouter);
app.use('/api/v1', gatewayRouter);

// Centralized error handling
app.use((err, req, res, next) => {
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
    geoService
};
