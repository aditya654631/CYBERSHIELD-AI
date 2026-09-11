"""
CyberShield AI — Deterministic Delhi Origin Resolution Service
SIH26184 | Phase 1 Step 15 Core Repair

Resolves complainant origin / locality deterministically for Delhi operational pilot:
Priority:
1. Valid officer-provided coordinates within Delhi bounding box -> OFFICER_COORDINATES
2. Exact normalized match with one of 60 Delhi operational clusters -> LOCALITY_CLUSTER_MATCH
3. Legitimate Delhi locality aliases -> LOCALITY_ALIAS_MATCH
4. District-level reference fallback (DELHI_ZONE_CENTROIDS) -> DISTRICT_FALLBACK
5. Unresolved -> UNRESOLVED

Strict Rules:
- NO random coordinates
- NO default Connaught Place
- NO outside-Delhi coordinates
"""

import re
import math
from typing import Dict, Any, Optional, Tuple

# Delhi geographic bounding box
DELHI_LAT_MIN = 28.38
DELHI_LAT_MAX = 28.92
DELHI_LON_MIN = 76.80
DELHI_LON_MAX = 77.45

# Canonical Delhi District / Zone Centroids
DELHI_ZONE_CENTROIDS = {
    "CENTRAL_NEW_DELHI": (28.6360, 77.1989),
    "SOUTH": (28.5410, 77.2041),
    "SOUTH_EAST": (28.5414, 77.2643),
    "WEST": (28.6442, 77.0999),
    "SOUTH_WEST_DWARKA": (28.5758, 77.0731),
    "NORTH": (28.6990, 77.2102),
    "NORTH_WEST": (28.7255, 77.1355),
    "EAST": (28.6252, 77.2953),
    "NORTH_EAST_SHAHDARA": (28.6683, 77.3005),
}

# District name normalizations
DISTRICT_ALIASES = {
    "central": "CENTRAL_NEW_DELHI",
    "central delhi": "CENTRAL_NEW_DELHI",
    "new delhi": "CENTRAL_NEW_DELHI",
    "central_new_delhi": "CENTRAL_NEW_DELHI",
    "south": "SOUTH",
    "south delhi": "SOUTH",
    "south_east": "SOUTH_EAST",
    "southeast": "SOUTH_EAST",
    "south east": "SOUTH_EAST",
    "south east delhi": "SOUTH_EAST",
    "west": "WEST",
    "west delhi": "WEST",
    "south_west": "SOUTH_WEST_DWARKA",
    "southwest": "SOUTH_WEST_DWARKA",
    "south west": "SOUTH_WEST_DWARKA",
    "south west delhi": "SOUTH_WEST_DWARKA",
    "south_west_dwarka": "SOUTH_WEST_DWARKA",
    "dwarka": "SOUTH_WEST_DWARKA",
    "north": "NORTH",
    "north delhi": "NORTH",
    "north_west": "NORTH_WEST",
    "northwest": "NORTH_WEST",
    "north west": "NORTH_WEST",
    "north west delhi": "NORTH_WEST",
    "east": "EAST",
    "east delhi": "EAST",
    "north_east": "NORTH_EAST_SHAHDARA",
    "northeast": "NORTH_EAST_SHAHDARA",
    "north east": "NORTH_EAST_SHAHDARA",
    "north east delhi": "NORTH_EAST_SHAHDARA",
    "shahdara": "NORTH_EAST_SHAHDARA",
    "north_east_shahdara": "NORTH_EAST_SHAHDARA",
}

# 60 Delhi Operational Clusters (Canonical Reference Inventory)
DELHI_CLUSTERS_INVENTORY = [
    {"id": 7, "name": "Connaught Place, Delhi", "district": "CENTRAL_NEW_DELHI", "lat": 28.6315, "lon": 77.2167},
    {"id": 8, "name": "Karol Bagh, Delhi", "district": "CENTRAL_NEW_DELHI", "lat": 28.6514, "lon": 77.1907},
    {"id": 9, "name": "Paharganj, Delhi", "district": "CENTRAL_NEW_DELHI", "lat": 28.6433, "lon": 77.2137},
    {"id": 10, "name": "Patel Nagar, Delhi", "district": "CENTRAL_NEW_DELHI", "lat": 28.6575, "lon": 77.1650},
    {"id": 11, "name": "Rajendra Place, Delhi", "district": "CENTRAL_NEW_DELHI", "lat": 28.6441, "lon": 77.1795},
    {"id": 12, "name": "Mandi House, Delhi", "district": "CENTRAL_NEW_DELHI", "lat": 28.6258, "lon": 77.2345},
    {"id": 13, "name": "Chanakyapuri, Delhi", "district": "CENTRAL_NEW_DELHI", "lat": 28.5983, "lon": 77.1925},
    {"id": 14, "name": "Hauz Khas, Delhi", "district": "SOUTH", "lat": 28.5494, "lon": 77.2001},
    {"id": 15, "name": "Green Park, Delhi", "district": "SOUTH", "lat": 28.5588, "lon": 77.2074},
    {"id": 16, "name": "Saket District Centre, Delhi", "district": "SOUTH", "lat": 28.5245, "lon": 77.2066},
    {"id": 17, "name": "Greater Kailash, Delhi", "district": "SOUTH", "lat": 28.5355, "lon": 77.2410},
    {"id": 18, "name": "Malviya Nagar, Delhi", "district": "SOUTH", "lat": 28.5398, "lon": 77.2064},
    {"id": 19, "name": "Vasant Kunj, Delhi", "district": "SOUTH", "lat": 28.5293, "lon": 77.1528},
    {"id": 20, "name": "Defence Colony, Delhi", "district": "SOUTH", "lat": 28.5724, "lon": 77.2325},
    {"id": 21, "name": "Mehrauli, Delhi", "district": "SOUTH", "lat": 28.5186, "lon": 77.1860},
    {"id": 22, "name": "Nehru Place, Delhi", "district": "SOUTH_EAST", "lat": 28.5494, "lon": 77.2530},
    {"id": 23, "name": "Kalkaji, Delhi", "district": "SOUTH_EAST", "lat": 28.5402, "lon": 77.2580},
    {"id": 24, "name": "Lajpat Nagar, Delhi", "district": "SOUTH_EAST", "lat": 28.5677, "lon": 77.2433},
    {"id": 25, "name": "Okhla Industrial Area, Delhi", "district": "SOUTH_EAST", "lat": 28.5355, "lon": 77.2810},
    {"id": 26, "name": "CR Park, Delhi", "district": "SOUTH_EAST", "lat": 28.5372, "lon": 77.2514},
    {"id": 27, "name": "Govindpuri, Delhi", "district": "SOUTH_EAST", "lat": 28.5312, "lon": 77.2625},
    {"id": 28, "name": "Sarita Vihar, Delhi", "district": "SOUTH_EAST", "lat": 28.5284, "lon": 77.3006},
    {"id": 29, "name": "Rajouri Garden, Delhi", "district": "WEST", "lat": 28.6415, "lon": 77.1209},
    {"id": 30, "name": "Janakpuri, Delhi", "district": "WEST", "lat": 28.6219, "lon": 77.0878},
    {"id": 31, "name": "Tilak Nagar, Delhi", "district": "WEST", "lat": 28.6365, "lon": 77.0965},
    {"id": 32, "name": "Punjabi Bagh, Delhi", "district": "WEST", "lat": 28.6692, "lon": 77.1264},
    {"id": 33, "name": "Paschim Vihar, Delhi", "district": "WEST", "lat": 28.6694, "lon": 77.0924},
    {"id": 34, "name": "Uttam Nagar, Delhi", "district": "WEST", "lat": 28.6219, "lon": 77.0583},
    {"id": 35, "name": "Vikaspuri, Delhi", "district": "WEST", "lat": 28.6377, "lon": 77.0700},
    {"id": 36, "name": "Kirti Nagar, Delhi", "district": "WEST", "lat": 28.6558, "lon": 77.1466},
    {"id": 37, "name": "Dwarka Sector 6, Delhi", "district": "SOUTH_WEST_DWARKA", "lat": 28.5921, "lon": 77.0682},
    {"id": 38, "name": "Dwarka Sector 10, Delhi", "district": "SOUTH_WEST_DWARKA", "lat": 28.5815, "lon": 77.0570},
    {"id": 39, "name": "Dwarka Sector 12, Delhi", "district": "SOUTH_WEST_DWARKA", "lat": 28.5925, "lon": 77.0410},
    {"id": 40, "name": "Dwarka Sector 21, Delhi", "district": "SOUTH_WEST_DWARKA", "lat": 28.5522, "lon": 77.0582},
    {"id": 41, "name": "Palam, Delhi", "district": "SOUTH_WEST_DWARKA", "lat": 28.5889, "lon": 77.0867},
    {"id": 42, "name": "Mahipalpur, Delhi", "district": "SOUTH_WEST_DWARKA", "lat": 28.5475, "lon": 77.1275},
    {"id": 43, "name": "Civil Lines, Delhi", "district": "NORTH", "lat": 28.6814, "lon": 77.2227},
    {"id": 44, "name": "Model Town, Delhi", "district": "NORTH", "lat": 28.7027, "lon": 77.1937},
    {"id": 45, "name": "Mukherjee Nagar, Delhi", "district": "NORTH", "lat": 28.7088, "lon": 77.2144},
    {"id": 46, "name": "Kamla Nagar, Delhi", "district": "NORTH", "lat": 28.6811, "lon": 77.2025},
    {"id": 47, "name": "Kashmere Gate, Delhi", "district": "NORTH", "lat": 28.6665, "lon": 77.2285},
    {"id": 48, "name": "Burari, Delhi", "district": "NORTH", "lat": 28.7537, "lon": 77.1994},
    {"id": 49, "name": "Rohini Sector 3, Delhi", "district": "NORTH_WEST", "lat": 28.7011, "lon": 77.1120},
    {"id": 50, "name": "Rohini Sector 10, Delhi", "district": "NORTH_WEST", "lat": 28.7159, "lon": 77.1172},
    {"id": 51, "name": "Rohini Sector 15, Delhi", "district": "NORTH_WEST", "lat": 28.7290, "lon": 77.1285},
    {"id": 52, "name": "Pitampura, Delhi", "district": "NORTH_WEST", "lat": 28.6990, "lon": 77.1384},
    {"id": 53, "name": "Shalimar Bagh, Delhi", "district": "NORTH_WEST", "lat": 28.7165, "lon": 77.1575},
    {"id": 54, "name": "Ashok Vihar, Delhi", "district": "NORTH_WEST", "lat": 28.6912, "lon": 77.1726},
    {"id": 55, "name": "Wazirpur Industrial Area, Delhi", "district": "NORTH_WEST", "lat": 28.6985, "lon": 77.1650},
    {"id": 56, "name": "Narela, Delhi", "district": "NORTH_WEST", "lat": 28.8527, "lon": 77.0927},
    {"id": 57, "name": "Laxmi Nagar, Delhi", "district": "EAST", "lat": 28.6308, "lon": 77.2773},
    {"id": 58, "name": "Preet Vihar, Delhi", "district": "EAST", "lat": 28.6415, "lon": 77.2965},
    {"id": 59, "name": "Mayur Vihar Phase 1, Delhi", "district": "EAST", "lat": 28.6080, "lon": 77.2950},
    {"id": 60, "name": "Mayur Vihar Phase 2, Delhi", "district": "EAST", "lat": 28.6185, "lon": 77.3060},
    {"id": 61, "name": "Patparganj Industrial Area, Delhi", "district": "EAST", "lat": 28.6272, "lon": 77.3015},
    {"id": 62, "name": "Shahdara, Delhi", "district": "NORTH_EAST_SHAHDARA", "lat": 28.6738, "lon": 77.2882},
    {"id": 63, "name": "Dilshad Garden, Delhi", "district": "NORTH_EAST_SHAHDARA", "lat": 28.6852, "lon": 77.3195},
    {"id": 64, "name": "Anand Vihar, Delhi", "district": "NORTH_EAST_SHAHDARA", "lat": 28.6473, "lon": 77.3158},
    {"id": 65, "name": "Vivek Vihar, Delhi", "district": "NORTH_EAST_SHAHDARA", "lat": 28.6654, "lon": 77.3110},
    {"id": 66, "name": "Seelampur, Delhi", "district": "NORTH_EAST_SHAHDARA", "lat": 28.6698, "lon": 77.2680},
]

# Legitimate Locality Aliases mapping to Delhi Clusters
LOCALITY_ALIASES = {
    # Central / CP
    "cp": 7,
    "connaught place": 7,
    "connaught circus": 7,
    "rajiv chowk": 7,
    "barakhamba": 7,
    "karol bagh": 8,
    "paharganj": 9,
    "patel nagar": 10,
    "rajendra place": 11,
    "mandi house": 12,
    "chanakyapuri": 13,

    # South
    "hauz khas": 14,
    "green park": 15,
    "saket": 16,
    "saket district centre": 16,
    "saket district center": 16,
    "greater kailash": 17,
    "gk": 17,
    "gk 1": 17,
    "gk 2": 17,
    "malviya nagar": 18,
    "vasant kunj": 19,
    "defence colony": 20,
    "mehrauli": 21,

    # South East
    "nehru place": 22,
    "kalkaji": 23,
    "lajpat nagar": 24,
    "okhla": 25,
    "okhla industrial area": 25,
    "cr park": 26,
    "chittaranjan park": 26,
    "govindpuri": 27,
    "sarita vihar": 28,

    # West
    "rajouri garden": 29,
    "rajouri": 29,
    "janakpuri": 30,
    "tilak nagar": 31,
    "punjabi bagh": 32,
    "paschim vihar": 33,
    "uttam nagar": 34,
    "vikaspuri": 35,
    "kirti nagar": 36,

    # South West / Dwarka
    "dwarka": 37,
    "dwarka sector 6": 37,
    "dwarka sec 6": 37,
    "dwarka sector 10": 38,
    "dwarka sec 10": 38,
    "dwarka sector 12": 39,
    "dwarka sec 12": 39,
    "dwarka sector 21": 40,
    "dwarka sec 21": 40,
    "palam": 41,
    "mahipalpur": 42,

    # North
    "civil lines": 43,
    "model town": 44,
    "mukherjee nagar": 45,
    "kamla nagar": 46,
    "kashmere gate": 47,
    "burari": 48,

    # North West
    "rohini": 49,
    "rohini sector 3": 49,
    "rohini sec 3": 49,
    "rohini sector 10": 50,
    "rohini sec 10": 50,
    "rohini sector 15": 51,
    "rohini sec 15": 51,
    "pitampura": 52,
    "shalimar bagh": 53,
    "ashok vihar": 54,
    "wazirpur": 55,
    "wazirpur industrial area": 55,
    "narela": 56,

    # East
    "laxmi nagar": 57,
    "preet vihar": 58,
    "mayur vihar": 59,
    "mayur vihar phase 1": 59,
    "mayur vihar phase 2": 60,
    "patparganj": 61,
    "patparganj industrial area": 61,

    # North East / Shahdara
    "shahdara": 62,
    "dilshad garden": 63,
    "anand vihar": 64,
    "vivek vihar": 65,
    "seelampur": 66,
}


def _normalize_str(s: Optional[str]) -> str:
    """Normalizes string for robust locality matching."""
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"\bdelhi\b", "", s)
    s = re.sub(r"[,\.\-_/]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def resolve_delhi_origin(
    locality: Optional[str] = None,
    district: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> Dict[str, Any]:
    """
    Deterministically resolves a complaint's origin within the Delhi pilot.

    Returns dict:
        - resolved_lat: float or None
        - resolved_lon: float or None
        - resolved_district: str or None
        - resolved_cluster_id: int or None
        - resolved_cluster_name: str or None
        - provenance: "OFFICER_COORDINATES" | "LOCALITY_CLUSTER_MATCH" |
                      "LOCALITY_ALIAS_MATCH" | "DISTRICT_FALLBACK" | "UNRESOLVED"
        - description: str
    """
    # 1. Check valid officer-provided coordinates within Delhi bounding box
    if lat is not None and lon is not None:
        try:
            f_lat = float(lat)
            f_lon = float(lon)
            if not (math.isnan(f_lat) or math.isnan(f_lon)):
                if (DELHI_LAT_MIN <= f_lat <= DELHI_LAT_MAX) and (DELHI_LON_MIN <= f_lon <= DELHI_LON_MAX):
                    # Match nearest Delhi cluster for district affiliation
                    nearest_cluster = min(
                        DELHI_CLUSTERS_INVENTORY,
                        key=lambda c: haversine_km(f_lat, f_lon, c["lat"], c["lon"])
                    )
                    return {
                        "resolved_lat": f_lat,
                        "resolved_lon": f_lon,
                        "resolved_district": nearest_cluster["district"],
                        "resolved_cluster_id": nearest_cluster["id"],
                        "resolved_cluster_name": nearest_cluster["name"],
                        "provenance": "OFFICER_COORDINATES",
                        "description": f"Officer provided exact coordinates ({f_lat:.4f}, {f_lon:.4f}) within Delhi bounds."
                    }
        except (ValueError, TypeError):
            pass

    # 2. Exact normalized match with 60 Delhi clusters
    norm_loc = _normalize_str(locality)
    if norm_loc:
        for c in DELHI_CLUSTERS_INVENTORY:
            c_norm = _normalize_str(c["name"])
            if norm_loc == c_norm:
                return {
                    "resolved_lat": c["lat"],
                    "resolved_lon": c["lon"],
                    "resolved_district": c["district"],
                    "resolved_cluster_id": c["id"],
                    "resolved_cluster_name": c["name"],
                    "provenance": "LOCALITY_CLUSTER_MATCH",
                    "description": f"Exact match with Delhi operational cluster '{c['name']}'."
                }

    # 3. Legitimate locality alias match
    if norm_loc:
        # Check direct alias
        if norm_loc in LOCALITY_ALIASES:
            cid = LOCALITY_ALIASES[norm_loc]
            cluster = next((c for c in DELHI_CLUSTERS_INVENTORY if c["id"] == cid), None)
            if cluster:
                return {
                    "resolved_lat": cluster["lat"],
                    "resolved_lon": cluster["lon"],
                    "resolved_district": cluster["district"],
                    "resolved_cluster_id": cluster["id"],
                    "resolved_cluster_name": cluster["name"],
                    "provenance": "LOCALITY_ALIAS_MATCH",
                    "description": f"Locality alias '{locality}' matched cluster '{cluster['name']}' ({cluster['district']})."
                }

        # Check substring alias (e.g. 'dwarka sec 6 delhi' -> contains 'dwarka')
        for alias, cid in sorted(LOCALITY_ALIASES.items(), key=lambda x: -len(x[0])):
            if re.search(r"\b" + re.escape(alias) + r"\b", norm_loc):
                cluster = next((c for c in DELHI_CLUSTERS_INVENTORY if c["id"] == cid), None)
                if cluster:
                    return {
                        "resolved_lat": cluster["lat"],
                        "resolved_lon": cluster["lon"],
                        "resolved_district": cluster["district"],
                        "resolved_cluster_id": cluster["id"],
                        "resolved_cluster_name": cluster["name"],
                        "provenance": "LOCALITY_ALIAS_MATCH",
                        "description": f"Locality '{locality}' matched alias '{alias}' -> '{cluster['name']}'."
                    }

    # 4. District-level reference fallback
    norm_dist = _normalize_str(district) or (norm_loc if norm_loc in DISTRICT_ALIASES else None)
    if norm_dist and norm_dist in DISTRICT_ALIASES:
        canonical_dist = DISTRICT_ALIASES[norm_dist]
        if canonical_dist in DELHI_ZONE_CENTROIDS:
            d_lat, d_lon = DELHI_ZONE_CENTROIDS[canonical_dist]
            return {
                "resolved_lat": d_lat,
                "resolved_lon": d_lon,
                "resolved_district": canonical_dist,
                "resolved_cluster_id": None,
                "resolved_cluster_name": f"{canonical_dist} Centroid",
                "provenance": "DISTRICT_FALLBACK",
                "description": f"District-level reference centroid fallback for '{canonical_dist}' (lower precision)."
            }

    # 5. Unresolved
    return {
        "resolved_lat": None,
        "resolved_lon": None,
        "resolved_district": None,
        "resolved_cluster_id": None,
        "resolved_cluster_name": None,
        "provenance": "UNRESOLVED",
        "description": "Locality could not be deterministically resolved to Delhi pilot geography."
    }
