"""
Database Configuration Module
author: Barath Suresh
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_USER = os.getenv("MONGO_USER", "admin")
MONGO_PASS = os.getenv("MONGO_PASSWORD", "admin")
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DB = os.getenv("MONGO_DB", "medverify-authdb")

# MongoDB connection string
if MONGO_USER and MONGO_PASS:
    MONGO_URL = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}?authSource=admin"
else:
    MONGO_URL = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"

# Async client for FastAPI
client = AsyncIOMotorClient(MONGO_URL)
database = client[MONGO_DB]

# Collections
users_collection = database["users"]
refresh_tokens_collection = database["refresh_tokens"]

# Blockchain collections
nodes_collection = database["nodes"]
blocks_collection = database["blocks"]
elections_collection = database["elections"]
votes_collection = database["votes"]


# Helper function to get database
def get_database():
    return database
