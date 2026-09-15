"""
Open-Meteo weather client.

Person 01: Twin Engineer
"""

import requests


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_current_weather(latitude: float, longitude: float) -> dict:
    """
    Fetch current weather conditions from Open-Meteo.
    """

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "shortwave_radiation,"
            "cloud_cover"
        ),
    }

    response = requests.get(
        OPEN_METEO_URL,
        params=params,
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()
    current = data["current"]

    return {
        "outdoor_temp_c": current["temperature_2m"],
        "outdoor_rh_pct": current["relative_humidity_2m"],
        "solar_radiation_w_m2": current["shortwave_radiation"],
        "cloud_cover_pct": current["cloud_cover"],
    }