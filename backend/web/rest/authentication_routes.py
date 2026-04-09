"""
Authentication Routes - API Layer
Uses AuthService for business logic
author: Barath Suresh
"""

import logging
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
import os
from dotenv import load_dotenv

from services.auth.auth_service import AuthService
from config.logging_config import security_logger

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])

# Get max active sessions from environment variable
MAX_ACTIVE_SESSIONS = int(os.getenv("MAX_ACTIVE_SESSIONS", "5"))


class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterIn, http_request: Request):
    """
    Register a new user

    Args:
        request: User registration data
        http_request: FastAPI request object for logging

    Returns:
        TokenOut: JWT tokens for authenticated access
    """
    logger = logging.getLogger(__name__)
    client_ip = http_request.client.host if http_request.client else "unknown"

    logger.info(f"Registration attempt for {request.email} from {client_ip}")

    try:
        result = await AuthService.register_user(request.email, request.password)

        # Log successful registration
        security_logger.log_registration(request.email, True)
        logger.info(f"User registration successful: {request.email}")

        return TokenOut(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            token_type=result["token_type"],
        )

    except HTTPException as e:
        # Log failed registration
        security_logger.log_registration(request.email, False, e.detail)
        logger.warning(f"User registration failed: {request.email} - {e.detail}")
        raise
    except Exception as e:
        # Log unexpected error
        security_logger.log_registration(request.email, False, str(e))
        logger.error(
            f"Unexpected error during registration for {request.email}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/login", response_model=TokenOut)
async def login(request: LoginIn, http_request: Request):
    """
    Login user with email and password

    Args:
        request: User login credentials
        http_request: FastAPI request object for logging

    Returns:
        TokenOut: JWT tokens for authenticated access
    """
    logger = logging.getLogger(__name__)
    client_ip = http_request.client.host if http_request.client else "unknown"
    user_agent = http_request.headers.get("user-agent", "unknown")

    logger.info(f"Login attempt for {request.email} from {client_ip}")

    try:
        result = await AuthService.login_user(
            request.email, request.password, MAX_ACTIVE_SESSIONS
        )

        # Log successful login
        security_logger.log_login_attempt(request.email, True, client_ip, user_agent)
        logger.info(f"User login successful: {request.email}")

        return TokenOut(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            token_type=result["token_type"],
        )

    except HTTPException as e:
        # Log failed login
        security_logger.log_login_attempt(request.email, False, client_ip, user_agent)
        logger.warning(f"User login failed: {request.email} - {e.detail}")
        raise
    except Exception as e:
        # Log unexpected error
        security_logger.log_authentication_error(str(e), f"login for {request.email}")
        logger.error(f"Unexpected error during login for {request.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/refresh", response_model=TokenOut)
async def refresh_token(request: RefreshIn, http_request: Request):
    """
    Refresh access token using refresh token

    Args:
        request: Refresh token data
        http_request: FastAPI request object for logging

    Returns:
        TokenOut: New JWT tokens
    """
    logger = logging.getLogger(__name__)
    client_ip = http_request.client.host if http_request.client else "unknown"

    logger.debug(f"Token refresh attempt from {client_ip}")

    try:
        result = await AuthService.refresh_token(request.refresh_token)

        # Extract user ID from result for logging (if available)
        user_id = result.get("user_id", "unknown")
        security_logger.log_token_refresh(user_id, True)
        logger.info(f"Token refresh successful for user {user_id}")

        return TokenOut(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            token_type=result["token_type"],
        )

    except HTTPException as e:
        security_logger.log_token_refresh("unknown", False)
        logger.warning(f"Token refresh failed from {client_ip}: {e.detail}")
        raise
    except Exception as e:
        security_logger.log_authentication_error(str(e), "token refresh")
        logger.error(
            f"Unexpected error during token refresh from {client_ip}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/logout")
async def logout(request: LogoutIn, http_request: Request):
    """
    Logout user by invalidating refresh token

    Args:
        request: Refresh token to invalidate
        http_request: FastAPI request object for logging

    Returns:
        dict: Success confirmation
    """
    logger = logging.getLogger(__name__)
    client_ip = http_request.client.host if http_request.client else "unknown"

    logger.debug(f"Logout attempt from {client_ip}")

    try:
        success = await AuthService.logout_user(request.refresh_token)

        # Log logout attempt
        security_logger.log_logout(
            "unknown", success
        )  # We don't have user_id from token here

        if success:
            logger.info(f"User logout successful from {client_ip}")
        else:
            logger.warning(f"Logout attempt failed (token not found) from {client_ip}")

        return {"success": success, "message": "Logged out successfully"}

    except Exception as e:
        security_logger.log_authentication_error(str(e), "logout")
        logger.error(f"Unexpected error during logout from {client_ip}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
