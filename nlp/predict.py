import json
import os
import re

import torch
from safetensors.torch import load_file
from transformers import AutoModel, AutoTokenizer

from nlp.llm_parser import HVACConstraint, ClarificationResponse


HEADS = ["parameter", "direction", "intensity"]

DEFAULT_CONFIDENCE_THRESHOLD = 0.55

_PROJECT_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DEFAULT_ARTIFACT_DIR = os.path.join(
    _PROJECT_DIR,
    "artifacts",
    "distilbert",
)


# ============================================================
# ZONE EXTRACTION
# ============================================================

def extract_zone(text: str):
    """
    Extract the physical/semantic zone directly from the
    user's text.

    Examples:
        "it's freezing in the galley" -> "galley"
        "increase temperature in room1" -> "room1"
        "kitchen is too cold" -> "kitchen"
        "make the conference room warmer" -> "conference room"
    """

    text = text.lower().strip()

    # --------------------------------------------------------
    # Explicit room/zone identifiers
    # --------------------------------------------------------

    patterns = [
        # room1, room 1, room1A, room 1A
        r"\broom\s*([a-z]?\d+[a-z]?)\b",

        # lab1, lab 1, lab1A
        r"\blab\s*([a-z]?\d+[a-z]?)\b",

        # zone1, zone 1
        r"\bzone\s*([a-z]?\d+[a-z]?)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            value = match.group(1).replace(" ", "")

            prefix = pattern.split(r"\b")[1]

            if "room" in pattern:
                return f"room{value}"

            if "lab" in pattern:
                return f"lab{value}"

            if "zone" in pattern:
                return f"zone{value}"

    # --------------------------------------------------------
    # Named zones
    # --------------------------------------------------------

    named_zones = [
        "galley",
        "kitchen",
        "bedroom",
        "bathroom",
        "living room",
        "living",
        "office",
        "common room",
        "common",
        "conference room",
        "meeting room",
        "server room",
        "training room",
    ]

    # Longest first so "living room" wins over "living"
    named_zones.sort(key=len, reverse=True)

    for zone in named_zones:
        if re.search(rf"\b{re.escape(zone)}\b", text):
            return zone

    return None


# ============================================================
# MULTI-HEAD MODEL
# ============================================================

class MultiHeadSlotModel(torch.nn.Module):

    def __init__(self, backbone, n_classes, dropout=0.1):
        super().__init__()

        self.encoder = AutoModel.from_pretrained(backbone)

        hidden = self.encoder.config.hidden_size

        self.dropout = torch.nn.Dropout(dropout)

        self.heads = torch.nn.ModuleDict({
            head: torch.nn.Linear(
                hidden,
                n_classes[head]
            )
            for head in HEADS
        })

    def forward(self, input_ids, attention_mask):

        out = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask
        )

        pooled = self.dropout(
            out.last_hidden_state[:, 0]
        )

        return {
            head: self.heads[head](pooled)
            for head in HEADS
        }


# ============================================================
# PREDICTOR
# ============================================================

class SlotPredictor:

    def __init__(
        self,
        artifact_dir=DEFAULT_ARTIFACT_DIR,
        confidence_threshold=DEFAULT_CONFIDENCE_THRESHOLD
    ):

        self.artifact_dir = artifact_dir
        self.confidence_threshold = confidence_threshold

        # ----------------------------------------------------
        # Load label maps
        # ----------------------------------------------------

        label_map_path = os.path.join(
            artifact_dir,
            "label_maps.json"
        )

        with open(label_map_path, "r", encoding="utf-8") as f:
            maps = json.load(f)

        self.label_maps = maps["label_maps"]
        self.inv_maps = maps["inv_maps"]

        # ----------------------------------------------------
        # Tokenizer
        # ----------------------------------------------------

        self.tokenizer = AutoTokenizer.from_pretrained(
            artifact_dir
        )

        # ----------------------------------------------------
        # Model
        # ----------------------------------------------------

        backbone = maps["backbone"]

        n_classes = {
            head: len(self.inv_maps[head])
            for head in HEADS
        }

        self.model = MultiHeadSlotModel(
            backbone=backbone,
            n_classes=n_classes
        )

        model_path = os.path.join(
            artifact_dir,
            "model.safetensors"
        )

        state_dict = load_file(model_path)

        self.model.load_state_dict(
            state_dict
        )

        self.model.eval()

    # ========================================================
    # RAW ML PREDICTION
    # ========================================================

    @torch.no_grad()
    def _raw_predict(self, text):

        encoded = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=64
        )

        outputs = self.model(
            input_ids=encoded["input_ids"],
            attention_mask=encoded["attention_mask"]
        )

        result = {}

        for head in HEADS:

            probabilities = torch.softmax(
                outputs[head],
                dim=-1
            )[0]

            confidence, index = torch.max(
                probabilities,
                dim=-1
            )

            index = index.item()

            label = self.inv_maps[head][index]

            result[head] = (
                label,
                confidence.item()
            )

        return result

    # ========================================================
    # PARSE
    # ========================================================

    def parse(self, text, context=None):

        context = context or {}

        # ----------------------------------------------------
        # STEP 1: Extract zone directly
        # ----------------------------------------------------

        zone = extract_zone(text)

        # If no zone in current sentence, use context
        if zone is None:
            zone = context.get("zone_id")

        # ----------------------------------------------------
        # STEP 2: DistilBERT predicts only the other fields
        # ----------------------------------------------------

        raw = self._raw_predict(text)

        print("\nRAW MODEL PREDICTION:")

        for head, (label, confidence) in raw.items():

            print(
                f"{head:<12} -> "
                f"{label:<15} "
                f"confidence={confidence:.4f}"
            )

        # ----------------------------------------------------
        # Resolve ML predictions
        # ----------------------------------------------------

        resolved = {}

        missing = []

        confidence_values = []

        for head in HEADS:

            label, confidence = raw[head]

            confidence_values.append(confidence)

            if confidence < self.confidence_threshold:

                # Context fallback
                if head in context:
                    resolved[head] = context[head]
                else:
                    missing.append(head)

            else:
                resolved[head] = label

        # ----------------------------------------------------
        # Zone is NOT ML predicted
        # ----------------------------------------------------

        if zone is None:
            missing.insert(0, "zone_id")
        else:
            resolved["zone_id"] = zone

        # ----------------------------------------------------
        # Missing information
        # ----------------------------------------------------

        if missing:

            return self._to_clarification(
                missing,
                resolved
            )

        # ----------------------------------------------------
        # Final constraint
        # ----------------------------------------------------

        confidence = min(confidence_values)

        return HVACConstraint(
            zone_id=resolved["zone_id"],
            parameter=resolved["parameter"],
            direction=resolved["direction"],
            intensity=resolved["intensity"],
            confidence=confidence,
            raw_text=text
        )

    # ========================================================
    # CLARIFICATION
    # ========================================================

    def _to_clarification(self, missing, resolved):

        prompts = {

            "zone_id":
                "Which room or zone is this about?",

            "parameter":
                "Is this about temperature, humidity, or airflow?",

            "direction":
                "Should I increase or decrease it?",

            "intensity":
                "Should the change be mild, moderate, or strong?",
        }

        field = missing[0]

        return ClarificationResponse(
            message=prompts[field]
        )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    import argparse

    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--artifacts",
        default=DEFAULT_ARTIFACT_DIR
    )

    ap.add_argument(
        "--text",
        required=True
    )

    ap.add_argument(
        "--context",
        default="{}"
    )

    args = ap.parse_args()

    predictor = SlotPredictor(
        args.artifacts
    )

    context = json.loads(args.context)

    result = predictor.parse(
        args.text,
        context=context
    )

    print(result)