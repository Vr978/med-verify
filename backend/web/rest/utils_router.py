"""
Utils Router - API Layer
Uses SystemService for business logic
author: Barath Suresh
"""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.system.system_service import SystemService
from config.database_config import blocks_collection
from utils.hash_utils import calculate_block_hash
from utils.crypto_utils import create_signing_message

# Configure logging
logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/utils", tags=["utils"])


@router.get("/health")
async def orchestrator_health_check():
    """
    Health check endpoint for the orchestrator service

    Returns:
        dict: Comprehensive health status of all system components
    """
    try:
        health_status = await SystemService.get_comprehensive_health()

        # Return appropriate HTTP status based on health
        if health_status["status"] == "healthy":
            return {"success": True, "data": health_status}
        else:
            return JSONResponse(
                status_code=503, content={"success": False, "data": health_status}
            )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={"error": f"Health check failed: {str(e)}", "success": False},
        )


@router.get("/debug/info")
async def debug_info():
    """
    Debug endpoint providing system information

    Returns:
        dict: System debug information
    """
    try:
        debug_info = await SystemService.get_system_info()
        return {"success": True, "data": debug_info}

    except Exception as e:
        logger.error(f"Debug info failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Debug info failed: {str(e)}", "success": False},
        )


@router.get("/debug/collections")
async def debug_collections():
    """
    Debug endpoint showing collection statistics

    Returns:
        dict: Database collection statistics
    """
    try:
        collections_info = await SystemService.get_collection_statistics()
        return {"success": True, "data": collections_info}

    except Exception as e:
        logger.error(f"Debug collections failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Debug collections failed: {str(e)}", "success": False},
        )


@router.get("/debug/auth")
async def debug_auth():
    """
    Debug endpoint showing authentication statistics

    Returns:
        dict: Auth system statistics and information
    """
    try:
        auth_stats = await SystemService.get_auth_statistics()
        return {"success": True, "data": auth_stats}

    except Exception as e:
        logger.error(f"Debug auth failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Debug auth failed: {str(e)}", "success": False},
        )


@router.get("/performance")
async def performance_metrics():
    """
    Get system performance metrics

    Returns:
        dict: Performance and usage metrics
    """
    try:
        metrics = await SystemService.get_performance_metrics()
        return {"success": True, "data": metrics}

    except Exception as e:
        logger.error(f"Performance metrics failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Performance metrics failed: {str(e)}",
                "success": False,
            },
        )


@router.get("/debug/blocks")
async def debug_blocks():
    """
    Debug endpoint to examine block data format and hashing
    """
    try:
        # Get first few blocks
        cursor = blocks_collection.find().sort("block_number", 1).limit(2)
        blocks = await cursor.to_list(length=None)

        debug_info = []

        for block in blocks:
            # Convert ObjectId to string for JSON serialization
            if "_id" in block:
                block["_id"] = str(block["_id"])

            # Calculate expected hash
            expected_hash = calculate_block_hash(block)

            # Create signing message for non-genesis blocks
            signing_message = None
            if block["block_number"] > 0:
                message_bytes = create_signing_message(block)
                signing_message = message_bytes.decode("utf-8")

            debug_info.append(
                {
                    "block_number": block["block_number"],
                    "stored_timestamp": str(block["timestamp"]),
                    "timestamp_type": str(type(block["timestamp"])),
                    "expected_hash": expected_hash,
                    "actual_hash": block["block_hash"],
                    "hash_match": expected_hash == block["block_hash"],
                    "signing_message": signing_message,
                    "full_block": block,
                }
            )

        return {"success": True, "data": debug_info}

    except Exception as e:
        logger.error(f"Debug blocks failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Debug blocks failed: {str(e)}",
                "success": False,
            },
        )
