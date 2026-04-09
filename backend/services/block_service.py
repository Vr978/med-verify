"""
Block Service for DPoS blockchain
Handles block creation, validation, and chain management
"""

import logging
import hashlib
import json
from typing import List, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection

from config.database_config import (
    blocks_collection,
    elections_collection,
    nodes_collection,
)
from model.block import Block, BlockCreate, Transaction
from services.dpos_service import dpos_service
from services.node_service import node_service
from utils.crypto_utils import (
    create_signing_message,
    sign_message,
    verify_signature,
    derive_public_key,
)
from utils.hash_utils import calculate_block_hash, calculate_merkle_root
from utils.validation_utils import validate_block_data, validate_model_hash


logger = logging.getLogger(__name__)


class BlockService:
    """Service class for managing blockchain blocks"""

    def __init__(self):
        self.collection = blocks_collection
        self.elections_collection = elections_collection

    def calculate_hash(self, data: str) -> str:
        """Calculate SHA-256 hash of data"""
        from utils.hash_utils import calculate_sha256

        return calculate_sha256(data)
        # Create deterministic string representation for hashing
        hash_data = {
            "block_number": block_data["block_number"],
            "previous_hash": block_data["previous_hash"],
            "merkle_root": block_data["merkle_root"],
            "timestamp": (
                block_data["timestamp"].isoformat()
                if isinstance(block_data["timestamp"], datetime)
                else block_data["timestamp"]
            ),
            "delegate_id": block_data["delegate_id"],
            "round_id": block_data["round_id"],
            "model_hashes": sorted(block_data["model_hashes"]),  # Sort for determinism
        }

        hash_string = json.dumps(hash_data, sort_keys=True)
        return self.calculate_hash(hash_string)

    def calculate_merkle_root(self, model_hashes: List[str]) -> str:
        """Use utils function for Merkle root calculation"""
        return calculate_merkle_root(model_hashes)

    async def get_latest_block(self) -> Optional[dict]:
        """Get the latest block in the chain"""
        try:
            latest_block = await self.collection.find_one(sort=[("block_number", -1)])
            if latest_block:
                latest_block["_id"] = str(latest_block["_id"])
            return latest_block
        except Exception as e:
            logger.error(f"Error getting latest block: {str(e)}")
            return None

    async def create_genesis_block(self) -> dict:
        """
        Create the genesis block (first block in the chain)

        Returns:
            dict: Success/error response
        """
        try:
            # Check if genesis block already exists
            existing_genesis = await self.collection.find_one({"block_number": 0})
            if existing_genesis:
                return {"success": False, "error": "Genesis block already exists"}

            # Create genesis block data directly as dict
            timestamp = datetime.now(timezone.utc)
            genesis_data = {
                "block_id": "genesis",
                "block_number": 0,
                "previous_hash": "0" * 64,  # Genesis has no previous block
                "merkle_root": self.calculate_merkle_root([]),
                "timestamp": timestamp.isoformat() + "Z",  # Store as ISO string
                "delegate_id": "system",
                "round_id": "genesis",
                "model_hashes": [],
                "transaction_count": 0,
                "block_hash": "",  # Will be calculated
                "signature": None,
                "size_bytes": 0,
                "is_valid": True,
                "metadata": {},
            }

            # Calculate block hash
            genesis_data["block_hash"] = calculate_block_hash(genesis_data)

            # Insert genesis block
            result = await self.collection.insert_one(genesis_data)

            if result.inserted_id:
                logger.info("Genesis block created successfully")
                return {
                    "success": True,
                    "data": {
                        "message": "Genesis block created",
                        "block_id": "genesis",
                        "block_number": 0,
                    },
                }
            else:
                return {"success": False, "error": "Failed to create genesis block"}

        except Exception as e:
            logger.error(f"Error creating genesis block: {str(e)}")
            return {
                "success": False,
                "error": f"Genesis block creation error: {str(e)}",
            }

    async def add_block(self, block_create: BlockCreate) -> dict:
        """
        Add a new block to the blockchain

        Args:
            block_create: Block creation data including private key

        Returns:
            dict: Success/error response with block data
        """
        try:
            # Validate model hash format
            if not validate_model_hash(block_create.model_hash):
                return {
                    "success": False,
                    "error": "Invalid model hash format. Must be 64-character SHA-256 hash.",
                }

            # Verify delegate is authorized for current round
            is_valid_delegate = await dpos_service.is_valid_delegate(
                block_create.delegate_id, block_create.round_id
            )

            if not is_valid_delegate:
                logger.warning(
                    f"Block rejected - Invalid delegate: {block_create.delegate_id} for round {block_create.round_id}"
                )
                return {
                    "success": False,
                    "error": f"Node '{block_create.delegate_id}' is not an authorized delegate for round '{block_create.round_id}'",
                }

            # SECURITY: Verify that the private key belongs to the claimed delegate
            try:
                # Derive public key from provided private key
                derived_public_key = derive_public_key(block_create.private_key_b64)

                # Get the delegate's registered public key from the node service
                delegate_result = await node_service.get_node_by_id(
                    block_create.delegate_id
                )
                if not delegate_result["success"]:
                    logger.error(
                        f"Block rejected - Delegate node not found: {block_create.delegate_id}"
                    )
                    return {
                        "success": False,
                        "error": f"Delegate node '{block_create.delegate_id}' not found in registered nodes",
                    }

                registered_public_key = delegate_result["data"]["node"]["public_key"]

                # Verify the derived public key matches the registered public key
                if derived_public_key != registered_public_key:
                    logger.warning(
                        f"Block rejected - Private key ownership verification failed for delegate: {block_create.delegate_id}"
                    )
                    return {
                        "success": False,
                        "error": f"Private key does not belong to delegate '{block_create.delegate_id}'. This is a security violation.",
                    }

                logger.info(
                    f"Private key ownership verified for delegate: {block_create.delegate_id}"
                )

            except ValueError as e:
                logger.error(f"Block rejected - Invalid private key format: {str(e)}")
                return {
                    "success": False,
                    "error": f"Invalid private key format: {str(e)}",
                }
            except Exception as e:
                logger.error(
                    f"Block rejected - Private key verification error: {str(e)}"
                )
                return {
                    "success": False,
                    "error": f"Private key verification failed: {str(e)}",
                }

            # Get latest block for chain continuity
            latest_block = await self.get_latest_block()
            if latest_block is None:
                # Create genesis block first
                genesis_result = await self.create_genesis_block()
                if not genesis_result["success"]:
                    return genesis_result
                latest_block = await self.get_latest_block()

            # Create new block
            new_block_number = latest_block["block_number"] + 1

            # Combine primary hash with collaborative hashes
            model_hashes = [block_create.model_hash]
            if block_create.collaborative_hashes:
                model_hashes.extend(block_create.collaborative_hashes)
                logger.info(
                    f"Block includes {len(block_create.collaborative_hashes)} collaborative hashes"
                )

            timestamp = datetime.now(timezone.utc)

            block_data = {
                "block_id": f"block_{new_block_number}",
                "block_number": new_block_number,
                "previous_hash": latest_block["block_hash"],
                "merkle_root": self.calculate_merkle_root(model_hashes),
                "timestamp": timestamp.isoformat()
                + "Z",  # Store as ISO string with Z suffix
                "delegate_id": block_create.delegate_id,
                "round_id": block_create.round_id,
                "model_hashes": model_hashes,
                "transaction_count": len(model_hashes),
                "block_hash": "",  # Will be calculated
                "signature": None,  # Will be added after hash calculation
                "size_bytes": len(json.dumps(model_hashes)),
                "metadata": block_create.metadata or {},
            }

            # Validate block data structure
            validation_errors = validate_block_data(block_data)
            if validation_errors:
                logger.error(f"Block validation failed: {validation_errors}")
                return {
                    "success": False,
                    "error": f"Block validation failed: {'; '.join(validation_errors)}",
                }

            # Calculate block hash
            block_data["block_hash"] = calculate_block_hash(block_data)

            # Create signing message and sign with delegate's private key
            message = create_signing_message(block_data)
            block_data["signature"] = sign_message(
                block_create.private_key_b64, message
            )

            # Create final block model
            new_block = Block(
                **block_data,
                is_valid=True,
            )

            # Use the original block_data for insertion, not the model dump
            block_dict = block_data.copy()

            # Insert block into database
            result = await self.collection.insert_one(block_dict)

            if result.inserted_id:
                # Update election block count
                await self.elections_collection.update_one(
                    {"round_id": block_create.round_id}, {"$inc": {"blocks_created": 1}}
                )

                logger.info(
                    f"Block added successfully: #{new_block_number} by delegate {block_create.delegate_id}"
                )

                # Return created block data
                created_block = await self.collection.find_one(
                    {"_id": result.inserted_id}
                )
                created_block["_id"] = str(created_block["_id"])

                return {
                    "success": True,
                    "data": {
                        "message": "Block added successfully",
                        "block": created_block,
                    },
                }
            else:
                return {"success": False, "error": "Failed to add block to database"}

        except Exception as e:
            logger.error(f"Error adding block: {str(e)}")
            return {"success": False, "error": f"Block creation error: {str(e)}"}

    async def get_blockchain(self, limit: Optional[int] = None) -> dict:
        """
        Get the entire blockchain or recent blocks

        Args:
            limit: Maximum number of blocks to return (None for all)

        Returns:
            dict: Success response with blockchain data
        """
        try:
            # Build query
            cursor = self.collection.find().sort("block_number", 1)  # Ascending order

            if limit:
                cursor = cursor.limit(limit)

            blocks = await cursor.to_list(length=None)

            # Convert ObjectId to string and format timestamps
            for block in blocks:
                block["_id"] = str(block["_id"])
                if isinstance(block["timestamp"], datetime):
                    block["timestamp"] = block["timestamp"].isoformat()

            # Get chain statistics
            total_blocks = len(blocks)
            latest_block_number = blocks[-1]["block_number"] if blocks else -1

            logger.info(
                f"Retrieved blockchain: {total_blocks} blocks (latest: #{latest_block_number})"
            )

            return {
                "success": True,
                "data": {
                    "blocks": blocks,
                    "chain_info": {
                        "total_blocks": total_blocks,
                        "latest_block_number": latest_block_number,
                        "genesis_hash": blocks[0]["block_hash"] if blocks else None,
                    },
                },
            }

        except Exception as e:
            logger.error(f"Error retrieving blockchain: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to retrieve blockchain: {str(e)}",
            }

    async def verify_chain_integrity(self) -> dict:
        """
        Verify the integrity of the entire blockchain including signatures

        Returns:
            dict: Verification results
        """
        try:
            # Get all blocks in order
            cursor = self.collection.find().sort("block_number", 1)
            blocks = await cursor.to_list(length=None)

            if not blocks:
                return {
                    "success": True,
                    "data": {
                        "message": "No blocks to verify",
                        "is_valid": True,
                        "issues": [],
                    },
                }

            issues = []

            # Verify each block
            for i, block in enumerate(blocks):
                block_number = block["block_number"]

                # Skip signature verification for genesis block
                if block_number > 0:
                    # Get delegate's public key from nodes collection
                    delegate = await nodes_collection.find_one(
                        {"node_id": block["delegate_id"]}
                    )
                    if not delegate:
                        issues.append(
                            {
                                "block_number": block_number,
                                "issue": "Delegate not found",
                                "delegate_id": block["delegate_id"],
                            }
                        )
                        continue

                    # Verify block signature
                    message = create_signing_message(block)
                    if not verify_signature(
                        delegate["public_key"], message, block["signature"]
                    ):
                        issues.append(
                            {
                                "block_number": block_number,
                                "issue": "Invalid block signature",
                                "delegate_id": block["delegate_id"],
                            }
                        )

                # Verify block hash
                expected_hash = calculate_block_hash(block)
                if block["block_hash"] != expected_hash:
                    issues.append(
                        {
                            "block_number": block_number,
                            "issue": "Invalid block hash",
                            "expected": expected_hash,
                            "actual": block["block_hash"],
                        }
                    )

                # Verify chain continuity (except genesis)
                if i > 0:
                    previous_block = blocks[i - 1]
                    if block["previous_hash"] != previous_block["block_hash"]:
                        issues.append(
                            {
                                "block_number": block_number,
                                "issue": "Broken chain link",
                                "expected_previous": previous_block["block_hash"],
                                "actual_previous": block["previous_hash"],
                            }
                        )

                # Verify block number sequence
                if block_number != i:
                    issues.append(
                        {
                            "block_number": block_number,
                            "issue": "Invalid block number sequence",
                            "expected": i,
                            "actual": block_number,
                        }
                    )

            is_valid = len(issues) == 0

            logger.info(
                f"Chain verification completed: {'VALID' if is_valid else 'INVALID'} ({len(issues)} issues)"
            )

            return {
                "success": True,
                "data": {
                    "message": f"Chain verification completed",
                    "is_valid": is_valid,
                    "total_blocks": len(blocks),
                    "issues_found": len(issues),
                    "issues": issues,
                },
            }

        except Exception as e:
            logger.error(f"Error verifying chain integrity: {str(e)}")
            return {"success": False, "error": f"Chain verification error: {str(e)}"}

    async def get_block_by_number(self, block_number: int) -> dict:
        """
        Get a specific block by its number

        Args:
            block_number: Block number to retrieve

        Returns:
            dict: Success/error response with block data
        """
        try:
            block = await self.collection.find_one({"block_number": block_number})

            if not block:
                return {"success": False, "error": f"Block #{block_number} not found"}

            block["_id"] = str(block["_id"])
            if isinstance(block["timestamp"], datetime):
                block["timestamp"] = block["timestamp"].isoformat()

            return {"success": True, "data": {"block": block}}

        except Exception as e:
            logger.error(f"Error retrieving block #{block_number}: {str(e)}")
            return {"success": False, "error": f"Failed to retrieve block: {str(e)}"}

    async def get_blocks_by_delegate(self, delegate_id: str) -> dict:
        """
        Get all blocks created by a specific delegate

        Args:
            delegate_id: Delegate node ID

        Returns:
            dict: Success response with delegate's blocks
        """
        try:
            cursor = self.collection.find({"delegate_id": delegate_id}).sort(
                "block_number", 1
            )
            blocks = await cursor.to_list(length=None)

            # Convert ObjectId to string and format timestamps
            for block in blocks:
                block["_id"] = str(block["_id"])
                if isinstance(block["timestamp"], datetime):
                    block["timestamp"] = block["timestamp"].isoformat()

            return {
                "success": True,
                "data": {
                    "delegate_id": delegate_id,
                    "blocks": blocks,
                    "total_blocks": len(blocks),
                },
            }

        except Exception as e:
            logger.error(
                f"Error retrieving blocks for delegate {delegate_id}: {str(e)}"
            )
            return {
                "success": False,
                "error": f"Failed to retrieve delegate blocks: {str(e)}",
            }


# Create global service instance
block_service = BlockService()
