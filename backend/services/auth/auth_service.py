"""
Authentication Service - Business Logic
Handles user registration, login, token management
author: Barath Suresh
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any
from fastapi import HTTPException

from config.database_config import users_collection, refresh_tokens_collection
from config.logging_config import performance_logger
from model.user import User, RefreshToken
from security.security_config import (
    hash_password,
    verify_password,
    create_access_token,
    new_refresh_token,
)


class AuthService:
    """Authentication service for user management and JWT operations"""

    @staticmethod
    async def register_user(email: str, password: str) -> Dict[str, Any]:
        """
        Register a new user and return JWT tokens

        Args:
            email: User email address
            password: Plain text password

        Returns:
            Dict containing access_token, refresh_token, and user info

        Raises:
            HTTPException: If email already exists
        """
        logger = logging.getLogger(__name__)
        start_time = time.time()

        logger.debug(f"Checking if user exists: {email}")

        # Check if user already exists
        db_start = time.time()
        existing = await users_collection.find_one({"email": email})
        performance_logger.log_database_operation(
            "find_one", "users", time.time() - db_start
        )

        if existing:
            logger.warning(f"Registration attempt for existing email: {email}")
            raise HTTPException(status_code=409, detail="Email already registered")

        logger.info(f"Creating new user: {email}")

        # Create user
        user = User(email=email, password_hash=hash_password(password))

        db_start = time.time()
        result = await users_collection.insert_one(
            user.model_dump(by_alias=True, exclude={"id"})
        )
        performance_logger.log_database_operation(
            "insert_one", "users", time.time() - db_start
        )
        user_id = str(result.inserted_id)

        logger.debug(f"User created with ID: {user_id}")

        # Clean up any existing tokens (shouldn't exist, but just in case)
        db_start = time.time()
        await refresh_tokens_collection.delete_many({"user_id": user_id})
        performance_logger.log_database_operation(
            "delete_many", "refresh_tokens", time.time() - db_start
        )

        # Generate tokens
        logger.debug(f"Generating tokens for user: {user_id}")
        access_token = create_access_token(user_id)
        raw_refresh, hash_refresh, exp = new_refresh_token()

        # Save refresh token
        rt = RefreshToken(user_id=user_id, token_hash=hash_refresh, expires_at=exp)
        db_start = time.time()
        await refresh_tokens_collection.insert_one(
            rt.model_dump(by_alias=True, exclude={"id"})
        )
        performance_logger.log_database_operation(
            "insert_one", "refresh_tokens", time.time() - db_start
        )

        total_time = time.time() - start_time
        logger.info(f"User registration completed for {email} in {total_time:.3f}s")

        return {
            "access_token": access_token,
            "refresh_token": raw_refresh,
            "token_type": "bearer",
            "user_id": user_id,
            "email": email,
        }

    @staticmethod
    async def login_user(
        email: str, password: str, max_active_sessions: int = 5
    ) -> Dict[str, Any]:
        """
        Login user and return JWT tokens

        Args:
            email: User email address
            password: Plain text password
            max_active_sessions: Maximum concurrent sessions allowed

        Returns:
            Dict containing access_token, refresh_token, and user info

        Raises:
            HTTPException: If credentials are invalid
        """
        logger = logging.getLogger(__name__)
        start_time = time.time()

        logger.debug(f"Attempting login for: {email}")

        # Find user
        db_start = time.time()
        user_doc = await users_collection.find_one({"email": email})
        performance_logger.log_database_operation(
            "find_one", "users", time.time() - db_start
        )

        if not user_doc or not verify_password(password, user_doc["password_hash"]):
            logger.warning(f"Invalid credentials for: {email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id = str(user_doc["_id"])
        logger.debug(f"User found: {user_id}")

        # Clean up expired and revoked tokens
        logger.debug(f"Cleaning up expired tokens for user: {user_id}")
        db_start = time.time()
        cleanup_result = await refresh_tokens_collection.delete_many(
            {
                "user_id": user_id,
                "$or": [
                    {"revoked": True},
                    {"expires_at": {"$lt": datetime.now(timezone.utc)}},
                ],
            }
        )
        performance_logger.log_database_operation(
            "delete_many", "refresh_tokens", time.time() - db_start
        )

        if cleanup_result.deleted_count > 0:
            logger.debug(f"Cleaned up {cleanup_result.deleted_count} expired tokens")

        # Manage session limits
        logger.debug(f"Managing session limits for user: {user_id}")
        await AuthService._manage_session_limits(user_id, max_active_sessions)

        # Generate new tokens
        logger.debug(f"Generating new tokens for user: {user_id}")
        access_token = create_access_token(user_id)
        raw_refresh, hash_refresh, exp = new_refresh_token()

        # Save refresh token
        rt = RefreshToken(user_id=user_id, token_hash=hash_refresh, expires_at=exp)
        db_start = time.time()
        await refresh_tokens_collection.insert_one(
            rt.model_dump(by_alias=True, exclude={"id"})
        )
        performance_logger.log_database_operation(
            "insert_one", "refresh_tokens", time.time() - db_start
        )

        total_time = time.time() - start_time
        logger.info(f"User login completed for {email} in {total_time:.3f}s")

        return {
            "access_token": access_token,
            "refresh_token": raw_refresh,
            "token_type": "bearer",
            "user_id": user_id,
            "email": email,
        }

    @staticmethod
    async def refresh_token(refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token

        Args:
            refresh_token: Raw refresh token string

        Returns:
            Dict containing new access_token and refresh_token

        Raises:
            HTTPException: If refresh token is invalid or expired
        """
        # Hash the token to find it in database
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        # Find the refresh token record
        token_record = await refresh_tokens_collection.find_one(
            {
                "token_hash": token_hash,
                "revoked": False,
                "expires_at": {"$gt": datetime.now(timezone.utc)},
            }
        )

        if not token_record:
            raise HTTPException(
                status_code=401, detail="Invalid or expired refresh token"
            )

        user_id = token_record["user_id"]

        # Delete the old token (single-use refresh tokens)
        await refresh_tokens_collection.delete_one({"_id": token_record["_id"]})

        # Clean up other expired/revoked tokens
        await refresh_tokens_collection.delete_many(
            {
                "user_id": user_id,
                "$or": [
                    {"revoked": True},
                    {"expires_at": {"$lt": datetime.now(timezone.utc)}},
                ],
            }
        )

        # Issue new tokens
        access_token = create_access_token(user_id)
        raw_refresh, hash_refresh, exp = new_refresh_token()

        rt = RefreshToken(user_id=user_id, token_hash=hash_refresh, expires_at=exp)
        await refresh_tokens_collection.insert_one(
            rt.model_dump(by_alias=True, exclude={"id"})
        )

        return {
            "access_token": access_token,
            "refresh_token": raw_refresh,
            "token_type": "bearer",
        }

    @staticmethod
    async def logout_user(refresh_token: str) -> bool:
        """
        Logout user by invalidating refresh token

        Args:
            refresh_token: Raw refresh token string

        Returns:
            bool: True if logout successful
        """
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        result = await refresh_tokens_collection.delete_one({"token_hash": token_hash})
        return result.deleted_count > 0

    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by user ID

        Args:
            user_id: User's unique identifier

        Returns:
            User document or None if not found
        """
        from bson import ObjectId

        try:
            user_doc = await users_collection.find_one({"_id": ObjectId(user_id)})
            if user_doc:
                user_doc["_id"] = str(user_doc["_id"])
            return user_doc
        except Exception:
            return None

    @staticmethod
    async def _manage_session_limits(user_id: str, max_sessions: int):
        """
        Manage active session limits by removing oldest sessions if needed

        Args:
            user_id: User's unique identifier
            max_sessions: Maximum allowed concurrent sessions
        """
        # Count active sessions
        active_count = await refresh_tokens_collection.count_documents(
            {
                "user_id": user_id,
                "revoked": False,
                "expires_at": {"$gt": datetime.now(timezone.utc)},
            }
        )

        # Remove oldest sessions if we're at or above limit
        if active_count >= max_sessions:
            tokens_to_delete = active_count - max_sessions + 1
            oldest_tokens = (
                await refresh_tokens_collection.find(
                    {
                        "user_id": user_id,
                        "revoked": False,
                        "expires_at": {"$gt": datetime.now(timezone.utc)},
                    }
                )
                .sort("created_at", 1)
                .limit(tokens_to_delete)
                .to_list(length=None)
            )

            if oldest_tokens:
                oldest_ids = [token["_id"] for token in oldest_tokens]
                await refresh_tokens_collection.delete_many(
                    {"_id": {"$in": oldest_ids}}
                )
