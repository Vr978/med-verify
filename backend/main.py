import os
import logging
import time
from fastapi import FastAPI, Request, Response
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timezone
from config.database_config import (
    users_collection,
    refresh_tokens_collection,
    nodes_collection,
    blocks_collection,
    elections_collection,
    votes_collection,
)
from config.logging_config import setup_logging, performance_logger
import web.rest.authentication_routes as auth
import web.rest.users as users
import web.rest.utils_router as utils
import web.rest.node_routes as nodes
import web.rest.dpos_routes as dpos
import web.rest.block_routes as blocks

# Global scheduler instance
scheduler = None


async def check_expired_rounds():
    """
    Background task to check and automatically end expired election rounds
    Runs every minute to check if current active round has expired
    """
    try:
        from services.dpos_service import dpos_service

        logger = logging.getLogger("scheduler")

        # Check if there's an active election
        active_election = await elections_collection.find_one({"is_active": True})

        if active_election:
            current_time = datetime.now(timezone.utc)
            end_time = active_election["end_time"]

            # Handle different datetime formats
            if isinstance(end_time, str):
                # Parse ISO string
                end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            elif not end_time.tzinfo:
                # Add timezone if missing
                end_time = end_time.replace(tzinfo=timezone.utc)

            # Check if round has expired
            if current_time > end_time:
                logger.info(
                    f"Round {active_election['round_id']} has expired. Auto-ending..."
                )

                result = await dpos_service.end_current_round()

                if result["success"]:
                    logger.info(
                        f"Round {active_election['round_id']} ended automatically"
                    )
                else:
                    logger.error(f"Failed to auto-end round: {result['error']}")
            else:
                # Calculate remaining time
                remaining = end_time - current_time
                logger.debug(
                    f"Round {active_election['round_id']} active. Expires in: {remaining}"
                )
        else:
            logger.debug("No active election round found")

    except Exception as e:
        logger.error(f"Error in check_expired_rounds: {str(e)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logging first
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Authentication System")
    logger.info("Setting up database indexes...")

    try:
        # Startup: Create indexes
        await users_collection.create_index("email", unique=True)
        logger.info("Created unique index on users.email")

        await refresh_tokens_collection.create_index("token_hash")
        logger.info("Created index on refresh_tokens.token_hash")

        await refresh_tokens_collection.create_index("user_id")
        logger.info("Created index on refresh_tokens.user_id")

        # TTL index: Automatically delete expired tokens after they expire
        # MongoDB will automatically remove documents where expires_at < current time
        await refresh_tokens_collection.create_index("expires_at", expireAfterSeconds=0)
        logger.info("Created TTL index on refresh_tokens.expires_at")

        # Blockchain collection indexes
        await nodes_collection.create_index("node_id", unique=True)
        logger.info("Created unique index on nodes.node_id")

        await nodes_collection.create_index("public_key", unique=True)
        logger.info("Created unique index on nodes.public_key")

        await blocks_collection.create_index("block_number", unique=True)
        logger.info("Created unique index on blocks.block_number")

        await blocks_collection.create_index("block_hash", unique=True)
        logger.info("Created unique index on blocks.block_hash")

        await blocks_collection.create_index("delegate_id")
        logger.info("Created index on blocks.delegate_id")

        await blocks_collection.create_index("round_id")
        logger.info("Created index on blocks.round_id")

        await elections_collection.create_index("round_id", unique=True)
        logger.info("Created unique index on elections.round_id")

        await elections_collection.create_index("is_active")
        logger.info("Created index on elections.is_active")

        await votes_collection.create_index(["voter_node_id", "round_id"], unique=True)
        logger.info("Created compound unique index on votes.voter_node_id + round_id")

        logger.info("Database indexes created successfully")

        # Start the background scheduler for automatic round ending
        global scheduler
        scheduler = AsyncIOScheduler()

        # Schedule check_expired_rounds to run every minute
        scheduler.add_job(
            check_expired_rounds,
            "interval",
            minutes=2,
            id="round_expiry_check",
            name="Check Expired Election Rounds",
            replace_existing=True,
        )

        scheduler.start()
        logger.info(
            "Background scheduler started - checking for expired rounds every two minute"
        )
        logger.info("DPoS Blockchain System ready to serve requests")

    except Exception as e:
        logger.error(f"Failed to setup database indexes: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down DPoS Blockchain System")

    # Stop the scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("Background scheduler stopped")

    logger.info("Server shutdown complete")


def create_app():
    app = FastAPI(
        title="DPoS Blockchain API (FastAPI + MongoDB)",
        description="Delegated Proof of Stake blockchain for secure model hash sharing with JWT authentication",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        """
        Logging middleware for performance monitoring and request tracking
        """
        start_time = time.time()

        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Log request start
        logger = logging.getLogger("fastapi")
        logger.debug(f"REQUEST {request.method} {request.url.path} from {client_ip}")

        try:
            # Process request
            response: Response = await call_next(request)

            # Calculate request duration
            duration = time.time() - start_time

            # Log performance
            performance_logger.log_request_time(
                endpoint=str(request.url.path),
                method=request.method,
                duration=duration,
                status_code=response.status_code,
            )

            # Log request completion
            status_text = "SUCCESS" if response.status_code < 400 else "ERROR"
            logger.info(
                f"{status_text} {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)"
            )

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"EXCEPTION {request.method} {request.url.path} - ERROR after {duration:.3f}s: {str(e)}"
            )
            raise

    # Include routers
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(utils.router)

    # Blockchain routers
    app.include_router(nodes.router)
    app.include_router(dpos.router)
    app.include_router(blocks.router)

    return app


app = create_app()
