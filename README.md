<div align="center">

# 🏥 MedVerify

### Federated Learning Verification Platform on Google Kubernetes Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://mongodb.com)
[![Docker](https://img.shields.io/badge/Docker-Multi--stage-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Kubernetes](https://img.shields.io/badge/GKE-Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)](https://cloud.google.com/kubernetes-engine)
[![Jenkins](https://img.shields.io/badge/Jenkins-CI%2FCD-D33833?style=for-the-badge&logo=jenkins&logoColor=white)](Jenkinsfile)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

</div>

---

MedVerify is a **distributed federated learning infrastructure** for training and verifying medical AI models (Brain Tumor MRI classification) across hospital nodes — without ever sharing raw patient data. Model integrity is cryptographically enforced via a custom **Delegated Proof of Stake (DPoS) blockchain** backed by MongoDB, with all model update hashes stored in an immutable on-chain ledger.

The system is containerized with **Docker**, deployed on **Google Kubernetes Engine (GKE)** with horizontal autoscaling and fault-tolerant scheduling, and shipped via a **Jenkins declarative CI/CD pipeline** that gates every deploy behind automated integrity validation.

---

## System Architecture

![MedVerify System Architecture](docs/architecture.png)

```mermaid
flowchart TD
    subgraph DEV["💻 Developer Workflow"]
        GIT[Git Push to main]
    end

    subgraph CI["🔧 Jenkins CI/CD Pipeline"]
        J1[1 · Checkout]
        J2[2 · K8s Lint\nkubectl dry-run]
        J3[3 · Test\nBatchValidator self-test]
        J4A[4a · Build backend\nDocker multi-stage]
        J4B[4b · Build fl-backend\nDocker multi-stage]
        J5[5 · Push to GCR\n:BUILD-SHA + :latest]
        J6[6 · Deploy to GKE\nkubectl set image]
        J7[7 · Verify Rollout\nrollout status + HPA]
    end

    subgraph GKE["☸️ Google Kubernetes Engine — namespace: medverify"]
        subgraph Clients["🏥 Hospital FL Client Pods  (HPA 2–10)"]
            C1[Node 1\nFastAPI :8600]
            C2[Node 2\nFastAPI :8601]
            C3[Node 3\nFastAPI :8602]
        end
        subgraph FL["⚡ FL Aggregator  (HPA 2–10 replicas)"]
            UPLOAD[POST /fl/upload]
            AGG[POST /fl/aggregate]
            BV["🛡️ BatchValidator\n800+ SHA-256 checks"]
        end
        subgraph Chain["🔗 DPoS Blockchain API  (HPA 2–6 replicas)"]
            ELECT[DPoS Election]
            BLOCK[Block Service\nMerkle + Ed25519]
            VERIFY[Chain Verify]
        end
    end

    subgraph DB["🍃 MongoDB — Immutable Ledger"]
        BLOCKS[(blocks)]
        ELECTIONS[(elections)]
        NODES[(nodes)]
        VOTES[(votes)]
        USERS[(users)]
    end

    GIT --> J1 --> J2 --> J3
    J3 --> J4A & J4B
    J4A & J4B --> J5 --> J6 --> J7
    J6 -->|Rolling update| GKE

    C1 & C2 & C3 -->|Upload .pt| UPLOAD --> AGG --> BV
    BV -->|Verified hashes| BLOCK --> BLOCKS
    ELECT --> ELECTIONS
    VERIFY --> BLOCKS

    classDef ci fill:#B71C1C,stroke:#EF5350,color:#fff
    classDef gke fill:#0D47A1,stroke:#42A5F5,color:#fff
    classDef fl fill:#1B5E20,stroke:#66BB6A,color:#fff
    classDef db fill:#1A237E,stroke:#7986CB,color:#fff
    classDef dev fill:#37474F,stroke:#90A4AE,color:#fff
    class J1,J2,J3,J4A,J4B,J5,J6,J7 ci
    class C1,C2,C3 gke
    class UPLOAD,AGG,BV,ELECT,BLOCK,VERIFY fl
    class BLOCKS,ELECTIONS,NODES,VOTES,USERS db
    class GIT dev
```

---

## Key Features

| Feature | Details |
|---|---|
| **FastAPI Microservices** | Two independent services: DPoS Blockchain API (`:8000`) + FL Aggregator (`:8500`) |
| **GKE Deployment** | Kubernetes manifests in `k8s/` with HPA (2–10 replicas), liveness & readiness probes |
| **Docker** | Multi-stage builds with non-root user and healthchecks; built in parallel by Jenkins |
| **Jenkins CI/CD** | 7-stage declarative pipeline: lint → test → parallel build → GCR push → GKE rolling deploy |
| **Federated Learning** | BrainTumorNet CNN trained locally at each hospital node; FedAvg aggregation |
| **DPoS Consensus** | Delegated Proof of Stake election, Ed25519 signing, Merkle root per block |
| **Batch Integrity Validation** | 800+ model update hashes verified per training round via SHA-256 re-computation; **gates Jenkins deploy** |
| **Immutable MongoDB Ledger** | Model hashes, block signatures and chain linkage persisted with TTL indexes |
| **JWT Auth** | Access + refresh token flow, per-user session limits, TTL-indexed token store |

---

## Repository Structure

```
med-verify/
├── Jenkinsfile               # ← Declarative CI/CD pipeline (7 stages)
│
├── backend/                  # DPoS Blockchain API (FastAPI)
│   ├── Dockerfile            # Multi-stage, non-root — built by Jenkins Stage 4
│   ├── main.py               # App factory + background scheduler
│   ├── config/               # DB, logging config
│   ├── model/                # Pydantic models (Block, Node, Vote…)
│   ├── services/             # block_service, dpos_service, node_service
│   ├── security/             # JWT auth, token management
│   ├── utils/                # Crypto, hash, validation utilities
│   └── web/rest/             # FastAPI routers
│
├── fl_backend/               # Federated Learning Microservice (FastAPI)
│   ├── Dockerfile            # Multi-stage, GPU-compatible — built by Jenkins Stage 4
│   ├── main.py               # App factory
│   ├── core/
│   │   ├── fl_service.py     # Train / Upload / Aggregate endpoints
│   │   ├── batch_validator.py# 800+ SHA-256 checks — runs in Jenkins Stage 3
│   │   ├── config.py         # FL env config
│   │   └── utils.py          # Hashing, logging helpers
│   ├── clients/              # Local training (BrainTumorNet, FedAvg dataset split)
│   └── server/               # Aggregator, blockchain client
│
├── k8s/                      # Kubernetes / GKE manifests — dry-run validated by Jenkins Stage 2
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml          # Template — fill before deploying
│   ├── mongodb-deployment.yaml
│   ├── backend-deployment.yaml
│   ├── fl-backend-deployment.yaml
│   └── hpa.yaml              # HorizontalPodAutoscaler (CPU + memory)
│
├── docker-compose.yml        # Local multi-service orchestration
├── round_run.py              # Automated FL round orchestrator
├── scripts/
│   └── mongo-init.js         # MongoDB collection bootstrap
└── docs/
    └── architecture.png      # System architecture diagram
```

---

## CI/CD — Jenkins Pipeline

The [`Jenkinsfile`](Jenkinsfile) at the repo root automates the entire lifecycle from code push to live GKE deployment. Every stage is gated — a failure at any point prevents promotion to the next stage.

```mermaid
flowchart LR
    subgraph trigger["Trigger"]
        PUSH["🔀 git push\nto main"]
    end

    subgraph pipeline["Jenkins Declarative Pipeline"]
        S1["① Checkout\nClone + log commit SHA"]
        S2["② Lint & Validate\nkubectl dry-run\non all k8s/manifests"]
        S3["③ Test ⛔ GATE\nBatchValidator\nSHA-256 self-test"]
        S4["④ Build (parallel)\nDocker multi-stage\nbackend + fl-backend"]
        S5["⑤ Push to GCR\n:BUILD-SHA + :latest\n(main branch only)"]
        S6["⑥ Deploy to GKE\nkubectl set image\nrolling zero-downtime"]
        S7["⑦ Verify Rollout\nrollout status\nHPA + pod report"]
    end

    subgraph post["Post-build"]
        CLEAN["🧹 Cleanup\nrmi images\ncleanWs()"]
    end

    PUSH --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> CLEAN

    style S3 fill:#B71C1C,color:#fff
    style PUSH fill:#37474F,color:#fff
    style CLEAN fill:#4A148C,color:#fff
```

### Stage Breakdown

| # | Stage | What it does | Why it matters |
|---|---|---|---|
| 1 | **Checkout** | Clones repo, logs branch + 7-char commit SHA | Full traceability per build |
| 2 | **Lint & Validate** | `kubectl apply --dry-run=client` on every manifest in `k8s/` | Catches YAML schema errors before any image is built |
| 3 | **Test ⛔** | Runs `BatchValidator` SHA-256 self-test via `python3 -m fl_backend.core.batch_validator` | **Hard gate** — pipeline aborts if integrity logic is broken |
| 4 | **Build** | Parallel `docker build --target runtime` for `backend/` and `fl_backend/` | Parallel execution cuts build time ~50% |
| 5 | **Push to GCR** | Tags as `:BUILD_NUMBER-SHA` + `:latest`, pushes both | Exact tag in `kubectl set image` guarantees K8s sees a new image |
| 6 | **Deploy to GKE** | `kubectl set image` triggers rolling update; falls back to `kubectl apply` on first run | Zero-downtime deploy; old pods stay up until new ones pass readiness probes |
| 7 | **Verify Rollout** | `kubectl rollout status` with 180s timeout; prints pod + HPA status | Pipeline fails if rollout stalls — e.g. OOMKilled or CrashLoopBackOff |

### Jenkins Credentials Setup

Configure these in **Manage Jenkins → Credentials → System → Global**:

| Credential ID | Kind | Description |
|---|---|---|
| `GCP_SA_KEY` | Secret File | GCP service account JSON — used by `gcloud auth` |
| `GCP_PROJECT_ID` | Secret Text | GCP project ID for GCR image paths |
| `GKE_CLUSTER_NAME` | Secret Text | Target GKE cluster name |
| `GKE_ZONE` | Secret Text | GKE zone, e.g. `us-central1-a` |

### Branch Strategy

```
feature/* branch  →  Stage 1–4 only  (lint + test + build, no push/deploy)
main branch       →  All 7 stages    (full pipeline through GKE deploy)
v*.*.* tag        →  All 7 stages    (release deploy)
```

---

## Quick Start

### Prerequisites

- Docker 24+ and Docker Compose v2
- Python 3.11 (for local dev without Docker)
- MongoDB 7.0 (or use the Docker Compose stack)

### 1 — Clone & configure

```bash
git clone https://github.com/Vr978/med-verify.git
cd med-verify

# Copy and fill in env secrets
cp backend/.env.example backend/.env
# Edit backend/.env: set MONGO_PASSWORD, JWT_SECRET, etc.
```

### 2 — Run locally with Docker Compose

```bash
docker compose up --build
```

Services start on:
- **DPoS Blockchain API** → http://localhost:8000/docs
- **FL Aggregator** → http://localhost:8500/docs
- **MongoDB** → localhost:27017

### 3 — Run an FL round

```bash
# In a separate terminal (after compose is up)
python round_run.py
```

This will: elect delegates → trigger training on each client → poll until done → upload models → batch-validate 800+ hashes → aggregate via FedAvg → commit block to blockchain.

---

## Deploying to GKE (Manual)

> **Preferred**: Use the Jenkins pipeline for all GKE deployments.  
> Use these manual steps only for bootstrapping or emergency hotfixes.

```bash
# 1. Build & push images
export PROJECT_ID=your-gcp-project-id

docker build -t gcr.io/$PROJECT_ID/medverify-backend:latest ./backend
docker build -t gcr.io/$PROJECT_ID/medverify-fl-backend:latest ./fl_backend
docker push gcr.io/$PROJECT_ID/medverify-backend:latest
docker push gcr.io/$PROJECT_ID/medverify-fl-backend:latest

# 2. Update image references in k8s/*.yaml
sed -i "s/YOUR_GCP_PROJECT/$PROJECT_ID/g" k8s/backend-deployment.yaml k8s/fl-backend-deployment.yaml

# 3. Populate secrets (see k8s/secrets.yaml template)
# Never commit real values — use GCP Secret Manager in production

# 4. Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/mongodb-deployment.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/fl-backend-deployment.yaml
kubectl apply -f k8s/hpa.yaml

# 5. Verify
kubectl get pods -n medverify
kubectl get hpa -n medverify
```

The HPA automatically scales the FL backend from **2 to 10 pods** based on CPU utilisation — distributing model validation and aggregation across GKE compute nodes.

---

## How the Integrity Verification Works

```
Training Round (per hospital node)
    │
    ▼
Local BrainTumorNet training (PyTorch, FedAvg split)
    │
    ▼ SHA-256(model.pt) ──────────────────────────────────────────┐
    │                                                              │
    ▼                                                    Client submits hash
FL Aggregator receives model upload                               │
    │                                                              │
    ▼                                                              │
BatchValidator.validate(paths, expected_hashes)  ◄────────────────┘
    │   • re-computes SHA-256 from bytes on disk
    │   • constant-time comparison (HMAC-safe)
    │   • quarantines mismatches
    │   • self-test also runs as Jenkins Stage 3 gate
    ▼
FedAvg aggregation on validated models only
    │
    ▼
DPoS Blockchain API: add_block()
    │   • Verifies delegate is elected for current round
    │   • Derives & checks Ed25519 public key ownership
    │   • Computes Merkle root of all model hashes
    │   • Signs block with delegate private key
    │   • Chains to previous block hash
    ▼
MongoDB (immutable — no DELETE, no UPDATE on blocks collection)
```

---

## DPoS Consensus

Delegates are elected each round via the `/dpos/elect` endpoint. Each elected hospital node:

1. Trains a local model partition
2. Submits model hash to the blockchain API
3. The lead delegate aggregates and signs the block

A background scheduler (APScheduler, every 2 min) auto-expires rounds. All blocks are verifiable via `/blocks/verify-chain`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.115 + Uvicorn |
| ML Training | PyTorch 2.4, BrainTumorNet CNN |
| Dataset | Brain Tumor MRI (HuggingFace `Hemg/Brain-Tumor-MRI-Dataset`) |
| Consensus | Custom DPoS — Ed25519 signing, Merkle tree |
| Database | MongoDB 7.0 (Motor async driver) |
| Containerization | Docker (multi-stage, non-root) |
| Orchestration | Google Kubernetes Engine, HPA, PVC |
| CI/CD | Jenkins declarative pipeline (7 stages, GCR + GKE) |
| Auth | JWT (access + refresh), bcrypt, PyNaCl |
| Hashing | SHA-256 (hashlib), HMAC constant-time compare |

---

## License

MIT — see [LICENSE](LICENSE).
