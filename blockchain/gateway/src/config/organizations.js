'use strict';

const path = require('path');
const fs = require('fs');

function resolveNetworkDir() {
    if (process.env.FABRIC_NETWORK_DIR) {
        return path.resolve(process.env.FABRIC_NETWORK_DIR);
    }
    // Default location relative to gateway directory: ../network
    return path.resolve(__dirname, '..', '..', '..', 'network');
}

function resolveKeyFile(keystoreDir) {
    if (!fs.existsSync(keystoreDir)) {
        return null;
    }
    const files = fs.readdirSync(keystoreDir);
    // Prefer priv_sk or any *_sk file
    const privSk = files.find(f => f === 'priv_sk');
    if (privSk) {
        return path.join(keystoreDir, privSk);
    }
    const anySk = files.find(f => f.endsWith('_sk') || f.endsWith('.pem') || f.endsWith('.key'));
    return anySk ? path.join(keystoreDir, anySk) : null;
}

const NETWORK_DIR = resolveNetworkDir();
const PEER_ORGS_DIR = path.join(NETWORK_DIR, 'organizations', 'peerOrganizations');

const ORGANIZATIONS = {
    BankA: {
        orgName: 'BankA',
        mspId: 'BankAMSP',
        domain: 'banka.cybershield.net',
        peerHostAlias: 'peer0.banka.cybershield.net',
        defaultPort: 7051,
        get peerEndpoint() {
            return process.env.BANKA_PEER_ENDPOINT || `localhost:${this.defaultPort}`;
        },
        get tlsCaCertPath() {
            return path.join(PEER_ORGS_DIR, this.domain, 'peers', this.peerHostAlias, 'tls', 'ca.crt');
        },
        get tlsCaPath() {
            return this.tlsCaCertPath;
        },
        get certPath() {
            const user1Cert = path.join(PEER_ORGS_DIR, this.domain, 'users', `User1@${this.domain}`, 'msp', 'signcerts', `User1@${this.domain}-cert.pem`);
            if (fs.existsSync(user1Cert)) return user1Cert;
            return path.join(PEER_ORGS_DIR, this.domain, 'users', `Admin@${this.domain}`, 'msp', 'signcerts', `Admin@${this.domain}-cert.pem`);
        },
        get keyPath() {
            const user1Keystore = path.join(PEER_ORGS_DIR, this.domain, 'users', `User1@${this.domain}`, 'msp', 'keystore');
            const resolved = resolveKeyFile(user1Keystore);
            if (resolved) return resolved;
            return resolveKeyFile(path.join(PEER_ORGS_DIR, this.domain, 'users', `Admin@${this.domain}`, 'msp', 'keystore'));
        }
    },

    BankB: {
        orgName: 'BankB',
        mspId: 'BankBMSP',
        domain: 'bankb.cybershield.net',
        peerHostAlias: 'peer0.bankb.cybershield.net',
        defaultPort: 8051,
        get peerEndpoint() {
            return process.env.BANKB_PEER_ENDPOINT || `localhost:${this.defaultPort}`;
        },
        get tlsCaCertPath() {
            return path.join(PEER_ORGS_DIR, this.domain, 'peers', this.peerHostAlias, 'tls', 'ca.crt');
        },
        get certPath() {
            const user1Cert = path.join(PEER_ORGS_DIR, this.domain, 'users', `User1@${this.domain}`, 'msp', 'signcerts', `User1@${this.domain}-cert.pem`);
            if (fs.existsSync(user1Cert)) return user1Cert;
            return path.join(PEER_ORGS_DIR, this.domain, 'users', `Admin@${this.domain}`, 'msp', 'signcerts', `Admin@${this.domain}-cert.pem`);
        },
        get keyPath() {
            const user1Keystore = path.join(PEER_ORGS_DIR, this.domain, 'users', `User1@${this.domain}`, 'msp', 'keystore');
            const resolved = resolveKeyFile(user1Keystore);
            if (resolved) return resolved;
            return resolveKeyFile(path.join(PEER_ORGS_DIR, this.domain, 'users', `Admin@${this.domain}`, 'msp', 'keystore'));
        }
    },

    BankC: {
        orgName: 'BankC',
        mspId: 'BankCMSP',
        domain: 'bankc.cybershield.net',
        peerHostAlias: 'peer0.bankc.cybershield.net',
        defaultPort: 9051,
        get peerEndpoint() {
            return process.env.BANKC_PEER_ENDPOINT || `localhost:${this.defaultPort}`;
        },
        get tlsCaCertPath() {
            return path.join(PEER_ORGS_DIR, this.domain, 'peers', this.peerHostAlias, 'tls', 'ca.crt');
        },
        get certPath() {
            const user1Cert = path.join(PEER_ORGS_DIR, this.domain, 'users', `User1@${this.domain}`, 'msp', 'signcerts', `User1@${this.domain}-cert.pem`);
            if (fs.existsSync(user1Cert)) return user1Cert;
            return path.join(PEER_ORGS_DIR, this.domain, 'users', `Admin@${this.domain}`, 'msp', 'signcerts', `Admin@${this.domain}-cert.pem`);
        },
        get keyPath() {
            const user1Keystore = path.join(PEER_ORGS_DIR, this.domain, 'users', `User1@${this.domain}`, 'msp', 'keystore');
            const resolved = resolveKeyFile(user1Keystore);
            if (resolved) return resolved;
            return resolveKeyFile(path.join(PEER_ORGS_DIR, this.domain, 'users', `Admin@${this.domain}`, 'msp', 'keystore'));
        }
    },

    I4C: {
        orgName: 'I4C',
        mspId: 'I4CMSP',
        domain: 'i4c.cybershield.net',
        peerHostAlias: 'peer0.i4c.cybershield.net',
        defaultPort: 10051,
        get peerEndpoint() {
            return process.env.I4C_PEER_ENDPOINT || `localhost:${this.defaultPort}`;
        },
        get tlsCaCertPath() {
            return path.join(PEER_ORGS_DIR, this.domain, 'peers', this.peerHostAlias, 'tls', 'ca.crt');
        },
        get certPath() {
            const user1Cert = path.join(PEER_ORGS_DIR, this.domain, 'users', `User1@${this.domain}`, 'msp', 'signcerts', `User1@${this.domain}-cert.pem`);
            if (fs.existsSync(user1Cert)) return user1Cert;
            return path.join(PEER_ORGS_DIR, this.domain, 'users', `Admin@${this.domain}`, 'msp', 'signcerts', `Admin@${this.domain}-cert.pem`);
        },
        get keyPath() {
            const user1Keystore = path.join(PEER_ORGS_DIR, this.domain, 'users', `User1@${this.domain}`, 'msp', 'keystore');
            const resolved = resolveKeyFile(user1Keystore);
            if (resolved) return resolved;
            return resolveKeyFile(path.join(PEER_ORGS_DIR, this.domain, 'users', `Admin@${this.domain}`, 'msp', 'keystore'));
        }
    },

    LEA: {
        orgName: 'LEA',
        mspId: 'LEAMSP',
        domain: 'lea.cybershield.net',
        peerHostAlias: 'peer0.lea.cybershield.net',
        defaultPort: 11051,
        get peerEndpoint() {
            return process.env.LEA_PEER_ENDPOINT || `localhost:${this.defaultPort}`;
        },
        get tlsCaCertPath() {
            return path.join(PEER_ORGS_DIR, this.domain, 'peers', this.peerHostAlias, 'tls', 'ca.crt');
        },
        get certPath() {
            const user1Cert = path.join(PEER_ORGS_DIR, this.domain, 'users', `User1@${this.domain}`, 'msp', 'signcerts', `User1@${this.domain}-cert.pem`);
            if (fs.existsSync(user1Cert)) return user1Cert;
            return path.join(PEER_ORGS_DIR, this.domain, 'users', `Admin@${this.domain}`, 'msp', 'signcerts', `Admin@${this.domain}-cert.pem`);
        },
        get keyPath() {
            const user1Keystore = path.join(PEER_ORGS_DIR, this.domain, 'users', `User1@${this.domain}`, 'msp', 'keystore');
            const resolved = resolveKeyFile(user1Keystore);
            if (resolved) return resolved;
            return resolveKeyFile(path.join(PEER_ORGS_DIR, this.domain, 'users', `Admin@${this.domain}`, 'msp', 'keystore'));
        }
    }
};

function getOrgConfig(identifier) {
    if (!identifier) {
        throw new Error('Organization identifier is required.');
    }
    const normalized = String(identifier).trim().toUpperCase();

    for (const [key, config] of Object.entries(ORGANIZATIONS)) {
        if (key.toUpperCase() === normalized ||
            config.mspId.toUpperCase() === normalized ||
            config.orgName.toUpperCase() === normalized) {
            return config;
        }
    }

    throw new Error(`Unknown organization '${identifier}'. Supported organizations: ${Object.keys(ORGANIZATIONS).join(', ')}`);
}

function listKnownOrgs() {
    return Object.keys(ORGANIZATIONS);
}

module.exports = {
    ORGANIZATIONS,
    getOrgConfig,
    listKnownOrgs,
    NETWORK_DIR,
    CHANNEL_NAME: process.env.FABRIC_CHANNEL || 'cyber-intelligence',
    CHAINCODE_NAME: process.env.FABRIC_CHAINCODE || 'geo-intelligence'
};
