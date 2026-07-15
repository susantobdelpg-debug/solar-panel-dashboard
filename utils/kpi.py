from __future__ import annotations

import numpy as np
import pandas as pd
import pytz
from pvlib import irradiance, solarposition

from utils.config import (
    CO2_FACTOR_KG_PER_KWH,
    ELECTRICITY_TARIFF_RP_PER_KWH,
    LOCATIONS,
    NOCT_C,
    PANEL_AREA_M2,
    PANEL_AZIMUTH_DEG,
    PANEL_CAPACITY_WP,
    PANEL_EFFICIENCY,
    PANEL_TILT_DEG,
    STC_CELL_TEMP_C,
    STC_IRRADIANCE_W_M2,
    SYSTEM_DERATE,
    TEMP_COEFF_PMAX_PER_C,
)


def calculate_poa_irradiance(
    df: pd.DataFrame,
    lat: float,
    lon: float,
    surface_tilt: float = PANEL_TILT_DEG,
    surface_azimuth: float | None = PANEL_AZIMUTH_DEG,
) -> pd.Series:
    """Calculate Plane of Array (POA) global irradiance using pvlib isotropic sky diffuse model.

    Transposes horizontal direct and diffuse radiation to a tilted panel surface.
    """
    # 1. Localize naive datetime index based on longitude (WIB = UTC+7, WITA = UTC+8)
    offset_hours = 7 if lon < 115.0 else 8
    tz = pytz.FixedOffset(offset_hours * 60)
    dt_index = pd.DatetimeIndex(df["datetime"]).tz_localize(tz)

    # 2. Compute solar position
    solpos = solarposition.get_solarposition(dt_index, lat, lon)
    solar_zenith = solpos["apparent_zenith"].to_numpy()
    solar_azimuth = solpos["azimuth"].to_numpy()

    # 3. Calculate DNI (Direct Normal Irradiance) from Direct Horizontal Irradiance (direct_rad)
    # DirHI = DNI * cos(zenith) => DNI = DirHI / cos(zenith)
    cos_zenith = np.cos(np.radians(solar_zenith))
    # Avoid division by zero when sun is low or below the horizon
    dni = np.where(cos_zenith > 0.087, df["direct_rad"] / cos_zenith, 0.0)
    dni = np.clip(dni, 0, 1367)  # Clip to solar constant

    # 4. Determine panel tilt and azimuth
    tilt = surface_tilt
    if surface_azimuth is not None:
        azimuth = surface_azimuth
    else:
        # Dynamically face equator: North (0 deg) for Southern Hemisphere, South (180 deg) for Northern Hemisphere
        azimuth = 180.0 if lat >= 0.0 else 0.0

    # 5. Compute Plane of Array (POA) components
    poa_components = irradiance.get_total_irradiance(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        solar_zenith=solar_zenith,
        solar_azimuth=solar_azimuth,
        dni=dni,
        ghi=df["ghi"],
        dhi=df["diffuse_rad"],
        model="isotropic",
        albedo=0.2,
    )

    return poa_components["poa_global"]


def compute_pv_output(
    df: pd.DataFrame,
    lat: float,
    lon: float,
    panel_area_m2: float,
    panel_efficiency: float,
    system_derate: float = SYSTEM_DERATE,
    surface_tilt: float = PANEL_TILT_DEG,
    surface_azimuth: float | None = PANEL_AZIMUTH_DEG,
) -> pd.DataFrame:
    """Estimate PV power output for every timestamp in `df`.

    Model (documented, simplified - see README for assumptions):
      1. Plane of Array (POA) Irradiance calculation (via pvlib transposition)
      2. Ideal DC power at STC efficiency:  P_dc_ideal = POA * area * eff
      3. Cell temperature (NOCT approximation):
             T_cell = T_amb + (NOCT - 20) / 800 * POA
      4. Temperature de-rate (typical c-Si coefficient):
             f_temp = 1 + coeff * (T_cell - 25)
      5. AC output after system losses (inverter, wiring, soiling, mismatch):
             P_ac = P_dc_ideal * f_temp * SYSTEM_DERATE

    This is a weather-model-based ESTIMATE, not a measurement from real
    panel/inverter telemetry. It is intended for comparative KPI analysis
    across locations, not as a substitute for on-site monitoring data.
    """
    out = df.copy()

    # Transpose horizontal irradiance to Plane of Array (POA)
    if "direct_rad" in out.columns and "diffuse_rad" in out.columns:
        out["poa_global"] = calculate_poa_irradiance(out, lat, lon, surface_tilt, surface_azimuth)
    else:
        # Fallback to GHI if direct/diffuse columns are missing
        out["poa_global"] = out["ghi"]

    out["p_dc_ideal_w"] = out["poa_global"] * panel_area_m2 * panel_efficiency

    out["cell_temp_c"] = out["temp_c"] + (NOCT_C - 20) / 800 * out["poa_global"]
    out["temp_derate"] = 1 + TEMP_COEFF_PMAX_PER_C * (out["cell_temp_c"] - STC_CELL_TEMP_C)
    out["temp_derate"] = out["temp_derate"].clip(lower=0)

    out["p_ac_w"] = out["p_dc_ideal_w"] * out["temp_derate"] * system_derate
    out["p_ac_w"] = out["p_ac_w"].clip(lower=0)

    return out


def _integrate_wh(series_w: pd.Series, datetime_index: pd.Series) -> float:
    """Trapezoidal integration of a power series (W) over time -> Wh."""
    if len(series_w) < 2:
        return 0.0
    t_hours = (datetime_index - datetime_index.iloc[0]).dt.total_seconds() / 3600.0
    trapezoid_fn = getattr(np, "trapezoid", None) or np.trapz
    return float(trapezoid_fn(series_w.to_numpy(), t_hours.to_numpy()))


def calculate_kpis(
    df: pd.DataFrame,
    lat: float,
    lon: float,
    panel_area_m2: float,
    panel_efficiency: float,
    system_derate: float = SYSTEM_DERATE,
    co2_factor: float = CO2_FACTOR_KG_PER_KWH,
    tariff: float = ELECTRICITY_TARIFF_RP_PER_KWH,
    surface_tilt: float = PANEL_TILT_DEG,
    surface_azimuth: float | None = PANEL_AZIMUTH_DEG,
) -> dict[str, float]:
    """Calculate the KPI set reported in the study, for one location.

    total_energy_kwh, peak_power_w, avg_daytime_power_w,
    performance_ratio_pct (true weather-normalized PR),
    capacity_factor_vs_nameplate_pct (naive peak/nameplate ratio, kept for
    comparability with the original study), co2_saved_kg, cost_saving_rp.
    """
    if df.empty:
        return {
            "total_energy_kwh": 0.0,
            "peak_power_w": 0.0,
            "avg_daytime_power_w": 0.0,
            "performance_ratio_pct": 0.0,
            "capacity_factor_vs_nameplate_pct": 0.0,
            "co2_saved_kg": 0.0,
            "cost_saving_rp": 0.0,
            "avg_ghi_kwh_m2_day": 0.0,
        }

    pv = compute_pv_output(
        df,
        lat,
        lon,
        panel_area_m2=panel_area_m2,
        panel_efficiency=panel_efficiency,
        system_derate=system_derate,
        surface_tilt=surface_tilt,
        surface_azimuth=surface_azimuth,
    )

    energy_actual_wh = _integrate_wh(pv["p_ac_w"], pv["datetime"])
    energy_ideal_wh = _integrate_wh(pv["p_dc_ideal_w"], pv["datetime"])  # STC-equivalent, no derates

    total_energy_kwh = energy_actual_wh / 1000.0
    peak_power_w = float(pv["p_ac_w"].max())

    daylight = pv[pv["ghi"] > 20]  # ignore near-zero-irradiance night hours
    avg_daytime_power_w = float(daylight["p_ac_w"].mean()) if not daylight.empty else 0.0

    # True performance ratio: actual (loss-inclusive) energy vs. the energy
    # the same panel would yield at the SAME measured irradiance with zero
    # system losses. This isolates the combined temperature + system-loss
    # effect, unlike a naive peak/nameplate ratio.
    performance_ratio_pct = float(energy_actual_wh / energy_ideal_wh * 100) if energy_ideal_wh > 0 else 0.0

    panel_capacity_wp = panel_area_m2 * STC_IRRADIANCE_W_M2 * panel_efficiency
    capacity_factor_vs_nameplate_pct = float(peak_power_w / panel_capacity_wp * 100) if panel_capacity_wp > 0.0 else 0.0

    co2_saved_kg = total_energy_kwh * co2_factor
    cost_saving_rp = total_energy_kwh * tariff

    n_days = max((pv["datetime"].max() - pv["datetime"].min()).total_seconds() / 86400.0, 1e-9)
    avg_ghi_kwh_m2_day = float(pv["ghi"].mean() * 24 / 1000.0)  # rough daily-average irradiance proxy

    return {
        "total_energy_kwh": total_energy_kwh,
        "peak_power_w": peak_power_w,
        "avg_daytime_power_w": avg_daytime_power_w,
        "performance_ratio_pct": performance_ratio_pct,
        "capacity_factor_vs_nameplate_pct": capacity_factor_vs_nameplate_pct,
        "co2_saved_kg": co2_saved_kg,
        "cost_saving_rp": cost_saving_rp,
        "avg_ghi_kwh_m2_day": avg_ghi_kwh_m2_day,
        "n_days": n_days,
    }


def calculate_all_locations(
    dataframes: dict[str, pd.DataFrame],
    panel_area_m2: float,
    panel_efficiency: float,
    system_derate: float = SYSTEM_DERATE,
    co2_factor: float = CO2_FACTOR_KG_PER_KWH,
    tariff: float = ELECTRICITY_TARIFF_RP_PER_KWH,
    surface_tilt: float = PANEL_TILT_DEG,
    surface_azimuth: float | None = PANEL_AZIMUTH_DEG,
) -> pd.DataFrame:
    """Run calculate_kpis for every location and return a comparison table."""
    rows = []
    for location, df in dataframes.items():
        meta = LOCATIONS.get(location, {"lat": -6.2088, "lon": 106.8456})
        lat_val = meta["lat"]
        lon_val = meta["lon"]
        if location.startswith("Custom ("):
            try:
                parts = location.replace("Custom (", "").replace(")", "").split(",")
                lat_val = float(parts[0])
                lon_val = float(parts[1])
            except Exception:
                pass
        kpis = calculate_kpis(
            df,
            lat=lat_val,
            lon=lon_val,
            panel_area_m2=panel_area_m2,
            panel_efficiency=panel_efficiency,
            system_derate=system_derate,
            co2_factor=co2_factor,
            tariff=tariff,
            surface_tilt=surface_tilt,
            surface_azimuth=surface_azimuth,
        )
        kpis["location"] = location
        rows.append(kpis)
    cols = [
        "location",
        "total_energy_kwh",
        "peak_power_w",
        "avg_daytime_power_w",
        "performance_ratio_pct",
        "capacity_factor_vs_nameplate_pct",
        "co2_saved_kg",
        "cost_saving_rp",
        "avg_ghi_kwh_m2_day",
    ]
    return pd.DataFrame(rows)[cols]
