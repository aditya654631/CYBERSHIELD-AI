import argparse
import random
import json
import os
from datetime import datetime, timedelta

def generate_dataset(dataset_type="dev"):
    is_full = (dataset_type == "full")
    num_complaints = 20000 if is_full else 500
    num_transactions = 100000 if is_full else 2500
    num_accounts = 10000 if is_full else 500
    num_atms = 2000 if is_full else 100
    num_clusters = 25 if is_full else 10

    print(f"[SyntheticGenerator] Generating {dataset_type.upper()} dataset:")
    print(f" - Complaints: {num_complaints}")
    print(f" - Transactions: {num_transactions}")
    print(f" - Accounts: {num_accounts}")
    print(f" - ATMs: {num_atms}")
    print(f" - Clusters: {num_clusters}")

    clusters = [
        {"name": "Vijay Nagar, Indore", "lat": 22.7533, "lon": 75.8937, "district": "Indore", "risk": 0.87},
        {"name": "Palasia, Indore", "lat": 22.7244, "lon": 75.8839, "district": "Indore", "risk": 0.61},
        {"name": "Rau, Indore", "lat": 22.6288, "lon": 75.8080, "district": "Indore", "risk": 0.34},
        {"name": "MP Nagar, Bhopal", "lat": 23.2332, "lon": 77.4343, "district": "Bhopal", "risk": 0.74},
        {"name": "New Market, Bhopal", "lat": 23.2363, "lon": 77.4013, "district": "Bhopal", "risk": 0.58},
        {"name": "Freeganj, Ujjain", "lat": 23.1824, "lon": 75.7892, "district": "Ujjain", "risk": 0.65},
        {"name": "Civic Center, Jabalpur", "lat": 23.1686, "lon": 79.9339, "district": "Jabalpur", "risk": 0.52},
        {"name": "City Center, Gwalior", "lat": 26.2037, "lon": 78.1969, "district": "Gwalior", "risk": 0.49},
        {"name": "Sarafa Bazaar, Indore", "lat": 22.7179, "lon": 75.8544, "district": "Indore", "risk": 0.70},
        {"name": "Kolar Road, Bhopal", "lat": 23.1856, "lon": 77.4222, "district": "Bhopal", "risk": 0.46}
    ]

    os.makedirs("ml/data", exist_ok=True)
    summary_file = f"ml/data/synthetic_{dataset_type}_meta.json"
    with open(summary_file, "w") as f:
        json.dump({
            "generated_at": datetime.utcnow().isoformat(),
            "type": dataset_type,
            "complaints_count": num_complaints,
            "transactions_count": num_transactions,
            "accounts_count": num_accounts,
            "clusters": clusters
        }, f, indent=2)

    print(f"[SyntheticGenerator] Dataset metadata written to {summary_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CyberShield AI Synthetic Data Generator")
    parser.add_argument("--full", action="store_true", help="Generate full 20,000 complaints dataset")
    args = parser.parse_args()
    generate_dataset("full" if args.full else "dev")
