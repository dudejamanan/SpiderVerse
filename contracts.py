from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


# ============================================================
# 1. DIGITAL TWIN STATE
# ============================================================

class TwinState(BaseModel):
    zone_id: str

    indoor_temp_c: float
    indoor_rh_pct: float
    co2_ppm: float

    outdoor_temp_c: float
    outdoor_rh_pct: float

    occupancy_count: int

    current_setpoint_c: float
    energy_draw_kw: float

    timestamp: datetime


# ============================================================
# 2. LLM PARSED CONSTRAINT
# ============================================================

class LLMConstraint(BaseModel):
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


# ============================================================
# 3. RL AGENT ACTION
# ============================================================

class RLAction(BaseModel):
    zone_id: str

    setpoint_delta_c: float
    new_setpoint_c: float


# ============================================================
# 4. USER FEEDBACK REQUEST
# ============================================================

class FeedbackRequest(BaseModel):
    zone_id: str
    text: str


# ============================================================
# 5. REGION REQUEST
# ============================================================

class RegionRequest(BaseModel):
    region: str