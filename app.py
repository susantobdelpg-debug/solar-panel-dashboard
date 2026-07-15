import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import folium
from streamlit_folium import st_folium

from utils.config import (
    APP_TITLE,
    CO2_FACTOR_KG_PER_KWH,
    ELECTRICITY_TARIFF_RP_PER_KWH,
    FORECAST_DAYS,
    LOCATIONS,
    PANEL_AREA_M2,
    PANEL_AZIMUTH_DEG,
    PANEL_CAPACITY_WP,
    PANEL_EFFICIENCY,
    PANEL_TILT_DEG,
    PAST_DAYS,
    SYSTEM_DERATE,
)
from utils.kpi import calculate_all_locations, calculate_kpis, compute_pv_output
from utils.open_meteo_api import (
    fetch_solar_weather,
    generate_mock_weather,
    weather_to_dataframe,
)

def get_location_name(lat: float, lon: float) -> str:
    for name, meta in LOCATIONS.items():
        if abs(meta["lat"] - lat) < 0.001 and abs(meta["lon"] - lon) < 0.001:
            return name
    return f"Custom ({lat:.2f}, {lon:.2f})"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="\u2600\ufe0f",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        .custom-hero {
            background-color: #6b7280;
            border-radius: 12px;
            padding: 24px 32px;
            margin-bottom: 1.5rem;
            color: #ffffff;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .custom-hero h1 {
            color: #ff9800;
            font-size: 2.2rem;
            font-weight: 700;
            margin: 0 0 8px 0;
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }
        .custom-hero p {
            color: #cbd5e1;
            font-size: 0.95rem;
            margin: 0;
        }
        .section-title { color: #0f172a; font-size: 1.15rem; font-weight: 700; margin: 1.1rem 0 0.35rem; }
        .assumption-note {
            background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px;
            padding: 0.75rem 1rem; font-size: 0.85rem; color: #92400e; margin: 0.5rem 0 1rem;
        }
        .mock-banner {
            background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px;
            padding: 0.75rem 1rem; font-size: 0.9rem; color: #991b1b; margin-bottom: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_header(location_name: str, start_str: str, end_str: str) -> None:
    st.markdown(
        f"""
        <div class="custom-hero">
            <h1>☀️ SOLAR PANEL DASHBOARD - {location_name}</h1>
            <p>Analyzing real-time and historical solar energy potential (30 days past + 7 days forecast). Filtered range: {start_str} to {end_str}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_cards(
    kpis: dict,
    lat: float,
    panel_capacity_wp: float,
    co2_factor: float,
    tariff: float,
    energy_gain_kwh: float,
    energy_gain_pct: float,
    selected_tilt: float,
    selected_azimuth: float,
    panel_area_m2: float,
    panel_efficiency: float,
) -> None:
    col1, col2, col3, col4 = st.columns(4)
    
    col1.markdown(
        f"""
        <div style="background-color: #7b8895; border-top: 4px solid #f59e0b; border-radius: 12px; padding: 18px; position: relative; box-shadow: 0 4px 6px rgba(0,0,0,0.1); min-height: 155px;">
            <div style="position: absolute; top: 12px; right: 16px; font-size: 2.2rem;">⚡</div>
            <div style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: #cbd5e1; letter-spacing: 0.05em; margin-bottom: 12px;">Total Energy Yield</div>
            <div style="font-size: 1.85rem; font-weight: 700; color: #ffffff; margin-bottom: 8px; line-height: 1.1;">{kpis['total_energy_kwh']:.2f} kWh</div>
            <div style="font-size: 0.75rem; color: #cbd5e1; font-weight: 500; line-height: 1.35;">
                Flat (tilt 0°): {kpis['total_energy_kwh'] - energy_gain_kwh:.2f} kWh <br/>
                Gain: <span style="color: {'#4ade80' if energy_gain_kwh >= 0 else '#f87171'}; font-weight: 700;">{'+' if energy_gain_kwh >= 0 else ''}{energy_gain_kwh:.2f} kWh ({'+' if energy_gain_pct >= 0 else ''}{energy_gain_pct:.1f}%)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    col2.markdown(
        f"""
        <div style="background-color: #7b8895; border-top: 4px solid #06b6d4; border-radius: 12px; padding: 18px; position: relative; box-shadow: 0 4px 6px rgba(0,0,0,0.1); min-height: 155px;">
            <div style="position: absolute; top: 12px; right: 16px; font-size: 2.2rem;">🔥</div>
            <div style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: #cbd5e1; letter-spacing: 0.05em; margin-bottom: 12px;">Peak Power Output</div>
            <div style="font-size: 1.85rem; font-weight: 700; color: #ffffff; margin-bottom: 12px; line-height: 1.1;">{kpis['peak_power_w']:.1f} W</div>
            <div style="font-size: 0.75rem; color: #cbd5e1; font-weight: 500;">Daylight Avg: {kpis['avg_daytime_power_w']:.1f} W</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    col3.markdown(
        f"""
        <div style="background-color: #7b8895; border-top: 4px solid #10b981; border-radius: 12px; padding: 18px; position: relative; box-shadow: 0 4px 6px rgba(0,0,0,0.1); min-height: 155px;">
            <div style="position: absolute; top: 12px; right: 16px; font-size: 2.2rem;">🌱</div>
            <div style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: #cbd5e1; letter-spacing: 0.05em; margin-bottom: 12px;">CO₂ Saved</div>
            <div style="font-size: 1.85rem; font-weight: 700; color: #ffffff; margin-bottom: 12px; line-height: 1.1;">{kpis['co2_saved_kg']:.2f} kg</div>
            <div style="font-size: 0.75rem; color: #cbd5e1; font-weight: 500;">Equivalent to clean energy production</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    savings_formatted = f"Rp {kpis['cost_saving_rp']:,.0f}".replace(",", ".")
    col4.markdown(
        f"""
        <div style="background-color: #7b8895; border-top: 4px solid #ec4899; border-radius: 12px; padding: 18px; position: relative; box-shadow: 0 4px 6px rgba(0,0,0,0.1); min-height: 155px;">
            <div style="position: absolute; top: 12px; right: 16px; font-size: 2.2rem;">💰</div>
            <div style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: #cbd5e1; letter-spacing: 0.05em; margin-bottom: 12px;">Financial Savings</div>
            <div style="font-size: 1.85rem; font-weight: 700; color: #ffffff; margin-bottom: 12px; line-height: 1.1;">{savings_formatted}</div>
            <div style="font-size: 0.75rem; color: #cbd5e1; font-weight: 500;">Saved electricity expenses</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    tilt = selected_tilt
    azimuth = selected_azimuth
    
    # Direction labels for azimuth
    dirs = [
        (0.0, 22.5, "Utara"), (22.5, 67.5, "Timur Laut"), (67.5, 112.5, "Timur"),
        (112.5, 157.5, "Tenggara"), (157.5, 202.5, "Selatan"), (202.5, 247.5, "Barat Daya"),
        (247.5, 292.5, "Barat"), (292.5, 337.5, "Barat Laut"), (337.5, 360.1, "Utara")
    ]
    direction_text = "Utara"
    for low, high, dname in dirs:
        if low <= azimuth < high:
            direction_text = dname
            break
    direction_label = f"{azimuth:.0f}° (Menghadap {direction_text})"

    st.markdown(
        f"""
        <div class="assumption-note" style="margin-top: 20px;">
        <b>Asumsi model:</b> orientasi panel (tilt {tilt:.1f}°, azimuth {direction_label}),
        temperatur sel (NOCT {45:.0f}°C), koefisien suhu daya −0.4%/°C,
        de-rate sistem (inverter+kabel+soiling+mismatch) {SYSTEM_DERATE*100:.0f}%,
        faktor emisi grid {co2_factor:.2f} kg CO₂/kWh,
        tarif listrik Rp {tariff:,.2f}/kWh.
        Kapasitas Nameplate Dinamis: {panel_capacity_wp:.0f} Wp (Luas: {panel_area_m2:.2f} m², Efisiensi: {panel_efficiency*100:.1f}%). Performance Ratio: {kpis['performance_ratio_pct']:.1f}%.
        Semua nilai ini dapat diubah di panel sidebar interaktif.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_charts(pv_df: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">Tren Radiasi, Cuaca & Output Daya</div>', unsafe_allow_html=True)

    fig_rad = go.Figure()
    fig_rad.add_trace(go.Scatter(
        x=pv_df["datetime"], y=pv_df["ghi"], name="GHI (Horizontal, W/m\u00b2)",
        line=dict(color="#f59e0b", dash="dot"), yaxis="y1",
    ))
    fig_rad.add_trace(go.Scatter(
        x=pv_df["datetime"], y=pv_df["poa_global"], name="POA (Pada Panel, W/m\u00b2)",
        line=dict(color="#ea580c"), yaxis="y1",
    ))
    fig_rad.add_trace(go.Scatter(
        x=pv_df["datetime"], y=pv_df["cloud_cover_pct"], name="Tutupan Awan (%)",
        line=dict(color="#64748b", dash="dash"), yaxis="y2",
    ))
    fig_rad.update_layout(
        title=dict(
            text="Radiasi Matahari (GHI vs POA) vs Tutupan Awan",
            y=0.95,
            x=0,
            xanchor="left",
            yanchor="top"
        ),
        height=380,
        margin=dict(l=10, r=10, t=80, b=10),
        yaxis=dict(title="Radiasi (W/m\u00b2)"),
        yaxis2=dict(title="Tutupan Awan (%)", overlaying="y", side="right", range=[0, 100]),
        legend=dict(
            orientation="h",
            y=1.05,
            yanchor="bottom",
            x=0,
            xanchor="left"
        ),
    )
    st.plotly_chart(fig_rad, use_container_width=True)

    left, right = st.columns(2)
    power_fig = px.line(
        pv_df, x="datetime", y="p_ac_w",
        labels={"datetime": "Waktu", "p_ac_w": "Daya AC (W)"},
        title="Hourly Power Output",
    )
    power_fig.update_traces(line_color="#ea580c")
    power_fig.update_layout(height=340, margin=dict(l=10, r=10, t=48, b=10))
    left.plotly_chart(power_fig, use_container_width=True)

    energy_hourly = pv_df["p_ac_w"] / 1000.0  # approx kWh per hourly step
    energy_fig = px.bar(
        pv_df.assign(energy_kwh=energy_hourly), x="datetime", y="energy_kwh",
        labels={"datetime": "Waktu", "energy_kwh": "Energi (kWh)"},
        title="Hourly Energy Generated",
    )
    energy_fig.update_traces(marker_color="#2563eb")
    energy_fig.update_layout(height=340, margin=dict(l=10, r=10, t=48, b=10))
    right.plotly_chart(energy_fig, use_container_width=True)


def render_comparison(all_locations_df: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">Perbandingan Antar Lokasi</div>', unsafe_allow_html=True)
    st.caption("Dihitung dengan model & asumsi yang SAMA untuk semua lokasi pada rentang waktu yang sama.")

    display_df = all_locations_df.copy()
    display_df = display_df.rename(columns={
        "location": "Lokasi", "total_energy_kwh": "Total Energi (kWh)",
        "peak_power_w": "Daya Puncak (W)", "avg_daytime_power_w": "Rata-rata Daya Siang (W)",
        "performance_ratio_pct": "PR Sebenarnya (%)",
        "capacity_factor_vs_nameplate_pct": "Rasio ke Nameplate (%)",
        "co2_saved_kg": "CO\u2082 Saved (kg)", "cost_saving_rp": "Penghematan (Rp)",
        "avg_ghi_kwh_m2_day": "Rata-rata Iradiasi (kWh/m\u00b2/hari)",
    })
    st.dataframe(
        display_df.style.format({
            "Total Energi (kWh)": "{:.2f}", "Daya Puncak (W)": "{:.1f}",
            "Rata-rata Daya Siang (W)": "{:.1f}", "PR Sebenarnya (%)": "{:.1f}",
            "Rasio ke Nameplate (%)": "{:.1f}", "CO\u2082 Saved (kg)": "{:.2f}",
            "Penghematan (Rp)": "Rp {:,.0f}", "Rata-rata Iradiasi (kWh/m\u00b2/hari)": "{:.2f}",
        }),
        use_container_width=True, hide_index=True,
    )

    bar_fig = px.bar(
        all_locations_df.sort_values("total_energy_kwh", ascending=False),
        x="location", y="total_energy_kwh",
        labels={"location": "Lokasi", "total_energy_kwh": "Total Energi (kWh)"},
        title="Total Energi per Lokasi", color="total_energy_kwh",
        color_continuous_scale=["#fef3c7", "#f59e0b", "#b45309"],
    )
    bar_fig.update_layout(height=360, margin=dict(l=10, r=10, t=48, b=10), showlegend=False, coloraxis_showscale=False)
    st.plotly_chart(bar_fig, use_container_width=True)


def load_location_data(lat: float, lon: float) -> tuple[pd.DataFrame, str, bool]:
    """Return (dataframe, timezone_str, used_mock_data)."""
    try:
        payload = fetch_solar_weather(lat, lon)
        df = weather_to_dataframe(payload)
        if df.empty:
            raise ValueError("Respons Open-Meteo kosong")
        tz = payload.get("timezone", "Asia/Jakarta")
        return df, tz, False
    except Exception:
        tz = "Asia/Jakarta" if lon < 115.0 else "Asia/Makassar"
        return generate_mock_weather(), tz, True


# Initialize session state for manual and map selection coordinates if not present
if "selected_lat" not in st.session_state:
    st.session_state.selected_lat = -6.2088  # Jakarta default
if "selected_lon" not in st.session_state:
    st.session_state.selected_lon = 106.8456

with st.sidebar:
    st.subheader("Configuration")
    
    # 3 Location Modes Selection
    location_mode = st.radio(
        "Mode Pilihan Lokasi",
        ["Kota preset", "Input koordinat manual", "Pilih di peta"],
        index=0
    )
    
    if location_mode == "Kota preset":
        selected_location = st.selectbox("Select City", list(LOCATIONS.keys()))
        lat = LOCATIONS[selected_location]["lat"]
        lon = LOCATIONS[selected_location]["lon"]
        location_name = selected_location
    elif location_mode == "Input koordinat manual":
        lat = st.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=st.session_state.selected_lat,
            step=0.0001,
            format="%.4f",
            help="Masukkan Latitude lokasi antara -90 dan 90"
        )
        lon = st.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=st.session_state.selected_lon,
            step=0.0001,
            format="%.4f",
            help="Masukkan Longitude lokasi antara -180 dan 180"
        )
        # Update session state for persistence
        st.session_state.selected_lat = lat
        st.session_state.selected_lon = lon
        location_name = get_location_name(lat, lon)
    else:  # Pilih di peta
        lat = st.session_state.selected_lat
        lon = st.session_state.selected_lon
        location_name = get_location_name(lat, lon)
        st.info("📍 Silakan klik pada peta interaktif di halaman utama untuk menaruh marker lokasi.")
        
    refresh_clicked = st.button("Refresh data", type="primary", use_container_width=True)

if refresh_clicked:
    fetch_solar_weather.clear()

raw_df, timezone_str, used_mock = load_location_data(lat, lon)

# Reactively update panel tilt/azimuth defaults when latitude changes
if "last_lat" not in st.session_state:
    st.session_state.last_lat = lat
    st.session_state.panel_tilt = float(abs(lat))
    st.session_state.panel_azimuth = 0.0 if lat < 0.0 else 180.0

if abs(st.session_state.last_lat - lat) > 0.0001:
    st.session_state.last_lat = lat
    st.session_state.panel_tilt = float(abs(lat))
    st.session_state.panel_azimuth = 0.0 if lat < 0.0 else 180.0

with st.sidebar:
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 6px; margin-top: 16px; margin-bottom: 8px;">
            <span style="font-size: 1.25rem;">📍</span>
            <span style="font-weight: 600; font-size: 1.1rem; color: #1e293b;">Location Details</span>
        </div>
        <div style="background-color: #e2ecf8; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <p style="margin: 0 0 10px 0; font-size: 0.95rem; color: #1e3a8a;"><b>City:</b> <span style="color: #0f172a;">{location_name}</span></p>
            <p style="margin: 0 0 10px 0; font-size: 0.95rem; color: #1e3a8a;"><b>Latitude:</b> <span style="color: #0f172a;">{lat:.4f}</span></p>
            <p style="margin: 0 0 10px 0; font-size: 0.95rem; color: #1e3a8a;"><b>Longitude:</b> <span style="color: #0f172a;">{lon:.4f}</span></p>
            <p style="margin: 0; font-size: 0.95rem; color: #1e3a8a;"><b>Timezone:</b> <span style="color: #0f172a;">{timezone_str}</span></p>
        </div>
        
        <div style="display: flex; align-items: center; gap: 6px; margin-top: 16px; margin-bottom: 8px;">
            <span style="font-size: 1.25rem;">⚡</span>
            <span style="font-weight: 600; font-size: 1.1rem; color: #1e293b;">Solar Panel Specs</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    panel_eff_pct = st.slider(
        "Panel Efficiency (%)",
        min_value=10.0,
        max_value=30.0,
        value=20.0,
        step=0.5,
        help="Efisiensi konversi panel surya pada Standard Test Conditions (STC). Efisiensi di atas 23% tidak umum untuk panel konsumen standar (residensial)."
    )
    panel_eff = panel_eff_pct / 100.0
    
    panel_area = st.number_input(
        "Panel Area (m²)",
        min_value=0.1,
        value=2.0,
        step=0.1,
        format="%.2f",
        help="Luas permukaan panel surya dalam meter persegi"
    )
    if panel_area > 1000.0:
        st.warning("⚠️ Skala luas panel di atas 1000 m² sudah melampaui skala residensial standar.")
    panel_tilt = st.slider(
        "Kemiringan Panel (Tilt)",
        min_value=0.0,
        max_value=90.0,
        value=st.session_state.panel_tilt,
        step=1.0,
        help="Sudut kemiringan panel surya terhadap permukaan horizontal"
    )
    panel_azimuth = st.slider(
        "Arah Hadap Panel (Azimuth)",
        min_value=0.0,
        max_value=360.0,
        value=st.session_state.panel_azimuth,
        step=5.0,
        help="Arah orientasi kompas (0/360=Utara, 90=Timur, 180=Selatan, 270=Barat)"
    )
    st.session_state.panel_tilt = panel_tilt
    st.session_state.panel_azimuth = panel_azimuth
    
    dirs = [
        (0.0, 22.5, "Utara 🧭"), (22.5, 67.5, "Timur Laut 🧭"), (67.5, 112.5, "Timur 🧭"),
        (112.5, 157.5, "Tenggara 🧭"), (157.5, 202.5, "Selatan 🧭"), (202.5, 247.5, "Barat Daya 🧭"),
        (247.5, 292.5, "Barat 🧭"), (292.5, 337.5, "Barat Laut 🧭"), (337.5, 360.1, "Utara 🧭")
    ]
    direction_text = "Utara 🧭"
    for low, high, dname in dirs:
        if low <= panel_azimuth < high:
            direction_text = dname
            break
    st.caption(f"Arah Hadap Aktif: **{direction_text} ({panel_azimuth:.0f}°)**")
    
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 6px; margin-top: 16px; margin-bottom: 8px;">
            <span style="font-size: 1.25rem;">💰</span>
            <span style="font-weight: 600; font-size: 1.1rem; color: #1e293b;">Economics & Ecology</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    co2_savings_factor = st.number_input(
        "CO2 Savings Factor (kg/kWh)",
        min_value=0.0,
        max_value=2.0,
        value=float(CO2_FACTOR_KG_PER_KWH),
        step=0.01,
        format="%.2f",
        help="Faktor emisi grid untuk konversi energi bersih menjadi reduksi emisi karbon"
    )
    elec_price = st.number_input(
        "Electricity Price (IDR/kWh)",
        min_value=0,
        max_value=10000,
        value=1500,
        step=50,
        help="Tarif listrik retail PLN per kWh"
    )
    
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 6px; margin-top: 16px; margin-bottom: 8px;">
            <span style="font-size: 1.25rem;">📅</span>
            <span style="font-weight: 600; font-size: 1.1rem; color: #1e293b;">Date Range Filter</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    min_date = raw_df["datetime"].min().date()
    max_date = raw_df["datetime"].max().date()
    selected_dates = st.date_input(
        "Select Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        help="Pilih rentang tanggal analisis data"
    )
    
    show_comparison = st.checkbox("Tampilkan perbandingan semua lokasi", value=False)
    st.caption(f"Data di-cache selama 1 jam. Rentang: {PAST_DAYS} hari historis + {FORECAST_DAYS} hari prakiraan.")
    st.divider()
    st.caption("Sumber: Open-Meteo Forecast API (shortwave_radiation, temperature_2m, cloud_cover).")

if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    filtered_df = raw_df[(raw_df["datetime"] >= start_dt) & (raw_df["datetime"] <= end_dt)]
    start_str = start_date.strftime("%B %d, %Y")
    end_str = end_date.strftime("%B %d, %Y")
else:
    filtered_df = raw_df
    start_str = min_date.strftime("%B %d, %Y")
    end_str = max_date.strftime("%B %d, %Y")

render_header(location_name.upper(), start_str, end_str)

# Map Selection Mode Main Page Widget
if location_mode == "Pilih di peta":
    st.markdown('<div class="section-title">🗺️ Pilih Koordinat dengan Mengklik Peta di Bawah Ini</div>', unsafe_allow_html=True)
    m = folium.Map(location=[st.session_state.selected_lat, st.session_state.selected_lon], zoom_start=5)
    folium.Marker(
        [st.session_state.selected_lat, st.session_state.selected_lon],
        popup=f"Terpilih: {st.session_state.selected_lat:.4f}, {st.session_state.selected_lon:.4f}"
    ).add_to(m)
    map_data = st_folium(m, height=350, use_container_width=True, key="dashboard_map_selector")
    if map_data and map_data.get("last_clicked"):
        click_lat = map_data["last_clicked"]["lat"]
        click_lon = map_data["last_clicked"]["lng"]
        if abs(st.session_state.selected_lat - click_lat) > 0.0001 or abs(st.session_state.selected_lon - click_lon) > 0.0001:
            st.session_state.selected_lat = click_lat
            st.session_state.selected_lon = click_lon
            st.rerun()

if used_mock:
    st.markdown(
        '<div class="mock-banner">\u26a0\ufe0f Tidak dapat menjangkau Open-Meteo API - menampilkan '
        '<b>data simulasi</b> agar dashboard tetap dapat didemokan. Angka di bawah ini BUKAN data cuaca nyata. '
        'Jalankan aplikasi dengan akses internet ke api.open-meteo.com untuk data aktual.</div>',
        unsafe_allow_html=True,
    )

pv_df = compute_pv_output(
    filtered_df,
    lat=lat,
    lon=lon,
    panel_area_m2=panel_area,
    panel_efficiency=panel_eff,
    surface_tilt=panel_tilt,
    surface_azimuth=panel_azimuth,
)
kpis = calculate_kpis(
    filtered_df,
    lat=lat,
    lon=lon,
    panel_area_m2=panel_area,
    panel_efficiency=panel_eff,
    co2_factor=co2_savings_factor,
    tariff=elec_price,
    surface_tilt=panel_tilt,
    surface_azimuth=panel_azimuth,
)

# Calculate flat horizontal panel baseline (tilt=0)
kpis_baseline = calculate_kpis(
    filtered_df,
    lat=lat,
    lon=lon,
    panel_area_m2=panel_area,
    panel_efficiency=panel_eff,
    co2_factor=co2_savings_factor,
    tariff=elec_price,
    surface_tilt=0.0,
    surface_azimuth=0.0,
)
energy_gain_kwh = kpis["total_energy_kwh"] - kpis_baseline["total_energy_kwh"]
if kpis_baseline["total_energy_kwh"] > 0:
    energy_gain_pct = (energy_gain_kwh / kpis_baseline["total_energy_kwh"]) * 100
else:
    energy_gain_pct = 0.0

panel_capacity_val = panel_area * 1000.0 * panel_eff
render_kpi_cards(
    kpis,
    lat=lat,
    panel_capacity_wp=panel_capacity_val,
    co2_factor=co2_savings_factor,
    tariff=elec_price,
    energy_gain_kwh=energy_gain_kwh,
    energy_gain_pct=energy_gain_pct,
    selected_tilt=panel_tilt,
    selected_azimuth=panel_azimuth,
    panel_area_m2=panel_area,
    panel_efficiency=panel_eff,
)

tab1, tab2 = st.tabs(["📊 Interactive Visualizations", "📋 Detailed Data Table"])

with tab1:
    render_charts(pv_df)

with tab2:
    st.markdown('<div class="section-title">Data Mentah</div>', unsafe_allow_html=True)
    display_columns = ["datetime", "ghi", "poa_global", "temp_c", "cloud_cover_pct", "p_dc_ideal_w", "cell_temp_c", "p_ac_w"]
    st.dataframe(
        pv_df[display_columns],
        use_container_width=True, hide_index=True,
        column_config={
            "datetime": st.column_config.DatetimeColumn("Waktu"),
            "ghi": st.column_config.NumberColumn("Radiasi GHI (W/m\u00b2)", format="%.1f"),
            "poa_global": st.column_config.NumberColumn("Radiasi POA (W/m\u00b2)", format="%.1f"),
            "temp_c": st.column_config.NumberColumn("Suhu (\u00b0C)", format="%.1f"),
            "cloud_cover_pct": st.column_config.NumberColumn("Tutupan Awan (%)", format="%.1f"),
            "p_dc_ideal_w": st.column_config.NumberColumn("P DC Ideal (W)", format="%.1f"),
            "cell_temp_c": st.column_config.NumberColumn("Suhu Sel (\u00b0C)", format="%.1f"),
            "p_ac_w": st.column_config.NumberColumn("P AC Aktual (W)", format="%.1f"),
        },
    )

if show_comparison:
    st.divider()
    with st.spinner("Menghitung KPI untuk semua lokasi..."):
        all_dfs = {}
        any_mock = False
        for name, meta in LOCATIONS.items():
            df_loc, tz_loc, mock_flag = load_location_data(meta["lat"], meta["lon"])
            
            # Apply date range filtering to other locations
            if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
                start_date, end_date = selected_dates
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date) + pd.Timedelta(hours=23, minutes=59, seconds=59)
                df_loc_filtered = df_loc[(df_loc["datetime"] >= start_dt) & (df_loc["datetime"] <= end_dt)]
            else:
                df_loc_filtered = df_loc
                
            all_dfs[name] = df_loc_filtered
            any_mock = any_mock or mock_flag
            
        # Add the active custom location to comparison if it is not a preset
        if location_name not in LOCATIONS:
            all_dfs[location_name] = filtered_df
            
        comparison_df = calculate_all_locations(
            all_dfs,
            panel_area_m2=panel_area,
            panel_efficiency=panel_eff,
            co2_factor=co2_savings_factor,
            tariff=elec_price,
            surface_tilt=panel_tilt,
            surface_azimuth=panel_azimuth,
        )
    if any_mock:
        st.caption("\u26a0\ufe0f Sebagian lokasi memakai data simulasi (Open-Meteo tidak terjangkau).")
    render_comparison(comparison_df)
