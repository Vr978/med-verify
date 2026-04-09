"""
Global configuration constants for the FL backend.
Centralizes environment variables and filesystem paths.
"""

import os

# ------------------------------
# Backend & Blockchain Settings
# ------------------------------
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")

# ------------------------------
# Federated Learning Parameters
# ------------------------------
CLIENT_INDEX = int(os.getenv("CLIENT_INDEX", 0))
TOTAL_CLIENTS = int(os.getenv("TOTAL_CLIENTS", 1))

# ------------------------------
# Network Settings
# ------------------------------
FL_BACKEND_HOST = os.getenv("FL_BACKEND_HOST", "127.0.0.1")
FL_BACKEND_PORT = int(os.getenv("FL_BACKEND_PORT", "8500"))
AGGREGATOR_API_URL = os.getenv("AGGREGATOR_API_URL", "http://127.0.0.1:8500")

# ------------------------------
# Model Storage Paths
# ------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_MODEL_DIR = os.path.join(BASE_DIR, "tmp_models")
CLIENT_MODEL_DIR = os.path.join(LOCAL_MODEL_DIR, f"client_{CLIENT_INDEX+1}")

os.makedirs(CLIENT_MODEL_DIR, exist_ok=True)

# ------------------------------
# Dataset Cache (optional optimization)
# ------------------------------
DATASET_CACHE_DIR = os.getenv("DATASET_CACHE_DIR", os.path.join(BASE_DIR, "dataset_cache"))
os.makedirs(DATASET_CACHE_DIR, exist_ok=True)

# ------------------------------
# Startup confirmation (for clarity)
# ------------------------------
print(
    f"🌱 Environment loaded → CLIENT_INDEX={CLIENT_INDEX}, "
    f"TOTAL_CLIENTS={TOTAL_CLIENTS}, BACKEND_API_URL={BACKEND_API_URL}, "
    f"AGGREGATOR_API_URL={AGGREGATOR_API_URL}"
)
