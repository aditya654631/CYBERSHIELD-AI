'use strict';

class GatewayError extends Error {
    constructor(message, code = 'GATEWAY_ERROR', statusCode = 500, details = null) {
        super(message);
        this.name = this.constructor.name;
        this.code = code;
        this.statusCode = statusCode;
        this.details = details;
    }
}

class ValidationError extends GatewayError {
    constructor(message, details = null) {
        super(message, 'VALIDATION_ERROR', 400, details);
    }
}

class AuthorizationError extends GatewayError {
    constructor(message, details = null) {
        super(message, 'PERMISSION_DENIED', 403, details);
    }
}

class NotFoundError extends GatewayError {
    constructor(message, details = null) {
        super(message, 'NOT_FOUND', 404, details);
    }
}

class FabricUnavailableError extends GatewayError {
    constructor(message, details = null) {
        super(message, 'FABRIC_UNAVAILABLE', 503, details);
    }
}

module.exports = {
    GatewayError,
    ValidationError,
    AuthorizationError,
    NotFoundError,
    FabricUnavailableError
};
