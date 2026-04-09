"""
System Service - Business Logic
Handles health checks, system monitoring, and debug operations for auth system
author: Barath Suresh
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from config.database_config import (
    users_collection,
    refresh_tokens_collection,
)

logger = logging.getLogger(__name__)


class SystemService:
    """Business logic for system health and monitoring"""

    @staticmethod
    async def get_comprehensive_health() -> Dict[str, Any]:
        """
        Get comprehensive system health status for auth system

        Returns:
            Dict containing detailed health information for all components
        """
        health_status = {
            "service": "auth-api",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {},
        }

        # Test database connections and get counts for auth collections
        try:
            user_count = await users_collection.count_documents({})
            token_count = await refresh_tokens_collection.count_documents(
                {"revoked": False}
            )

            health_status["components"]["database"] = {
                "status": "healthy",
                "collections": {
                    "users": user_count,
                    "active_tokens": token_count,
                },
            }

        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["status"] = "degraded"

        # Check authentication service
        try:
            import os

            jwt_secret = os.getenv("JWT_SECRET")
            jwt_algorithm = os.getenv("JWT_ALGORITHM")

            auth_healthy = jwt_secret and len(jwt_secret) > 10 and jwt_algorithm

            health_status["components"]["authentication"] = {
                "status": "healthy" if auth_healthy else "misconfigured",
                "jwt_configured": bool(jwt_secret),
                "algorithm_set": bool(jwt_algorithm),
            }

            if not auth_healthy:
                health_status["status"] = "degraded"

        except Exception as e:
            logger.error(f"Authentication health check failed: {str(e)}")
            health_status["components"]["authentication"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["status"] = "degraded"

        # Check auth service availability
        try:
            from services.auth.auth_service import AuthService

            health_status["components"]["auth_service"] = {
                "status": "healthy",
                "description": "Authentication service available",
            }

        except Exception as e:
            logger.error(f"Auth service health check failed: {str(e)}")
            health_status["components"]["auth_service"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["status"] = "degraded"

        return health_status

    @staticmethod
    async def get_system_info() -> Dict[str, Any]:
        """
        Get system debug information

        Returns:
            Dict containing system configuration and environment info
        """
        try:
            import os
            import sys

            return {
                "system": {
                    "python_version": sys.version,
                    "platform": sys.platform,
                },
                "environment": {
                    "mongo_host": os.getenv("MONGO_HOST", "localhost"),
                    "mongo_port": os.getenv("MONGO_PORT", "27017"),
                    "mongo_db": os.getenv("MONGO_DB", "medverify-authdb"),
                    "jwt_algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
                    "api_base_url": os.getenv("API_BASE_URL", "http://localhost:8000"),
                    "max_active_sessions": os.getenv("MAX_ACTIVE_SESSIONS", "5"),
                },
                "services": {
                    "architecture": "auth-only",
                    "description": "Authentication service with MongoDB",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"System info collection failed: {str(e)}")
            return {
                "error": f"System info collection failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    @staticmethod
    async def get_collection_statistics() -> Dict[str, Any]:
        """
        Get detailed database collection statistics

        Returns:
            Dict containing statistics for all MongoDB collections
        """
        try:
            collections_info = {}

            collections = {
                "users": users_collection,
                "refresh_tokens": refresh_tokens_collection,
            }

            for name, collection in collections.items():
                try:
                    count = await collection.count_documents({})
                    # Get a sample document structure (keys only)
                    sample = await collection.find_one({})
                    sample_keys = list(sample.keys()) if sample else []

                    collections_info[name] = {
                        "count": count,
                        "sample_keys": sample_keys,
                        "status": "accessible",
                    }
                except Exception as e:
                    collections_info[name] = {"error": str(e), "status": "error"}

            return {
                "collections": collections_info,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Collection statistics failed: {str(e)}")
            return {
                "error": f"Collection statistics failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    @staticmethod
    async def get_performance_metrics() -> Dict[str, Any]:
        """
        Get basic performance and usage metrics

        Returns:
            Dict containing performance metrics
        """
        try:
            # Database operation metrics
            start_time = datetime.now()

            # Test database response time
            await users_collection.count_documents({})
            db_response_time = (datetime.now() - start_time).total_seconds()

            # Collection sizes
            users_count = await users_collection.count_documents({})
            active_tokens = await refresh_tokens_collection.count_documents(
                {"revoked": False, "expires_at": {"$gt": datetime.now(timezone.utc)}}
            )

            return {
                "database": {
                    "response_time_seconds": round(db_response_time, 4),
                    "status": "responsive" if db_response_time < 1.0 else "slow",
                },
                "usage": {
                    "total_users": users_count,
                    "active_tokens": active_tokens,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Performance metrics collection failed: {str(e)}")
            return {
                "error": f"Performance metrics collection failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    @staticmethod
    async def get_auth_statistics() -> Dict[str, Any]:
        """
        Get comprehensive authentication system statistics

        Returns:
            Dict containing auth statistics and information
        """
        try:
            logger.info("Collecting authentication statistics")

            # User statistics
            total_users = await users_collection.count_documents({})
            verified_users = await users_collection.count_documents(
                {"email_verified": True}
            )
            unverified_users = total_users - verified_users

            # Token statistics
            total_tokens = await refresh_tokens_collection.count_documents({})
            active_tokens = await refresh_tokens_collection.count_documents(
                {"revoked": False, "expires_at": {"$gt": datetime.now(timezone.utc)}}
            )
            expired_tokens = await refresh_tokens_collection.count_documents(
                {"expires_at": {"$lt": datetime.now(timezone.utc)}}
            )
            revoked_tokens = await refresh_tokens_collection.count_documents(
                {"revoked": True}
            )

            # Recent registrations (last 24 hours)
            from datetime import timedelta

            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            recent_registrations = await users_collection.count_documents(
                {"created_at": {"$gte": yesterday}}
            )

            # User registration timeline (last 7 days)
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            pipeline = [
                {"$match": {"created_at": {"$gte": week_ago}}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$created_at",
                            }
                        },
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id": 1}},
            ]

            registration_timeline = {}
            async for doc in users_collection.aggregate(pipeline):
                registration_timeline[doc["_id"]] = doc["count"]

            return {
                "users": {
                    "total_users": total_users,
                    "verified_users": verified_users,
                    "unverified_users": unverified_users,
                    "recent_registrations": recent_registrations,
                    "registration_timeline": registration_timeline,
                },
                "tokens": {
                    "total_tokens": total_tokens,
                    "active_tokens": active_tokens,
                    "expired_tokens": expired_tokens,
                    "revoked_tokens": revoked_tokens,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Auth statistics collection failed: {str(e)}")
            return {
                "error": f"Auth statistics collection failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
