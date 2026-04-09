"""
Logging Configuration Module
Sets up comprehensive logging for the authentication system
author: Barath Suresh
"""

import logging
import logging.config
import os
import sys
from datetime import datetime
from typing import Dict, Any


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels"""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        # Add color to the log level
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"

        # Format the message
        formatted = super().format(record)
        return formatted


class SecurityLogger:
    """Security-focused logging for authentication events"""

    def __init__(self):
        self.logger = logging.getLogger("security")

    def log_login_attempt(
        self, email: str, success: bool, ip: str = None, user_agent: str = None
    ):
        """Log user login attempts"""
        status = "SUCCESS" if success else "FAILED"
        extra_info = f" from {ip}" if ip else ""
        if user_agent:
            extra_info += f" (UA: {user_agent[:50]}...)"

        if success:
            self.logger.info(f"Login {status} for {email}{extra_info}")
        else:
            self.logger.warning(f"Login {status} for {email}{extra_info}")

    def log_registration(self, email: str, success: bool, reason: str = None):
        """Log user registration attempts"""
        if success:
            self.logger.info(f"User registration SUCCESS: {email}")
        else:
            reason_msg = f" - {reason}" if reason else ""
            self.logger.warning(f"User registration FAILED: {email}{reason_msg}")

    def log_token_refresh(self, user_id: str, success: bool):
        """Log token refresh attempts"""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"Token refresh {status} for user {user_id}")

    def log_logout(self, user_id: str, success: bool):
        """Log logout events"""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"User logout {status}: {user_id}")

    def log_authentication_error(self, error: str, context: str = None):
        """Log authentication-related errors"""
        context_msg = f" ({context})" if context else ""
        self.logger.error(f"Auth error{context_msg}: {error}")


class PerformanceLogger:
    """Performance monitoring logger"""

    def __init__(self):
        self.logger = logging.getLogger("performance")

    def log_request_time(
        self, endpoint: str, method: str, duration: float, status_code: int
    ):
        """Log API request performance"""
        if duration > 1.0:  # Log slow requests (>1 second)
            self.logger.warning(
                f"SLOW REQUEST: {method} {endpoint} - {duration:.3f}s (HTTP {status_code})"
            )
        elif duration > 0.5:  # Log moderately slow requests
            self.logger.info(
                f"REQUEST: {method} {endpoint} - {duration:.3f}s (HTTP {status_code})"
            )
        else:
            self.logger.debug(
                f"REQUEST: {method} {endpoint} - {duration:.3f}s (HTTP {status_code})"
            )

    def log_database_operation(self, operation: str, collection: str, duration: float):
        """Log database operation performance"""
        if duration > 0.5:
            self.logger.warning(
                f"SLOW DB: {operation} on {collection} - {duration:.3f}s"
            )
        else:
            self.logger.debug(f"DB: {operation} on {collection} - {duration:.3f}s")


def setup_logging() -> Dict[str, Any]:
    """
    Setup comprehensive logging configuration using environment variables

    Returns:
        Dict containing logging configuration
    """

    # Load environment variables with defaults
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_console = os.getenv("LOG_CONSOLE", "true").lower() == "true"
    log_file = os.getenv("LOG_FILE", "true").lower() == "true"
    log_colors = os.getenv("LOG_COLORS", "true").lower() == "true"

    # Log directory configuration
    log_dir_env = os.getenv("LOG_DIR", "logs")
    if os.path.isabs(log_dir_env):
        log_dir = log_dir_env
    else:
        log_dir = os.path.join(os.path.dirname(__file__), "..", log_dir_env)

    # Create logs directory if file logging is enabled
    if log_file:
        os.makedirs(log_dir, exist_ok=True)

    # File rotation settings
    max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # Security log settings
    security_log_level = os.getenv("SECURITY_LOG_LEVEL", "INFO").upper()
    security_backup_count = int(os.getenv("SECURITY_LOG_BACKUP_COUNT", "10"))

    # Performance log settings
    performance_log_level = os.getenv("PERFORMANCE_LOG_LEVEL", "DEBUG").upper()
    performance_backup_count = int(os.getenv("PERFORMANCE_LOG_BACKUP_COUNT", "3"))

    # Error log settings
    error_log_level = os.getenv("ERROR_LOG_LEVEL", "WARNING").upper()
    error_backup_count = int(os.getenv("ERROR_LOG_BACKUP_COUNT", "10"))

    # Logging configuration
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "simple": {
                "format": "%(asctime)s - %(levelname)s - %(message)s",
                "datefmt": "%H:%M:%S",
            },
            "colored": {
                "()": ColoredFormatter,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {},
    }

    # Add console handler if enabled
    if log_console:
        formatter = "colored" if log_colors else "simple"
        config["handlers"]["console"] = {
            "class": "logging.StreamHandler",
            "level": log_level,
            "formatter": formatter,
            "stream": sys.stdout,
        }

    # Add file handlers if file logging is enabled
    if log_file:
        # Main application log
        config["handlers"]["file_all"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": os.path.join(log_dir, "auth_system.log"),
            "maxBytes": max_bytes,
            "backupCount": backup_count,
        }

        # Security log
        config["handlers"]["file_security"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": security_log_level,
            "formatter": "detailed",
            "filename": os.path.join(log_dir, "security.log"),
            "maxBytes": max_bytes,
            "backupCount": security_backup_count,
        }

        # Performance log
        config["handlers"]["file_performance"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": performance_log_level,
            "formatter": "detailed",
            "filename": os.path.join(log_dir, "performance.log"),
            "maxBytes": max_bytes // 2,  # Smaller for performance logs
            "backupCount": performance_backup_count,
        }

        # Error log
        config["handlers"]["file_errors"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": error_log_level,
            "formatter": "detailed",
            "filename": os.path.join(log_dir, "errors.log"),
            "maxBytes": max_bytes,
            "backupCount": error_backup_count,
        }

    # Update logger configurations with available handlers
    available_handlers = list(config["handlers"].keys())

    config["loggers"] = {
        "security": {
            "level": security_log_level,
            "handlers": [
                h
                for h in available_handlers
                if h in ["console", "file_security", "file_all"]
            ],
            "propagate": False,
        },
        "performance": {
            "level": performance_log_level,
            "handlers": [
                h for h in available_handlers if h in ["file_performance", "file_all"]
            ],
            "propagate": False,
        },
        "fastapi": {
            "level": log_level,
            "handlers": [h for h in available_handlers if h in ["console", "file_all"]],
            "propagate": False,
        },
        "uvicorn": {
            "level": "INFO",
            "handlers": [h for h in available_handlers if h in ["console", "file_all"]],
            "propagate": False,
        },
        "uvicorn.access": {
            "level": "INFO",
            "handlers": [h for h in available_handlers if h in ["file_all"]],
            "propagate": False,
        },
    }

    config["root"] = {
        "level": log_level,
        "handlers": [
            h for h in available_handlers if h in ["console", "file_all", "file_errors"]
        ],
    }

    # Apply configuration
    logging.config.dictConfig(config)

    # Create logger instances and log configuration info
    app_logger = logging.getLogger(__name__)
    app_logger.info(f"Logging system initialized - Level: {log_level}")

    if log_console:
        app_logger.info(f"Console logging enabled with colors: {log_colors}")

    if log_file:
        app_logger.info(f"File logging enabled - Directory: {log_dir}")
        app_logger.info(f"Log rotation: {max_bytes} bytes, {backup_count} backups")
    else:
        app_logger.info("File logging disabled")

    app_logger.info(f"Available handlers: {', '.join(available_handlers)}")

    return config


# Initialize security and performance loggers
security_logger = SecurityLogger()
performance_logger = PerformanceLogger()

# Export commonly used loggers
__all__ = [
    "setup_logging",
    "security_logger",
    "performance_logger",
    "SecurityLogger",
    "PerformanceLogger",
]
