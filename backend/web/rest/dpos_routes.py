"""
DPoS Routes for Delegated Proof of Stake consensus
Handles delegate elections and round management endpoints
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from model.election import ElectionRequest
from services.dpos_service import dpos_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dpos", tags=["dpos"])


@router.post("/elect")
async def start_election(election_request: ElectionRequest):
    """
    Start a new delegate election round

    Args:
        election_request: Election parameters

    Returns:
        dict: Success/error response with election results
    """
    logger.info(
        f"Election request: {election_request.delegate_count} delegates for {election_request.round_duration_hours}h"
    )

    result = await dpos_service.start_new_election(election_request)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/delegates/current")
async def get_current_delegates():
    """
    Get delegates for the current active round

    Returns:
        dict: Current delegates information
    """
    logger.info("Current delegates request")

    result = await dpos_service.get_current_delegates()

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/delegates/{round_id}")
async def get_delegates_by_round(round_id: str):
    """
    Get delegates for a specific round

    Args:
        round_id: Round identifier

    Returns:
        dict: Delegates information for the round
    """
    logger.info(f"Delegates request for round: {round_id}")

    result = await dpos_service.get_delegates_by_round(round_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/elections/history")
async def get_election_history(
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of elections to return"
    )
):
    """
    Get history of past elections

    Args:
        limit: Maximum number of elections to return

    Returns:
        dict: Election history
    """
    logger.info(f"Election history request (limit: {limit})")

    result = await dpos_service.get_election_history(limit=limit)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.post("/round/end")
async def end_current_round():
    """
    End the current active round (manual control)

    Returns:
        dict: Success/error response
    """
    logger.info("Manual round end request")

    result = await dpos_service.end_current_round()

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/validate/delegate/{delegate_id}")
async def validate_delegate(
    delegate_id: str,
    round_id: Optional[str] = Query(
        None,
        description="Round ID to validate against (current round if not specified)",
    ),
):
    """
    Validate if a node is an authorized delegate

    Args:
        delegate_id: Node ID to validate
        round_id: Round ID to validate against

    Returns:
        dict: Validation result
    """
    logger.info(f"Delegate validation request: {delegate_id} for round {round_id}")

    try:
        # If no round_id specified, get current round
        if not round_id:
            current_result = await dpos_service.get_current_delegates()
            if not current_result["success"]:
                raise HTTPException(status_code=404, detail="No active round found")
            round_id = current_result["data"]["round_id"]

        is_valid = await dpos_service.is_valid_delegate(delegate_id, round_id)

        return {
            "success": True,
            "data": {
                "delegate_id": delegate_id,
                "round_id": round_id,
                "is_valid_delegate": is_valid,
                "message": f"Delegate {delegate_id} is {'authorized' if is_valid else 'not authorized'} for round {round_id}",
            },
        }

    except Exception as e:
        logger.error(f"Error validating delegate {delegate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


@router.get("/status/current")
async def get_dpos_status():
    """
    Get current DPoS system status

    Returns:
        dict: DPoS system status information
    """
    logger.info("DPoS status request")

    try:
        # Get current delegates info
        current_result = await dpos_service.get_current_delegates()

        if current_result["success"]:
            # Active round exists
            delegates_data = current_result["data"]

            return {
                "success": True,
                "data": {
                    "status": "active",
                    "current_round": {
                        "round_id": delegates_data["round_id"],
                        "delegate_count": len(delegates_data["delegates"]),
                        "start_time": delegates_data["election_info"]["start_time"],
                        "end_time": delegates_data["election_info"]["end_time"],
                        "blocks_created": delegates_data["election_info"][
                            "blocks_created"
                        ],
                    },
                    "active_delegates": [
                        {
                            "node_id": delegate["node_id"],
                            "name": delegate["name"],
                            "stake_amount": delegate["stake_amount"],
                        }
                        for delegate in delegates_data["delegates"]
                        if delegate["is_active"]
                    ],
                },
            }
        else:
            # No active round
            # Get election history to show last round info
            history_result = await dpos_service.get_election_history(limit=1)

            last_round = None
            if history_result["success"] and history_result["data"]["elections"]:
                last_election = history_result["data"]["elections"][0]
                last_round = {
                    "round_id": last_election["round_id"],
                    "end_time": last_election["end_time"],
                    "blocks_created": last_election["blocks_created"],
                }

            return {
                "success": True,
                "data": {
                    "status": "inactive",
                    "message": "No active DPoS round. Start a new election to begin consensus.",
                    "last_round": last_round,
                },
            }

    except Exception as e:
        logger.error(f"Error getting DPoS status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status error: {str(e)}")


@router.post("/check-expiry")
async def check_round_expiry():
    """
    Manually check if the current active round has expired and end it if necessary
    This endpoint is useful for testing the automatic expiry system

    Returns:
        dict: Result of the expiry check and any actions taken
    """
    logger.info("Manual round expiry check requested")

    try:
        result = await dpos_service.check_and_end_expired_rounds()

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except Exception as e:
        logger.error(f"Error during manual expiry check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Expiry check error: {str(e)}")
