# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Where the networks of this folder are stored."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

GRM_NETWORK_STORE_JSON = os.path.join(HERE, "data", "grm_network_store.json")
GRM_NETWORK_STORE_JSON_ENRICHED = os.path.join(HERE, "data", "grm_network_fully_enriched.json")
# written by import_cf4.py from the Cosmicflows-4 table (not shipped: download it from the EDD, see README)
GRM_NETWORK_STORE_CF4 = os.path.join(HERE, "data", "grm_network_cf4.json")
# the CF4 store when it has been built, the enriched network otherwise
GRM_NETWORK_STORE_FULL_CF4 = GRM_NETWORK_STORE_CF4 if os.path.exists(GRM_NETWORK_STORE_CF4) \
    else GRM_NETWORK_STORE_JSON_ENRICHED
