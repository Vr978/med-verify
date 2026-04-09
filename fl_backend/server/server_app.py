"""
Server-side FastAPI app for the aggregator node.
Used when running the aggregator independently (optional).
"""

from fastapi import FastAPI, UploadFile, File
from fl_backend.server.aggregator import aggregate_models
from fl_backend.server.blockchain_client import register_model_hash
from fl_backend.core.utils import compute_model_hash, log_event
from fl_backend.core.env_loader import load_environment
from fl_backend.core.config import LOCAL_MODEL_DIR
import shutil, os
from datetime import datetime

# Load .env and detect context
load_environment()
NODE_ROLE = os.getenv("NODE_ROLE", "server").lower()

app = FastAPI(title="Federated Aggregator Server")

uploaded_models = []


@app.post("/upload")
async def upload_model(file: UploadFile = File(...)):
    """Receive model files from FL clients."""
    os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
    save_path = os.path.join(LOCAL_MODEL_DIR, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    uploaded_models.append(save_path)

    log_event("Aggregator", f"📦 Model uploaded: {file.filename}")
    return {"status": "uploaded", "file": file.filename}


@app.post("/aggregate")
async def aggregate_and_commit(delegate_id: str = "hospital_a", round_id: str = "default_round"):
    """
    Aggregate uploaded models and record the aggregated hash on blockchain.
    """
    if not uploaded_models:
        log_event("Aggregator", "⚠️ No uploaded models found for aggregation.")
        return {"error": "No uploaded models to aggregate."}

    try:
        # Aggregate models from all uploaded clients
        agg_path = aggregate_models(uploaded_models)
        model_hash = compute_model_hash(agg_path)

        # Record aggregation event
        log_event("Aggregator", f"✅ Aggregation complete. Hash: {model_hash[:12]}...")

        # Commit hash to blockchain
        register_model_hash(delegate_id, round_id, agg_path)
        log_event("Blockchain", f"🔗 Model hash committed for {delegate_id}")

        # Optional timestamp for tracking
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "success": True,
            "timestamp": timestamp_str,
            "aggregated_model": agg_path,
            "model_hash": model_hash,
            "message": "Aggregated model committed to blockchain.",
        }

    except Exception as e:
        log_event("Aggregator", f"❌ Aggregation or blockchain commit failed: {e}")
        return {"success": False, "error": str(e)}


@app.get("/status")
def status():
    """Health check and current aggregator state."""
    return {
        "status": "running",
        "role": NODE_ROLE,
        "uploaded_models": len(uploaded_models),
        "model_dir": LOCAL_MODEL_DIR,
    }
