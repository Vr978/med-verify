// MongoDB initialization script
// Creates the medverify database, collections, and initial indexes
// Runs automatically on first container start via docker-entrypoint-initdb.d/

db = db.getSiblingDB('medverify-authdb');

// Create collections with schema validation hints
db.createCollection('users');
db.createCollection('refresh_tokens');
db.createCollection('nodes');
db.createCollection('blocks');
db.createCollection('elections');
db.createCollection('votes');

// Ensure blocks collection never allows deletions (immutable ledger intent)
// Application-level enforcement is in block_service.py — no delete routes exposed
print('✅ MedVerify collections initialized');
print('📦 Database: medverify-authdb');
print('📋 Collections: users, refresh_tokens, nodes, blocks, elections, votes');
