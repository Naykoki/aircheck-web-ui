import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="AirCheck TH", layout="wide")
st.title("🌍 AirCheck TH (Simulation – Cloud Safe)")

# ---------- INPUT ----------
province = st.selectbox(
    "จังหวัด",
    ["กรุงเทพมหานคร", "ระยอง", "อยุธยา", "สระบุรี", "ราชบุรี", "ชลบุรี", "จันทบุรี"]
)

coords = {
    "กรุงเทพมหานคร": (13.7563, 100.5018),
    "ระยอง": (12.6814, 101.2770),
    "อยุธยา": (14.3532, 100.5689),
    "สระบุรี": (14.5289, 100.9105),
    "ราชบุรี": (13.5360, 99.8171),
    "ชลบุรี": (13.3611, 100.9847),
    "จันทบุรี": (12.6112, 102.1035)
}
lat, lon = coords[province]

start_date = st.date_input("วันที่เริ่ม", datetime.now().date())
num_days = st.slider("จำนวนวัน", 1, 7, 1)

params = st.multiselect(
    "พารามิเตอร์",
    ["NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH"],
    default=["NO", "NO2", "NOx", "WS", "Temp", "RH"]
)

# ---------- FETCH OPEN-METEO ----------
@st.cache_data(show_spinner=False)
def fetch_weather_aq(lat, lon, start, days):
    sd = start.strftime("%Y-%m-%d")
    ed = (start + timedelta(days=days - 1)).strftime("%Y-%m-%d")

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
        f"&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
    )
    w = requests.get(url).json()["hourly"]

    aq_url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
        f"&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
    )
    aq = requests.get(aq_url).json()["hourly"]

    df = pd.DataFrame({
        "time": pd.to_datetime(w["time"]),
        "Temp": w["temperature_2m"],
        "RH": w["relative_humidity_2m"],
        "WS": w["wind_speed_10m"],
        "WD": w["wind_direction_10m"],
        "CO": aq["carbon_monoxide"],
        "NO2": aq["nitrogen_dioxide"],
        "SO2": aq["sulphur_dioxide"],
        "O3": aq["ozone"],
    })
    return df

df_ref = fetch_weather_aq(lat, lon, start_date, num_days)

# ---------- SIMULATION ----------
rows = []
for _, r in df_ref.iterrows():
    row = {
        "DateTime": r["time"],
        "Temp": r["Temp"],
        "RH": r["RH"],
        "WS": max(0.5, r["WS"] * random.uniform(0.7, 1.1)),
        "WD": r["WD"],
        "NO": random.uniform(5, 25),
        "NO2": r["NO2"] * random.uniform(1.1, 1.4),
        "CO": r["CO"] * random.uniform(1.05, 1.3),
        "SO2": r["SO2"] * random.uniform(1.0, 1.2),
        "O3": r["O3"] * random.uniform(0.9, 1.2),
    }
    row["NOx"] = row["NO"] + row["NO2"]
    rows.append({k: row[k] for k in params if k in row})

df = pd.DataFrame(rows)
st.dataframe(df.head(48))

# ---------- EXPORT ----------
buf = BytesIO()
df.to_excel(buf, index=False)
st.download_button("📥 ดาวน์โหลด Excel", buf.getvalue(), "AirCheckTH.xlsx")
