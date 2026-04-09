"""
Cryptographic utilities for Ed25519 operations
Handles key generation, signing, and verification
"""

import base64
from typing import Tuple
from datetime import datetime
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import Base64Encoder


def generate_keypair() -> Tuple[str, str]:
    """
    Generate a new Ed25519 keypair

    Returns:
        Tuple[str, str]: (private_key_base64, public_key_base64)
    """
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key

    private_key_b64 = base64.b64encode(bytes(signing_key)).decode("utf-8")
    public_key_b64 = base64.b64encode(bytes(verify_key)).decode("utf-8")

    return private_key_b64, public_key_b64


def create_signing_message(block_data: dict) -> bytes:
    """
    Create a deterministic message for signing from block data

    Args:
        block_data: Block data dictionary containing index, previous_hash, etc.

    Returns:
        bytes: Message to sign
    """
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

    signing_fields = {
        "block_number": block_data["block_number"],
        "previous_hash": block_data["previous_hash"],
        "merkle_root": block_data["merkle_root"],
        "timestamp": timestamp_str,
        "delegate_id": block_data["delegate_id"],
        "round_id": block_data["round_id"],
    }
    # Create deterministic string representation
    message = "|".join(f"{k}:{v}" for k, v in sorted(signing_fields.items()))
    return message.encode("utf-8")


def sign_message(private_key_b64: str, message_bytes: bytes) -> str:
    """
    Sign a message using an Ed25519 private key

    Args:
        private_key_b64: Base64 encoded private key
        message_bytes: Message to sign

    Returns:
        str: Base64 encoded signature
    """
    private_key_bytes = base64.b64decode(private_key_b64)
    signing_key = SigningKey(private_key_bytes)
    signature = signing_key.sign(message_bytes)
    return base64.b64encode(signature.signature).decode("utf-8")


def verify_signature(
    public_key_b64: str, message_bytes: bytes, signature_b64: str
) -> bool:
    """
    Verify an Ed25519 signature

    Args:
        public_key_b64: Base64 encoded public key
        message_bytes: Original message that was signed
        signature_b64: Base64 encoded signature to verify

    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        public_key_bytes = base64.b64decode(public_key_b64)
        verify_key = VerifyKey(public_key_bytes)
        signature_bytes = base64.b64decode(signature_b64)
        verify_key.verify(message_bytes, signature_bytes)
        return True
    except Exception:
        return False


def derive_public_key(private_key_b64: str) -> str:
    """
    Derive the public key from a private key

    Args:
        private_key_b64: Base64 encoded private key

    Returns:
        str: Base64 encoded public key

    Raises:
        ValueError: If the private key is invalid
    """
    try:
        private_key_bytes = base64.b64decode(private_key_b64)
        signing_key = SigningKey(private_key_bytes)
        verify_key = signing_key.verify_key
        return base64.b64encode(bytes(verify_key)).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Invalid private key: {str(e)}")
