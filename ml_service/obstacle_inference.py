from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision.models import MobileNet_V3_Small_Weights

from ml_service.model import build_mobilenet_v3_obstacle_classifier, load_checkpoint
from ml_service.obstacle_labels import OBSTACLE_TYPE_CLASS_ORDER


def _build_narrative_reasons(
    probabilities: Dict[str, float],
    top_class: str,
    checkpoint_loaded: bool,
) -> List[str]:
    reasons: List[str] = []

    sorted_probs = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
    top3 = sorted_probs[:3]
    reasons.append(
        "The model ranks obstacle types by estimated probability: "
        + ", ".join(f"{name} ({p:.3f})" for name, p in top3)
        + "."
    )
    reasons.append(
        f"The selected label is {top_class!r} because it has the highest softmax score "
        f"({probabilities[top_class]:.4f}) among the nine classes."
    )
    if not checkpoint_loaded:
        reasons.append(
            "No fine-tuned obstacle checkpoint was loaded: outputs are not reliable for production map updates."
        )
    # Note: obstacle classification is independent from path-condition classification.
    reasons.append(
        "This obstacle model runs regardless of whether the surface-path label predicts an obstructed condition."
    )
    return reasons


class ObstacleImageClassifier:
    """
    MobileNetV3-small transfer-learning classifier for obstacle type imagery.
    """

    def __init__(
        self,
        *,
        device: str = "cpu",
        checkpoint_path: str | None = None,
        pretrained_backbone: bool = True,
    ) -> None:
        self._device = torch.device(device)
        self._weights_enum = MobileNet_V3_Small_Weights.IMAGENET1K_V1
        self._model = build_mobilenet_v3_obstacle_classifier(
            pretrained_backbone=pretrained_backbone
        ).to(self._device)
        self._model.eval()
        self._checkpoint_loaded = False
        if checkpoint_path:
            load_checkpoint(self._model, checkpoint_path, map_location=self._device)
            self._checkpoint_loaded = True

    @property
    def checkpoint_loaded(self) -> bool:
        return self._checkpoint_loaded

    def _preprocess(self, image: Image.Image) -> torch.Tensor:
        transform = self._weights_enum.transforms()
        return transform(image).unsqueeze(0).to(self._device)

    @torch.inference_mode()
    def predict_proba(self, image_bytes: bytes) -> Dict[str, Any]:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        batch = self._preprocess(img)
        logits = self._model(batch)
        probs = F.softmax(logits, dim=1).squeeze(0).cpu()

        class_names = list(OBSTACLE_TYPE_CLASS_ORDER)
        probabilities = {class_names[i]: float(probs[i]) for i in range(len(class_names))}

        best_idx = int(torch.argmax(probs).item())
        top_class = class_names[best_idx]
        confidence = float(probs[best_idx].item())
        narrative_reasons = _build_narrative_reasons(
            probabilities, top_class, self._checkpoint_loaded
        )

        return {
            "obstacle_type": top_class,
            "confidence": confidence,
            "probabilities": probabilities,
            "narrative_reasons": narrative_reasons,
            "checkpoint_loaded": self._checkpoint_loaded,
        }

