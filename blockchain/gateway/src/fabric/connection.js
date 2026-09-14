'use strict';

const fs = require('fs');
const grpc = require('@grpc/grpc-js');

/**
 * Creates a gRPC client connection to a Fabric peer with strict TLS verification.
 * @param {string} peerEndpoint e.g. 'localhost:7051' or 'peer0.banka.cybershield.net:7051'
 * @param {string} tlsCaCertPath Path to TLS root CA certificate
 * @param {string} peerHostAlias e.g. 'peer0.banka.cybershield.net'
 * @returns {grpc.Client}
 */
function createGrpcClient(peerEndpoint, tlsCaCertPath, peerHostAlias) {
    if (!peerEndpoint) {
        throw new Error('peerEndpoint is required for gRPC connection.');
    }
    if (!tlsCaCertPath) {
        throw new Error('tlsCaCertPath is required for TLS connection.');
    }
    if (!fs.existsSync(tlsCaCertPath)) {
        throw new Error(`TLS CA certificate not found at: ${tlsCaCertPath}`);
    }

    const tlsRootCert = fs.readFileSync(tlsCaCertPath);
    const tlsCredentials = grpc.credentials.createSsl(tlsRootCert);

    const clientOptions = {
        'grpc.ssl_target_name_override': peerHostAlias,
        'grpc.default_authority': peerHostAlias,
        'grpc.max_receive_message_length': 100 * 1024 * 1024,
        'grpc.max_send_message_length': 100 * 1024 * 1024
    };

    return new grpc.Client(peerEndpoint, tlsCredentials, clientOptions);
}

module.exports = {
    createGrpcClient
};
