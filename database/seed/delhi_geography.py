"""
CyberShield AI — Delhi Geography Definitions
Phase 1 Step 4: 60 Location Clusters across 9 Delhi Zones & 240 Synthetic Context ATMs
"""

import random
from typing import List, Dict, Any
from database.seed.seed_config import (
    SYNTHETIC_RANDOM_SEED, BANK_NAMES, ATM_PREFIX
)

# 60 Realistic Delhi Location Clusters categorized across the 9 Operational Zones
DELHI_CLUSTERS_DATA = [
    # 1. CENTRAL_NEW_DELHI (7 clusters)
    {"name": "Connaught Place, Delhi", "zone": "CENTRAL_NEW_DELHI", "lat": 28.6315, "lon": 77.2167, "radius": 2.0, "fraud_count": 42, "risk": 0.86},
    {"name": "Karol Bagh, Delhi", "zone": "CENTRAL_NEW_DELHI", "lat": 28.6514, "lon": 77.1907, "radius": 2.2, "fraud_count": 38, "risk": 0.79},
    {"name": "Paharganj, Delhi", "zone": "CENTRAL_NEW_DELHI", "lat": 28.6433, "lon": 77.2137, "radius": 1.8, "fraud_count": 29, "risk": 0.72},
    {"name": "Patel Nagar, Delhi", "zone": "CENTRAL_NEW_DELHI", "lat": 28.6575, "lon": 77.1650, "radius": 2.1, "fraud_count": 24, "risk": 0.65},
    {"name": "Rajendra Place, Delhi", "zone": "CENTRAL_NEW_DELHI", "lat": 28.6441, "lon": 77.1795, "radius": 1.9, "fraud_count": 31, "risk": 0.75},
    {"name": "Mandi House, Delhi", "zone": "CENTRAL_NEW_DELHI", "lat": 28.6258, "lon": 77.2345, "radius": 1.7, "fraud_count": 18, "risk": 0.58},
    {"name": "Chanakyapuri, Delhi", "zone": "CENTRAL_NEW_DELHI", "lat": 28.5983, "lon": 77.1925, "radius": 2.5, "fraud_count": 14, "risk": 0.45},

    # 2. SOUTH (8 clusters)
    {"name": "Hauz Khas, Delhi", "zone": "SOUTH", "lat": 28.5494, "lon": 77.2001, "radius": 2.0, "fraud_count": 28, "risk": 0.70},
    {"name": "Green Park, Delhi", "zone": "SOUTH", "lat": 28.5588, "lon": 77.2074, "radius": 1.8, "fraud_count": 25, "risk": 0.66},
    {"name": "Saket District Centre, Delhi", "zone": "SOUTH", "lat": 28.5245, "lon": 77.2066, "radius": 2.2, "fraud_count": 45, "risk": 0.88},
    {"name": "Greater Kailash, Delhi", "zone": "SOUTH", "lat": 28.5355, "lon": 77.2410, "radius": 2.3, "fraud_count": 34, "risk": 0.77},
    {"name": "Malviya Nagar, Delhi", "zone": "SOUTH", "lat": 28.5398, "lon": 77.2064, "radius": 2.0, "fraud_count": 30, "risk": 0.71},
    {"name": "Vasant Kunj, Delhi", "zone": "SOUTH", "lat": 28.5293, "lon": 77.1528, "radius": 3.0, "fraud_count": 26, "risk": 0.64},
    {"name": "Defence Colony, Delhi", "zone": "SOUTH", "lat": 28.5724, "lon": 77.2325, "radius": 1.9, "fraud_count": 22, "risk": 0.60},
    {"name": "Mehrauli, Delhi", "zone": "SOUTH", "lat": 28.5186, "lon": 77.1860, "radius": 2.5, "fraud_count": 27, "risk": 0.68},

    # 3. SOUTH_EAST (7 clusters)
    {"name": "Nehru Place, Delhi", "zone": "SOUTH_EAST", "lat": 28.5494, "lon": 77.2530, "radius": 2.0, "fraud_count": 52, "risk": 0.91},
    {"name": "Kalkaji, Delhi", "zone": "SOUTH_EAST", "lat": 28.5402, "lon": 77.2580, "radius": 2.1, "fraud_count": 37, "risk": 0.78},
    {"name": "Lajpat Nagar, Delhi", "zone": "SOUTH_EAST", "lat": 28.5677, "lon": 77.2433, "radius": 2.2, "fraud_count": 41, "risk": 0.82},
    {"name": "Okhla Industrial Area, Delhi", "zone": "SOUTH_EAST", "lat": 28.5355, "lon": 77.2810, "radius": 2.8, "fraud_count": 48, "risk": 0.89},
    {"name": "CR Park, Delhi", "zone": "SOUTH_EAST", "lat": 28.5372, "lon": 77.2514, "radius": 1.9, "fraud_count": 23, "risk": 0.62},
    {"name": "Govindpuri, Delhi", "zone": "SOUTH_EAST", "lat": 28.5312, "lon": 77.2625, "radius": 1.8, "fraud_count": 35, "risk": 0.76},
    {"name": "Sarita Vihar, Delhi", "zone": "SOUTH_EAST", "lat": 28.5284, "lon": 77.3006, "radius": 2.4, "fraud_count": 20, "risk": 0.59},

    # 4. WEST (8 clusters)
    {"name": "Rajouri Garden, Delhi", "zone": "WEST", "lat": 28.6415, "lon": 77.1209, "radius": 2.2, "fraud_count": 39, "risk": 0.80},
    {"name": "Janakpuri, Delhi", "zone": "WEST", "lat": 28.6219, "lon": 77.0878, "radius": 2.5, "fraud_count": 44, "risk": 0.84},
    {"name": "Tilak Nagar, Delhi", "zone": "WEST", "lat": 28.6365, "lon": 77.0965, "radius": 2.0, "fraud_count": 33, "risk": 0.73},
    {"name": "Punjabi Bagh, Delhi", "zone": "WEST", "lat": 28.6692, "lon": 77.1264, "radius": 2.1, "fraud_count": 30, "risk": 0.69},
    {"name": "Paschim Vihar, Delhi", "zone": "WEST", "lat": 28.6694, "lon": 77.0924, "radius": 2.3, "fraud_count": 28, "risk": 0.67},
    {"name": "Uttam Nagar, Delhi", "zone": "WEST", "lat": 28.6219, "lon": 77.0583, "radius": 2.4, "fraud_count": 46, "risk": 0.87},
    {"name": "Vikaspuri, Delhi", "zone": "WEST", "lat": 28.6377, "lon": 77.0700, "radius": 2.2, "fraud_count": 27, "risk": 0.66},
    {"name": "Kirti Nagar, Delhi", "zone": "WEST", "lat": 28.6558, "lon": 77.1466, "radius": 2.0, "fraud_count": 31, "risk": 0.71},

    # 5. SOUTH_WEST_DWARKA (6 clusters)
    {"name": "Dwarka Sector 6, Delhi", "zone": "SOUTH_WEST_DWARKA", "lat": 28.5921, "lon": 77.0682, "radius": 2.2, "fraud_count": 36, "risk": 0.75},
    {"name": "Dwarka Sector 10, Delhi", "zone": "SOUTH_WEST_DWARKA", "lat": 28.5815, "lon": 77.0570, "radius": 2.0, "fraud_count": 32, "risk": 0.72},
    {"name": "Dwarka Sector 12, Delhi", "zone": "SOUTH_WEST_DWARKA", "lat": 28.5925, "lon": 77.0410, "radius": 2.1, "fraud_count": 29, "risk": 0.68},
    {"name": "Dwarka Sector 21, Delhi", "zone": "SOUTH_WEST_DWARKA", "lat": 28.5522, "lon": 77.0582, "radius": 2.4, "fraud_count": 38, "risk": 0.78},
    {"name": "Palam, Delhi", "zone": "SOUTH_WEST_DWARKA", "lat": 28.5889, "lon": 77.0867, "radius": 2.3, "fraud_count": 35, "risk": 0.74},
    {"name": "Mahipalpur, Delhi", "zone": "SOUTH_WEST_DWARKA", "lat": 28.5475, "lon": 77.1275, "radius": 2.5, "fraud_count": 43, "risk": 0.85},

    # 6. NORTH (6 clusters)
    {"name": "Civil Lines, Delhi", "zone": "NORTH", "lat": 28.6814, "lon": 77.2227, "radius": 2.0, "fraud_count": 21, "risk": 0.57},
    {"name": "Model Town, Delhi", "zone": "NORTH", "lat": 28.7027, "lon": 77.1937, "radius": 2.2, "fraud_count": 31, "risk": 0.71},
    {"name": "Mukherjee Nagar, Delhi", "zone": "NORTH", "lat": 28.7088, "lon": 77.2144, "radius": 2.0, "fraud_count": 36, "risk": 0.76},
    {"name": "Kamla Nagar, Delhi", "zone": "NORTH", "lat": 28.6811, "lon": 77.2025, "radius": 1.8, "fraud_count": 28, "risk": 0.68},
    {"name": "Kashmere Gate, Delhi", "zone": "NORTH", "lat": 28.6665, "lon": 77.2285, "radius": 2.1, "fraud_count": 37, "risk": 0.79},
    {"name": "Burari, Delhi", "zone": "NORTH", "lat": 28.7537, "lon": 77.1994, "radius": 3.0, "fraud_count": 19, "risk": 0.54},

    # 7. NORTH_WEST (8 clusters)
    {"name": "Rohini Sector 3, Delhi", "zone": "NORTH_WEST", "lat": 28.7011, "lon": 77.1120, "radius": 2.1, "fraud_count": 34, "risk": 0.73},
    {"name": "Rohini Sector 10, Delhi", "zone": "NORTH_WEST", "lat": 28.7159, "lon": 77.1172, "radius": 2.3, "fraud_count": 47, "risk": 0.87},
    {"name": "Rohini Sector 15, Delhi", "zone": "NORTH_WEST", "lat": 28.7290, "lon": 77.1285, "radius": 2.2, "fraud_count": 31, "risk": 0.69},
    {"name": "Pitampura, Delhi", "zone": "NORTH_WEST", "lat": 28.6990, "lon": 77.1384, "radius": 2.4, "fraud_count": 40, "risk": 0.81},
    {"name": "Shalimar Bagh, Delhi", "zone": "NORTH_WEST", "lat": 28.7165, "lon": 77.1575, "radius": 2.2, "fraud_count": 29, "risk": 0.67},
    {"name": "Ashok Vihar, Delhi", "zone": "NORTH_WEST", "lat": 28.6912, "lon": 77.1726, "radius": 2.0, "fraud_count": 26, "risk": 0.63},
    {"name": "Wazirpur Industrial Area, Delhi", "zone": "NORTH_WEST", "lat": 28.6985, "lon": 77.1650, "radius": 2.3, "fraud_count": 38, "risk": 0.79},
    {"name": "Narela, Delhi", "zone": "NORTH_WEST", "lat": 28.8527, "lon": 77.0927, "radius": 3.5, "fraud_count": 23, "risk": 0.61},

    # 8. EAST (5 clusters)
    {"name": "Laxmi Nagar, Delhi", "zone": "EAST", "lat": 28.6308, "lon": 77.2773, "radius": 2.0, "fraud_count": 49, "risk": 0.90},
    {"name": "Preet Vihar, Delhi", "zone": "EAST", "lat": 28.6415, "lon": 77.2965, "radius": 2.1, "fraud_count": 33, "risk": 0.74},
    {"name": "Mayur Vihar Phase 1, Delhi", "zone": "EAST", "lat": 28.6080, "lon": 77.2950, "radius": 2.3, "fraud_count": 35, "risk": 0.75},
    {"name": "Mayur Vihar Phase 2, Delhi", "zone": "EAST", "lat": 28.6185, "lon": 77.3060, "radius": 2.0, "fraud_count": 28, "risk": 0.68},
    {"name": "Patparganj Industrial Area, Delhi", "zone": "EAST", "lat": 28.6272, "lon": 77.3015, "radius": 2.2, "fraud_count": 39, "risk": 0.81},

    # 9. NORTH_EAST_SHAHDARA (5 clusters)
    {"name": "Shahdara, Delhi", "zone": "NORTH_EAST_SHAHDARA", "lat": 28.6738, "lon": 77.2882, "radius": 2.2, "fraud_count": 43, "risk": 0.83},
    {"name": "Dilshad Garden, Delhi", "zone": "NORTH_EAST_SHAHDARA", "lat": 28.6852, "lon": 77.3195, "radius": 2.3, "fraud_count": 36, "risk": 0.76},
    {"name": "Anand Vihar, Delhi", "zone": "NORTH_EAST_SHAHDARA", "lat": 28.6473, "lon": 77.3158, "radius": 2.4, "fraud_count": 46, "risk": 0.88},
    {"name": "Vivek Vihar, Delhi", "zone": "NORTH_EAST_SHAHDARA", "lat": 28.6654, "lon": 77.3110, "radius": 2.0, "fraud_count": 27, "risk": 0.65},
    {"name": "Seelampur, Delhi", "zone": "NORTH_EAST_SHAHDARA", "lat": 28.6698, "lon": 77.2680, "radius": 2.1, "fraud_count": 38, "risk": 0.80}
]

def generate_delhi_atms(clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deterministically generates 4 ATMs per cluster (total 240 ATMs).
    Uses a dedicated local random generator seeded with SYNTHETIC_RANDOM_SEED.
    """
    rng = random.Random(SYNTHETIC_RANDOM_SEED + 101)
    atms = []
    atm_counter = 1

    for c in clusters:
        c_name = c["name"]
        zone = c["zone"]
        c_lat = c["lat"]
        c_lon = c["lon"]

        # Generate 4 ATMs per cluster with realistic slight geographic jitter (< 0.8 km)
        for i in range(4):
            bank = BANK_NAMES[(atm_counter + i) % len(BANK_NAMES)]
            atm_code = f"{ATM_PREFIX}{atm_counter:04d}"
            # small offset: 0.001 deg is ~111 meters
            d_lat = rng.uniform(-0.005, 0.005)
            d_lon = rng.uniform(-0.005, 0.005)
            lat = round(c_lat + d_lat, 6)
            lon = round(c_lon + d_lon, 6)
            risk = "CRITICAL" if c["risk"] >= 0.80 else ("HIGH" if c["risk"] >= 0.65 else "MEDIUM")

            atms.append({
                "atm_code": atm_code,
                "bank_name": bank,
                "address": f"Plot {rng.randint(1, 99)}, Near Metro Station, {c_name}",
                "city": "Delhi",
                "district": zone,
                "state": "Delhi",
                "latitude": lat,
                "longitude": lon,
                "cash_available": True,
                "risk_rating": risk,
                "cluster_name": c_name
            })
            atm_counter += 1

    return atms
