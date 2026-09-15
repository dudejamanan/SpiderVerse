from dataclasses import dataclass
from typing import Optional

from nlp.llm_parser import (
    HVACConstraint,
    ClarificationResponse,
)

from nlp.ml_parser import (
    load_ml_parser,
    parse_complaint_with_context as parse_with_ml,
)


# ============================================================
# CONVERSATION STATE
# ============================================================

@dataclass
class ConversationState:
    zone_id: Optional[str] = None
    parameter: Optional[str] = None
    direction: Optional[str] = None
    intensity: Optional[str] = None

    issue_active: bool = False
    awaiting_resolution: bool = False

    raw_text: Optional[str] = None


# ============================================================
# CONVERSATION MANAGER
# ============================================================

class ConversationManager:

    def __init__(self):

        # Load the trained ML parser once when a conversation
        # manager is created.
        load_ml_parser()

        self.state = ConversationState()


    # ========================================================
    # PROCESS MESSAGE
    # ========================================================

    def process_message(self, message: str):

        if not message or not message.strip():

            return {
                "type": "clarification",
                "reply": "Please describe the HVAC problem you are experiencing.",
            }

        message = message.strip()

        # ----------------------------------------------------
        # If we are waiting for the user to confirm whether
        # the previous HVAC problem has been resolved.
        # ----------------------------------------------------

        if self.state.awaiting_resolution:

            return self.handle_resolution(message)


        # ----------------------------------------------------
        # Parse the new complaint using our trained ML parser.
        # ----------------------------------------------------

        result = self.parse_message(message)


        # ----------------------------------------------------
        # If parser returned a complete HVAC constraint
        # ----------------------------------------------------

        if isinstance(result, HVACConstraint):

            self.store_constraint(result)

            constraint = self.build_constraint_from_state()

            if constraint is None:

                return {
                    "type": "clarification",
                    "reply": (
                        "I understood the HVAC issue, but some "
                        "information is still missing. Please provide "
                        "the room or zone."
                    ),
                }

            self.state.issue_active = True
            self.state.awaiting_resolution = True

            return {
                "type": "constraint",
                "reply": self.generate_constraint_reply(constraint),
                "constraint": constraint.model_dump(),
            }


        # ----------------------------------------------------
        # Parser needs clarification
        # ----------------------------------------------------

        if isinstance(result, ClarificationResponse):

            return {
                "type": "clarification",
                "reply": result.message,
            }


        # ----------------------------------------------------
        # Unexpected result
        # ----------------------------------------------------

        return {
            "type": "error",
            "reply": "I could not understand the HVAC request.",
        }


    # ========================================================
    # PARSE MESSAGE USING ML
    # ========================================================

    def parse_message(self, message: str):

        context = {
            "zone_id": self.state.zone_id,
            "parameter": self.state.parameter,
            "direction": self.state.direction,
            "intensity": self.state.intensity,
        }

        # Remove empty values from context.
        context = {
            key: value
            for key, value in context.items()
            if value is not None
        }

        try:

            result = parse_with_ml(
                message,
                context,
            )

            return result

        except Exception as error:

            print(f"ML parser error: {error}")

            return ClarificationResponse(
                message=(
                    "I could not understand the HVAC issue. "
                    "Please describe whether the room is too hot, "
                    "too cold, humid, dry, stuffy, or has too much airflow."
                )
            )


    # ========================================================
    # STORE CONSTRAINT
    # ========================================================

    def store_constraint(self, constraint: HVACConstraint):

        if constraint.zone_id:
            self.state.zone_id = constraint.zone_id

        if constraint.parameter:
            self.state.parameter = constraint.parameter

        if constraint.direction:
            self.state.direction = constraint.direction

        if constraint.intensity:
            self.state.intensity = constraint.intensity

        if constraint.raw_text:

            if self.state.raw_text:

                self.state.raw_text += " " + constraint.raw_text.strip()

            else:

                self.state.raw_text = constraint.raw_text.strip()


    # ========================================================
    # BUILD FINAL HVAC CONSTRAINT
    # ========================================================

    def build_constraint_from_state(self):

        # Every required field must be present before sending
        # the constraint to the backend / RL controller.

        if not self.state.zone_id:
            return None

        if not self.state.parameter:
            return None

        if not self.state.direction:
            return None

        if not self.state.intensity:
            return None

        return HVACConstraint(
            zone_id=self.state.zone_id,
            parameter=self.state.parameter,
            direction=self.state.direction,
            intensity=self.state.intensity,
            confidence=0.90,
            raw_text=self.state.raw_text or "",
        )


    # ========================================================
    # GENERATE RESPONSE
    # ========================================================

    def generate_constraint_reply(self, constraint: HVACConstraint):

        direction_text = {
            "increase": "increase",
            "decrease": "decrease",
        }

        parameter_text = {
            "temperature": "temperature",
            "humidity": "humidity",
            "airflow": "airflow",
        }

        direction = direction_text.get(
            constraint.direction,
            constraint.direction,
        )

        parameter = parameter_text.get(
            constraint.parameter,
            constraint.parameter,
        )

        intensity = constraint.intensity

        return (
            f"I understood that you want the {parameter} "
            f"in {constraint.zone_id} to {direction} "
            f"with {intensity} intensity."
        )


    # ========================================================
    # HANDLE RESOLUTION
    # ========================================================

    def handle_resolution(self, message: str):

        normalized = message.strip().lower()

        # ----------------------------------------------------
        # YES → ISSUE RESOLVED
        # ----------------------------------------------------

        yes_words = {
            "yes",
            "y",
            "yeah",
            "yep",
            "resolved",
            "fixed",
            "fine",
            "okay",
            "ok",
            "good",
            "all good",
            "works",
            "working",
        }

        if normalized in yes_words:

            self.state.issue_active = False
            self.state.awaiting_resolution = False

            return {
                "type": "resolved",
                "reply": (
                    f"Great. The HVAC issue in "
                    f"{self.state.zone_id} has been marked as resolved."
                ),
            }


        # ----------------------------------------------------
        # NO → ISSUE STILL ACTIVE
        # ----------------------------------------------------

        no_words = {
            "no",
            "n",
            "nope",
            "not resolved",
            "still bad",
            "still not fixed",
            "not fixed",
            "not yet",
        }

        if normalized in no_words:

            self.state.issue_active = True
            self.state.awaiting_resolution = False

            return {
                "type": "clarification",
                "reply": (
                    "Please describe what is still wrong "
                    "with the room."
                ),
            }


        # ----------------------------------------------------
        # AMBIGUOUS RESOLUTION
        # ----------------------------------------------------

        ambiguous_resolution_words = {
            "maybe",
            "not sure",
            "i'm not sure",
            "im not sure",
            "i don't know",
            "i dont know",
            "perhaps",
            "possibly",
            "unsure",
            "idk",
            "don't know",
            "dont know",
        }

        if normalized in ambiguous_resolution_words:

            return {
                "type": "clarification",
                "reply": (
                    f"Is the problem in {self.state.zone_id} "
                    "resolved? Please answer yes or no, or "
                    "describe what is still wrong."
                ),
            }


        # ----------------------------------------------------
        # USER MAY HAVE DESCRIBED A NEW PROBLEM INSTEAD
        # ----------------------------------------------------

        result = self.parse_message(message)

        if isinstance(result, HVACConstraint):

            self.store_constraint(result)

            constraint = self.build_constraint_from_state()

            if constraint is not None:

                self.state.issue_active = True
                self.state.awaiting_resolution = True

                return {
                    "type": "constraint",
                    "reply": self.generate_constraint_reply(
                        constraint
                    ),
                    "constraint": constraint.model_dump(),
                }


        # ----------------------------------------------------
        # STILL UNCLEAR
        # ----------------------------------------------------

        return {
            "type": "clarification",
            "reply": (
                f"Is the problem in {self.state.zone_id} "
                "resolved? Please answer yes or no, or "
                "describe what is still wrong."
            ),
        }


    # ========================================================
    # RESET CONVERSATION
    # ========================================================

    def reset(self):

        self.state = ConversationState()