
from fastapi import FastAPI
from pydantic import BaseModel
from uuid import uuid4

from nlp.llm_parser import (
    parse_complaint,
    HVACConstraint,
    ClarificationResponse,
)

from nlp.conversation import ConversationManager


# ============================================================
# Create FastAPI application
# ============================================================

app = FastAPI(
    title="HVAC NLP API",
    description="Conversational HVAC occupant assistant",
    version="1.0.0",
)


# ============================================================
# Request model
# ============================================================

class ComplaintRequest(BaseModel):
    """
    Request body for the simple NLP parser endpoint.
    """

    complaint: str


# ============================================================
# Chat request model
# ============================================================

class ChatRequest(BaseModel):
    """
    Request body for the conversational endpoint.

    session_id is optional.
    If it is not supplied, a new conversation is created.
    """

    session_id: str | None = None
    message: str


# ============================================================
# Store active conversations
# ============================================================

conversations: dict[str, ConversationManager] = {}


# ============================================================
# Get or create conversation
# ============================================================

def get_conversation(
    session_id: str | None,
):
    """
    Return an existing conversation or create a new one.
    """

    # --------------------------------------------------------
    # Create a new session ID
    # --------------------------------------------------------

    if not session_id:
        session_id = str(uuid4())

    # --------------------------------------------------------
    # Create conversation manager if necessary
    # --------------------------------------------------------

    if session_id not in conversations:

        conversations[session_id] = ConversationManager()

    return session_id, conversations[session_id]


# ============================================================
# Simple NLP parser endpoint
# ============================================================

@app.post("/nlp/parse")
def parse_nlp_complaint(
    request: ComplaintRequest,
):
    """
    Parse a single HVAC complaint.

    Example request:

    {
        "complaint": "Room 3 is too hot"
    }
    """

    result = parse_complaint(
        request.complaint
    )

    # --------------------------------------------------------
    # Successfully parsed
    # --------------------------------------------------------

    if isinstance(
        result,
        HVACConstraint
    ):

        return {
            "status": "success",
            "clarification_needed": False,
            "constraint": result.model_dump(),
        }

    # --------------------------------------------------------
    # Clarification required
    # --------------------------------------------------------

    if isinstance(
        result,
        ClarificationResponse
    ):

        return {
            "status": "clarification_required",
            "clarification_needed": True,
            "message": result.message,
        }

    # --------------------------------------------------------
    # Unexpected result
    # --------------------------------------------------------

    return {
        "status": "error",
        "message": "Unexpected parser response.",
    }


# ============================================================
# Conversational chat endpoint
# ============================================================

@app.post("/nlp/chat")
def chat(
    request: ChatRequest,
):
    """
    Process one message in a conversation.

    The session ID allows the server to remember:

    - room/zone
    - HVAC parameter
    - direction
    - intensity
    - whether the issue is active
    - whether the system is waiting for resolution
    """

    # --------------------------------------------------------
    # Get existing conversation or create a new one
    # --------------------------------------------------------

    session_id, conversation = get_conversation(
        request.session_id
    )

    # --------------------------------------------------------
    # Process user message
    # --------------------------------------------------------

    result = conversation.process_message(
        request.message
    )

    # --------------------------------------------------------
    # Build base response
    # --------------------------------------------------------

    response = {
        "session_id": session_id,
        "type": result["type"],
        "reply": result["reply"],
    }

    # --------------------------------------------------------
    # Include structured constraint if available
    # --------------------------------------------------------

    if "constraint" in result:

        response["constraint"] = result["constraint"]

    # --------------------------------------------------------
    # Include current conversation state
    # --------------------------------------------------------

    response["conversation_state"] = {
        "zone_id": conversation.state.zone_id,
        "parameter": conversation.state.parameter,
        "direction": conversation.state.direction,
        "intensity": conversation.state.intensity,
        "issue_active": conversation.state.issue_active,
        "awaiting_resolution": (
            conversation.state.awaiting_resolution
        ),
    }

    return response


# ============================================================
# Health check
# ============================================================

@app.get("/health")
def health_check():
    """
    Check whether the NLP API is running.
    """

    return {
        "status": "ok",
        "service": "nlp",
        "active_sessions": len(conversations),
    }

