"""
Runs a local Federated Learning client as a FastAPI microservice.
Each client trains asynchronously on its local data partition and
registers the model hash to the blockchain backend with its private key.
"""

from fastapi import FastAPI, Query, BackgroundTasks
from fl_backend.core.env_loader import load_environment
load_environment()
from fl_backend.clients.train_utils import train_local_model
from fl_backend.server.blockchain_client import register_model_hash
from fl_backend.core.config import CLIENT_INDEX, TOTAL_CLIENTS
from fl_backend.core.utils import log_event, compute_model_hash
import uvicorn
import os
import threading

# Track client state in memory
client_state = {
    "is_training": False,
    "last_round": None,
    "last_delegate": None,
    "last_model_path": None,
    "last_model_hash": None,
    "last_loss": None,
    "status": "idle"
}

app = FastAPI(title=f"FL Client Node {CLIENT_INDEX + 1}")

@app.get("/status")
def status():
    """Simple health check + training status."""
    return {
        "client_index": CLIENT_INDEX,
        "total_clients": TOTAL_CLIENTS,
        "training": client_state
    }

# -------------------------------
# 🔧 Background training workflow
# -------------------------------
def run_training_job(delegate_id: str, round_id: str, client_index: int, total_clients: int):
    """Background task: train locally and push model hash to blockchain."""
    try:
        client_state.update({
            "is_training": True,
            "status": f"training round {round_id}",
            "last_delegate": delegate_id,
            "last_round": round_id
        })

        log_event("Client", f"🏥 Training started for {delegate_id} (Client {client_index + 1}/{total_clients})")

        # Local FL training
        result = train_local_model(epochs=1, client_index=client_index, total_clients=total_clients)
        model_hash = compute_model_hash(result["path"])

        client_state.update({
            "is_training": False,
            "status": "completed",
            "last_model_path": result["path"],
            "last_model_hash": model_hash,
            "last_loss": result["loss"]
        })

        log_event("Client", f"✅ Training complete for {delegate_id} | Loss: {result['loss']:.4f}")

        # Register signed model hash on blockchain
        register_model_hash(delegate_id, round_id, result["path"])
        log_event("Client", f"🔐 Model hash registered on blockchain for {delegate_id} ({model_hash[:10]}...)")

    except Exception as e:
        client_state.update({
            "is_training": False,
            "status": f"error: {e}"
        })
        log_event("Client", f"❌ Error in training job for {delegate_id}: {e}")

@app.post("/fl/train")
def train_client(
    background_tasks: BackgroundTasks,
    delegate_id: str = Query(..., description="Delegate ID (e.g., hospital_a)"),
    round_id: str = Query(..., description="Active round ID"),
    client_index: int = Query(CLIENT_INDEX, description="Client index"),
    total_clients: int = Query(TOTAL_CLIENTS, description="Total number of clients"),
):
    """
    Asynchronously trigger local model training.
    Returns immediately while training runs in the background.
    """
    if client_state["is_training"]:
        return {"status": "busy", "message": "Training already in progress."}

    log_event("Client", f"📡 Training request accepted for {delegate_id} (round={round_id})")
    background_tasks.add_task(run_training_job, delegate_id, round_id, client_index, total_clients)

    return {
        "status": "accepted",
        "delegate_id": delegate_id,
        "round_id": round_id,
        "client_index": client_index,
        "message": "Training started in background"
    }

if __name__ == "__main__":
    host = os.getenv("CLIENT_HOST", "127.0.0.1")
    port = int(os.getenv("CLIENT_PORT", 8600 + CLIENT_INDEX))  # unique per node
    log_event("Client", f"🚀 Starting FL Client Node {CLIENT_INDEX + 1} on {host}:{port}")
    uvicorn.run("fl_backend.clients.client_app:app", host=host, port=port, reload=True)
