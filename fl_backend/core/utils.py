"""
Shared utility functions for hashing, logging, and common tasks.
Enhanced for decentralized FL architecture.
"""

import os
import hashlib
import datetime

# Identify node context (role + index)
NODE_ROLE = os.getenv("NODE_ROLE", "hybrid").lower()
CLIENT_INDEX = int(os.getenv("CLIENT_INDEX", 0))

# Optional file logging directory
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ---------------------------------------
# Hashing
# ---------------------------------------
def compute_model_hash(file_path: str) -> str:
    """Compute a SHA-256 hash for the given file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ---------------------------------------
# Time utilities
# ---------------------------------------
def timestamp() -> str:
    """Return formatted timestamp string."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------
# Logging utilities
# ---------------------------------------
def log_event(source: str, message: str, to_file: bool = True):
    """
    Log a formatted event message to console (and optionally to per-node log file).

    Args:
        source (str): Subsystem or module name (e.g., "FL", "Blockchain")
        message (str): The message to log
        to_file (bool): If True, also write to logs/<role>_<client>.log
    """
    prefix = f"[{timestamp()}] [{NODE_ROLE.upper()}-{CLIENT_INDEX}] [{source}]"
    formatted = f"{prefix} {message}"
    print(formatted)

    if to_file:
        log_file = os.path.join(LOG_DIR, f"{NODE_ROLE}_client{CLIENT_INDEX}.log")
        with open(log_file, "a") as f:
            f.write(formatted + "\n")


# ---------------------------------------
# Example internal testing
# ---------------------------------------
if __name__ == "__main__":
    log_event("System", "Logging test event")
    print(f"Hash test: {compute_model_hash(__file__)}")
