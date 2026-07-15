"""Configuration and assumptions for the Solar PV KPI dashboard.

All engineering assumptions used for KPI calculations are centralized here so
they are easy to audit, cite in a report, and adjust as better local data
becomes available.
"""

APP_TITLE = "Dashboard KPI Sistem Panel Surya"

# --- Locations analyzed in the study -----------------------------------
# adm_note is just a human label; lat/lon drive the Open-Meteo query.
LOCATIONS = {
    "Jakarta": {"lat": -6.2088, "lon": 106.8456},
    "Bandung": {"lat": -6.9175, "lon": 107.6191},
    "Bali / Denpasar": {"lat": -8.6705, "lon": 115.2126},
    "Semarang": {"lat": -6.9667, "lon": 110.4167},
    "Medan": {"lat": 3.5952, "lon": 98.6722},
    "Balikpapan": {"lat": -1.2379, "lon": 116.8529},
}

# --- Panel specification (as stated in the study) -----------------------
PANEL_AREA_M2 = 2.0        # m^2
PANEL_EFFICIENCY = 0.20    # fraction, at Standard Test Conditions (STC)
STC_IRRADIANCE_W_M2 = 1000.0  # STC reference irradiance, W/m^2
PANEL_CAPACITY_WP = PANEL_AREA_M2 * STC_IRRADIANCE_W_M2 * PANEL_EFFICIENCY  # 400 Wp

# --- Panel Orientation (transposition defaults) ------------------------
# 15 degrees is standard for self-cleaning of rainwater runoff in tropical climates
PANEL_TILT_DEG = 15.0
# Facing equator dynamically (None) or specify degrees (0 = North, 180 = South)
PANEL_AZIMUTH_DEG = None

# --- Temperature derating (simple NOCT model) ----------------------------
# Cell temperature estimated with the NOCT approximation:
#   T_cell = T_ambient + (NOCT - 20) / 800 * G
# Power temperature coefficient for a typical crystalline-silicon module.
NOCT_C = 45.0                 # deg C, typical datasheet NOCT for c-Si modules
TEMP_COEFF_PMAX_PER_C = -0.004  # fraction per deg C above 25 C (typical c-Si)
STC_CELL_TEMP_C = 25.0

# --- System losses not captured by the temperature model -----------------
# Combined de-rate for inverter efficiency, wiring/mismatch losses, and
# soiling. This is a documented ASSUMPTION (typical residential PV system
# range is roughly 0.80-0.90); replace with a measured value if available.
SYSTEM_DERATE = 0.86

# --- Environmental & financial conversion factors -------------------------
# Indonesia grid emission factor (kg CO2 / kWh). This is an ASSUMPTION based
# on commonly cited Jawa-Bali interconnection system figures; verify against
# the latest official Kementerian ESDM / PLN grid emission factor before
# using in a publication.
CO2_FACTOR_KG_PER_KWH = 0.85

# PLN retail electricity tariff (Rp / kWh). ASSUMPTION - update with the
# tariff class actually relevant to the study (e.g. R1/900VA-RTM,
# R1/1300VA, etc.) and cite the PLN tariff schedule used.
ELECTRICITY_TARIFF_RP_PER_KWH = 1444.70

# --- Data window ----------------------------------------------------------
PAST_DAYS = 30      # historical days to pull from Open-Meteo
FORECAST_DAYS = 7   # forward-looking days to pull from Open-Meteo

# --- Open-Meteo endpoint ---------------------------------------------------
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_CACHE_SECONDS = 3600
