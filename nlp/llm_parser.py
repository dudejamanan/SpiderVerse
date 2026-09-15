
"""
HVAC Natural Language Parser

Architecture:
    User text
        |
        +--> Zone extraction (rule-based)
        |
        +--> 3-head DistilBERT
        |       ├── parameter
        |       ├── direction
        |       └── intensity
        |
        +--> Local rule-based fallback
        |
        +--> Gemini fallback
        |
        v
    HVACConstraint

IMPORTANT:
    Zone is NOT predicted by DistilBERT.
    Zone is extracted directly from the user's text.

DistilBERT predicts only:
    - parameter
    - direction
    - intensity
"""

import os
import re
import time
from typing import Literal, Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from nlp.prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================

class ParsedHVACConstraint(BaseModel):
    """
    Schema returned by Gemini.

    Fields are optional because Gemini may not understand
    every part of the user's sentence.
    """

    zone_id: Optional[str] = None

    parameter: Optional[
        Literal["temperature", "humidity", "airflow"]
    ] = None

    direction: Optional[
        Literal["increase", "decrease"]
    ] = None

    intensity: Optional[
        Literal["mild", "moderate", "strong"]
    ] = None

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )


class HVACConstraint(BaseModel):
    """
    Fully resolved HVAC command.
    """

    zone_id: str

    parameter: Literal[
        "temperature",
        "humidity",
        "airflow",
    ]

    direction: Literal[
        "increase",
        "decrease",
    ]

    intensity: Literal[
        "mild",
        "moderate",
        "strong",
    ]

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    raw_text: str


class ClarificationResponse(BaseModel):
    """
    Returned when the parser cannot safely resolve
    a required part of the command.
    """

    clarification_needed: bool = True
    message: str


# ============================================================
# GEMINI CLIENT
# ============================================================

client = None

if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as error:
        print(f"Gemini client initialization failed: {error}")


# ============================================================
# GEMINI HELPERS
# ============================================================

def build_examples() -> str:
    """
    Convert FEW_SHOT_EXAMPLES into text for Gemini.
    """

    if not FEW_SHOT_EXAMPLES:
        return ""

    if isinstance(FEW_SHOT_EXAMPLES, str):
        return FEW_SHOT_EXAMPLES

    return "\n".join(
        str(example)
        for example in FEW_SHOT_EXAMPLES
    )


def build_user_prompt(raw_text: str) -> str:
    """
    Build the Gemini user prompt.
    """

    examples = build_examples()

    prompt = ""

    if examples:
        prompt += (
            "Here are some examples of HVAC commands:\n\n"
            f"{examples}\n\n"
        )

    prompt += (
        "Parse the following HVAC complaint.\n\n"
        f"User input: {raw_text}"
    )

    return prompt


def call_llm(
    raw_text: str,
    retries: int = 2,
) -> ParsedHVACConstraint:
    """
    Call Gemini using structured output.

    Gemini is used only as a fallback when the local/ML
    parser cannot confidently resolve the command.
    """

    if client is None:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    last_error = None

    for attempt in range(retries + 1):

        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=build_user_prompt(raw_text),
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "response_schema": ParsedHVACConstraint,
                },
            )

            parsed = response.parsed

            if isinstance(parsed, ParsedHVACConstraint):
                return parsed

            return ParsedHVACConstraint.model_validate(
                parsed
            )

        except Exception as error:
            last_error = error

            if attempt < retries:
                time.sleep(1.0)

    raise RuntimeError(
        f"Gemini parsing failed: {last_error}"
    )


# ============================================================
# ZONE EXTRACTION
# ============================================================

def extract_zone(text: str) -> Optional[str]:
    """
    Extract HVAC zone directly from the text.

    Examples:
        "it's freezing in the galley" -> galley
        "make room1 warmer"           -> room1
        "make room 1 warmer"          -> room1
        "increase airflow in kitchen"-> kitchen
        "cool lab2"                   -> lab2
        "increase airflow in zone 3"  -> zone3
        "reduce temperature in office"-> office

    Zone is intentionally NOT predicted by DistilBERT.
    """

    if not isinstance(text, str):
        return None

    text = text.strip().lower()

    # --------------------------------------------------------
    # Numeric zones
    # --------------------------------------------------------

    patterns = [
        # room1 / room 1 / room1a / room 1a
        r"\broom\s*(\d+[a-z]?)\b",

        # lab1 / lab 1 / lab1a
        r"\blab\s*(\d+[a-z]?)\b",

        # zone1 / zone 1 / zone1a
        r"\bzone\s*(\d+[a-z]?)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            prefix = pattern.split("\\b")[1]
            prefix = prefix.replace(r"\s*", "")

            # Determine original prefix explicitly
            if "room" in pattern:
                return f"room{match.group(1)}"

            if "lab" in pattern:
                return f"lab{match.group(1)}"

            if "zone" in pattern:
                return f"zone{match.group(1)}"

    # --------------------------------------------------------
    # Named zones
    # --------------------------------------------------------

    named_zones = [
        "conference room",
        "meeting room",
        "server room",
        "training room",
        "common room",
        "living room",

        "galley",
        "kitchen",
        "bedroom",
        "bathroom",
        "office",
        "living",
        "common",
    ]

    # Longest first so "living room" is detected before "living".
    named_zones.sort(
        key=len,
        reverse=True,
    )

    for zone in named_zones:
        pattern = rf"\b{re.escape(zone)}\b"

        if re.search(pattern, text):
            return zone

    return None


# ============================================================
# LOCAL PARAMETER DETECTION
# ============================================================

def detect_parameter(
    text: str,
) -> Optional[str]:
    """
    Detect HVAC parameter from keywords.
    """

    text = text.lower()

    # Temperature
    temperature_words = [
        "temperature",
        "temp",
        "hot",
        "cold",
        "cool",
        "cooler",
        "warm",
        "warmer",
        "freezing",
        "heating",
        "heat",
        "chilly",
    ]

    for word in temperature_words:
        if re.search(
            rf"\b{re.escape(word)}\b",
            text,
        ):
            return "temperature"

    # Humidity
    humidity_words = [
        "humidity",
        "humid",
        "dry",
        "dryer",
        "moisture",
        "moist",
    ]

    for word in humidity_words:
        if re.search(
            rf"\b{re.escape(word)}\b",
            text,
        ):
            return "humidity"

    # Airflow
    airflow_words = [
        "airflow",
        "air flow",
        "ventilation",
        "vent",
        "fan",
        "circulation",
        "air circulation",
    ]

    for word in airflow_words:
        if word in text:
            return "airflow"

    return None


# ============================================================
# LOCAL DIRECTION DETECTION
# ============================================================

def detect_direction(
    text: str,
) -> Optional[str]:
    """
    Detect increase/decrease direction.
    """

    text = text.lower()

    # --------------------------------------------------------
    # Increase
    # --------------------------------------------------------

    increase_patterns = [
        r"\bincrease\b",
        r"\bincreasing\b",
        r"\bincreased\b",
        r"\braise\b",
        r"\braised\b",
        r"\braising\b",
        r"\bboost\b",
        r"\bboosted\b",
        r"\bboosting\b",
        r"\bup\b",
        r"\bhigher\b",
        r"\bmore\b",
        r"\bwarmer\b",
        r"\bwarm\s*up\b",
        r"\bheat\s*up\b",
        r"\bturn\s*up\b",
        r"\bturn\s*it\s*up\b",
        r"\bstronger\b",
        r"\bmore\s+air\b",
        r"\bmore\s+airflow\b",
    ]

    for pattern in increase_patterns:
        if re.search(pattern, text):
            return "increase"

    # --------------------------------------------------------
    # Decrease
    # --------------------------------------------------------

    decrease_patterns = [
        r"\bdecrease\b",
        r"\bdecreasing\b",
        r"\bdecreased\b",
        r"\blower\b",
        r"\blowering\b",
        r"\breduce\b",
        r"\breduced\b",
        r"\breducing\b",
        r"\bdim\b",
        r"\bdown\b",
        r"\bless\b",
        r"\bcooler\b",
        r"\bcool\s*down\b",
        r"\bturn\s*down\b",
        r"\bturn\s*it\s*down\b",
        r"\bweaker\b",
        r"\bless\s+air\b",
        r"\bless\s+airflow\b",
    ]

    for pattern in decrease_patterns:
        if re.search(pattern, text):
            return "decrease"

    # --------------------------------------------------------
    # Temperature semantic phrases
    # --------------------------------------------------------

    if re.search(
        r"\btoo\s+cold\b|\bfreezing\b|\bchilly\b",
        text,
    ):
        return "increase"

    if re.search(
        r"\btoo\s+hot\b|\bboiling\b|\bsweltering\b",
        text,
    ):
        return "decrease"

    return None


# ============================================================
# LOCAL INTENSITY DETECTION
# ============================================================

def detect_intensity(
    text: str,
) -> Optional[str]:
    """
    Detect intensity.

    IMPORTANT:
        Returns "mild", not "slight", because the trained
        DistilBERT model and Pydantic schema use:

            mild
            moderate
            strong
    """

    text = text.lower()

    # --------------------------------------------------------
    # Strong
    # --------------------------------------------------------

    strong_patterns = [
        r"\bvery\b",
        r"\bextremely\b",
        r"\bextreme\b",
        r"\bseverely\b",
        r"\bsevere\b",
        r"\bdrastically\b",
        r"\bdrastic\b",
        r"\ba\s+lot\b",
        r"\bmuch\b",
        r"\bmaximum\b",
        r"\bmax\b",
        r"\bstrong\b",
        r"\bstrongly\b",
        r"\bway\s+too\b",
        r"\bfreezing\b",
        r"\bboiling\b",
    ]

    for pattern in strong_patterns:
        if re.search(pattern, text):
            return "strong"

    # --------------------------------------------------------
    # Mild
    # --------------------------------------------------------

    mild_patterns = [
        r"\bslight\b",
        r"\bslightly\b",
        r"\blittle\b",
        r"\ba\s+little\b",
        r"\bbit\b",
        r"\ba\s+bit\b",
        r"\bsomewhat\b",
        r"\bgently\b",
        r"\bminor\b",
        r"\bminorly\b",
        r"\bslightly\b",
    ]

    for pattern in mild_patterns:
        if re.search(pattern, text):
            return "mild"

    # --------------------------------------------------------
    # Moderate
    # --------------------------------------------------------

    moderate_patterns = [
        r"\bmoderate\b",
        r"\bmoderately\b",
        r"\bmedium\b",
        r"\bnormal\b",
        r"\bsome\b",
    ]

    for pattern in moderate_patterns:
        if re.search(pattern, text):
            return "moderate"

    return None


# ============================================================
# LOCAL RULE-BASED PARSER
# ============================================================

def local_parser(
    raw_text: str,
    existing_zone: Optional[str] = None,
    existing_parameter: Optional[str] = None,
    existing_direction: Optional[str] = None,
    existing_intensity: Optional[str] = None,
):
    """
    Rule-based fallback parser.

    Context values are used when the current message
    does not repeat information from a previous message.
    """

    zone = extract_zone(raw_text)
    parameter = detect_parameter(raw_text)
    direction = detect_direction(raw_text)
    intensity = detect_intensity(raw_text)

    # --------------------------------------------------------
    # Use conversation context where needed
    # --------------------------------------------------------

    zone = zone or existing_zone
    parameter = parameter or existing_parameter
    direction = direction or existing_direction
    intensity = intensity or existing_intensity

    # --------------------------------------------------------
    # Required information
    # --------------------------------------------------------

    if not zone:
        return ClarificationResponse(
            message=(
                "Which room or zone is this about? "
                "For example: galley, room1, kitchen, "
                "office, or conference room."
            )
        )

    if not parameter:
        return ClarificationResponse(
            message=(
                f"I understand you're referring to {zone}, "
                "but I couldn't identify the HVAC parameter. "
                "Is this about temperature, humidity, or airflow?"
            )
        )

    if not direction:
        return ClarificationResponse(
            message=(
                f"I understand the issue is related to "
                f"{parameter} in {zone}. "
                "Should it be increased or decreased?"
            )
        )

    # If intensity is not explicitly mentioned,
    # moderate is used as the safe default.
    intensity = intensity or "moderate"

    return HVACConstraint(
        zone_id=zone,
        parameter=parameter,
        direction=direction,
        intensity=intensity,
        confidence=0.60,
        raw_text=raw_text,
    )


# ============================================================
# ML PARSER
# ============================================================

def parse_with_ml(
    raw_text: str,
    existing_zone: Optional[str] = None,
    existing_parameter: Optional[str] = None,
    existing_direction: Optional[str] = None,
    existing_intensity: Optional[str] = None,
):
    """
    Parse using the trained 3-head DistilBERT model.

    DistilBERT predicts ONLY:

        parameter
        direction
        intensity

    Zone is extracted separately using extract_zone().

    If an ML prediction is below the confidence threshold,
    conversation context can supply that field.

    Returns:
        HVACConstraint
        ClarificationResponse
        None

    None means:
        ML could not confidently resolve the command,
        so another parser should be tried.
    """

    # Runtime import is intentional.
    #
    # nlp.predict imports HVACConstraint from this module.
    # A top-level import would therefore create a circular
    # import.
    from nlp.predict import SlotPredictor, extract_zone

    predictor = SlotPredictor()

    # --------------------------------------------------------
    # Zone extraction
    # --------------------------------------------------------

    zone = extract_zone(raw_text)

    if zone is None:
        zone = existing_zone

    # --------------------------------------------------------
    # DistilBERT prediction
    # --------------------------------------------------------

    raw_prediction = predictor._raw_predict(
        raw_text
    )

    resolved = {}
    confidences = []

    heads = [
        "parameter",
        "direction",
        "intensity",
    ]

    for head in heads:

        label, confidence = raw_prediction[head]

        print(
            f"ML {head:<12} -> "
            f"{label:<15} "
            f"confidence={confidence:.4f}"
        )

        # ----------------------------------------------------
        # High-confidence ML prediction
        # ----------------------------------------------------

        if confidence >= predictor.confidence_threshold:
            resolved[head] = label
            confidences.append(confidence)

        # ----------------------------------------------------
        # Context fallback
        # ----------------------------------------------------

        elif head == "parameter" and existing_parameter:
            resolved[head] = existing_parameter

        elif head == "direction" and existing_direction:
            resolved[head] = existing_direction

        elif head == "intensity" and existing_intensity:
            resolved[head] = existing_intensity

    # --------------------------------------------------------
    # Zone is required
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
    # Parameter and direction are required
    # --------------------------------------------------------

    if "parameter" not in resolved:
        return None

    if "direction" not in resolved:
        return None

    # --------------------------------------------------------
    # Intensity
    # --------------------------------------------------------

    if "intensity" not in resolved:
        resolved["intensity"] = (
            existing_intensity
            or "moderate"
        )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    if confidences:
        confidence = min(confidences)
    else:
        confidence = 0.0

    # --------------------------------------------------------
    # Final constraint
    # --------------------------------------------------------

    return HVACConstraint(
        zone_id=zone,
        parameter=resolved["parameter"],
        direction=resolved["direction"],
        intensity=resolved["intensity"],
        confidence=confidence,
        raw_text=raw_text,
    )


# ============================================================
# GEMINI FALLBACK
# ============================================================

def fallback_parser(
    raw_text: str,
):
    """
    Simple Gemini fallback wrapper.
    """

    result = call_llm(raw_text)

    if not result.zone_id:
        return ClarificationResponse(
            message=(
                "Which room or zone is this about? "
                "For example: galley, room1, kitchen, "
                "office, or conference room."
            )
        )

    if not result.parameter:
        return ClarificationResponse(
            message=(
                f"I understand you're referring to "
                f"{result.zone_id}, but I couldn't identify "
                "the HVAC parameter."
            )
        )

    if not result.direction:
        return ClarificationResponse(
            message=(
                f"I understand the issue is related to "
                f"{result.parameter} in {result.zone_id}. "
                "Should it be increased or decreased?"
            )
        )

    intensity = result.intensity or "moderate"

    return HVACConstraint(
        zone_id=result.zone_id,
        parameter=result.parameter,
        direction=result.direction,
        intensity=intensity,
        confidence=result.confidence,
        raw_text=raw_text,
    )


# ============================================================
# MAIN PARSER
# ============================================================

def parse_complaint(
    raw_text: str,
):
    """
    Main parser.

    Priority:

        1. DistilBERT + direct zone extraction
        2. Local rule-based parser
        3. Gemini

    This keeps Gemini as a fallback rather than making
    every request dependent on the API.
    """

    if not isinstance(raw_text, str):
        raise TypeError(
            "Complaint must be a string."
        )

    if not raw_text.strip():
        raise ValueError(
            "Complaint cannot be empty."
        )

    # ========================================================
    # 1. ML PARSER
    # ========================================================

    try:
        print("\n=== ML PARSER ===")

        ml_result = parse_with_ml(
            raw_text
        )

        if isinstance(
            ml_result,
            HVACConstraint,
        ):
            return ml_result

        if isinstance(
            ml_result,
            ClarificationResponse,
        ):
            return ml_result

    except Exception as error:
        print(
            f"ML parser unavailable: {error}"
        )

    # ========================================================
    # 2. LOCAL FALLBACK
    # ========================================================

    try:
        print("\n=== LOCAL FALLBACK ===")

        local_result = local_parser(
            raw_text
        )

        if isinstance(
            local_result,
            HVACConstraint,
        ):
            return local_result

        if isinstance(
            local_result,
            ClarificationResponse,
        ):
            return local_result

    except Exception as error:
        print(
            f"Local parser unavailable: {error}"
        )

    # ========================================================
    # 3. GEMINI FALLBACK
    # ========================================================

    try:
        print("\n=== GEMINI FALLBACK ===")

        return fallback_parser(
            raw_text
        )

    except Exception as error:

        print(
            f"Gemini unavailable: {error}"
        )

        return ClarificationResponse(
            message=(
                "I couldn't clearly understand the complaint. "
                "Please include the room or zone and describe "
                "the HVAC issue."
            )
        )


# ============================================================
# CONTEXT-AWARE PARSER
# ============================================================

def parse_complaint_with_context(
    raw_text: str,
    existing_zone: Optional[str] = None,
    existing_parameter: Optional[str] = None,
    existing_direction: Optional[str] = None,
    existing_intensity: Optional[str] = None,
):
    """
    Context-aware HVAC parser.

    Example conversation:

        User:
            "It's too cold in the galley."

        Context:
            zone = galley
            parameter = temperature
            direction = increase

        User:
            "A little."

    The second message can use the existing context.
    """

    if not isinstance(raw_text, str):
        raise TypeError(
            "Complaint must be a string."
        )

    if not raw_text.strip():
        raise ValueError(
            "Complaint cannot be empty."
        )

    # ========================================================
    # 1. ML + CONTEXT
    # ========================================================

    try:
        print("\n=== ML CONTEXT PARSER ===")

        ml_result = parse_with_ml(
            raw_text=raw_text,
            existing_zone=existing_zone,
            existing_parameter=existing_parameter,
            existing_direction=existing_direction,
            existing_intensity=existing_intensity,
        )

        if isinstance(
            ml_result,
            HVACConstraint,
        ):
            return ml_result

        if isinstance(
            ml_result,
            ClarificationResponse,
        ):
            return ml_result

    except Exception as error:
        print(
            f"ML context parser unavailable: {error}"
        )

    # ========================================================
    # 2. LOCAL + CONTEXT
    # ========================================================

    try:
        print("\n=== LOCAL CONTEXT FALLBACK ===")

        local_result = local_parser(
            raw_text=raw_text,
            existing_zone=existing_zone,
            existing_parameter=existing_parameter,
            existing_direction=existing_direction,
            existing_intensity=existing_intensity,
        )

        if isinstance(
            local_result,
            HVACConstraint,
        ):
            return local_result

        if isinstance(
            local_result,
            ClarificationResponse,
        ):
            return local_result

    except Exception as error:
        print(
            f"Local context parser unavailable: {error}"
        )

    # ========================================================
    # 3. GEMINI CONTEXT FALLBACK
    # ========================================================

    try:
        print("\n=== GEMINI CONTEXT FALLBACK ===")

        context_parts = []

        if existing_zone:
            context_parts.append(
                f"Previous zone: {existing_zone}"
            )

        if existing_parameter:
            context_parts.append(
                f"Previous parameter: {existing_parameter}"
            )

        if existing_direction:
            context_parts.append(
                f"Previous direction: {existing_direction}"
            )

        if existing_intensity:
            context_parts.append(
                f"Previous intensity: {existing_intensity}"
            )

        context_text = "\n".join(
            context_parts
        )

        prompt = raw_text

        if context_text:
            prompt = (
                "Conversation context:\n"
                f"{context_text}\n\n"
                "New user message:\n"
                f"{raw_text}"
            )

        result = call_llm(
            prompt
        )

        # ----------------------------------------------------
        # Merge Gemini result with existing context
        # ----------------------------------------------------

        zone = (
            result.zone_id
            or existing_zone
        )

        parameter = (
            result.parameter
            or existing_parameter
        )

        direction = (
            result.direction
            or existing_direction
        )

        intensity = (
            result.intensity
            or existing_intensity
            or "moderate"
        )

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        if not zone:
            return ClarificationResponse(
                message=(
                    "Which room or zone is this about? "
                    "For example: galley, room1, kitchen, "
                    "office, or conference room."
                )
            )

        if not parameter:
            return ClarificationResponse(
                message=(
                    f"I understand you're referring to "
                    f"{zone}, but I couldn't identify "
                    "the HVAC parameter."
                )
            )

        if not direction:
            return ClarificationResponse(
                message=(
                    f"I understand the issue is related to "
                    f"{parameter} in {zone}. "
                    "Should it be increased or decreased?"
                )
            )

        return HVACConstraint(
            zone_id=zone,
            parameter=parameter,
            direction=direction,
            intensity=intensity,
            confidence=result.confidence,
            raw_text=raw_text,
        )

    except Exception as error:

        print(
            f"Gemini context parser unavailable: {error}"
        )

        # ====================================================
        # FINAL CONTEXT-ONLY ATTEMPT
        # ====================================================

        if (
            existing_zone
            and existing_parameter
            and existing_direction
        ):
            return HVACConstraint(
                zone_id=existing_zone,
                parameter=existing_parameter,
                direction=existing_direction,
                intensity=(
                    existing_intensity
                    or "moderate"
                ),
                confidence=0.40,
                raw_text=raw_text,
            )

        return ClarificationResponse(
            message=(
                "I couldn't clearly understand the complaint. "
                "Please include the room or zone and describe "
                "the HVAC issue."
            )
        )


# ============================================================
# SIMPLE MANUAL TEST
# ============================================================

if __name__ == "__main__":

    test_messages = [
        "it's freezing in the galley",
        "make room1 warmer",
        "increase airflow in the kitchen",
        "reduce humidity in the office",
        "make room 2 a little cooler",
    ]

    for message in test_messages:

        print("\n" + "=" * 70)
        print(f"INPUT: {message}")
        print("=" * 70)

        try:
            result = parse_complaint(
                message
            )

            print("\nRESULT:")
            print(result)

        except Exception as error:
            print(
                f"ERROR: {error}"
            )

