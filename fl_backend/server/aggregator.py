"""
Aggregation logic wrapper for the Federated Learning backend.
Performs weighted or simple averaging of model parameters received from clients.
"""

import os
import torch
import copy
from datetime import datetime
from fl_backend.clients.model_utils import BrainTumorNet
from fl_backend.core.config import LOCAL_MODEL_DIR
from fl_backend.core.utils import compute_model_hash, log_event

# Node role context
NODE_ROLE = os.getenv("NODE_ROLE", "server").lower()


def aggregate_models(model_paths: list[str]) -> str:
    """
    Aggregate model weights from multiple clients.

    Args:
        model_paths (list[str]): Paths to local model checkpoints (.pt files).

    Returns:
        str: Path to the aggregated model file.
    """
    if not model_paths:
        raise ValueError("No model paths provided for aggregation.")

    valid_paths = [p for p in model_paths if os.path.exists(p)]
    if not valid_paths:
        raise FileNotFoundError("No valid model files found for aggregation.")

    log_event("Aggregator", f"Starting aggregation from {len(valid_paths)} client models.")

    state_dicts = []
    for path in valid_paths:
        try:
            state_dicts.append(torch.load(path, map_location="cpu"))
            log_event("Aggregator", f"Loaded model: {os.path.basename(path)}")
        except Exception as e:
            log_event("Aggregator", f"⚠️ Skipping {path}: {e}")

    if not state_dicts:
        raise RuntimeError("Failed to load any model weights.")

    # Create reference model
    ref_model = BrainTumorNet()
    ref_state = ref_model.state_dict()
    common_keys = set(ref_state.keys())

    for sd in state_dicts:
        common_keys &= set(sd.keys())

    if not common_keys:
        raise ValueError("No common parameters across models.")

    agg_state = copy.deepcopy(ref_state)
    for key in common_keys:
        agg_state[key] = sum(sd[key] for sd in state_dicts) / len(state_dicts)

    ref_model.load_state_dict(agg_state, strict=False)

    # Timestamped aggregated filename
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
    agg_path = os.path.join(LOCAL_MODEL_DIR, f"aggregated_model_{timestamp_str}.pt")

    torch.save(ref_model.state_dict(), agg_path)
    model_hash = compute_model_hash(agg_path)

    log_event("Aggregator", f"✅ Aggregated model saved at {agg_path}")
    log_event("Aggregator", f"🔗 Hash: {model_hash[:12]}...")

    return agg_path
