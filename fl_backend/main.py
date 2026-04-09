"""
Entrypoint for the Federated Learning backend microservice.
This starts the FastAPI app, mounts the federated learning routes,
and enables decentralized training coordination.
"""
from fl_backend.core.env_loader import load_environment
load_environment()
from fl_backend.core.fl_service import router as fl_router
from fastapi import FastAPI
from fl_backend.core.fl_service import router as fl_router
from fl_backend.core.env_loader import load_environment
from fl_backend.core.utils import log_event
import uvicorn
import os

# Load environment first
load_environment()


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI app.
    """
    app = FastAPI(
        title="Federated Learning Backend (Decentralized Ready)",
        description="Handles training, aggregation, and blockchain communication for FL nodes.",
        version="1.0.0",
    )
    app.include_router(fl_router)
    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("FL_BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("FL_BACKEND_PORT", "8500"))
    node_role = os.getenv("NODE_ROLE", "hybrid").lower()

    log_event("System", f"🚀 Starting FL Backend [{node_role.upper()}] on {host}:{port}")

    uvicorn.run("fl_backend.main:app", host=host, port=port, reload=True)
