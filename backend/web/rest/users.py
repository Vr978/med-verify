"""
Users Router - API Layer
Uses proper authentication dependencies
author: Barath Suresh
"""

import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from security.dependencies import get_current_user

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


class MeOut(BaseModel):
    """Response model for current user information"""

    id: str
    email: str
    email_verified: bool


@router.get("/me", response_model=MeOut)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user information

    Returns:
        MeOut: Current user data
    """
    user_id = str(current_user["_id"])
    logger.info(f"User {user_id} requested their profile information")

    try:
        user_response = MeOut(
            id=user_id,
            email=current_user["email"],
            email_verified=current_user["email_verified"],
        )
        logger.debug(f"Successfully retrieved profile for user {user_id}")
        return user_response

    except Exception as e:
        logger.error(f"Error retrieving profile for user {user_id}: {str(e)}")
        raise
