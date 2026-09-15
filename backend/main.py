from fastapi import FastAPI, HTTPException

from contracts import FeedbackRequest, RegionRequest, TwinState, LLMConstraint, RLAction
from backend.store import store

from rl.agent import HVACAgent
from rl.hvac_env import HVACEnv
from twin.building_config import BuildingConfig, RoomConfig
from twin.building_twin import BuildingTwin

from rl.hvac_controller import calculate_hvac_action

from nlp.llm_parser import (
    parse_complaint_with_context,
    ClarificationResponse,
)

from pydantic import BaseModel, Field

from twin.location_config import get_location, list_locations

class ComfortConfirmation(BaseModel):
    comfortable: bool


class RoomConfigurationRequest(BaseModel):
    room_id: str
    area_m2: float = 30.0
    height_m: float = 3.0
    window_area_m2: float = 5.0
    R: float = 2.0
    C: float = 156_000.0
    shading_coefficient: float = 0.5
    ventilation_ach: float = 1.5
    hvac_capacity_w: float = 2_000.0
    cop: float = 3.5
    initial_temp_c: float = 24.0
    initial_rh_pct: float = 50.0
    initial_co2_ppm: float = 420.0
    initial_occupancy: int = 0


class BuildingConfigurationRequest(BaseModel):
    location_id: str
    building_id: str = "default_building"
    rooms: list[RoomConfigurationRequest] = Field(
        default_factory=lambda: [
            RoomConfigurationRequest(room_id="room_0")
        ]
    )

app = FastAPI(
    title="Digital Twin HVAC Optimizer",
    description="Backend API for HVAC optimization",
    version="1.0.0",
)


# --------------------------------------------------
# Configurable Digital Twin
# --------------------------------------------------

active_location_id = "chennai"


def build_twin(
    location_id: str,
    building_id: str,
    rooms: list[RoomConfigurationRequest],
) -> BuildingTwin:
    location = get_location(location_id)

    return BuildingTwin(
        BuildingConfig(
            building_id=building_id,
            latitude=location.latitude,
            longitude=location.longitude,
            rooms=[
                RoomConfig(**room.model_dump())
                for room in rooms
            ],
        )
    )


building = build_twin(
    location_id=active_location_id,
    building_id="default_building",
    rooms=[RoomConfigurationRequest(room_id="room_0")],
)

def get_twin(zone_id: str):
    try:
        return building.get_room(zone_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Zone not found: {zone_id}",
        )



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


@app.get("/building_config")
def get_building_config():
    config = building.get_config()
    location = get_location(active_location_id)
    config["location"] = {
        "location_id": location.location_id,
        "name": location.name,
        "country": location.country,
        "latitude": location.latitude,
        "longitude": location.longitude,
    }
    return config


@app.get("/locations")
def get_locations():
    return list_locations()


@app.post("/building_config")
def configure_building(request: BuildingConfigurationRequest):
    global active_location_id, building

    try:
        new_building = build_twin(
            location_id=request.location_id,
            building_id=request.building_id,
            rooms=request.rooms,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    active_location_id = request.location_id.strip().lower()
    building = new_building

    store.constraints.clear()
    store.twin_states.clear()
    store.actions.clear()

    return get_building_config()


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

    hvac_capacity_w = float(
        twin.config.hvac_capacity_w
    )

    hvac_power_w = calculate_hvac_action(
        indoor_temp_c=twin.indoor_temp_c,
        target_setpoint_c=new_setpoint,
        max_hvac_power_w=hvac_capacity_w,
    )

    # Update Twin setpoint
    twin.current_setpoint_c = new_setpoint

    # Apply HVAC action
    new_state = twin.step(
        dt=SIMULATION_DT_SECONDS,
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
        "hvac_capacity_w": hvac_capacity_w,
        "simulation_dt_seconds": SIMULATION_DT_SECONDS,
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

    # Apply HVAC action for one configured timestep.
    new_state = twin.step(
        dt=SIMULATION_DT_SECONDS,
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
        "simulation_dt_seconds": SIMULATION_DT_SECONDS,
        "energy_draw_kwh": (
            new_state.energy_draw_kw
            * SIMULATION_DT_SECONDS
            / 3600.0
        ),
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