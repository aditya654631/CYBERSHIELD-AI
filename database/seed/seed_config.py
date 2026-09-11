"""
CyberShield AI — Synthetic Dataset Configuration
Phase 1 Step 4: Delhi Operational Dataset Configuration
"""

# Global deterministic random seed for full reproducibility
SYNTHETIC_RANDOM_SEED = 26184

# Dataset versioning and markers
DATASET_VERSION = "delhi_synthetic_v2"
COMPLAINT_PREFIX = "CMP-DL-"
ACCOUNT_PREFIX = "SYN-DL-ACC-"
TRANSACTION_PREFIX = "TXN-DL-"
ATM_PREFIX = "ATM-DL-"

# Target generation scales
NUM_COMPLAINTS = 3000
NUM_ACCOUNTS = 6000
TARGET_ATMS = 240
WITHDRAWAL_RATIO = 0.70  # ~70% of complaints have realized cash-out outcomes for ML training labels

# Delhi 9 Operational Zones
DELHI_ZONES = [
    "CENTRAL_NEW_DELHI",
    "SOUTH",
    "SOUTH_EAST",
    "WEST",
    "SOUTH_WEST_DWARKA",
    "NORTH",
    "NORTH_WEST",
    "EAST",
    "NORTH_EAST_SHAHDARA"
]

# Fraud Types (12 categories)
FRAUD_TYPES = [
    "UPI fraud",
    "phishing",
    "investment scam",
    "fake customer-care scam",
    "remote-access scam",
    "marketplace scam",
    "loan-app scam",
    "impersonation scam",
    "account takeover",
    "QR-code scam",
    "job scam",
    "e-commerce scam"
]

# Payment Channels
PAYMENT_CHANNELS = [
    "UPI",
    "IMPS",
    "NEFT",
    "RTGS",
    "Card",
    "Wallet",
    "NetBanking"
]

# Banking Institutions
BANK_NAMES = [
    "State Bank of India",
    "HDFC Bank",
    "ICICI Bank",
    "Axis Bank",
    "Punjab National Bank",
    "Bank of Baroda",
    "Canara Bank",
    "Kotak Mahindra Bank"
]

# Amount bands (min, max, weight)
AMOUNT_BANDS = [
    ("SMALL", 1000.0, 10000.0, 0.25),       # 25%
    ("MEDIUM", 10000.0, 50000.0, 0.35),     # 35%
    ("HIGH", 50000.0, 200000.0, 0.25),      # 25%
    ("VERY_HIGH", 200000.0, 1000000.0, 0.15) # 15%
]

# Hop-count target distribution
HOP_DISTRIBUTION = [
    (1, 0.15),  # 15% Direct 1-hop
    (2, 0.30),  # 30% 2-hop
    (3, 0.30),  # 30% 3-hop
    (4, 0.25)   # 25% 4+ hop / branching
]

# Reporting Delay categories in hours
REPORTING_DELAYS = [
    ("< 30 min", 0.1, 0.5, 0.20),
    ("30-120 min", 0.5, 2.0, 0.35),
    ("2-6 hours", 2.0, 6.0, 0.25),
    ("6-24 hours", 6.0, 24.0, 0.15),
    ("1-3 days", 24.0, 72.0, 0.05)
]
