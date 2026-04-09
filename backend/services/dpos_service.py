"""
DPoS Service for Delegated Proof of Stake consensus mechanism
Handles delegate elections, voting, and round management
"""

import logging
import hashlib
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorCollection

from config.database_config import (
    nodes_collection,
    elections_collection,
    votes_collection,
)
from model.election import Election, ElectionRequest, Delegate, Vote
from services.node_service import node_service


logger = logging.getLogger(__name__)


class DPoSService:
    """Service class for managing DPoS consensus"""

    def __init__(self):
        self.elections_collection = elections_collection
        self.votes_collection = votes_collection
        self.nodes_collection = nodes_collection

    def generate_round_id(self, timestamp: datetime) -> str:
        """Generate a unique round ID based on timestamp"""
        round_string = f"round_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        return round_string

    async def start_new_election(self, election_request: ElectionRequest) -> dict:
        """
        Start a new delegate election round

        Args:
            election_request: Election parameters

        Returns:
            dict: Success/error response with election data
        """
        try:
            # Check if there's already an active election
            active_election = await self.elections_collection.find_one(
                {"is_active": True}
            )
            if active_election:
                logger.warning(
                    "Election request rejected - Active election already exists"
                )
                return {
                    "success": False,
                    "error": "An election is already active. Wait for it to complete.",
                }

            # Get all active nodes
            nodes_result = await node_service.get_all_nodes(include_inactive=False)
            if not nodes_result["success"]:
                return nodes_result

            active_nodes = nodes_result["data"]["nodes"]

            if len(active_nodes) < election_request.delegate_count:
                return {
                    "success": False,
                    "error": f"Not enough active nodes ({len(active_nodes)}) for requested delegates ({election_request.delegate_count})",
                }

            # Create new election
            now = datetime.now(timezone.utc)
            round_id = self.generate_round_id(now)

            election = Election(
                round_id=round_id,
                election_time=now,
                start_time=now,
                end_time=now + timedelta(hours=election_request.round_duration_hours),
                delegates=[],
                total_stake=nodes_result["data"]["total_stake"],
                delegate_count=election_request.delegate_count,
                is_active=True,
                blocks_created=0,
            )

            # Insert election into database
            result = await self.elections_collection.insert_one(
                election.dict(by_alias=True)
            )

            if result.inserted_id:
                # Perform automatic election based on stake
                election_result = await self._conduct_stake_based_election(
                    round_id, active_nodes, election_request.delegate_count
                )

                if election_result["success"]:
                    logger.info(
                        f"New election started: {round_id} with {election_request.delegate_count} delegates"
                    )
                    return {
                        "success": True,
                        "data": {
                            "message": "Election started successfully",
                            "round_id": round_id,
                            "delegates": election_result["data"]["delegates"],
                            "election_info": {
                                "start_time": now.isoformat(),
                                "end_time": (
                                    now
                                    + timedelta(
                                        hours=election_request.round_duration_hours
                                    )
                                ).isoformat(),
                                "total_stake": nodes_result["data"]["total_stake"],
                                "participating_nodes": len(active_nodes),
                            },
                        },
                    }
                else:
                    # Clean up failed election
                    await self.elections_collection.delete_one(
                        {"_id": result.inserted_id}
                    )
                    return election_result
            else:
                return {
                    "success": False,
                    "error": "Failed to create election in database",
                }

        except Exception as e:
            logger.error(f"Error starting election: {str(e)}")
            return {"success": False, "error": f"Election error: {str(e)}"}

    async def _conduct_stake_based_election(
        self, round_id: str, nodes: List[dict], delegate_count: int
    ) -> dict:
        """
        Conduct election based on stake amounts (simplified DPoS)

        Args:
            round_id: Round identifier
            nodes: List of active nodes
            delegate_count: Number of delegates to elect

        Returns:
            dict: Election results
        """
        try:
            # Sort nodes by stake amount (descending)
            sorted_nodes = sorted(nodes, key=lambda x: x["stake_amount"], reverse=True)

            # Select top nodes as delegates
            elected_delegates = []
            for i in range(min(delegate_count, len(sorted_nodes))):
                node = sorted_nodes[i]
                delegate = Delegate(
                    node_id=node["node_id"],
                    name=node["name"],
                    stake_amount=node["stake_amount"],
                    votes_received=node[
                        "stake_amount"
                    ],  # In this simplified version, stake = votes
                    is_active=True,
                )
                elected_delegates.append(delegate)

            # Update election with delegates
            update_result = await self.elections_collection.update_one(
                {"round_id": round_id},
                {
                    "$set": {
                        "delegates": [delegate.dict() for delegate in elected_delegates]
                    }
                },
            )

            if update_result.modified_count > 0:
                logger.info(
                    f"Elected {len(elected_delegates)} delegates for round {round_id}"
                )
                return {
                    "success": True,
                    "data": {
                        "delegates": [
                            delegate.dict() for delegate in elected_delegates
                        ],
                        "total_elected": len(elected_delegates),
                    },
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to update election with delegates",
                }

        except Exception as e:
            logger.error(f"Error conducting election: {str(e)}")
            return {"success": False, "error": f"Election process error: {str(e)}"}

    async def get_current_delegates(self) -> dict:
        """
        Get delegates for the current active round

        Returns:
            dict: Current delegates information
        """
        try:
            # Find active election
            active_election = await self.elections_collection.find_one(
                {"is_active": True}
            )

            if not active_election:
                return {"success": False, "error": "No active election round found"}

            active_election["_id"] = str(active_election["_id"])

            logger.info(
                f"Retrieved current delegates for round {active_election['round_id']}"
            )

            return {
                "success": True,
                "data": {
                    "round_id": active_election["round_id"],
                    "delegates": active_election["delegates"],
                    "election_info": {
                        "start_time": active_election["start_time"].isoformat(),
                        "end_time": active_election["end_time"].isoformat(),
                        "total_stake": active_election["total_stake"],
                        "blocks_created": active_election["blocks_created"],
                    },
                },
            }

        except Exception as e:
            logger.error(f"Error retrieving current delegates: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to retrieve delegates: {str(e)}",
            }

    async def get_delegates_by_round(self, round_id: str) -> dict:
        """
        Get delegates for a specific round

        Args:
            round_id: Round identifier

        Returns:
            dict: Delegates information for the round
        """
        try:
            election = await self.elections_collection.find_one({"round_id": round_id})

            if not election:
                return {
                    "success": False,
                    "error": f"Election round '{round_id}' not found",
                }

            election["_id"] = str(election["_id"])

            return {
                "success": True,
                "data": {
                    "round_id": round_id,
                    "delegates": election["delegates"],
                    "election_info": {
                        "start_time": election["start_time"].isoformat(),
                        "end_time": election["end_time"].isoformat(),
                        "is_active": election["is_active"],
                        "total_stake": election["total_stake"],
                        "blocks_created": election["blocks_created"],
                    },
                },
            }

        except Exception as e:
            logger.error(f"Error retrieving delegates for round {round_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to retrieve delegates: {str(e)}",
            }

    async def is_valid_delegate(self, delegate_id: str, round_id: str) -> bool:
        """
        Check if a node is a valid delegate for the given round

        Args:
            delegate_id: Node ID to check
            round_id: Round identifier

        Returns:
            bool: True if node is a valid delegate
        """
        try:
            election = await self.elections_collection.find_one(
                {"round_id": round_id, "is_active": True}
            )

            if not election:
                return False

            # Check if delegate_id is in the list of elected delegates
            for delegate in election.get("delegates", []):
                if delegate["node_id"] == delegate_id and delegate["is_active"]:
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking delegate validity: {str(e)}")
            return False

    async def get_election_history(self, limit: int = 10) -> dict:
        """
        Get history of past elections

        Args:
            limit: Maximum number of elections to return

        Returns:
            dict: Election history
        """
        try:
            cursor = (
                self.elections_collection.find().sort("election_time", -1).limit(limit)
            )
            elections = await cursor.to_list(length=None)

            # Convert ObjectId to string
            for election in elections:
                election["_id"] = str(election["_id"])
                election["start_time"] = election["start_time"].isoformat()
                election["end_time"] = election["end_time"].isoformat()
                election["election_time"] = election["election_time"].isoformat()

            return {
                "success": True,
                "data": {"elections": elections, "count": len(elections)},
            }

        except Exception as e:
            logger.error(f"Error retrieving election history: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to retrieve election history: {str(e)}",
            }

    async def end_current_round(self) -> dict:
        """
        End the current active round (for manual control)

        Returns:
            dict: Success/error response
        """
        try:
            result = await self.elections_collection.update_one(
                {"is_active": True},
                {"$set": {"is_active": False, "end_time": datetime.now(timezone.utc)}},
            )

            if result.modified_count > 0:
                logger.info("Current election round ended manually")
                return {
                    "success": True,
                    "data": {"message": "Current round ended successfully"},
                }
            else:
                return {"success": False, "error": "No active round found to end"}

        except Exception as e:
            logger.error(f"Error ending current round: {str(e)}")
            return {"success": False, "error": f"Failed to end round: {str(e)}"}

    async def check_and_end_expired_rounds(self) -> dict:
        """
        Check if the current active round has expired and end it automatically
        This method can be called manually or by scheduled tasks

        Returns:
            dict: Result of the expiry check and any actions taken
        """
        try:
            # Get active election
            active_election = await self.elections_collection.find_one(
                {"is_active": True}
            )

            if not active_election:
                return {
                    "success": True,
                    "data": {
                        "message": "No active election found",
                        "action_taken": False,
                    },
                }

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
                # Round has expired - end it
                end_result = await self.end_current_round()

                if end_result["success"]:
                    logger.info(
                        f"Round {active_election['round_id']} automatically ended due to expiry"
                    )
                    return {
                        "success": True,
                        "data": {
                            "message": f"Round {active_election['round_id']} ended due to expiry",
                            "round_id": active_election["round_id"],
                            "expired_at": current_time.isoformat(),
                            "action_taken": True,
                        },
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to end expired round: {end_result['error']}",
                    }
            else:
                # Round is still active
                remaining_time = end_time - current_time
                return {
                    "success": True,
                    "data": {
                        "message": "Round is still active",
                        "round_id": active_election["round_id"],
                        "expires_at": end_time.isoformat(),
                        "remaining_seconds": remaining_time.total_seconds(),
                        "action_taken": False,
                    },
                }

        except Exception as e:
            logger.error(f"Error checking expired rounds: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to check expired rounds: {str(e)}",
            }


# Create global service instance
dpos_service = DPoSService()
