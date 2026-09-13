"""
CyberShield AI — Phase A.4G: Delhi V6 Controlled Synthetic Dataset Generator Design
Planned generator for V6 dataset incorporating:
1. 9 Behavioral Archetypes with controlled stochastic transition distributions
2. Pre-event money-flow trajectory and multi-account geographic consensus observables
3. Anti-triviality constraints (nearest origin <= 22%, terminal mule match <= 48%)
4. Clean separation of observable features vs latent generation factors
5. Distinct seed universe:
   - Training seed: 36184
   - Development seed: 36185
   - External holdout seed: 36186

NOTE: DESIGN PHASE ONLY. FULL GENERATION IS DEFERRED TO IMPLEMENTATION PHASE.
DO NOT EXECUTE FULL GENERATION IN PHASE A.4G.
"""

import os
import sys
import json
from typing import Dict, Any, List, Tuple

# Re-use geographical ground truth (60 Delhi Clusters & 11 Revenue Districts)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ml.data.generate_delhi_v5_dataset import (
    DELHI_CLUSTERS_V5 as DELHI_CLUSTERS_V6,
    ALL_11_DISTRICTS,
    DISTRICT_ADJACENCY,
    haversine_km
)

# Seeds for V6 Universe
V6_TRAIN_SEED = 36184
V6_DEV_SEED = 36185
V6_FINAL_HOLDOUT_SEED = 36186

# 9 Behavioral Archetypes
ARCHETYPES_V6: List[Dict[str, Any]] = [
    {
        "id": "LOCAL_RAPID_CASHOUT",
        "prevalence": 0.18,
        "max_hops": 2,
        "victim_district_prob": 0.70,
        "adjacent_district_prob": 0.20,
        "stochastic_prob": 0.10
    },
    {
        "id": "NEARBY_COMMERCIAL_CORRIDOR",
        "prevalence": 0.16,
        "max_hops": 3,
        "commercial_hub_prob": 0.60,
        "adjacent_prob": 0.25,
        "stochastic_prob": 0.15
    },
    {
        "id": "TERMINAL_MULE_DISTRICT",
        "prevalence": 0.15,
        "max_hops": 4,
        "terminal_district_prob": 0.52,
        "adjacent_prob": 0.30,
        "stochastic_prob": 0.18
    },
    {
        "id": "TRANSPORT_HUB_MOVEMENT",
        "prevalence": 0.12,
        "max_hops": 4,
        "transport_hub_prob": 0.58,
        "adjacent_prob": 0.28,
        "stochastic_prob": 0.14
    },
    {
        "id": "CROSS_DISTRICT_MULE_CHAIN",
        "prevalence": 0.12,
        "max_hops": 5,
        "terminal_corridor_prob": 0.45,
        "intermediate_prob": 0.35,
        "stochastic_prob": 0.20
    },
    {
        "id": "RECURRING_SYNDICATE_CORRIDOR",
        "prevalence": 0.10,
        "max_hops": 4,
        "syndicate_cluster_prob": 0.65,
        "failover_prob": 0.25,
        "stochastic_prob": 0.10
    },
    {
        "id": "HIGH_VALUE_DELAYED_CASHOUT",
        "prevalence": 0.07,
        "max_hops": 6,
        "atm_hub_prob": 0.60,
        "peripheral_branch_prob": 0.25,
        "stochastic_prob": 0.15
    },
    {
        "id": "MULTI_BANK_DISPERSAL",
        "prevalence": 0.06,
        "max_hops": 5,
        "convergent_hub_prob": 0.55,
        "adjacent_strip_prob": 0.30,
        "stochastic_prob": 0.15
    },
    {
        "id": "NIGHTTIME_ATM_CASHOUT",
        "prevalence": 0.04,
        "max_hops": 3,
        "kiosk_cluster_prob": 0.62,
        "transit_atm_prob": 0.25,
        "stochastic_prob": 0.13
    }
]

def planned_v6_generator_interface():
    """
    Design signature for the full generator implementation in the next phase.
    """
    return {
        "version": "v6.0-design",
        "status": "DESIGN_FROZEN",
        "message": "Full generation to be executed in subsequent implementation phase."
    }

if __name__ == "__main__":
    print("CyberShield AI — Delhi V6 Generator Design")
    print(f"Seeds: Train={V6_TRAIN_SEED}, Dev={V6_DEV_SEED}, FinalHoldout={V6_FINAL_HOLDOUT_SEED}")
    print(f"Archetypes: {len(ARCHETYPES_V6)}")
    print("STATUS: DESIGN ONLY — Generation deferred to implementation phase.")
