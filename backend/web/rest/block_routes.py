"""
Block Routes for DPoS blockchain
Handles block creation, retrieval, and chain verification endpoints
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from model.block import BlockCreate
from services.block_service import block_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.post("/add")
async def add_block(block_data: BlockCreate):
    """
    Add a new block to the blockchain
    Only authorized delegates can add blocks for their round

    Args:
        block_data: Block creation data with model hash

    Returns:
        dict: Success/error response with block data
    """
    logger.info(
        f"Block add request: delegate {block_data.delegate_id} for round {block_data.round_id}"
    )

    result = await block_service.add_block(block_data)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/chain")
async def get_blockchain(
    limit: Optional[int] = Query(
        None, ge=1, le=1000, description="Maximum number of blocks to return"
    )
):
    """
    Get the blockchain or recent blocks

    Args:
        limit: Maximum number of blocks to return (None for all blocks)

    Returns:
        dict: Success response with blockchain data
    """
    logger.info(f"Blockchain request (limit: {limit})")

    result = await block_service.get_blockchain(limit=limit)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/verify")
async def verify_chain():
    """
    Verify the integrity of the entire blockchain

    Returns:
        dict: Chain verification results
    """
    logger.info("Chain verification request")

    result = await block_service.verify_chain_integrity()

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/latest")
async def get_latest_block():
    """
    Get the latest block in the chain

    Returns:
        dict: Success/error response with latest block data
    """
    logger.info("Latest block request")

    try:
        latest_block = await block_service.get_latest_block()

        if not latest_block:
            return {"success": False, "error": "No blocks found in the chain"}

        return {"success": True, "data": {"block": latest_block}}

    except Exception as e:
        logger.error(f"Error getting latest block: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get latest block: {str(e)}"
        )


@router.get("/{block_number}")
async def get_block_by_number(block_number: int):
    """
    Get a specific block by its number

    Args:
        block_number: Block number to retrieve

    Returns:
        dict: Success/error response with block data
    """
    logger.info(f"Block request: #{block_number}")

    result = await block_service.get_block_by_number(block_number)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/delegate/{delegate_id}")
async def get_blocks_by_delegate(delegate_id: str):
    """
    Get all blocks created by a specific delegate

    Args:
        delegate_id: Delegate node ID

    Returns:
        dict: Success response with delegate's blocks
    """
    logger.info(f"Delegate blocks request: {delegate_id}")

    result = await block_service.get_blocks_by_delegate(delegate_id)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.post("/genesis")
async def create_genesis_block():
    """
    Create the genesis block (first block in the chain)
    This should only be called once to initialize the blockchain

    Returns:
        dict: Success/error response
    """
    logger.info("Genesis block creation request")

    result = await block_service.create_genesis_block()

    if not result["success"]:
        if "already exists" in result["error"]:
            raise HTTPException(status_code=409, detail=result["error"])
        else:
            raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/stats/summary")
async def get_blockchain_stats():
    """
    Get blockchain statistics summary

    Returns:
        dict: Blockchain statistics
    """
    logger.info("Blockchain stats request")

    try:
        # Get blockchain data
        chain_result = await block_service.get_blockchain()

        if not chain_result["success"]:
            raise HTTPException(status_code=500, detail=chain_result["error"])

        blocks = chain_result["data"]["blocks"]

        if not blocks:
            return {
                "success": True,
                "data": {
                    "message": "No blocks in the chain",
                    "total_blocks": 0,
                    "chain_stats": {},
                },
            }

        # Calculate statistics
        total_blocks = len(blocks)
        total_transactions = sum(block.get("transaction_count", 0) for block in blocks)
        total_model_hashes = sum(len(block.get("model_hashes", [])) for block in blocks)

        # Delegate statistics
        delegate_counts = {}
        for block in blocks:
            delegate = block.get("delegate_id", "unknown")
            delegate_counts[delegate] = delegate_counts.get(delegate, 0) + 1

        # Round statistics
        round_counts = {}
        for block in blocks:
            round_id = block.get("round_id", "unknown")
            round_counts[round_id] = round_counts.get(round_id, 0) + 1

        return {
            "success": True,
            "data": {
                "chain_summary": {
                    "total_blocks": total_blocks,
                    "total_transactions": total_transactions,
                    "total_model_hashes": total_model_hashes,
                    "genesis_hash": blocks[0]["block_hash"] if blocks else None,
                    "latest_block_number": (
                        blocks[-1]["block_number"] if blocks else None
                    ),
                    "latest_block_hash": blocks[-1]["block_hash"] if blocks else None,
                },
                "delegate_stats": {
                    "unique_delegates": len(delegate_counts),
                    "blocks_per_delegate": dict(
                        sorted(
                            delegate_counts.items(), key=lambda x: x[1], reverse=True
                        )
                    ),
                    "most_active_delegate": (
                        max(delegate_counts.items(), key=lambda x: x[1])
                        if delegate_counts
                        else None
                    ),
                },
                "round_stats": {
                    "unique_rounds": len(round_counts),
                    "blocks_per_round": dict(
                        sorted(round_counts.items(), key=lambda x: x[1], reverse=True)
                    ),
                    "average_blocks_per_round": (
                        sum(round_counts.values()) / len(round_counts)
                        if round_counts
                        else 0
                    ),
                },
            },
        }

    except Exception as e:
        logger.error(f"Error getting blockchain stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")


@router.get("/search/model/{model_hash}")
async def search_by_model_hash(model_hash: str):
    """
    Search for blocks containing a specific model hash

    Args:
        model_hash: Model hash to search for

    Returns:
        dict: Success response with matching blocks
    """
    logger.info(f"Model hash search: {model_hash}")

    try:
        # Get all blocks and search for the model hash
        chain_result = await block_service.get_blockchain()

        if not chain_result["success"]:
            raise HTTPException(status_code=500, detail=chain_result["error"])

        blocks = chain_result["data"]["blocks"]
        matching_blocks = []

        for block in blocks:
            if model_hash in block.get("model_hashes", []):
                matching_blocks.append(block)

        return {
            "success": True,
            "data": {
                "search_term": model_hash,
                "matching_blocks": matching_blocks,
                "total_matches": len(matching_blocks),
            },
        }

    except Exception as e:
        logger.error(f"Error searching for model hash {model_hash}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
