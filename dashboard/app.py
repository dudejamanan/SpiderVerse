import streamlit as st
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="SpiderSense",
    page_icon="🕷️",
    layout="wide",
)

# --------------------------------------------------
# Styling
# --------------------------------------------------

st.markdown(
    """
    <style>
    .main-title {
        font-size: 42px;
        font-weight: 700;
        margin-bottom: 0;
    }

    .subtitle {
        font-size: 18px;
        color: #777;
        margin-bottom: 30px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# Header
# --------------------------------------------------

st.markdown(
    '<div class="main-title">🕷️ SpiderSense</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">Digital Twin HVAC Optimization System</div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------
# Sidebar
# --------------------------------------------------

st.sidebar.title("Controls")

try:
    locations_response = requests.get(
        f"{API_URL}/locations",
        timeout=5,
    )
    config_response = requests.get(
        f"{API_URL}/building_config",
        timeout=5,
    )

    if (
        locations_response.status_code != 200
        or config_response.status_code != 200
    ):
        st.error("Could not retrieve building configuration.")
        st.stop()

    locations = locations_response.json()
    active_config = config_response.json()

except requests.exceptions.ConnectionError:
    st.error("Backend is not running. Start FastAPI first.")
    st.stop()

location_group = st.sidebar.selectbox(
    "Location group",
    ["india", "outside_india"],
    format_func=lambda value: (
        "India" if value == "india" else "Outside India"
    ),
)

location_options = locations.get(location_group, [])
location = st.sidebar.selectbox(
    "Location",
    location_options,
    format_func=lambda item: item["name"],
)

st.sidebar.caption(
    f"{location['name']}, {location['country']} | "
    f"{location['latitude']:.4f}, {location['longitude']:.4f}"
)

existing_rooms = active_config.get("rooms", [])
room_count = st.sidebar.number_input(
    "Number of rooms",
    min_value=1,
    max_value=100,
    value=max(1, len(existing_rooms)),
    step=1,
)

room_requests = []

for room_index in range(int(room_count)):
    existing_room = (
        existing_rooms[room_index]
        if room_index < len(existing_rooms)
        else {}
    )

    with st.sidebar.expander(f"Room {room_index + 1}"):
        room_id = st.text_input(
            "Room ID",
            value=existing_room.get(
                "room_id",
                f"room_{room_index}",
            ),
            key=f"room_id_{room_index}",
        )

        room_requests.append({
            "room_id": room_id,
            "area_m2": st.number_input(
                "Area (m²)",
                min_value=0.1,
                value=float(existing_room.get("area_m2", 30.0)),
                key=f"area_{room_index}",
            ),
            "height_m": st.number_input(
                "Height (m)",
                min_value=0.1,
                value=float(existing_room.get("height_m", 3.0)),
                key=f"height_{room_index}",
            ),
            "window_area_m2": st.number_input(
                "Window area (m²)",
                min_value=0.0,
                value=float(existing_room.get("window_area_m2", 5.0)),
                key=f"window_area_{room_index}",
            ),
            "R": st.number_input(
                "Thermal resistance R",
                min_value=0.0001,
                value=float(existing_room.get("R", 2.0)),
                key=f"r_{room_index}",
            ),
            "C": st.number_input(
                "Thermal capacitance C (J/K)",
                min_value=1.0,
                value=float(existing_room.get("C", 156000.0)),
                key=f"c_{room_index}",
            ),
            "shading_coefficient": st.number_input(
                "Shading coefficient",
                min_value=0.0,
                max_value=1.0,
                value=float(existing_room.get("shading_coefficient", 0.5)),
                key=f"shading_{room_index}",
            ),
            "ventilation_ach": st.number_input(
                "Ventilation ACH",
                min_value=0.0,
                value=float(existing_room.get("ventilation_ach", 1.5)),
                key=f"ventilation_{room_index}",
            ),
            "hvac_capacity_w": st.number_input(
                "HVAC capacity (W)",
                min_value=1.0,
                value=float(existing_room.get("hvac_capacity_w", 2000.0)),
                key=f"capacity_{room_index}",
            ),
            "cop": st.number_input(
                "COP",
                min_value=0.1,
                value=float(existing_room.get("cop", 3.5)),
                key=f"cop_{room_index}",
            ),
            "initial_temp_c": st.number_input(
                "Initial temperature (°C)",
                value=float(existing_room.get("initial_temp_c", 24.0)),
                key=f"initial_temp_{room_index}",
            ),
            "initial_rh_pct": st.number_input(
                "Initial humidity (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(existing_room.get("initial_rh_pct", 50.0)),
                key=f"initial_rh_{room_index}",
            ),
            "initial_co2_ppm": st.number_input(
                "Initial CO2 (ppm)",
                min_value=0.0,
                value=float(existing_room.get("initial_co2_ppm", 420.0)),
                key=f"initial_co2_{room_index}",
            ),
            "initial_occupancy": st.number_input(
                "Initial occupancy",
                min_value=0,
                value=int(existing_room.get("initial_occupancy", 0)),
                step=1,
                key=f"initial_occupancy_{room_index}",
            ),
        })

if st.sidebar.button("Apply Building Configuration"):
    configuration_response = requests.post(
        f"{API_URL}/building_config",
        json={
            "location_id": location["location_id"],
            "building_id": active_config.get(
                "building_id",
                "default_building",
            ),
            "rooms": room_requests,
        },
        timeout=5,
    )

    if configuration_response.status_code == 200:
        st.sidebar.success("Building configuration applied.")
        st.rerun()

    st.sidebar.error(configuration_response.text)

zone_id = st.sidebar.selectbox(
    "Select Room",
    [room["room_id"] for room in active_config.get("rooms", [])],
)

if st.sidebar.button("🔄 Refresh"):
    st.rerun()

# --------------------------------------------------
# Get Twin State
# --------------------------------------------------

try:
    response = requests.get(
        f"{API_URL}/twin_state/{zone_id}",
        timeout=5,
    )

    if response.status_code != 200:
        st.error("Could not retrieve Twin state.")
        st.stop()

    state = response.json()

except requests.exceptions.ConnectionError:
    st.error("Backend is not running. Start FastAPI first.")
    st.stop()

# --------------------------------------------------
# Live Twin State
# --------------------------------------------------

st.subheader(f"🌐 Live Digital Twin — {zone_id}")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "🌡 Indoor Temperature",
        f"{state['indoor_temp_c']:.2f} °C",
    )

with col2:
    st.metric(
        "🎯 Setpoint",
        f"{state['current_setpoint_c']:.2f} °C",
    )

with col3:
    st.metric(
        "🫁 CO₂",
        f"{state['co2_ppm']:.0f} ppm",
    )

with col4:
    st.metric(
        "⚡ Energy",
        f"{state['energy_draw_kw']:.3f} kW",
    )

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "💧 Humidity",
        f"{state['indoor_rh_pct']:.1f} %",
    )

with col2:
    st.metric(
        "👥 Occupancy",
        f"{state['occupancy_count']}",
    )

with col3:
    st.metric(
        "🌤 Outdoor Temperature",
        f"{state['outdoor_temp_c']:.1f} °C",
    )

st.divider()

# --------------------------------------------------
# Manual HVAC Control
# --------------------------------------------------

st.subheader("🎛️ Manual HVAC Control")

selected_room_config = next(
    room
    for room in active_config.get("rooms", [])
    if room["room_id"] == zone_id
)

hvac_capacity_w = int(
    selected_room_config["hvac_capacity_w"]
)

st.caption(
    "Use this to demonstrate how the Digital Twin responds "
    "to HVAC actions."
)

hvac_power = st.slider(
    "HVAC Power (W)",
    min_value=-hvac_capacity_w,
    max_value=hvac_capacity_w,
    value=0,
    step=max(1, min(500, hvac_capacity_w)),
)

if hvac_power < 0:
    st.info("❄️ Cooling")
elif hvac_power > 0:
    st.info("🔥 Heating")
else:
    st.info("⏸ HVAC Off")

if st.button("Apply HVAC Action"):

    try:
        result = requests.post(
            f"{API_URL}/test_hvac/{zone_id}",
            params={
                "hvac_power_w": hvac_power
            },
            timeout=5,
        )

        if result.status_code == 200:
            st.success("HVAC action applied successfully!")
            st.rerun()
        else:
            st.error(
                f"HVAC action failed: {result.text}"
            )

    except requests.exceptions.ConnectionError:
        st.error("Backend is not running.")

st.divider()

# --------------------------------------------------
# History
# --------------------------------------------------

st.subheader("📈 Twin History")

try:
    history_response = requests.get(
        f"{API_URL}/history",
        timeout=5,
    )

    if history_response.status_code == 200:

        history = history_response.json()

        # Only show records for selected zone
        zone_history = [
            record
            for record in history
            if record.get("zone_id") == zone_id
        ]

        if zone_history:

            rows = []

            for record in zone_history:

                new_state = record.get("new_state")

                if new_state:
                    rows.append({
                        "timestamp": new_state["timestamp"],
                        "temperature": new_state["indoor_temp_c"],
                        "energy": new_state["energy_draw_kw"],
                        "co2": new_state["co2_ppm"],
                    })

            if rows:

                df = pd.DataFrame(rows)

                df["timestamp"] = pd.to_datetime(
                    df["timestamp"]
                )

                df = df.sort_values("timestamp")

                st.write("### 🌡 Temperature")

                st.line_chart(
                    df.set_index("timestamp")["temperature"]
                )

                st.write("### ⚡ Energy Consumption")

                st.line_chart(
                    df.set_index("timestamp")["energy"]
                )

                st.write("### 🫁 CO₂")

                st.line_chart(
                    df.set_index("timestamp")["co2"]
                )

            else:
                st.info("No history available yet.")

        else:
            st.info(
                "No history yet. Apply a few HVAC actions "
                "to generate Twin data."
            )

    else:
        st.warning("Could not retrieve history.")

except requests.exceptions.ConnectionError:
    st.warning("Backend is not running.")

st.divider()

# --------------------------------------------------
# Occupant Feedback
# --------------------------------------------------

st.subheader("🗣️ Occupant Feedback")

feedback = st.text_area(
    "Tell SpiderSense how the room feels",
    placeholder="Example: It is too hot in room A",
    height=100,
)

if st.button("Submit Feedback", type="primary"):

    if not feedback.strip():

        st.warning("Please enter some feedback.")

    else:

        try:

            result = requests.post(
                f"{API_URL}/submit_feedback",
                json={
                    "zone_id": zone_id,
                    "text": feedback,
                },
                timeout=5,
            )

            if result.status_code == 200:

                st.success(
                    "Feedback submitted successfully!"
                )

                st.json(result.json())

            else:

                st.error(
                    f"Feedback submission failed: "
                    f"{result.text}"
                )

        except requests.exceptions.ConnectionError:

            st.error("Backend is not running.")

st.divider()

# --------------------------------------------------
# RL Optimization
# --------------------------------------------------

st.subheader("🤖 AI HVAC Optimization")

if st.button("Optimize HVAC", type="primary"):

    try:

        result = requests.post(
            f"{API_URL}/optimize/{zone_id}",
            timeout=10,
        )

        if result.status_code == 200:

            data = result.json()

            st.success(
                "HVAC optimization completed!"
            )

            action = data["action"]

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "New Setpoint",
                    f"{action['new_setpoint_c']:.1f} °C",
                )

            with col2:
                st.metric(
                    "Setpoint Change",
                    f"{action['setpoint_delta_c']:+.1f} °C",
                )

            with col3:
                st.metric(
                    "HVAC Power",
                    f"{data['hvac_power_w']:.0f} W",
                )

            st.subheader("Updated Twin State")

            st.json(
                data["new_state"]
            )

        elif result.status_code == 503:

            st.warning(
                "RL model is not trained yet. "
                "Optimization will become available "
                "once Person 2 adds the trained model."
            )

        elif result.status_code == 400:

            st.warning(
                "No HVAC constraint is available yet. "
                "Submit occupant feedback first."
            )

        else:

            st.error(
                f"Optimization failed: {result.text}"
            )

    except requests.exceptions.ConnectionError:

        st.error("Backend is not running.")

# --------------------------------------------------
# Footer
# --------------------------------------------------

st.divider()

st.caption(
    "SpiderSense • Digital Twin + NLP + "
    "Reinforcement Learning"
)