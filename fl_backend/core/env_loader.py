"""
Centralized environment variable loader for consistent dotenv initialization.
"""

import os
from dotenv import load_dotenv


def load_environment(dotenv_path: str = None) -> str:
    """
    Load environment variables from a .env file (if available).

    Args:
        dotenv_path (str, optional): Path to .env file. Defaults to project root.

    Returns:
        str: The resolved .env file path (or empty string if none found).
    """
    if dotenv_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dotenv_path = os.path.join(base_dir, ".env")

    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        loaded = True
        print(f"🌱 Environment loaded from: {dotenv_path}")
    else:
        loaded = False
        print("⚠️ No .env file found — using system environment variables.")

    if loaded:
        keys = ["CLIENT_INDEX", "TOTAL_CLIENTS", "BACKEND_API_URL", "FL_BACKEND_PORT"]
        found = [k for k in keys if k in os.environ]
        print(f"🌿 Loaded keys: {', '.join(found) if found else 'None'}")

    return dotenv_path if loaded else ""
