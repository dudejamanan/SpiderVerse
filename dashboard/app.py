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

zone_id = st.sidebar.selectbox(
    "Select Zone",
    ["room_a", "room_b"],
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

st.caption(
    "Use this to demonstrate how the Digital Twin responds "
    "to HVAC actions."
)

hvac_power = st.slider(
    "HVAC Power (W)",
    min_value=-2000,
    max_value=2000,
    value=0,
    step=500,
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