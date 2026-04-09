"""
Blockchain client for interacting with the blockchain microservice.
Handles model hash registration, verification, and integrity logging.
"""

import os
import requests
from fl_backend.core.config import BACKEND_API_URL
from fl_backend.core.utils import log_event, compute_model_hash


def register_model_hash(delegate_id: str, round_id: str, model_path: str) -> str:
    """
    Register a model hash on the blockchain backend.

    Includes the delegate's private key (base64) from .env for signing.

    Args:
        delegate_id (str): Delegate identifier (e.g., hospital_a)
        round_id (str): Federated round identifier
        model_path (str): Path to the model checkpoint

    Returns:
        str: SHA-256 hash of the model
    """
    model_hash = compute_model_hash(model_path)

    # Fetch private key for the delegate (env var names like PRIVATE_KEY_HOSPITAL_A)
    private_key_b64 = os.getenv(f"PRIVATE_KEY_{delegate_id.upper()}")
    payload = {
        "delegate_id": delegate_id,
        "round_id": round_id,
        "model_hash": model_hash,
    }
    if private_key_b64:
        payload["private_key_b64"] = private_key_b64
    else:
        log_event("Blockchain", f"⚠️ No private key found for {delegate_id}")

    try:
        res = requests.post(f"{BACKEND_API_URL}/blocks/add", json=payload, timeout=15)
        if res.status_code == 200:
            log_event(
                "Blockchain",
                f"✅ Model hash registered for {delegate_id} ({model_hash[:10]}...)",
            )
        else:
            log_event(
                "Blockchain",
                f"⚠️ Blockchain rejected ({res.status_code}): {res.text}",
            )
    except requests.exceptions.RequestException as e:
        log_event("Blockchain", f"❌ Connection error: {e}")
    except Exception as e:
        log_event("Blockchain", f"❌ Unexpected error: {e}")

    return model_hash


def verify_model_hash(model_hash: str) -> bool:
    """Verify if a given model hash exists on the blockchain ledger."""
    try:
        res = requests.get(f"{BACKEND_API_URL}/blocks/verify/{model_hash}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            exists = data.get("exists", False)
            log_event("Blockchain", f"🔍 Verification {model_hash[:10]}... → {exists}")
            return exists
        else:
            log_event(
                "Blockchain",
                f"⚠️ Verification failed ({res.status_code}): {res.text}",
            )
    except Exception as e:
        log_event("Blockchain", f"❌ Error verifying model hash: {e}")
    return False
