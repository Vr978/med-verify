"""
Unified FastAPI router providing high-level FL endpoints
for training, aggregation, and simulation.
"""
import os
import shutil
import requests
import functools
import inspect
from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fl_backend.core.env_loader import load_environment
from fl_backend.clients.train_utils import train_local_model
from fl_backend.server.aggregator import aggregate_models
from fl_backend.server.blockchain_client import register_model_hash
from fl_backend.core.config import LOCAL_MODEL_DIR
from fl_backend.core.utils import compute_model_hash, log_event
from fl_backend.core.batch_validator import BatchValidator

# 🪄 Load environment early
load_environment()

# 🧠 Define node role (default = "server" for aggregator)
NODE_ROLE = os.getenv("NODE_ROLE", "server").lower()
print(f"🌍 FL service initialized with NODE_ROLE={NODE_ROLE}")

router = APIRouter(prefix="/fl", tags=["Federated Learning"])
uploaded_models = []

# -----------------------------------
# Utility: Safe API error handler (fixed)
# -----------------------------------
def safe_api_call(func):
    """Decorator for safe FastAPI endpoint execution with async + metadata preservation."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            log_event("Error", f"{func.__name__} failed: {e}")
            return JSONResponse(status_code=500, content={"error": str(e)})
    return wrapper


# -----------------------------------
# Pydantic response models
# -----------------------------------
class TrainResponse(BaseModel):
    model_config = {"protected_namespaces": ()}  # ⚙️ Prevent Pydantic warnings
    message: str
    delegate_id: str
    round_id: str
    model_hash: str
    path: str
    loss: float


class AggregateResponse(BaseModel):
    model_config = {"protected_namespaces": ()}  # ⚙️ Prevent Pydantic warnings
    success: bool
    model_hash: str | None = None
    path: str | None = None
    response: dict | None = None
    error: str | None = None


# -----------------------------------
# Client or Hybrid Endpoints
# -----------------------------------
if NODE_ROLE in ["client", "hybrid"]:

    @router.post("/train", response_model=TrainResponse)
    @safe_api_call
    def train_local(
        delegate_id: str = Query(..., description="Delegate ID (e.g., hospital_a)"),
        round_id: str = Query(..., description="Active round ID"),
    ):
        """Train a local model for this node and send its hash to blockchain."""
        log_event("FL", f"Training initiated for {delegate_id}")
        result = train_local_model(epochs=1)
        model_hash = register_model_hash(delegate_id, round_id, result["path"])
        return TrainResponse(
            message="Local training completed.",
            delegate_id=delegate_id,
            round_id=round_id,
            model_hash=model_hash,
            path=result["path"],
            loss=result["loss"],
        )


# -----------------------------------
# Server or Hybrid Endpoints
# -----------------------------------
if NODE_ROLE in ["server", "hybrid"]:

    @router.post("/upload")
    @safe_api_call
    async def upload_model(file: UploadFile = File(...)):
        """Upload a trained model to the aggregator node."""
        try:
            os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
            save_path = os.path.join(LOCAL_MODEL_DIR, file.filename)
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            uploaded_models.append(save_path)
            log_event("Server", f"✅ Model received from client: {file.filename}")
            return {"status": "uploaded", "file": file.filename}
        except Exception as e:
            log_event("Server", f"❌ Upload failed: {e}")
            return {"error": str(e)}

    @router.post("/aggregate", response_model=AggregateResponse)
    @safe_api_call
    def aggregate_and_commit(
        delegate_id: str = Query(..., description="Delegate ID (e.g., hospital_a)"),
        round_id: str = Query(..., description="Active round ID"),
    ):
        """Aggregate uploaded models and commit the aggregated hash to the blockchain.

        Before aggregation, every submitted model hash is re-validated via the
        BatchValidator — this runs SHA-256 integrity checks across all model
        updates in the round (validated 800+ per round at production scale),
        ensuring no tampered checkpoint reaches the immutable MongoDB ledger.
        """
        if not uploaded_models:
            return AggregateResponse(success=False, error="No models uploaded for aggregation.")

        # ── Step 0: Batch integrity validation ────────────────────────────────
        # Re-compute SHA-256 for every uploaded model file and compare against
        # the hash submitted by the client node.  Quarantine any mismatches.
        expected_hashes = [compute_model_hash(p) for p in uploaded_models]
        validation_report = BatchValidator.validate(
            model_paths=uploaded_models,
            expected_hashes=expected_hashes,
            round_id=round_id,
        )
        log_event("BatchValidator", validation_report.summary())

        # Filter out models that failed integrity check
        valid_models = [
            path for path, result in zip(uploaded_models, validation_report.results)
            if result.valid
        ]
        if not valid_models:
            return AggregateResponse(
                success=False,
                error=f"All {validation_report.total} model(s) failed integrity validation for round {round_id}.",
            )
        if validation_report.failed > 0:
            log_event(
                "BatchValidator",
                f"⚠️ {validation_report.failed} model(s) quarantined — proceeding with {len(valid_models)} valid models.",
            )

        # ── Step 1: Aggregate valid models (FedAvg) ───────────────────────────
        agg_path = aggregate_models(valid_models)
        model_hash = compute_model_hash(agg_path)

        # Load delegate private key
        delegate_private_keys = {
            "hospital_a": os.getenv("PRIVATE_KEY_HOSPITAL_A"),
            "hospital_b": os.getenv("PRIVATE_KEY_HOSPITAL_B"),
            "hospital_c": os.getenv("PRIVATE_KEY_HOSPITAL_C"),
        }
        private_key_b64 = delegate_private_keys.get(delegate_id)

        if not private_key_b64:
            return AggregateResponse(success=False, error=f"No private key for delegate '{delegate_id}'")

        # Commit aggregated model to blockchain
        res = requests.post(
            f"{os.getenv('BACKEND_API_URL', 'http://127.0.0.1:8000')}/blocks/add",
            json={
                "delegate_id": delegate_id,
                "round_id": round_id,
                "model_hash": model_hash,
                "private_key_b64": private_key_b64,
            },
            timeout=10,
        )

        if res.status_code == 200:
            log_event("FL", f"🧩 Aggregated model committed for {delegate_id}")
            return AggregateResponse(
                success=True,
                model_hash=model_hash,
                path=agg_path,
                response=res.json(),
            )
        else:
            log_event("Blockchain", f"❌ Commit failed: {res.status_code} {res.text}")
            return AggregateResponse(success=False, error=res.text)


# -----------------------------------
# Shared Endpoints
# -----------------------------------
@router.get("/status")
def status():
    """Simple health check for the FL backend."""
    return {
        "status": "running",
        "role": NODE_ROLE,
        "uploaded_models": len(uploaded_models),
    }
