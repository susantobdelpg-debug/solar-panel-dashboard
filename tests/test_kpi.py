import sys
import os
import pytest
import pandas as pd
import numpy as np

# Ensure workspace is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.kpi import compute_pv_output, calculate_kpis

def test_kpi_calculations_with_synthetic_data():
    # Define a simple 3-hour daytime profile (GHI: 500, 1000, 500 W/m2) at 25 deg C ambient
    datetimes = pd.to_datetime(["2026-07-14 11:00:00", "2026-07-14 12:00:00", "2026-07-14 13:00:00"])
    
    # We do NOT include direct_rad or diffuse_rad columns so compute_pv_output falls back to GHI
    df = pd.DataFrame({
        "datetime": datetimes,
        "ghi": [500.0, 1000.0, 500.0],
        "temp_c": [25.0, 25.0, 25.0]
    })
    
    # 1. Run compute_pv_output
    pv = compute_pv_output(df, lat=-6.2088, lon=106.8456, panel_area_m2=2.0, panel_efficiency=0.20)
    
    # --- Expected values calculation ---
    # Constants from config:
    # PANEL_AREA_M2 = 2.0
    # PANEL_EFFICIENCY = 0.20
    # SYSTEM_DERATE = 0.86
    # NOCT_C = 45.0
    # TEMP_COEFF_PMAX_PER_C = -0.004
    # STC_CELL_TEMP_C = 25.0
    
    # Hour 1 (11:00): GHI = 500 W/m2
    # P_dc_ideal = 500 * 2 * 0.2 = 200 W
    # T_cell = 25 + (45 - 20)/800 * 500 = 25 + 15.625 = 40.625 C
    # f_temp = 1 + (-0.004) * (40.625 - 25) = 1 - 0.0625 = 0.9375
    # P_ac = 200 * 0.9375 * 0.86 = 161.25 W
    assert pytest.approx(pv.loc[0, "p_dc_ideal_w"]) == 200.0
    assert pytest.approx(pv.loc[0, "cell_temp_c"]) == 40.625
    assert pytest.approx(pv.loc[0, "temp_derate"]) == 0.9375
    assert pytest.approx(pv.loc[0, "p_ac_w"]) == 161.25
    
    # Hour 2 (12:00): GHI = 1000 W/m2
    # P_dc_ideal = 1000 * 2 * 0.2 = 400 W
    # T_cell = 25 + (45 - 20)/800 * 1000 = 25 + 31.25 = 56.25 C
    # f_temp = 1 + (-0.004) * (56.25 - 25) = 1 - 0.125 = 0.875
    # P_ac = 400 * 0.875 * 0.86 = 301.0 W
    assert pytest.approx(pv.loc[1, "p_dc_ideal_w"]) == 400.0
    assert pytest.approx(pv.loc[1, "cell_temp_c"]) == 56.25
    assert pytest.approx(pv.loc[1, "temp_derate"]) == 0.875
    assert pytest.approx(pv.loc[1, "p_ac_w"]) == 301.0
    
    # Hour 3 (13:00): GHI = 500 W/m2
    # P_dc_ideal = 200 W, P_ac = 161.25 W
    assert pytest.approx(pv.loc[2, "p_dc_ideal_w"]) == 200.0
    assert pytest.approx(pv.loc[2, "p_ac_w"]) == 161.25
    
    # 2. Run calculate_kpis
    kpis = calculate_kpis(df, lat=-6.2088, lon=106.8456, panel_area_m2=2.0, panel_efficiency=0.20)
    
    # --- Expected integrated values ---
    # Integration over time (dt = 1 hour):
    # energy_actual_wh = (161.25 + 301.0)/2 * 1 + (301.0 + 161.25)/2 * 1 = 462.25 Wh
    # total_energy_kwh = 462.25 / 1000 = 0.46225 kWh
    assert pytest.approx(kpis["total_energy_kwh"]) == 0.46225
    
    # peak_power_w = max(P_ac) = 301.0 W
    assert pytest.approx(kpis["peak_power_w"]) == 301.0
    
    # energy_ideal_wh = (200 + 400)/2 * 1 + (400 + 200)/2 * 1 = 600.0 Wh
    # PR = energy_actual_wh / energy_ideal_wh = 462.25 / 600.0 = 0.7704166... (77.04166...%)
    assert pytest.approx(kpis["performance_ratio_pct"]) == 462.25 / 600.0 * 100.0
