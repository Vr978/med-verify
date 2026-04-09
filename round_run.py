"""
Automated Federated Learning round runner (decentralized version with async client polling).

Coordinates:
  • Delegate election (via blockchain backend)
  • Local training at each FL client node (ports 8600, 8601, …)
  • Polling client /status until model training finishes
  • Model upload to the aggregator node (port 8500)
  • Aggregation + blockchain commit by the lead delegate
"""

import requests
import os
import time
import schedule
from fl_backend.core.utils import log_event

# -----------------------------
# CONFIGURATION
# -----------------------------
FL_AGGREGATOR_BASE = os.getenv("FL_AGGREGATOR_BASE", "http://127.0.0.1:8500/fl")
FL_CLIENT_BASE_PORT = int(os.getenv("FL_CLIENT_BASE_PORT", 8600))  # First client port
BLOCKCHAIN_BASE = os.getenv("BLOCKCHAIN_BASE", "http://127.0.0.1:8000")
ROUND_INTERVAL_MINUTES = int(os.getenv("ROUND_INTERVAL_MINUTES", 60))  # automation interval
STATUS_POLL_INTERVAL = int(os.getenv("STATUS_POLL_INTERVAL", 5))  # seconds between /status checks

# ------------------------------------------------------
# 🧩 Helper Functions
# ------------------------------------------------------
def get_current_delegates():
    """Fetch active DPoS delegates from blockchain."""
    try:
        r = requests.get(f"{BLOCKCHAIN_BASE}/dpos/delegates/current", timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", {})
            round_id = data.get("round_id", None)
            delegates = [d["node_id"] for d in data.get("delegates", [])]
            if round_id and delegates:
                log_event("Orchestrator", f"✅ Active round: {round_id} | Delegates: {delegates}")
                return round_id, delegates
            log_event("Orchestrator", "⚠️ No delegates found in current election.")
            return None, []
        log_event("Orchestrator", f"⚠️ Failed to fetch delegates: {r.status_code} {r.text}")
        return None, []
    except Exception as e:
        log_event("Orchestrator", f"❌ Error fetching delegates: {e}")
        return None, []


def start_new_election(delegate_count=2, duration_hours=24):
    """Trigger a new election round in blockchain."""
    try:
        payload = {"delegate_count": delegate_count, "round_duration_hours": duration_hours}
        r = requests.post(f"{BLOCKCHAIN_BASE}/dpos/elect", json=payload, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", {})
            round_id = data.get("round_id")
            log_event("Blockchain", f"🎉 New election started: round_id={round_id}")
            return round_id
        log_event("Blockchain", f"⚠️ Failed to start election: {r.status_code} {r.text}")
        return None
    except Exception as e:
        log_event("Blockchain", f"❌ Election start error: {e}")
        return None


def poll_client_status(client_url, delegate_id):
    """Poll a client's /status endpoint until training completes."""
    status_url = client_url.replace("/fl/train", "/status")
    for _ in range(60):  # wait up to ~5 minutes (60×5s)
        try:
            res = requests.get(status_url, timeout=5)
            if res.status_code == 200:
                data = res.json().get("training", {})
                state = data.get("status", "unknown")
                if state == "completed" and data.get("last_model_path"):
                    log_event("Orchestrator", f"✅ {delegate_id} training done — model ready.")
                    return data.get("last_model_path")
                elif "error" in state:
                    log_event("Orchestrator", f"❌ {delegate_id} reported error: {state}")
                    return None
                else:
                    log_event("Orchestrator", f"⏳ {delegate_id} still training ({state})...")
            else:
                log_event("Orchestrator", f"⚠️ Failed to query {delegate_id} status: {res.status_code}")
        except Exception as e:
            log_event("Orchestrator", f"⚠️ Could not reach {delegate_id}: {e}")
        time.sleep(STATUS_POLL_INTERVAL)
    log_event("Orchestrator", f"⏰ Timeout waiting for {delegate_id} to finish.")
    return None


# ------------------------------------------------------
# 🧠 Core Simulation Logic
# ------------------------------------------------------
def simulate_one_round(round_id, delegates):
    """Run one full FL round using all delegates (train → poll → upload → aggregate)."""
    print(f"\n=== 🚀 Starting simulation for round: {round_id} ===\n")
    uploaded_paths = []
    total_clients = len(delegates)

    # 1️⃣ TRAINING PHASE (trigger async training)
    for idx, delegate_id in enumerate(delegates):
        client_port = FL_CLIENT_BASE_PORT + idx
        client_url = f"http://127.0.0.1:{client_port}/fl/train"
        log_event("Training", f"🚑 Triggering {delegate_id} on {client_url}")

        try:
            resp = requests.post(
                client_url,
                params={
                    "delegate_id": delegate_id,
                    "round_id": round_id,
                    "client_index": idx,
                    "total_clients": total_clients,
                },
                timeout=10,
            )

            if resp.status_code == 200:
                log_event("Training", f"✅ Training accepted for {delegate_id}")
            else:
                log_event("Training", f"❌ Training trigger failed for {delegate_id}: {resp.status_code}")
        except Exception as e:
            log_event("Training", f"⚠️ Could not trigger training for {delegate_id}: {e}")

    # 2️⃣ POLLING PHASE (wait for all clients)
    for idx, delegate_id in enumerate(delegates):
        client_port = FL_CLIENT_BASE_PORT + idx
        client_url = f"http://127.0.0.1:{client_port}/fl/train"
        file_path = poll_client_status(client_url, delegate_id)
        if file_path and os.path.exists(file_path):
            uploaded_paths.append(file_path)
        else:
            log_event("Orchestrator", f"⚠️ No model found for {delegate_id}, skipping upload.")

    # 3️⃣ UPLOAD PHASE (to aggregator)
    for file_path in uploaded_paths:
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                up = requests.post(f"{FL_AGGREGATOR_BASE}/upload", files=files, timeout=30)
                log_event("Upload", f"⬆️ Uploaded {os.path.basename(file_path)} ({up.status_code})")
        except Exception as e:
            log_event("Upload", f"❌ Upload failed for {file_path}: {e}")

    # 4️⃣ AGGREGATION PHASE
    if uploaded_paths:
        lead_delegate = delegates[0]
        log_event("Aggregator", f"⚙️ Aggregating models — lead: {lead_delegate}")
        try:
            agg = requests.post(
                f"{FL_AGGREGATOR_BASE}/aggregate",
                params={"delegate_id": lead_delegate, "round_id": round_id},
                timeout=120,
            )
            try:
                agg_data = agg.json()
            except Exception:
                agg_data = {"error": "Invalid JSON", "text": agg.text}
            log_event("Aggregator", f"✅ Aggregation result: {agg_data}")
        except Exception as e:
            log_event("Aggregator", f"❌ Aggregation failed: {e}")
    else:
        log_event("Aggregator", "⚠️ No models uploaded. Skipping aggregation.")

    print("=== ✅ Simulation for this round completed ===\n")


# ------------------------------------------------------
# ⏳ Scheduled Loop
# ------------------------------------------------------
def scheduled_job():
    """Repeats election → simulation loop every N minutes."""
    round_id, delegates = get_current_delegates()
    if not round_id or not delegates:
        log_event("Orchestrator", "🔄 No active delegates. Starting new election.")
        round_id = start_new_election(delegate_count=2, duration_hours=24)
        if not round_id:
            log_event("Orchestrator", "❌ Election failed, skipping this round.")
            return
        time.sleep(3)
        round_id, delegates = get_current_delegates()
        if not round_id or not delegates:
            log_event("Orchestrator", "⚠️ Delegates unavailable even after election.")
            return
    simulate_one_round(round_id, delegates)


# ------------------------------------------------------
# 🚦 Entrypoint
# ------------------------------------------------------
if __name__ == "__main__":
    print(f"🌍 Starting automated FL + Blockchain loop every {ROUND_INTERVAL_MINUTES} minutes.\n")

    # Run once immediately
    scheduled_job()

    # Then repeat periodically
    schedule.every(ROUND_INTERVAL_MINUTES).minutes.do(scheduled_job)
    while True:
        schedule.run_pending()
        time.sleep(1)
