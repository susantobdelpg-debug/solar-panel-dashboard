from __future__ import annotations

from typing import Any

import time
import logging
import numpy as np
import pandas as pd
import requests
import streamlit as st

logger = logging.getLogger(__name__)

from utils.config import (
    FORECAST_DAYS,
    OPEN_METEO_FORECAST_URL,
    PAST_DAYS,
    REQUEST_CACHE_SECONDS,
)

HOURLY_VARS = ["shortwave_radiation", "direct_radiation", "diffuse_radiation", "temperature_2m", "cloud_cover"]


@st.cache_data(ttl=REQUEST_CACHE_SECONDS, show_spinner="Mengambil data cuaca & radiasi dari Open-Meteo...")
def fetch_solar_weather(lat: float, lon: float, past_days: int = PAST_DAYS, forecast_days: int = FORECAST_DAYS) -> dict[str, Any]:
    """Fetch hourly shortwave radiation, temperature and cloud cover.

    Uses the Open-Meteo forecast endpoint with `past_days`, which returns
    verified historical actuals for the past window blended with the
    forecast horizon in a single call.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARS),
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timezone": "auto",
    }
    max_retries = 3
    backoff_factor = 2.0  # Jeda waktu bertambah: 2s, 4s, 6s...

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.warning(
                f"Percobaan {attempt}/{max_retries} mengambil data cuaca ({lat}, {lon}) gagal: {type(e).__name__} - {e}"
            )
            if attempt == max_retries:
                raise
            time.sleep(backoff_factor * attempt)


def weather_to_dataframe(payload: dict[str, Any]) -> pd.DataFrame:
    hourly = payload.get("hourly", {})
    if not hourly or "time" not in hourly:
        return pd.DataFrame(columns=["datetime", *HOURLY_VARS])

    df = pd.DataFrame({"datetime": pd.to_datetime(hourly["time"])})
    for var in HOURLY_VARS:
        df[var] = pd.to_numeric(pd.Series(hourly.get(var, [])), errors="coerce")

    df = df.rename(
        columns={
            "shortwave_radiation": "ghi",       # Global Horizontal Irradiance, W/m^2
            "direct_radiation": "direct_rad",   # Direct Horizontal Irradiance, W/m^2
            "diffuse_radiation": "diffuse_rad", # Diffuse Horizontal Irradiance, W/m^2
            "temperature_2m": "temp_c",
            "cloud_cover": "cloud_cover_pct",
        }
    )
    # Robustness: drop any row where GHI or temperature is missing/NaN,
    # as these are required for cell temperature and power calculations.
    return df.dropna(subset=["ghi", "temp_c"]).reset_index(drop=True)


def generate_mock_weather(past_days: int = PAST_DAYS, forecast_days: int = FORECAST_DAYS, seed: int = 7) -> pd.DataFrame:
    """Synthetic fallback so the app remains demoable without network access.

    NOT real data - only used when the Open-Meteo request fails (e.g. no
    internet access in a sandboxed/offline environment). The UI must make
    this clearly visible to the user whenever it is active.
    """
    rng = np.random.default_rng(seed)
    total_hours = (past_days + forecast_days) * 24
    start = pd.Timestamp.now(tz=None).normalize() - pd.Timedelta(days=past_days)
    idx = pd.date_range(start, periods=total_hours, freq="h")

    hour_of_day = idx.hour + idx.minute / 60
    # Bell-shaped daylight irradiance profile, peak ~ midday, plus cloud noise
    daylight = np.clip(np.sin((hour_of_day - 6) / 12 * np.pi), 0, None)
    clear_sky_ghi = daylight * 950
    cloud_cover = np.clip(rng.normal(55, 25, total_hours), 0, 100)
    cloud_attenuation = 1 - (cloud_cover / 100) * 0.6
    ghi = np.clip(clear_sky_ghi * cloud_attenuation + rng.normal(0, 15, total_hours), 0, None)
    temp_c = 26 + 5 * daylight + rng.normal(0, 0.8, total_hours)

    # Simple split of mock GHI into direct and diffuse components
    # On a clear day, direct is high. With cloud cover, diffuse increases.
    diffuse_fraction = 0.2 + 0.6 * (cloud_cover / 100)
    diffuse_fraction = np.clip(diffuse_fraction, 0.1, 1.0)
    diffuse_rad = ghi * diffuse_fraction
    direct_rad = ghi - diffuse_rad

    return pd.DataFrame(
        {
            "datetime": idx,
            "ghi": ghi,
            "direct_rad": direct_rad,
            "diffuse_rad": diffuse_rad,
            "temp_c": temp_c,
            "cloud_cover_pct": cloud_cover,
        }
    )
