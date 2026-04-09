"""
Validation utilities for blockchain data
Handles input validation and data integrity checks
"""

import re
from typing import Optional, Dict, Any, List
from datetime import datetime


def validate_node_id(node_id: str) -> bool:
    """
    Validate node ID format

    Args:
        node_id: Node identifier string

    Returns:
        bool: True if valid format
    """
    # Allow alphanumeric characters, underscores, and hyphens
    pattern = r"^[a-zA-Z0-9_-]{3,50}$"
    return bool(re.match(pattern, node_id))


def validate_stake_amount(amount: float) -> bool:
    """
    Validate stake amount

    Args:
        amount: Stake amount to validate

    Returns:
        bool: True if valid amount
    """
    return amount >= 0.1 and amount <= 1000000.0  # Min 0.1, Max 1M


def validate_model_hash(hash_string: str) -> bool:
    """
    Validate SHA-256 hash format

    Args:
        hash_string: Hash string to validate

    Returns:
        bool: True if valid SHA-256 format
    """
    # SHA-256 produces 64 character hex string
    pattern = r"^[a-fA-F0-9]{64}$"
    return bool(re.match(pattern, hash_string))


def validate_ed25519_key(key_b64: str, key_type: str = "public") -> bool:
    """
    Validate Ed25519 key format (base64)

    Args:
        key_b64: Base64 encoded key
        key_type: "public" or "private" key type

    Returns:
        bool: True if valid format
    """
    if not isinstance(key_b64, str):
        return False

    # Check if string is empty or too short/long for base64 Ed25519 key
    if not key_b64 or len(key_b64) < 40 or len(key_b64) > 50:
        return False

    try:
        import base64

        # Validate base64 format
        decoded = base64.b64decode(key_b64, validate=True)

        # Ed25519 keys are always 32 bytes
        if len(decoded) != 32:
            return False

        # Additional validation using PyNaCl if available
        try:
            from nacl.signing import SigningKey, VerifyKey

            if key_type == "private":
                # Try to create a SigningKey (will raise if invalid)
                SigningKey(decoded)
            else:  # public key
                # Try to create a VerifyKey (will raise if invalid)
                VerifyKey(decoded)

        except ImportError:
            # PyNaCl not available, just return basic validation
            pass
        except Exception:
            # Key failed PyNaCl validation
            return False

        return True

    except Exception:
        return False


def validate_ed25519_public_key(public_key_b64: str) -> Dict[str, Any]:
    """
    Comprehensive Ed25519 public key validation with detailed results

    Args:
        public_key_b64: Base64 encoded public key

    Returns:
        Dict with validation results: {
            "is_valid": bool,
            "errors": List[str],
            "key_info": Dict (if valid)
        }
    """
    result = {"is_valid": False, "errors": [], "key_info": {}}

    # Basic format checks
    if not isinstance(public_key_b64, str):
        result["errors"].append("Key must be a string")
        return result

    if not public_key_b64.strip():
        result["errors"].append("Key cannot be empty")
        return result

    # Base64 validation
    try:
        import base64

        decoded = base64.b64decode(public_key_b64, validate=True)
    except Exception as e:
        result["errors"].append(f"Invalid base64 format: {str(e)}")
        return result

    # Length validation
    if len(decoded) != 32:
        result["errors"].append(f"Ed25519 keys must be 32 bytes, got {len(decoded)}")
        return result

    # PyNaCl validation
    try:
        from nacl.signing import VerifyKey

        verify_key = VerifyKey(decoded)

        result["is_valid"] = True
        result["key_info"] = {
            "key_length": len(decoded),
            "key_hex": decoded.hex(),
            "is_curve25519": True,
        }

    except ImportError:
        result["errors"].append("PyNaCl library not available for advanced validation")
        # Still consider valid if basic checks pass
        result["is_valid"] = True
        result["key_info"] = {
            "key_length": len(decoded),
            "key_hex": decoded.hex(),
            "validation_level": "basic",
        }

    except Exception as e:
        result["errors"].append(f"Invalid Ed25519 public key: {str(e)}")
        return result

    return result


def validate_round_id(round_id: str) -> bool:
    """
    Validate round ID format

    Args:
        round_id: Round identifier

    Returns:
        bool: True if valid format
    """
    # Format: round_YYYYMMDD_HHMM
    pattern = r"^round_\d{8}_\d{6}$"
    return bool(re.match(pattern, round_id))


def validate_block_data(block_data: Dict[str, Any]) -> List[str]:
    """
    Validate block data structure

    Args:
        block_data: Block data dictionary

    Returns:
        List[str]: List of validation errors (empty if valid)
    """
    errors = []

    required_fields = [
        "block_number",
        "previous_hash",
        "merkle_root",
        "delegate_id",
        "round_id",
        "timestamp",
    ]

    # Check required fields
    for field in required_fields:
        if field not in block_data:
            errors.append(f"Missing required field: {field}")

    # Validate specific fields
    if "block_number" in block_data:
        if (
            not isinstance(block_data["block_number"], int)
            or block_data["block_number"] < 0
        ):
            errors.append("Block number must be non-negative integer")

    if "delegate_id" in block_data:
        if not validate_node_id(block_data["delegate_id"]):
            errors.append("Invalid delegate ID format")

    if "round_id" in block_data:
        if not validate_round_id(block_data["round_id"]):
            errors.append("Invalid round ID format")

    return errors


def sanitize_input(input_string: str, max_length: int = 255) -> str:
    """
    Sanitize user input string

    Args:
        input_string: Input to sanitize
        max_length: Maximum allowed length

    Returns:
        str: Sanitized string
    """
    if not isinstance(input_string, str):
        return ""

    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\']', "", input_string)

    # Limit length
    return sanitized[:max_length].strip()
