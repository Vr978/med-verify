"""
Security dependencies for FastAPI routes
author: Barath Suresh
"""

import os
from typing import Optional
from fastapi import HTTPException, Header, Depends
from jose import jwt, JWTError
from bson import ObjectId
from config.database_config import users_collection

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "secret-key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_AUD = os.getenv("JWT_AUD", "integrity-fl")
JWT_ISS = os.getenv("JWT_ISS", "integrity-fl")


async def get_current_user(authorization: str = Header(..., alias="Authorization")):
    """
    Dependency to get current authenticated user from JWT token.

    Args:
        authorization: Authorization header with Bearer token

    Returns:
        dict: User document from database

    Raises:
        HTTPException: If token is invalid or user not found
    """
    # Extract token from Authorization header
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid authorization header format"
        )

    token = authorization.split(" ", 1)[1]

    try:
        # Decode JWT token
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUD,
            issuer=JWT_ISS,
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=401, detail="Invalid token: missing subject"
            )

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    # Fetch user from database
    try:
        user_doc = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user_doc:
            raise HTTPException(status_code=401, detail="User not found")

        return user_doc
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid user ID")


async def get_optional_user(
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    Optional dependency to get current user (returns None if not authenticated).

    Args:
        authorization: Optional authorization header

    Returns:
        Optional[dict]: User document or None
    """
    if not authorization:
        return None

    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None
