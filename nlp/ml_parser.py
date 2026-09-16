
"""
Statistical NLP tier for HVAC complaint parsing.

Architecture:

    1. Rule-based / zone extraction
    2. THIS MODULE - trained 3-head DistilBERT
    3. Gemini fallback

IMPORTANT:
    Zone is NOT predicted by DistilBERT.

DistilBERT predicts only:
    - parameter
    - direction
    - intensity

Zone is extracted directly from the message using
nlp.predict.extract_zone().

Returns:
    HVACConstraint
    ClarificationResponse
    None

None means:
    ML confidence was too low and the caller should
    escalate to another parser.
"""

import json
import os
from typing import Optional, Union

import torch
import torch.nn.functional as F
from safetensors.torch import load_file
from transformers import AutoModel, AutoTokenizer

from nlp.llm_parser import (
    HVACConstraint,
    ClarificationResponse,
)


# ============================================================
# MODEL HEADS
# ============================================================

HEADS = [
    "parameter",
    "direction",
    "intensity",
]


LOW_CONFIDENCE_ESCALATE = 0.55


# ============================================================
# ARTIFACT PATH
# ============================================================

# ml_parser.py is:
#
#     SpiderVerse/
#         nlp/
#             ml_parser.py
#
# Model is:
#
#     SpiderVerse/
#         artifacts/
#             distilbert/
#
# Therefore go one directory above nlp/.

_PROJECT_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

DEFAULT_ARTIFACT_DIR = os.path.join(
    _PROJECT_DIR,
    "artifacts",
    "distilbert",
)


# ============================================================
# PREDICTOR SINGLETON
# ============================================================

_predictor = None


# ============================================================
# MODEL ARCHITECTURE
# ============================================================

class _MultiHeadSlotModel(torch.nn.Module):
    """
    Must exactly match the architecture used during training.

    The current trained model has THREE heads:

        parameter
        direction
        intensity
    """

    def __init__(
        self,
        backbone,
        n_classes,
        dropout=0.1,
    ):
        super().__init__()

        self.encoder = AutoModel.from_pretrained(
            backbone
        )

        hidden = self.encoder.config.hidden_size

        self.dropout = torch.nn.Dropout(
            dropout
        )

        self.heads = torch.nn.ModuleDict(
            {
                h: torch.nn.Linear(
                    hidden,
                    n_classes[h],
                )
                for h in HEADS
            }
        )

    def forward(
        self,
        input_ids,
        attention_mask,
    ):
        out = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        pooled = self.dropout(
            out.last_hidden_state[:, 0]
        )

        return {
            h: self.heads[h](pooled)
            for h in HEADS
        }


# ============================================================
# PREDICTOR
# ============================================================

class _Predictor:

    def __init__(
        self,
        artifact_dir,
        device=None,
    ):

        # ----------------------------------------------------
        # Verify artifact directory
        # ----------------------------------------------------

        if not os.path.isdir(artifact_dir):
            raise FileNotFoundError(
                f"Model artifact directory not found: "
                f"{artifact_dir}"
            )

        label_map_path = os.path.join(
            artifact_dir,
            "label_maps.json",
        )

        model_path = os.path.join(
            artifact_dir,
            "model.safetensors",
        )

        if not os.path.exists(label_map_path):
            raise FileNotFoundError(
                f"label_maps.json not found: "
                f"{label_map_path}"
            )

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"model.safetensors not found: "
                f"{model_path}"
            )

        # ----------------------------------------------------
        # Load metadata
        # ----------------------------------------------------

        with open(
            label_map_path,
            "r",
            encoding="utf-8",
        ) as f:
            meta = json.load(f)

        self.inv_maps = meta["inv_maps"]

        self.max_length = meta.get(
            "max_length",
            64,
        )

        self.backbone = meta.get(
            "backbone",
            "distilbert-base-uncased",
        )

        # ----------------------------------------------------
        # Device
        # ----------------------------------------------------

        self.device = torch.device(
            device
            or (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )
        )

        # ----------------------------------------------------
        # Number of classes
        # ----------------------------------------------------

        n_classes = {
            h: len(self.inv_maps[h])
            for h in HEADS
        }

        # ----------------------------------------------------
        # Tokenizer
        # ----------------------------------------------------

        self.tokenizer = (
            AutoTokenizer.from_pretrained(
                artifact_dir
            )
        )

        # ----------------------------------------------------
        # Model
        # ----------------------------------------------------

        self.model = _MultiHeadSlotModel(
            backbone=self.backbone,
            n_classes=n_classes,
        ).to(self.device)

        # ----------------------------------------------------
        # Load trained weights
        # ----------------------------------------------------

        state_dict = load_file(
            model_path
        )

        self.model.load_state_dict(
            state_dict
        )

        self.model.eval()

        print(
            f"ML parser loaded from: {artifact_dir}"
        )

        print(
            f"ML device: {self.device}"
        )

        print(
            "ML heads: "
            + ", ".join(HEADS)
        )


    # ========================================================
    # PREDICT
    # ========================================================

    @torch.no_grad()
    def predict(
        self,
        text: str,
    ) -> dict:
        """
        Predict the three HVAC slots.

        Returns:

            {
                "parameter": ("temperature", 0.91),
                "direction": ("increase", 0.87),
                "intensity": ("strong", 0.79)
            }
        """

        enc = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        enc = {
            key: value.to(self.device)
            for key, value in enc.items()
        }

        logits = self.model(
            enc["input_ids"],
            enc["attention_mask"],
        )

        result = {}

        for h in HEADS:

            probs = F.softmax(
                logits[h][0],
                dim=-1,
            )

            idx = int(
                probs.argmax()
            )

            result[h] = (
                self.inv_maps[h][idx],
                float(probs[idx]),
            )

        return result


# ============================================================
# LOAD MODEL
# ============================================================

def load_ml_parser(
    artifact_dir: str = DEFAULT_ARTIFACT_DIR,
    device: Optional[str] = None,
):
    """
    Load the trained model once.

    Call this during application startup.

    Example:

        load_ml_parser()

    """

    global _predictor

    _predictor = _Predictor(
        artifact_dir=artifact_dir,
        device=device,
    )

    return _predictor


# ============================================================
# PARSE WITH CONTEXT
# ============================================================

def parse_complaint_with_context(
    message: str,
    context: Optional[dict] = None,
) -> Union[
    HVACConstraint,
    ClarificationResponse,
    None,
]:
    """
    Parse an HVAC message using the trained model.

    Zone is extracted directly from the text.

    Context can provide missing information.

    Example context:

        {
            "zone_id": "galley",
            "parameter": "temperature",
            "direction": "increase",
            "intensity": "moderate"
        }

    Returns:

        HVACConstraint
            Successfully resolved.

        ClarificationResponse
            Required information is genuinely missing.

        None
            ML confidence is too low, so the caller should
            escalate to Gemini.
    """

    global _predictor

    # --------------------------------------------------------
    # Ensure model is loaded
    # --------------------------------------------------------

    if _predictor is None:
        load_ml_parser()

    # --------------------------------------------------------
    # Context
    # --------------------------------------------------------

    context = context or {}

    # --------------------------------------------------------
    # Zone extraction
    # --------------------------------------------------------

    # IMPORTANT:
    # Zone comes from rule-based extraction, NOT ML.

    from nlp.predict import extract_zone

    zone = extract_zone(
        message
    )

    if zone is None:
        zone = context.get(
            "zone_id"
        )

    # --------------------------------------------------------
    # ML prediction
    # --------------------------------------------------------

    raw = _predictor.predict(
        message
    )

    print(
        "\n=== ML PARSER ==="
    )

    for head in HEADS:

        label, confidence = raw[head]

        print(
            f"ML {head:<12} -> "
            f"{label:<15} "
            f"confidence={confidence:.4f}"
        )

    # --------------------------------------------------------
    # Resolve predictions
    # --------------------------------------------------------

    resolved = {}

    confidences = {}

    for head in HEADS:

        label, confidence = raw[head]

        # ----------------------------------------------------
        # High-confidence prediction
        # ----------------------------------------------------

        if confidence >= LOW_CONFIDENCE_ESCALATE:

            resolved[head] = label

            confidences[head] = confidence

            continue

        # ----------------------------------------------------
        # Low-confidence prediction
        # ----------------------------------------------------
        # If context contains the value, use context.
        # Otherwise escalate to Gemini.

        if context.get(head):

            resolved[head] = context[head]

            confidences[head] = 1.0

        else:

            print(
                f"ML {head} confidence too low "
                f"({confidence:.4f}) -> escalate"
            )

            return None

    # --------------------------------------------------------
    # Zone
    # --------------------------------------------------------

    if not zone:

        return ClarificationResponse(
            message=(
                "Which room or zone is this about? "
                "For example: galley, room1, kitchen, "
                "office, or conference room."
            )
        )

    # --------------------------------------------------------
    # Parameter
    # --------------------------------------------------------

    if "parameter" not in resolved:

        return None

    # --------------------------------------------------------
    # Direction
    # --------------------------------------------------------

    if "direction" not in resolved:

        return None

    # --------------------------------------------------------
    # Intensity
    # --------------------------------------------------------

    if "intensity" not in resolved:

        resolved["intensity"] = (
            context.get("intensity")
            or "moderate"
        )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    confidence = min(
        confidences.values()
    )

    # --------------------------------------------------------
    # Final HVAC constraint
    # --------------------------------------------------------

    return HVACConstraint(
        zone_id=zone,
        parameter=resolved["parameter"],
        direction=resolved["direction"],
        intensity=resolved["intensity"],
        confidence=confidence,
        raw_text=message,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "\nLoading ML parser..."
    )

    load_ml_parser()

    test_messages = [
        "it's freezing in the galley",
        "make room1 warmer",
        "increase airflow in the kitchen",
        "reduce humidity in the office",
    ]

    for message in test_messages:

        print(
            "\n" + "=" * 70
        )

        print(
            f"INPUT: {message}"
        )

        print(
            "=" * 70
        )

        try:

            result = (
                parse_complaint_with_context(
                    message
                )
            )

            print(
                "\nRESULT:"
            )

            print(
                result
            )

        except Exception as error:

            print(
                f"\nERROR: {error}"
            )

