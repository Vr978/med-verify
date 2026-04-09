"""
Defines the CNN architecture used for Brain Tumor Classification.
Designed to support dynamic flattening for flexible input sizes.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class BrainTumorNet(nn.Module):
    """
    CNN model with dynamic flatten size detection.
    Works with 224×224 RGB input or similar sizes.
    """

    def __init__(self):
        super(BrainTumorNet, self).__init__()
        self.conv1 = nn.Conv2d(3, 32, 3, 1)
        self.conv2 = nn.Conv2d(32, 64, 3, 1)
        self.fc1 = None  # initialized dynamically
        self.fc2 = nn.Linear(128, 4)  # 4-class output

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.max_pool2d(F.relu(self.conv2(x)), 2)
        x = torch.flatten(x, 1)

        # Lazy init of fc1 based on first forward pass
        if self.fc1 is None:
            self.fc1 = nn.Linear(x.shape[1], 128)
            self.add_module("fc1", self.fc1)

        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x
