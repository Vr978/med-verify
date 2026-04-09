"""
Node Service for DPoS blockchain network
Handles node registration, management, and stake operations
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection

from config.database_config import nodes_collection
from model.node import Node, NodeRegistration, NodeUpdate
from utils.crypto_utils import generate_keypair
from utils.validation_utils import (
    validate_node_id,
    validate_stake_amount,
    validate_ed25519_key,
)


logger = logging.getLogger(__name__)


class NodeService:
    """Service class for managing blockchain nodes"""

    def __init__(self):
        self.collection = nodes_collection

    async def register_node(self, node_data: NodeRegistration) -> dict:
        """
        Register a new node in the network

        Args:
            node_data: Node registration information

        Returns:
            dict: Success/error response with node data
        """
        try:
            # Validate input data
            if not validate_node_id(node_data.node_id):
                return {
                    "success": False,
                    "error": "Invalid node ID format. Use 3-50 alphanumeric characters, underscores, or hyphens.",
                }

            if not validate_stake_amount(node_data.stake_amount):
                return {
                    "success": False,
                    "error": "Invalid stake amount. Must be between 0.1 and 1,000,000.",
                }

            # Check if node_id already exists
            existing_node = await self.collection.find_one(
                {"node_id": node_data.node_id}
            )
            if existing_node:
                logger.warning(
                    f"Node registration failed - Node ID already exists: {node_data.node_id}"
                )
                return {
                    "success": False,
                    "error": f"Node with ID '{node_data.node_id}' already exists",
                }

            # Generate Ed25519 keypair if not provided
            if node_data.public_key:
                # Validate provided public key format
                if not validate_ed25519_key(node_data.public_key, "public"):
                    return {
                        "success": False,
                        "error": "Invalid Ed25519 public key format",
                    }

                # Use provided public key
                public_key = node_data.public_key
                private_key = None  # Not returned when using existing key

                # Check if public key already exists
                existing_key = await self.collection.find_one(
                    {"public_key": public_key}
                )
                if existing_key:
                    logger.warning(
                        f"Node registration failed - Public key already in use: {public_key[:16]}..."
                    )
                    return {
                        "success": False,
                        "error": "Public key is already registered to another node",
                    }
            else:
                # Generate new Ed25519 keypair
                private_key, public_key = generate_keypair()
                logger.info(
                    f"Generated new Ed25519 keypair for node: {node_data.node_id}"
                )

            # Create new node
            node = Node(
                node_id=node_data.node_id,
                name=node_data.name,
                public_key=public_key,
                stake_amount=node_data.stake_amount,
                is_active=True,
                registration_time=datetime.now(timezone.utc),
                last_active=datetime.now(timezone.utc),
            )

            # Insert into database
            result = await self.collection.insert_one(node.model_dump(by_alias=True))

            if result.inserted_id:
                logger.info(
                    f"Node registered successfully: {node_data.node_id} with stake {node_data.stake_amount}"
                )

                # Return the created node data
                created_node = await self.collection.find_one(
                    {"_id": result.inserted_id}
                )
                created_node["_id"] = str(created_node["_id"])

                response_data = {
                    "message": "Node registered successfully",
                    "node": created_node,
                }

                # Include generated keys in response (only when auto-generated)
                if private_key:
                    response_data["keys"] = {
                        "private_key": private_key,
                        "public_key": public_key,
                    }
                    logger.info(
                        f"Returning generated keypair for node: {node_data.node_id}"
                    )

                return {
                    "success": True,
                    "data": response_data,
                }
            else:
                logger.error(f"Failed to insert node: {node_data.node_id}")
                return {
                    "success": False,
                    "error": "Failed to register node in database",
                }

        except Exception as e:
            logger.error(f"Error registering node {node_data.node_id}: {str(e)}")
            return {"success": False, "error": f"Registration error: {str(e)}"}

    async def get_all_nodes(self, include_inactive: bool = False) -> dict:
        """
        Get all nodes in the network

        Args:
            include_inactive: Whether to include inactive nodes

        Returns:
            dict: Success response with list of nodes
        """
        try:
            # Build query filter
            query = {} if include_inactive else {"is_active": True}

            # Get nodes from database
            cursor = self.collection.find(query).sort(
                "stake_amount", -1
            )  # Sort by stake descending
            nodes = await cursor.to_list(length=None)

            # Convert ObjectId to string
            for node in nodes:
                node["_id"] = str(node["_id"])

            total_stake = sum(node["stake_amount"] for node in nodes)
            active_count = len([node for node in nodes if node["is_active"]])

            logger.info(
                f"Retrieved {len(nodes)} nodes (active: {active_count}, total stake: {total_stake})"
            )

            return {
                "success": True,
                "data": {
                    "nodes": nodes,
                    "total_nodes": len(nodes),
                    "active_nodes": active_count,
                    "total_stake": total_stake,
                },
            }

        except Exception as e:
            logger.error(f"Error retrieving nodes: {str(e)}")
            return {"success": False, "error": f"Failed to retrieve nodes: {str(e)}"}

    async def get_node_by_id(self, node_id: str) -> dict:
        """
        Get a specific node by ID

        Args:
            node_id: Node identifier

        Returns:
            dict: Success/error response with node data
        """
        try:
            node = await self.collection.find_one({"node_id": node_id})

            if not node:
                return {
                    "success": False,
                    "error": f"Node with ID '{node_id}' not found",
                }

            node["_id"] = str(node["_id"])

            # Update last active time
            await self.collection.update_one(
                {"node_id": node_id}, {"$set": {"last_active": datetime.now(timezone.utc)}}
            )

            return {"success": True, "data": {"node": node}}

        except Exception as e:
            logger.error(f"Error retrieving node {node_id}: {str(e)}")
            return {"success": False, "error": f"Failed to retrieve node: {str(e)}"}

    async def update_node(self, node_id: str, update_data: NodeUpdate) -> dict:
        """
        Update node information

        Args:
            node_id: Node identifier
            update_data: Fields to update

        Returns:
            dict: Success/error response
        """
        try:
            # Check if node exists
            existing_node = await self.collection.find_one({"node_id": node_id})
            if not existing_node:
                return {
                    "success": False,
                    "error": f"Node with ID '{node_id}' not found",
                }

            # Build update document
            update_doc = {"$set": {"last_active": datetime.now(timezone.utc)}}

            if update_data.name is not None:
                update_doc["$set"]["name"] = update_data.name
            if update_data.stake_amount is not None:
                update_doc["$set"]["stake_amount"] = update_data.stake_amount
            if update_data.is_active is not None:
                update_doc["$set"]["is_active"] = update_data.is_active

            # Update node
            result = await self.collection.update_one({"node_id": node_id}, update_doc)

            if result.modified_count > 0:
                logger.info(f"Node updated successfully: {node_id}")

                # Get updated node
                updated_node = await self.collection.find_one({"node_id": node_id})
                updated_node["_id"] = str(updated_node["_id"])

                return {
                    "success": True,
                    "data": {
                        "message": "Node updated successfully",
                        "node": updated_node,
                    },
                }
            else:
                return {"success": False, "error": "No changes were made to the node"}

        except Exception as e:
            logger.error(f"Error updating node {node_id}: {str(e)}")
            return {"success": False, "error": f"Failed to update node: {str(e)}"}

    async def get_nodes_by_stake_range(
        self, min_stake: float, max_stake: Optional[float] = None
    ) -> dict:
        """
        Get nodes within a specific stake range

        Args:
            min_stake: Minimum stake amount
            max_stake: Maximum stake amount (optional)

        Returns:
            dict: Success response with filtered nodes
        """
        try:
            # Build query
            query = {"stake_amount": {"$gte": min_stake}, "is_active": True}
            if max_stake is not None:
                query["stake_amount"]["$lte"] = max_stake

            cursor = self.collection.find(query).sort("stake_amount", -1)
            nodes = await cursor.to_list(length=None)

            # Convert ObjectId to string
            for node in nodes:
                node["_id"] = str(node["_id"])

            return {
                "success": True,
                "data": {
                    "nodes": nodes,
                    "count": len(nodes),
                    "stake_filter": {"min": min_stake, "max": max_stake},
                },
            }

        except Exception as e:
            logger.error(f"Error filtering nodes by stake: {str(e)}")
            return {"success": False, "error": f"Failed to filter nodes: {str(e)}"}


# Create global service instance
node_service = NodeService()
