"""
Training utilities for local FL clients.
Each client trains on its local dataset partition and saves model checkpoints.
"""

import os
import torch
import torch.nn as nn
from tqdm import tqdm
from fl_backend.clients.model_utils import BrainTumorNet
from fl_backend.clients.dataset_utils import load_brain_tumor_dataset
from fl_backend.core.config import LOCAL_MODEL_DIR


def train_local_model(epochs: int = 1, client_index: int = 0, total_clients: int = 1):
    """Train local model on dataset partition belonging to this client."""
    torch.manual_seed(42 + client_index)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    X, y = load_brain_tumor_dataset(
        limit=100,
        client_index=client_index,
        total_clients=total_clients
    )
    X, y = X.to(device), y.to(device)

    model = BrainTumorNet().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss()

    model.train()
    total_loss = 0.0
    batch_size = 8

    for epoch in range(epochs):
        running_loss = 0.0
        for i in tqdm(range(0, len(X), batch_size),
                      desc=f"Client {client_index+1} - Epoch {epoch+1}"):
            x_batch = X[i:i+batch_size]
            y_batch = y[i:i+batch_size]

            optimizer.zero_grad()
            outputs = model(x_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()

        avg_loss = running_loss / len(X)
        total_loss += avg_loss
        print(f"Client {client_index+1} - Epoch {epoch+1} - Avg Loss: {avg_loss:.4f}")

    # Save under client-specific subfolder
    client_dir = os.path.join(LOCAL_MODEL_DIR, f"client_{client_index+1}")
    os.makedirs(client_dir, exist_ok=True)
    save_path = os.path.join(client_dir, "local_model.pt")
    torch.save(model.state_dict(), save_path)
    print(f"💾 Model saved at {save_path}")

    return {"loss": total_loss / epochs, "path": save_path}
