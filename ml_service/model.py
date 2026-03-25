"""
MobileNetV3 (small) with transfer learning: ImageNet backbone + replaced classifier head.
"""

from __future__ import annotations

import torch
import torch.nn as nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

from ml_service.labels import PATH_CONDITION_CLASS_ORDER
from ml_service.obstacle_labels import OBSTACLE_TYPE_CLASS_ORDER


def num_path_classes() -> int:
    return len(PATH_CONDITION_CLASS_ORDER)


def num_obstacle_classes() -> int:
    return len(OBSTACLE_TYPE_CLASS_ORDER)


def build_mobilenet_v3_path_classifier(
    *,
    pretrained_backbone: bool = True,
) -> nn.Module:
    """
    Build MobileNetV3-Small where the final linear layer targets path-condition classes.
    """
    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained_backbone else None
    model = mobilenet_v3_small(weights=weights)
    n_classes = num_path_classes()
    # torchvision: classifier[3] is Linear(1024 -> 1000)
    last_linear = model.classifier[3]
    if not isinstance(last_linear, nn.Linear):
        raise RuntimeError("Unexpected MobileNetV3 classifier layout in torchvision.")
    in_features = last_linear.in_features
    model.classifier[3] = nn.Linear(in_features, n_classes)
    return model


def build_mobilenet_v3_obstacle_classifier(
    *,
    pretrained_backbone: bool = True,
) -> nn.Module:
    """
    Build MobileNetV3-small where the final classifier head targets obstacle types.
    """
    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained_backbone else None
    model = mobilenet_v3_small(weights=weights)
    n_classes = num_obstacle_classes()

    last_linear = model.classifier[3]
    if not isinstance(last_linear, nn.Linear):
        raise RuntimeError("Unexpected MobileNetV3 classifier layout in torchvision.")
    in_features = last_linear.in_features
    model.classifier[3] = nn.Linear(in_features, n_classes)
    return model


def save_checkpoint(model: nn.Module, path: str) -> None:
    torch.save(model.state_dict(), path)


def load_checkpoint(model: nn.Module, path: str, map_location: str | torch.device) -> nn.Module:
    try:
        state = torch.load(path, map_location=map_location, weights_only=True)
    except TypeError:
        state = torch.load(path, map_location=map_location)
    model.load_state_dict(state)
    return model
