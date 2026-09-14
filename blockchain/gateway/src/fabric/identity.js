'use strict';

const fs = require('fs');
const crypto = require('crypto');
const { signers } = require('@hyperledger/fabric-gateway');

/**
 * Loads an X.509 certificate for Fabric Gateway client identity.
 * @param {string} certPath Path to PEM certificate
 * @param {string} mspId Member Services Provider ID
 * @returns {{ mspId: string, credentials: Uint8Array }}
 */
function loadIdentity(certPath, mspId) {
    if (!certPath) {
        throw new Error('Certificate path is required.');
    }
    if (!fs.existsSync(certPath)) {
        throw new Error(`Certificate file not found at path: ${certPath}`);
    }
    if (!mspId) {
        throw new Error('MSP ID is required.');
    }

    const credentials = fs.readFileSync(certPath);
    return {
        mspId,
        credentials
    };
}

/**
 * Loads a private key and creates a private key signer for Fabric Gateway.
 * Never logs or exposes private key bytes.
 * @param {string} keyPath Path to PEM private key
 * @returns {import('@hyperledger/fabric-gateway').Signer}
 */
function loadSigner(keyPath) {
    if (!keyPath) {
        throw new Error('Private key path is required.');
    }
    if (!fs.existsSync(keyPath)) {
        throw new Error(`Private key file not found at path: ${keyPath}`);
    }

    const privateKeyPem = fs.readFileSync(keyPath);
    const privateKey = crypto.createPrivateKey(privateKeyPem);
    return signers.newPrivateKeySigner(privateKey);
}

module.exports = {
    loadIdentity,
    loadSigner
};
