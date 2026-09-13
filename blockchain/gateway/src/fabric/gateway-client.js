'use strict';

const { connect } = require('@hyperledger/fabric-gateway');
const { getOrgConfig, CHANNEL_NAME, CHAINCODE_NAME } = require('../config/organizations');
const { loadIdentity, loadSigner } = require('./identity');
const { createGrpcClient } = require('./connection');
const { FabricUnavailableError } = require('../utils/errors');

/**
 * Connects to the Fabric Gateway as a specified organization.
 * @param {string|object} orgIdentifier Organization name (e.g. 'BankA', 'I4C', etc.) or config object
 * @param {object} [options] Custom options
 * @returns {Promise<{ gateway: import('@hyperledger/fabric-gateway').Gateway, client: import('@grpc/grpc-js').Client, getNetwork: Function, getContract: Function, close: Function, orgConfig: object }>}
 */
async function connectGateway(orgIdentifier, options = {}) {
    let orgConfig;
    try {
        orgConfig = typeof orgIdentifier === 'string' ? getOrgConfig(orgIdentifier) : orgIdentifier;
    } catch (err) {
        throw err;
    }

    let client;
    let gateway;

    try {
        const identity = loadIdentity(orgConfig.certPath, orgConfig.mspId);
        const signer = loadSigner(orgConfig.keyPath);
        client = createGrpcClient(orgConfig.peerEndpoint, orgConfig.tlsCaCertPath, orgConfig.peerHostAlias);

        gateway = connect({
            client,
            identity,
            signer,
            evaluateOptions: () => ({ deadline: Date.now() + 10000 }),
            endorseOptions: () => ({ deadline: Date.now() + 15000 }),
            submitOptions: () => ({ deadline: Date.now() + 15000 }),
            commitStatusOptions: () => ({ deadline: Date.now() + 60000 })
        });

        const channelName = options.channelName || CHANNEL_NAME;
        const chaincodeName = options.chaincodeName || CHAINCODE_NAME;

        return {
            gateway,
            client,
            orgConfig,
            getNetwork: () => gateway.getNetwork(channelName),
            getContract: () => gateway.getNetwork(channelName).getContract(chaincodeName),
            close: () => {
                try {
                    gateway.close();
                } catch (e) {
                    // ignore close errors
                }
                try {
                    client.close();
                } catch (e) {
                    // ignore close errors
                }
            }
        };
    } catch (err) {
        if (client) {
            try { client.close(); } catch (e) {}
        }
        if (gateway) {
            try { gateway.close(); } catch (e) {}
        }
        throw new FabricUnavailableError(`Failed to connect Fabric Gateway for ${orgConfig.orgName}: ${err.message}`, err);
    }
}

module.exports = {
    connectGateway
};
