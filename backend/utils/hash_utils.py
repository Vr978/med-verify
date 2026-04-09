"""
Hash utilities for blockchain operations
Handles SHA-256 hashing and Merkle root calculations
"""

import hashlib
import json
from typing import List, Dict, Any
from datetime import datetime


def calculate_sha256(data: str) -> str:
    """
    Calculate SHA-256 hash of data

    Args:
        data: Input string to hash

    Returns:
        str: Hexadecimal hash string
    """
    return hashlib.sha256(data.encode()).hexdigest()


def calculate_block_hash(block_data: Dict[str, Any]) -> str:
    """
    Calculate hash for a block based on its content

    Args:
        block_data: Block data dictionary

    Returns:
        str: Block hash
    """
    # Create deterministic string representation for hashing
    timestamp = block_data["timestamp"]

    # Handle different timestamp formats consistently
    if isinstance(timestamp, datetime):
        timestamp_str = timestamp.isoformat() + "Z"
    elif isinstance(timestamp, dict) and "$date" in timestamp:
        # MongoDB datetime format - use the ISO string directly
        timestamp_str = timestamp["$date"]
    elif hasattr(timestamp, "isoformat"):
        # Another datetime-like object
        timestamp_str = timestamp.isoformat() + "Z"
    else:
        # Already a string - use as is
        timestamp_str = str(timestamp)

    hash_data = {
        "block_number": block_data["block_number"],
        "previous_hash": block_data["previous_hash"],
        "merkle_root": block_data["merkle_root"],
        "timestamp": timestamp_str,
        "delegate_id": block_data["delegate_id"],
        "round_id": block_data["round_id"],
        "model_hashes": sorted(
            block_data.get("model_hashes", [])
        ),  # Sort for determinism
    }

    hash_string = json.dumps(hash_data, sort_keys=True)
    return calculate_sha256(hash_string)


def calculate_merkle_root(model_hashes: List[str]) -> str:
    """
    Calculate Merkle root of model hashes
    Simple implementation - can be enhanced with proper Merkle tree

    Args:
        model_hashes: List of model hashes

    Returns:
        str: Merkle root hash
    """
    if not model_hashes:
        return calculate_sha256("empty")

    if len(model_hashes) == 1:
        return calculate_sha256(model_hashes[0])

    # Simple concatenation and hash - real Merkle tree would be more complex
    combined = "".join(sorted(model_hashes))
    return calculate_sha256(combined)


def generate_model_hash(model_data: bytes) -> str:
    """
    Generate SHA-256 hash for AI model data

    Args:
        model_data: Model weights or parameters as bytes

    Returns:
        str: SHA-256 hash of the model
    """
    return hashlib.sha256(model_data).hexdigest()
