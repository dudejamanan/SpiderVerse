from fastapi import FastAPI, HTTPException

from contracts import FeedbackRequest, RegionRequest, TwinState, LLMConstraint, RLAction
from backend.store import store

from rl.agent import HVACAgent
from rl.hvac_env import HVACEnv
from twin.room_twin import RoomTwin

from rl.hvac_controller import calculate_hvac_action

from nlp.llm_parser import (
    parse_complaint_with_context,
    ClarificationResponse,
)

from pydantic import BaseModel

class ComfortConfirmation(BaseModel):
    comfortable: bool

app = FastAPI(
    title="Digital Twin HVAC Optimizer",
    description="Backend API for HVAC optimization",
    version="1.0.0",
)


# --------------------------------------------------
# Demo Twin
# --------------------------------------------------

twins = {
    "room_a": RoomTwin(
        zone_id="room_a",
        region_id="chennai",
        initial_temp_c=24.0,
    ),
    "room_b": RoomTwin(
        zone_id="room_b",
        region_id="chennai",
        initial_temp_c=24.0,
    ),
}

def get_twin(zone_id: str) -> RoomTwin:
    if zone_id not in twins:
        raise HTTPException(
            status_code=404,
            detail=f"Zone not found: {zone_id}",
        )

    return twins[zone_id]



# --------------------------------------------------
# RL Agent
# --------------------------------------------------

agent = None
SIMULATION_DT_SECONDS = HVACEnv.DEFAULT_SIMULATION_DT_SECONDS


# --------------------------------------------------
# Basic endpoints
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "Digital Twin HVAC Optimizer API is running"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/history")
def get_history():
    return store.get_history()


# --------------------------------------------------
# Feedback
# --------------------------------------------------

@app.post("/submit_feedback")
def submit_feedback(feedback: FeedbackRequest):
    result = parse_complaint_with_context(
        raw_text=feedback.text,
        existing_zone=feedback.zone_id,
    )

    if isinstance(result, ClarificationResponse):
        return {
            "clarification_needed": True,
            "message": result.message,
        }

    constraint = LLMConstraint(
        zone_id=feedback.zone_id,
        parameter=result.parameter,
        direction=result.direction,
        intensity=result.intensity,
        confidence=result.confidence,
        raw_text=feedback.text,
    )

    store.save_constraint(constraint)

    conversation = store.get_conversation(feedback.zone_id)

    if conversation is None:
        store.start_conversation(feedback.zone_id)
    else:
        store.update_conversation(
            feedback.zone_id,
            active=True,
            iteration=conversation.get("iteration", 1),
        )

    return {
        "message": "Feedback parsed successfully",
        "clarification_needed": False,
        "constraint": constraint.model_dump(),
        "ready_for_optimization": True,
    }


@app.post("/confirm/{zone_id}")
def confirm_comfort(
    zone_id: str,
    confirmation: ComfortConfirmation,
):
    get_twin(zone_id)

    conversation = store.get_conversation(zone_id)

    if conversation is None:
        raise HTTPException(
            status_code=400,
            detail="No active conversation for this zone.",
        )

    if confirmation.comfortable:
        store.end_conversation(zone_id)

        return {
            "message": "Comfort achieved. HVAC optimization complete.",
            "conversation_active": False,
        }

    iteration = conversation.get("iteration", 1) + 1

    store.update_conversation(
        zone_id,
        active=True,
        iteration=iteration,
    )

    return {
        "message": "Please provide additional feedback.",
        "conversation_active": True,
        "iteration": iteration,
        "ask_feedback": True,
    }


@app.post("/test_optimize/{zone_id}")
def test_optimize(zone_id: str):

    twin = get_twin(zone_id)

    # Get the NLP constraint
    constraint = store.get_constraint(zone_id)

    if constraint is None:
        raise HTTPException(
            status_code=400,
            detail="No HVAC constraint available. Submit feedback first.",
        )

    # --------------------------------------------------
    # MOCK RL ACTION
    # --------------------------------------------------
    if constraint.direction == "decrease":
        delta = -1.0
    else:
        delta = 1.0

    new_setpoint = max(
        17.0,
        min(
            29.0,
            twin.current_setpoint_c + delta
        )
    )

    actual_delta = new_setpoint - twin.current_setpoint_c

    # Convert setpoint change → HVAC power
    hvac_power_w = actual_delta * 1000.0

    # Update Twin setpoint
    twin.current_setpoint_c = new_setpoint

    # Apply HVAC action
    new_state = twin.step(
        dt=300.0,
        hvac_action=hvac_power_w,
        occupancy_count=twin.occupancy_count,
    )

    # Store action
    action = {
        "zone_id": zone_id,
        "setpoint_delta_c": actual_delta,
        "new_setpoint_c": new_setpoint,
    }

    store.add_history({
        "zone_id": zone_id,
        "constraint": constraint.model_dump(),
        "action": action,
        "hvac_power_w": hvac_power_w,
        "new_state": new_state.model_dump(),
    })

    store.save_twin_state(new_state)

    store.update_conversation(
        zone_id,
        last_constraint=constraint.model_dump(),
        last_action=action,
    )

    return {
        "constraint": constraint.model_dump(),
        "action": action,
        "hvac_power_w": hvac_power_w,
        "new_state": new_state,
        "ask_confirmation": True,
        "confirmation_question": "Is the room comfortable now?",
    }
# --------------------------------------------------
# Region
# --------------------------------------------------

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
        "region": store.get_region(),
    }


# --------------------------------------------------
# Twin State
# --------------------------------------------------

@app.get("/twin_state/{zone_id}")
def get_twin_state(zone_id: str):
    twin = get_twin(zone_id)
    return twin.get_state()

@app.post("/test_hvac/{zone_id}")
def test_hvac(zone_id: str, hvac_power_w: float):

    twin = get_twin(zone_id)
    # Get current state
    old_state = twin.get_state()

    # Apply HVAC action for one timestep
    new_state = twin.step(
        dt=1.0,
        hvac_action=hvac_power_w,
        occupancy_count=twin.occupancy_count,
    )

    # Store the new state
    store.save_twin_state(new_state)

    # Store history
    store.add_history({
        "zone_id": zone_id,
        "type": "manual_test",
        "hvac_power_w": hvac_power_w,
        "old_state": old_state,
        "new_state": new_state,
    })

    return {
        "hvac_power_w": hvac_power_w,
        "old_state": old_state,
        "new_state": new_state,
    }

# --------------------------------------------------
# RL Optimization
# --------------------------------------------------

@app.post("/optimize/{zone_id}")
def optimize(zone_id: str):
    global agent

    twin = get_twin(zone_id)

    # 1. Get current Twin state
    state = twin.get_state()

    # 2. Get NLP constraint
    constraint = store.get_constraint(zone_id)

    if constraint is None:
        raise HTTPException(
            status_code=400,
            detail="No HVAC constraint available for this zone",
        )

    # 3. Load RL model only when optimization is requested
    if agent is None:
        try:
            agent = HVACAgent("rl/models/hvac_policy.zip")
        except Exception:
            raise HTTPException(
                status_code=503,
                detail="RL model is not ready yet. Please try again after the model is trained.",
            )

    # 4. Ask RL agent for action
    action = agent.predict(
        state,
        constraint.model_dump(),
    )

    action = RLAction(**action)
    # 5. Convert setpoint change -> room-specific HVAC power
    hvac_capacity_w = float(
        getattr(
            getattr(twin, "config", None),
            "hvac_capacity_w",
            2000.0,
        )
    )

    hvac_power_w = calculate_hvac_action(
        indoor_temp_c=state.indoor_temp_c,
        target_setpoint_c=action.new_setpoint_c,
        max_hvac_power_w=hvac_capacity_w,
    )

    hvac_power_w = float(
        max(
            -hvac_capacity_w,
            min(hvac_capacity_w, hvac_power_w),
        )
    )

    twin.current_setpoint_c = action.new_setpoint_c

    new_state = twin.step(
        dt=SIMULATION_DT_SECONDS,
        hvac_action=hvac_power_w,
        occupancy_count=twin.occupancy_count,
    )

    energy_draw_kwh = (
        new_state.energy_draw_kw
        * SIMULATION_DT_SECONDS
        / 3600.0
    )

    # 8. Store action and state
    store.save_action(action)

   
    store.save_twin_state(new_state)

    # 9. Store history
    store.add_history({
        "zone_id": zone_id,
        "constraint": constraint.model_dump(),
        "action": action.model_dump(),
        "hvac_power_w": hvac_power_w,
        "hvac_capacity_w": hvac_capacity_w,
        "simulation_dt_seconds": SIMULATION_DT_SECONDS,
        "energy_draw_kwh": energy_draw_kwh,
        "new_state": new_state.model_dump(),
    })

    store.update_conversation(
        zone_id,
        last_constraint=constraint.model_dump(),
        last_action=action.model_dump(),
    )

    # 10. Return complete result
    return {
        "constraint": constraint.model_dump(),
        "action": action.model_dump(),
        "hvac_power_w": hvac_power_w,
        "hvac_capacity_w": hvac_capacity_w,
        "simulation_dt_seconds": SIMULATION_DT_SECONDS,
        "energy_draw_kwh": energy_draw_kwh,
        "new_state": new_state,
        "ask_confirmation": True,
        "confirmation_question": "Is the room comfortable now?",
    }

@app.post("/test_constraint/{zone_id}")
def test_constraint(zone_id: str):

    get_twin(zone_id)  # Ensure the zone exists

    from contracts import LLMConstraint

    constraint = LLMConstraint(
        zone_id=zone_id,
        parameter="temperature",
        direction="decrease",
        intensity="moderate",
        confidence=0.95,
        raw_text="It is too hot in this room",
    )

    store.save_constraint(constraint)

    return {
        "message": "Test constraint created",
        "constraint": constraint.model_dump(),
    }