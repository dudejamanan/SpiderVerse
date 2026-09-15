import os
import re
import time
from typing import Literal, Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from nlp.prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES


load_dotenv()


# ============================================================
# Pydantic models
# ============================================================

class ParsedHVACConstraint(BaseModel):
    """
    Raw structured result returned by Gemini.

    Fields are optional because a user may mention only
    the room OR only the HVAC problem.
    """

    zone_id: Optional[str] = None

    parameter: Optional[
        Literal["temperature", "humidity", "airflow"]
    ] = None

    direction: Optional[
        Literal["increase", "decrease"]
    ] = None

    intensity: Optional[
        Literal["slight", "moderate", "strong"]
    ] = None

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )


class HVACConstraint(BaseModel):
    """
    Complete HVAC constraint sent to the backend/RL system.
    """

    zone_id: str

    parameter: Literal[
        "temperature",
        "humidity",
        "airflow"
    ]

    direction: Literal[
        "increase",
        "decrease"
    ]

    intensity: Literal[
        "slight",
        "moderate",
        "strong"
    ]

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    raw_text: str


class ClarificationResponse(BaseModel):
    """
    Response used when information is missing or ambiguous.
    """

    clarification_needed: bool = True
    message: str


# ============================================================
# Gemini client
# ============================================================

def get_gemini_client():

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Please add it to the .env file."
        )

    return genai.Client(api_key=api_key)


# ============================================================
# Gemini prompt helpers
# ============================================================

def build_examples() -> str:

    examples = []

    for example in FEW_SHOT_EXAMPLES:

        examples.append(
            f"""
Complaint:
"{example["complaint"]}"

Zone:
{example["zone_id"]}

Parameter:
{example["parameter"]}

Direction:
{example["direction"]}

Intensity:
{example["intensity"]}

Confidence:
{example["confidence"]}
"""
        )

    return "\n".join(examples)


def build_user_prompt(raw_text: str) -> str:

    examples = build_examples()

    return f"""
{SYSTEM_PROMPT}

Here are examples:

{examples}

Now analyze this occupant complaint:

"{raw_text}"

Return the structured result according to the required schema.

If the room/zone is missing, leave zone_id empty.

If the HVAC parameter is missing, leave parameter empty.

If direction is missing, leave direction empty.

If intensity is missing, leave intensity empty.

Do not invent information.
"""


# ============================================================
# Gemini call
# ============================================================

def call_llm(raw_text: str) -> ParsedHVACConstraint:

    client = get_gemini_client()

    max_attempts = 2

    for attempt in range(max_attempts):

        try:

            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=build_user_prompt(raw_text),
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ParsedHVACConstraint,
                },
            )

            if not response.parsed:
                raise RuntimeError(
                    "Gemini did not return a structured result."
                )

            return response.parsed

        except Exception as error:

            error_text = str(error)

            # ------------------------------------------------
            # Do NOT retry quota errors.
            # ------------------------------------------------

            if (
                "429" in error_text
                or "RESOURCE_EXHAUSTED" in error_text
            ):
                print("Gemini quota exceeded.")
                raise

            print(
                f"Gemini attempt "
                f"{attempt + 1}/{max_attempts} failed: "
                f"{error}"
            )

            if attempt == max_attempts - 1:
                raise

            time.sleep(2)


# ============================================================
# Local parser helpers
# ============================================================

def extract_zone(text: str) -> Optional[str]:

    text_lower = text.lower()

    patterns = [
        r"\b(room\s+\d+[a-z]?)\b",
        r"\b(lab\s+\d+[a-z]?)\b",
        r"\b(zone\s+\d+[a-z]?)\b",
        r"\b(conference\s+room)\b",
        r"\b(meeting\s+room)\b",
        r"\b(server\s+room)\b",
        r"\b(training\s+room)\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text_lower,
            re.IGNORECASE
        )

        if match:

            zone = match.group(1)

            return " ".join(
                word.capitalize()
                for word in zone.split()
            )

    return None


def detect_parameter(text: str) -> Optional[str]:

    text_lower = text.lower()

    # Temperature
    temperature_words = {
        "hot",
        "warm",
        "cold",
        "freezing",
        "cool",
        "cooler",
        "heat",
        "temperature",
        "chilly",
    }

    # Humidity
    humidity_words = {
        "humid",
        "humidity",
        "muggy",
        "damp",
        "dry",
    }

    # Airflow
    airflow_words = {
        "stuffy",
        "airflow",
        "air flow",
        "air circulation",
        "circulation",
        "fresh air",
        "draft",
        "draught",
        "air blowing",
        "blowing",
    }

    if any(
        word in text_lower
        for word in humidity_words
    ):
        return "humidity"

    if any(
        word in text_lower
        for word in airflow_words
    ):
        return "airflow"

    if any(
        word in text_lower
        for word in temperature_words
    ):
        return "temperature"

    return None


def detect_direction(
    text: str,
    parameter: Optional[str],
) -> Optional[str]:

    text_lower = text.lower()

    # --------------------------------------------------------
    # Temperature
    # --------------------------------------------------------

    if parameter == "temperature":

        if any(
            phrase in text_lower
            for phrase in [
                "too hot",
                "very hot",
                "extremely hot",
                "too warm",
                "very warm",
                "make it cooler",
                "cool it",
                "cooler",
                "reduce temperature",
                "lower temperature",
                "decrease temperature",
            ]
        ):
            return "decrease"

        if any(
            phrase in text_lower
            for phrase in [
                "too cold",
                "very cold",
                "extremely cold",
                "freezing",
                "too chilly",
                "make it warmer",
                "warm it",
                "warmer",
                "increase temperature",
                "raise temperature",
            ]
        ):
            return "increase"

    # --------------------------------------------------------
    # Humidity
    # --------------------------------------------------------

    if parameter == "humidity":

        if any(
            phrase in text_lower
            for phrase in [
                "too humid",
                "very humid",
                "humid",
                "muggy",
                "damp",
                "reduce humidity",
                "lower humidity",
                "decrease humidity",
            ]
        ):
            return "decrease"

        if any(
            phrase in text_lower
            for phrase in [
                "too dry",
                "very dry",
                "dry",
                "increase humidity",
                "raise humidity",
            ]
        ):
            return "increase"

    # --------------------------------------------------------
    # Airflow
    # --------------------------------------------------------

    if parameter == "airflow":

        if any(
            phrase in text_lower
            for phrase in [
                "stuffy",
                "poor air circulation",
                "poor circulation",
                "need more fresh air",
                "needs more fresh air",
                "increase airflow",
                "more airflow",
                "more air",
            ]
        ):
            return "increase"

        if any(
            phrase in text_lower
            for phrase in [
                "strong draft",
                "strong draught",
                "too much air",
                "too much air blowing",
                "air blowing too much",
                "excessive airflow",
                "too much airflow",
                "reduce airflow",
                "less airflow",
                "less air",
            ]
        ):
            return "decrease"

    return None


def detect_intensity(text: str) -> Optional[str]:

    text_lower = text.lower()

    # Strong
    if any(
        phrase in text_lower
        for phrase in [
            "extremely",
            "very",
            "freezing",
            "extremely hot",
            "extremely cold",
            "really hot",
            "really cold",
            "strong",
            "severe",
        ]
    ):
        return "strong"

    # Slight
    if any(
        phrase in text_lower
        for phrase in [
            "slightly",
            "a little",
            "little",
            "slight",
            "slightly warm",
            "slightly cold",
            "bit warm",
            "bit cold",
        ]
    ):
        return "slight"

    # Moderate is the default for a clear complaint
    return "moderate"


# ============================================================
# Local parser
# ============================================================

def local_parser(
    raw_text: str,
    existing_zone: Optional[str] = None,
    existing_parameter: Optional[str] = None,
    existing_direction: Optional[str] = None,
    existing_intensity: Optional[str] = None,
) -> (
    HVACConstraint
    | ClarificationResponse
    | None
):

    text = raw_text.strip()

    # --------------------------------------------------------
    # Extract information from current message
    # --------------------------------------------------------

    zone = extract_zone(text)

    parameter = detect_parameter(text)

    direction = detect_direction(
        text,
        parameter
    )

    intensity = detect_intensity(text)

    # --------------------------------------------------------
    # Use conversation context when information is missing
    # --------------------------------------------------------

    if zone is None:
        zone = existing_zone

    # --------------------------------------------------------
    # Parameter handling
    #
    # Important:
    # If the user gives a NEW HVAC condition, use the new
    # parameter instead of blindly keeping the old one.
    # --------------------------------------------------------

    if parameter is None:
        parameter = existing_parameter

    # --------------------------------------------------------
    # Direction handling
    # --------------------------------------------------------

    if direction is None:

        direction = existing_direction

    # --------------------------------------------------------
    # Intensity handling
    # --------------------------------------------------------

    if intensity is None:

        intensity = existing_intensity

    # --------------------------------------------------------
    # Room missing
    # --------------------------------------------------------

    if not zone:

        # We understood the HVAC problem but don't know
        # which room it belongs to.

        if parameter and direction:

            return ClarificationResponse(
                message=(
                    "Which room or zone are you in? "
                    "For example: Room 1, Room 2, "
                    "Conference Room, or Lab 3."
                )
            )

        return None

    # --------------------------------------------------------
    # HVAC parameter missing
    # --------------------------------------------------------

    if not parameter:

        return ClarificationResponse(
            message=(
                f"I know you're referring to {zone}, "
                "but I couldn't understand the HVAC issue. "
                "Could you tell me whether the room is too "
                "hot, too cold, too humid, too dry, "
                "or has insufficient airflow?"
            )
        )

    # --------------------------------------------------------
    # Direction missing
    # --------------------------------------------------------

    if not direction:

        return ClarificationResponse(
            message=(
                f"I understand you're referring to {zone} "
                f"and the issue is related to {parameter}. "
                "Could you tell me whether you want it "
                "increased or decreased?"
            )
        )

    # --------------------------------------------------------
    # Intensity missing
    # --------------------------------------------------------

    if not intensity:

        intensity = "moderate"

    # --------------------------------------------------------
    # Successful local parsing
    # --------------------------------------------------------

    return HVACConstraint(
        zone_id=zone,
        parameter=parameter,
        direction=direction,
        intensity=intensity,
        confidence=0.90,
        raw_text=raw_text,
    )


# ============================================================
# Original fallback parser
# ============================================================

def fallback_parser(
    raw_text: str,
) -> ParsedHVACConstraint | None:

    result = local_parser(raw_text)

    if isinstance(result, HVACConstraint):

        return ParsedHVACConstraint(
            zone_id=result.zone_id,
            parameter=result.parameter,
            direction=result.direction,
            intensity=result.intensity,
            confidence=result.confidence,
        )

    return None


# ============================================================
# Main parser
# ============================================================

def parse_complaint(
    raw_text: str,
) -> HVACConstraint | ClarificationResponse:

    if not isinstance(raw_text, str):
        raise TypeError("Complaint must be a string.")

    if not raw_text.strip():
        raise ValueError("Complaint cannot be empty.")

    # --------------------------------------------------------
    # LOCAL PARSER FIRST
    #
    # This prevents unnecessary Gemini requests.
    # --------------------------------------------------------

    local_result = local_parser(raw_text)

    if isinstance(
        local_result,
        HVACConstraint
    ):

        return local_result

    if isinstance(
        local_result,
        ClarificationResponse
    ):

        return local_result

    # --------------------------------------------------------
    # Gemini fallback
    #
    # Only used if the local parser cannot understand the
    # complaint.
    # --------------------------------------------------------

    try:

        result = call_llm(raw_text)

    except Exception as error:

        print(
            f"Gemini unavailable: {error}"
        )

        return ClarificationResponse(
            message=(
                "I couldn't clearly understand the complaint. "
                "Please include the room or zone and describe "
                "the HVAC issue. For example: "
                "'Room 2 is too hot.'"
            )
        )

    # --------------------------------------------------------
    # Gemini result
    # --------------------------------------------------------

    if not result.zone_id:

        return ClarificationResponse(
            message=(
                "Which room or zone are you in? "
                "For example: Room 1, Room 2, "
                "Conference Room, or Lab 3."
            )
        )

    if (
        not result.parameter
        or not result.direction
    ):

        return ClarificationResponse(
            message=(
                f"I know you're referring to "
                f"{result.zone_id}, but I couldn't clearly "
                "understand the HVAC issue. "
                "Could you tell me whether the room is too "
                "hot, too cold, too humid, too dry, "
                "or has insufficient airflow?"
            )
        )

    intensity = result.intensity or "moderate"

    if result.confidence < 0.5:

        return ClarificationResponse(
            message=(
                f"I understand you're referring to "
                f"{result.zone_id}, but I need a little "
                "more information about the HVAC problem."
            )
        )

    return HVACConstraint(
        zone_id=result.zone_id,
        parameter=result.parameter,
        direction=result.direction,
        intensity=intensity,
        confidence=result.confidence,
        raw_text=raw_text,
    )


# ============================================================
# Context-aware parser
# ============================================================

def parse_complaint_with_context(
    raw_text: str,
    existing_zone: Optional[str] = None,
    existing_parameter: Optional[str] = None,
    existing_direction: Optional[str] = None,
    existing_intensity: Optional[str] = None,
) -> HVACConstraint | ClarificationResponse:

    if not isinstance(raw_text, str):
        raise TypeError("Complaint must be a string.")

    if not raw_text.strip():
        raise ValueError("Complaint cannot be empty.")

    # --------------------------------------------------------
    # LOCAL CONTEXT-AWARE PARSER
    # --------------------------------------------------------

    local_result = local_parser(
        raw_text=raw_text,
        existing_zone=existing_zone,
        existing_parameter=existing_parameter,
        existing_direction=existing_direction,
        existing_intensity=existing_intensity,
    )

    if isinstance(
        local_result,
        HVACConstraint
    ):

        return local_result

    if isinstance(
        local_result,
        ClarificationResponse
    ):

        return local_result

    # --------------------------------------------------------
    # Gemini fallback WITH conversation context
    # --------------------------------------------------------

    context = f"""
CURRENT CONVERSATION CONTEXT:

Existing room/zone:
{existing_zone or "Not known"}

Existing parameter:
{existing_parameter or "Not known"}

Existing direction:
{existing_direction or "Not known"}

Existing intensity:
{existing_intensity or "Not known"}
"""

    prompt = f"""
{SYSTEM_PROMPT}

{context}

The occupant has sent this new message:

"{raw_text}"

IMPORTANT:

1. Extract HVAC information from the new message.

2. If the room/zone is not mentioned in the new message,
   use the existing room/zone from the conversation context.

3. If the parameter is not mentioned but the context clearly
   identifies it, reuse the existing parameter.

4. If the user describes a NEW HVAC condition, update the
   parameter, direction and intensity.

5. Never invent a room/zone when neither the message nor
   the conversation context contains one.

6. Return null for information that is genuinely unknown.

Example:

Existing zone:
Room 3

Existing parameter:
temperature

Existing direction:
decrease

Existing intensity:
strong

New message:
"It is too cold now"

Correct result:

zone_id = "Room 3"
parameter = "temperature"
direction = "increase"
intensity = "strong"

Return ONLY the structured result.
"""

    try:

        client = get_gemini_client()

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": ParsedHVACConstraint,
            },
        )

        if not response.parsed:

            raise RuntimeError(
                "Gemini did not return a structured result."
            )

        result = response.parsed

    except Exception as error:

        print(
            f"Gemini unavailable: {error}"
        )

        # ----------------------------------------------------
        # Final local clarification
        # ----------------------------------------------------

        if not existing_zone:

            return ClarificationResponse(
                message=(
                    "Which room or zone are you in? "
                    "For example: Room 1, Room 2, "
                    "Conference Room, or Lab 3."
                )
            )

        return ClarificationResponse(
            message=(
                f"I know you're referring to "
                f"{existing_zone}, but I couldn't clearly "
                "understand the HVAC issue. "
                "Could you tell me whether it is too hot, "
                "too cold, too humid, too dry, or has "
                "insufficient airflow?"
            )
        )

    # --------------------------------------------------------
    # Merge Gemini result with conversation context
    # --------------------------------------------------------

    zone_id = result.zone_id or existing_zone

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

    # --------------------------------------------------------
    # Zone missing
    # --------------------------------------------------------

    if not zone_id:

        return ClarificationResponse(
            message=(
                "Which room or zone are you in? "
                "For example: Room 1, Room 2, "
                "Conference Room, or Lab 3."
            )
        )

    # --------------------------------------------------------
    # HVAC information missing
    # --------------------------------------------------------

    if not parameter or not direction:

        return ClarificationResponse(
            message=(
                f"I know you're referring to {zone_id}, "
                "but I couldn't clearly understand the HVAC "
                "issue. Could you tell me whether the room is "
                "too hot, too cold, too humid, too dry, "
                "or has insufficient airflow?"
            )
        )

    # --------------------------------------------------------
    # Low confidence
    # --------------------------------------------------------

    if result.confidence < 0.5:

        return ClarificationResponse(
            message=(
                f"I understand you're referring to "
                f"{zone_id}, but I need a little more "
                "information about the HVAC problem."
            )
        )

    # --------------------------------------------------------
    # Complete constraint
    # --------------------------------------------------------

    return HVACConstraint(
        zone_id=zone_id,
        parameter=parameter,
        direction=direction,
        intensity=intensity,
        confidence=result.confidence,
        raw_text=raw_text,
    )

