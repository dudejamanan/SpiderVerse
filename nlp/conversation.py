
from dataclasses import dataclass
from typing import Optional

from nlp.llm_parser import (
    HVACConstraint,
    ClarificationResponse,
    parse_complaint_with_context,
)


# ============================================================
# Conversation state
# ============================================================

@dataclass
class ConversationState:
    """
    Stores the current HVAC issue for one conversation.
    """

    zone_id: Optional[str] = None
    parameter: Optional[str] = None
    direction: Optional[str] = None
    intensity: Optional[str] = None

    issue_active: bool = False
    awaiting_resolution: bool = False


# ============================================================
# Conversation manager
# ============================================================

class ConversationManager:

    def __init__(self):
        self.state = ConversationState()

    # --------------------------------------------------------
    # Reset conversation
    # --------------------------------------------------------

    def reset(self):
        """
        Clear the current issue and start a fresh conversation.
        """

        self.state = ConversationState()

    # --------------------------------------------------------
    # Store HVAC constraint
    # --------------------------------------------------------

    def store_constraint(
        self,
        constraint: HVACConstraint,
    ):
        """
        Store the latest HVAC constraint.
        """

        self.state.zone_id = constraint.zone_id
        self.state.parameter = constraint.parameter
        self.state.direction = constraint.direction
        self.state.intensity = constraint.intensity

        self.state.issue_active = True
        self.state.awaiting_resolution = True

    # --------------------------------------------------------
    # Parse message using existing conversation context
    # --------------------------------------------------------

    def parse_with_context(self, message: str):
        """
        Send the new message to the parser together with
        the information already stored in this conversation.

        This allows messages such as:

            "It is too cold now"

        to be understood as:

            Room 3 + temperature + increase
        """

        return parse_complaint_with_context(
            raw_text=message,
            existing_zone=self.state.zone_id,
            existing_parameter=self.state.parameter,
            existing_direction=self.state.direction,
            existing_intensity=self.state.intensity,
        )

    # --------------------------------------------------------
    # Handle resolution response
    # --------------------------------------------------------

    def handle_resolution(self, message: str):

        normalized = message.strip().lower()

        # ====================================================
        # YES / PROBLEM RESOLVED
        # ====================================================

        yes_words = {
            "yes",
            "yeah",
            "yep",
            "resolved",
            "fixed",
            "fixed now",
            "problem solved",
            "solved",
            "it is fixed",
            "it's fixed",
            "all good",
            "good now",
            "fine now",
        }

        if normalized in yes_words:

            self.reset()

            return {
                "type": "resolved",
                "reply": (
                    "Great! I'm glad the problem is resolved. "
                    "How can I help you with anything else?"
                ),
            }

        # ====================================================
        # NO / PROBLEM NOT RESOLVED
        # ====================================================

        no_words = {
            "no",
            "nope",
            "not yet",
            "still",
            "still hot",
            "still cold",
            "not fixed",
            "not solved",
            "problem remains",
            "not resolved",
        }

        if normalized in no_words:

            self.state.awaiting_resolution = False

            return {
                "type": "continue",
                "reply": (
                    f"Understood. The issue in "
                    f"{self.state.zone_id} is still active. "
                    "Please tell me what is still wrong or "
                    "describe how the room feels now."
                ),
            }

        # ====================================================
        # AMBIGUOUS RESOLUTION RESPONSE
        # ====================================================
        #
        # Examples:
        #
        # "maybe"
        # "not sure"
        # "I don't know"
        #
        # Since the system is currently waiting for a
        # resolution answer, do NOT immediately interpret
        # these as a new HVAC complaint.
        # ====================================================

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

        # ====================================================
        # USER GAVE A NEW HVAC DESCRIPTION
        #
        # Example:
        #
        # Previous:
        # Room 3 is too hot
        #
        # User:
        # It is too cold now
        #
        # Result:
        # Room 3 + temperature + increase
        # ====================================================

        result = self.parse_with_context(message)

        # ----------------------------------------------------
        # Successfully extracted new HVAC constraint
        # ----------------------------------------------------

        if isinstance(result, HVACConstraint):

            self.store_constraint(result)

            return {
                "type": "constraint",
                "reply": (
                    f"Understood. {result.zone_id} needs a "
                    f"{result.direction} adjustment to "
                    f"{result.parameter} with "
                    f"{result.intensity} intensity. "
                    "Is the problem resolved after this adjustment?"
                ),
                "constraint": result.model_dump(),
            }

        # ----------------------------------------------------
        # Clarification required
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
            "reply": (
                "I couldn't understand what is still wrong. "
                "Please describe how the room feels now."
            ),
        }

    # --------------------------------------------------------
    # Process user message
    # --------------------------------------------------------

    def process_message(self, message: str):
        """
        Process one user message.

        The conversation remembers previous information and
        passes it to the parser for every new message.
        """

        if not isinstance(message, str):
            raise TypeError("Message must be a string.")

        if not message.strip():
            raise ValueError("Message cannot be empty.")

        # ====================================================
        # WAITING FOR RESOLUTION
        # ====================================================

        if self.state.awaiting_resolution:

            return self.handle_resolution(message)

        # ====================================================
        # NORMAL HVAC MESSAGE
        # ====================================================

        result = self.parse_with_context(message)

        # ====================================================
        # CLARIFICATION REQUIRED
        # ====================================================

        if isinstance(result, ClarificationResponse):

            return {
                "type": "clarification",
                "reply": result.message,
            }

        # ====================================================
        # HVAC CONSTRAINT SUCCESSFULLY EXTRACTED
        # ====================================================

        if isinstance(result, HVACConstraint):

            self.store_constraint(result)

            return {
                "type": "constraint",
                "reply": (
                    f"I understand that {result.zone_id} "
                    f"needs a {result.direction} adjustment "
                    f"to {result.parameter} with "
                    f"{result.intensity} intensity. "
                    "Is the problem resolved after the adjustment?"
                ),
                "constraint": result.model_dump(),
            }

        # ====================================================
        # UNEXPECTED RESULT
        # ====================================================

        return {
            "type": "error",
            "reply": (
                "I couldn't understand that request. "
                "Please describe the HVAC problem again."
            ),
        }
