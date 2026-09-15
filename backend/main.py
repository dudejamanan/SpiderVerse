from fastapi import FastAPI

from contracts import FeedbackRequest, RegionRequest
from backend.store import store


app = FastAPI(
    title="Digital Twin HVAC Optimizer",
    description="Backend API for HVAC optimization",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "Digital Twin HVAC Optimizer API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# ============================================================
# FEEDBACK
# ============================================================

@app.post("/submit_feedback")
def submit_feedback(feedback: FeedbackRequest):

    # For now, store the raw feedback.
    # Later Person 3's NLP parser will convert it
    # into an LLMConstraint before we store it.

    return {
        "message": "Feedback received",
        "zone_id": feedback.zone_id,
        "text": feedback.text
    }


# ============================================================
# REGION
# ============================================================

@app.get("/region")
def get_region():
    return {
        "region": store.get_region()
    }


@app.post("/region")
def set_region(request: RegionRequest):

    store.set_region(request.region)

    return {
        "message": "Region updated",
        "region": store.get_region()
    }