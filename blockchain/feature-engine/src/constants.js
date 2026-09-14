'use strict';

const SCHEMA_VERSION = 'blockchain-feature-schema-v1';

const BANK_MSPS = ['BankAMSP', 'BankBMSP', 'BankCMSP'];
const AUTHORITY_MSPS = ['I4CMSP', 'LEAMSP'];
const ALL_CONSORTIUM_MSPS = [...BANK_MSPS, ...AUTHORITY_MSPS];

const EVENT_TYPES = {
    ATM_WITHDRAWAL_CONFIRMED: 'ATM_WITHDRAWAL_CONFIRMED',
    ATM_WITHDRAWAL_ATTEMPT: 'ATM_WITHDRAWAL_ATTEMPT',
    BRANCH_CASHOUT_CONFIRMED: 'BRANCH_CASHOUT_CONFIRMED',
    MULE_ACCOUNT_ACTIVITY: 'MULE_ACCOUNT_ACTIVITY',
    LEA_CONFIRMED_CLUSTER: 'LEA_CONFIRMED_CLUSTER',
    SIGNAL_CORRECTION: 'SIGNAL_CORRECTION',
    SIGNAL_REVOKED: 'SIGNAL_REVOKED'
};

const WINDOWS_MS = {
    '1h': 60 * 60 * 1000,
    '6h': 6 * 60 * 60 * 1000,
    '24h': 24 * 60 * 60 * 1000,
    '7d': 7 * 24 * 60 * 60 * 1000,
    '30d': 30 * 24 * 60 * 60 * 1000
};

const PROHIBITED_PII_FIELDS = [
    'victim_name',
    'victim_phone',
    'phone',
    'phone_number',
    'mobile',
    'account_number',
    'raw_account_number',
    'bank_account',
    'upi_id',
    'vpa',
    'aadhaar',
    'pan',
    'email',
    'password',
    'jwt',
    'token',
    'raw_transaction_history',
    'complaint_text',
    'raw_complaint'
];

module.exports = {
    SCHEMA_VERSION,
    BANK_MSPS,
    AUTHORITY_MSPS,
    ALL_CONSORTIUM_MSPS,
    EVENT_TYPES,
    WINDOWS_MS,
    PROHIBITED_PII_FIELDS
};
