"""
Dataset utilities for Federated Learning clients.
Handles dataset loading, preprocessing, and partitioning for each client node.
"""

import torch
from torchvision import transforms
from datasets import load_dataset


def load_brain_tumor_dataset(
    split: str = "train",
    limit: int = 100,
    client_index: int = 0,
    total_clients: int = 1,
    cache_dir: str = "./dataset_cache"
):
    """
    Load and partition Brain Tumor MRI dataset for federated clients.

    Args:
        split (str): dataset split name
        limit (int): max samples to load
        client_index (int): index of current client (0-based)
        total_clients (int): total number of participating clients
        cache_dir (str): local cache directory to avoid re-downloading dataset
    """
    dataset = load_dataset("Hemg/Brain-Tumor-MRI-Dataset", split=split, cache_dir=cache_dir)
    total_samples = min(limit, len(dataset))
    per_client = total_samples // total_clients

    start = client_index * per_client
    end = total_samples if client_index == total_clients - 1 else start + per_client
    subset = dataset.select(range(start, end))

    print(f"📦 Client {client_index+1}/{total_clients} -> {len(subset)} samples ({start}-{end})")

    transform = transforms.Compose([
        transforms.Lambda(lambda img: img.convert("RGB")),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
    ])

    imgs, labels = [], []
    for sample in subset:
        imgs.append(transform(sample["image"]))
        labels.append(sample["label"])

    X = torch.stack(imgs)
    y = torch.tensor(labels, dtype=torch.long)
    return X, y
