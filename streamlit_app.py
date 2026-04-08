import streamlit as st
import pandas as pd
import requests
import random
from datetime import datetime
import folium
from streamlit_folium import st_folium

# =========================
# CONFIG
# =========================
OPENWEATHER_API_KEY = "83381fd2dfb9760f22710f0a419897c0"
LAT = 13.7563
LON = 100.5018

st.set_page_config(page_title="AirCheck TH", layout="wide")

# =========================
# STYLE
# =========================
st.markdown("""
<style>
.big {font-size:28px; font-weight:bold;}
.good {color:green;}
.warn {color:orange;}
.bad {color:red;}
</style>
""", unsafe_allow_html=True)


# =========================
# API
# =========================
@st.cache_data(ttl=1800)
def get_openmeteo():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
        "forecast_days": 1,
        "timezone": "Asia/Bangkok"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


@st.cache_data(ttl=1800)
def get_air():
    url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={LAT}&lon={LON}&appid={OPENWEATHER_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


# =========================
# BUILD DATA
# =========================
def build_ref_df():
    om = get_openmeteo()
    air = get_air()

    if not om:
        return None

    hourly = om["hourly"]
    length = len(hourly["time"])

    # air base
    if air and "list" in air:
        comp = air["list"][0]["components"]
        base_no2 = comp.get("no2", 20)
        base_pm25 = comp.get("pm2_5", 15)
    else:
        base_no2, base_pm25 = 20, 15

    rows = []

    for i in range(length):
        factor = 0.8 + (i % 24) / 24

        rows.append({
            "time": pd.to_datetime(hourly["time"][i]),
            "Temp": hourly["temperature_2m"][i],
            "RH": hourly["relative_humidity_2m"][i],
            "WS": hourly["wind_speed_10m"][i],
            "WD": hourly["wind_direction_10m"][i],
            "NO2": base_no2 * factor,
            "PM2.5": base_pm25 * factor
        })

    return pd.DataFrame(rows)


# =========================
# STATUS
# =========================
def get_status(pm25):
    if pm25 < 25:
        return "ดี", "good"
    elif pm25 < 50:
        return "ปานกลาง", "warn"
    else:
        return "แย่", "bad"


# =========================
# UI
# =========================
st.title("🌫 AirCheck TH (Realistic Demo)")

ref_df = build_ref_df()

if ref_df is None:
    st.error("❌ โหลดข้อมูลไม่ได้")
    st.stop()

now = ref_df.iloc[0]

status_text, status_class = get_status(now["PM2.5"])

# ===== Top Info =====
col1, col2, col3 = st.columns(3)

col1.metric("🌡 Temp", f"{now['Temp']:.1f} °C")
col2.metric("💨 Wind", f"{now['WS']:.1f} m/s")
col3.metric("🌫 PM2.5", f"{now['PM2.5']:.1f}")

st.markdown(f"<div class='big {status_class}'>สถานะอากาศ: {status_text}</div>", unsafe_allow_html=True)

# =========================
# MAP
# =========================
st.subheader("🗺 แผนที่")

m = folium.Map(location=[LAT, LON], zoom_start=12)

# จุดโรงงาน
folium.Marker(
    [LAT, LON],
    tooltip="โรงงาน",
    icon=folium.Icon(color="red")
).add_to(m)

# ลูกศรลม (จำลอง)
wind_lat = LAT + (now["WS"] * 0.01)
wind_lon = LON + (now["WS"] * 0.01)

folium.PolyLine(
    locations=[[LAT, LON], [wind_lat, wind_lon]],
    color="blue"
).add_to(m)

st_folium(m, width=700)

# =========================
# CHART
# =========================
st.subheader("📊 กราฟ PM2.5")

st.line_chart(ref_df.set_index("time")["PM2.5"])
