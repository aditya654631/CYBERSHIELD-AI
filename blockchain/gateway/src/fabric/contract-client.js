'use strict';

const {
    GatewayError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    FabricUnavailableError
} = require('../utils/errors');

class ContractClient {
    /**
     * @param {import('@hyperledger/fabric-gateway').Contract} contract
     * @param {string} [orgMsp]
     */
    constructor(contract, orgMsp = null) {
        this.contract = contract;
        this.orgMsp = orgMsp;
    }

    /**
     * Evaluates a query transaction without committing to ledger.
     * @param {string} functionName
     * @param  {...string} args
     * @returns {Promise<any>} Parsed JSON or string result
     */
    async evaluate(functionName, ...args) {
        const stringArgs = args.map(a => (typeof a === 'object' && a !== null ? JSON.stringify(a) : String(a)));
        try {
            const resultBytes = await this.contract.evaluateTransaction(functionName, ...stringArgs);
            return this._parseResultBytes(resultBytes);
        } catch (err) {
            throw this._mapFabricError(err, functionName);
        }
    }

    /**
     * Submits an invoke transaction, endorses, submits to orderer, and awaits commit confirmation.
     * @param {string} functionName
     * @param  {...string} args
     * @returns {Promise<{ txId: string, result: any, status: string, blockNumber?: string }>}
     */
    async submit(functionName, ...args) {
        const stringArgs = args.map(a => (typeof a === 'object' && a !== null ? JSON.stringify(a) : String(a)));
        try {
            const proposal = this.contract.newProposal(functionName, { arguments: stringArgs });
            const transaction = await proposal.endorse();
            const txId = transaction.getTransactionId();
            const commit = await transaction.submit();

            // Await commit status confirmation from Gateway
            const status = await commit.getStatus();
            if (!status.successful) {
                throw new GatewayError(`Transaction ${txId} failed commit validation with status code: ${status.code}`, 'COMMIT_FAILURE', 500);
            }

            const resultBytes = transaction.getResult();
            const result = this._parseResultBytes(resultBytes);

            return {
                txId,
                status: 'COMMITTED',
                blockNumber: status.blockNumber ? String(status.blockNumber) : null,
                result
            };
        } catch (err) {
            throw this._mapFabricError(err, functionName);
        }
    }

    _parseResultBytes(bytes) {
        if (!bytes || bytes.length === 0) {
            return null;
        }
        const utf8 = Buffer.from(bytes).toString('utf8');
        try {
            return JSON.parse(utf8);
        } catch (e) {
            return utf8;
        }
    }

    _mapFabricError(err, functionName) {
        let msg = err.message || String(err);
        if (Array.isArray(err.details)) {
            const detailMsgs = err.details.map(d => (typeof d === 'object' ? (d.message || JSON.stringify(d)) : String(d))).join('; ');
            msg += ` | details: ${detailMsgs}`;
        } else if (err.details) {
            msg += ` | details: ${err.details}`;
        }
        if (err.cause && err.cause.message) {
            msg += ` | cause: ${err.cause.message}`;
        }

        if (msg.includes('Permission Denied') || msg.includes('Unauthorized MSP') || msg.includes('not authorized')) {
            return new AuthorizationError(`Access Denied in ${functionName}: ${msg}`, err);
        }
        if (msg.includes('does not exist') || msg.includes('not found')) {
            return new NotFoundError(`Ledger entity not found in ${functionName}: ${msg}`, err);
        }
        if (msg.includes('PII Security Violation') || msg.includes('Idempotency conflict') || msg.includes('must be') || msg.includes('is required') || msg.includes('already exists')) {
            return new ValidationError(`Invalid request in ${functionName}: ${msg}`, err);
        }
        if (msg.includes('UNAVAILABLE') || msg.includes('Connect Failed') || msg.includes('Deadline Exceeded') || msg.includes('no Raft leader')) {
            return new FabricUnavailableError(`Fabric service unavailable in ${functionName}: ${msg}`, err);
        }

        return new GatewayError(`Failed to execute ${functionName}: ${msg}`, 'CHAINCODE_EXECUTION_ERROR', 500, err);
    }
}

module.exports = ContractClient;
