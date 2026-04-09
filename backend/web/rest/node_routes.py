"""
Node Routes for DPoS blockchain network
Handles node registration and management endpoints
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from model.node import NodeRegistration, NodeUpdate
from services.node_service import node_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.post("/register")
async def register_node(node_data: NodeRegistration):
    """
    Register a new node in the DPoS network

    Args:
        node_data: Node registration information

    Returns:
        dict: Success/error response with node data
    """
    logger.info(f"Node registration request: {node_data.node_id}")

    result = await node_service.register_node(node_data)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/list")
async def list_nodes(
    include_inactive: bool = Query(
        False, description="Include inactive nodes in the response"
    )
):
    """
    Get all nodes in the network

    Args:
        include_inactive: Whether to include inactive nodes

    Returns:
        dict: Success response with list of nodes
    """
    logger.info(f"Node list request (include_inactive: {include_inactive})")

    result = await node_service.get_all_nodes(include_inactive=include_inactive)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/{node_id}")
async def get_node(node_id: str):
    """
    Get a specific node by ID

    Args:
        node_id: Node identifier

    Returns:
        dict: Success/error response with node data
    """
    logger.info(f"Node details request: {node_id}")

    result = await node_service.get_node_by_id(node_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.put("/{node_id}")
async def update_node(node_id: str, update_data: NodeUpdate):
    """
    Update node information

    Args:
        node_id: Node identifier
        update_data: Fields to update

    Returns:
        dict: Success/error response
    """
    logger.info(f"Node update request: {node_id}")

    result = await node_service.update_node(node_id, update_data)

    if not result["success"]:
        if "not found" in result["error"].lower():
            raise HTTPException(status_code=404, detail=result["error"])
        else:
            raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/stake/filter")
async def filter_nodes_by_stake(
    min_stake: float = Query(..., ge=0, description="Minimum stake amount"),
    max_stake: Optional[float] = Query(
        None, ge=0, description="Maximum stake amount (optional)"
    ),
):
    """
    Get nodes within a specific stake range

    Args:
        min_stake: Minimum stake amount
        max_stake: Maximum stake amount (optional)

    Returns:
        dict: Success response with filtered nodes
    """
    logger.info(f"Node stake filter request: min={min_stake}, max={max_stake}")

    result = await node_service.get_nodes_by_stake_range(min_stake, max_stake)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/stats/summary")
async def get_network_stats():
    """
    Get network statistics summary

    Returns:
        dict: Network statistics
    """
    logger.info("Network stats request")

    # Get all nodes (including inactive for full stats)
    result = await node_service.get_all_nodes(include_inactive=True)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    nodes = result["data"]["nodes"]

    # Calculate additional statistics
    stake_distribution = sorted([node["stake_amount"] for node in nodes], reverse=True)
    avg_stake = (
        sum(stake_distribution) / len(stake_distribution) if stake_distribution else 0
    )

    return {
        "success": True,
        "data": {
            "total_nodes": result["data"]["total_nodes"],
            "active_nodes": result["data"]["active_nodes"],
            "inactive_nodes": result["data"]["total_nodes"]
            - result["data"]["active_nodes"],
            "total_stake": result["data"]["total_stake"],
            "average_stake": round(avg_stake, 2),
            "highest_stake": stake_distribution[0] if stake_distribution else 0,
            "lowest_stake": stake_distribution[-1] if stake_distribution else 0,
            "stake_distribution": {
                "top_10_percent": sum(
                    stake_distribution[: max(1, len(stake_distribution) // 10)]
                ),
                "median_stake": (
                    stake_distribution[len(stake_distribution) // 2]
                    if stake_distribution
                    else 0
                ),
            },
        },
    }
