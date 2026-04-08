import streamlit as st
import pandas as pd
import random
import requests
import time
from datetime import datetime, timedelta
from io import BytesIO
import folium
from streamlit_folium import st_folium

# 🔑 ใส่ API KEY (สมัครฟรี)
OPENWEATHER_API_KEY = "YOUR_API_KEY"

st.set_page_config(page_title="AirCheck TH", layout="wide")

st.title("🌏 AirCheck TH (PRO)")
st.caption("Hybrid: Multi-API + Cache + Simulation")

# ---------------- SESSION ----------------
if "factories" not in st.session_state:
    st.session_state.factories = []

if "station" not in st.session_state:
    st.session_state.station = None

if "last_ref" not in st.session_state:
    st.session_state.last_ref = None

# ---------------- จังหวัด ----------------
province_coords = {
    "กรุงเทพมหานคร": (13.7563,100.5018),
    "ระยอง": (12.6814,101.2770),
    "ชลบุรี": (13.3611,100.9847),
    "สระบุรี": (14.5289,100.9105),
    "อยุธยา": (14.3532,100.5689),
    "ราชบุรี": (13.5360,99.8171),
    "จันทบุรี": (12.6112,102.1035)
}

# ---------------- Sidebar ----------------
st.sidebar.header("⚙ การตั้งค่า")

province = st.sidebar.selectbox("📍 จังหวัด", list(province_coords.keys()))
center_lat,center_lon = province_coords[province]

start_date = st.sidebar.date_input("📅 วันที่เริ่ม", datetime.now().date())
num_days = st.sidebar.slider("จำนวนวัน",1,7,1)

near_road = st.sidebar.checkbox("🚗 ใกล้ถนน")
near_factory = st.sidebar.checkbox("🏭 ใกล้โรงงาน")
near_community = st.sidebar.checkbox("🏘 ใกล้ชุมชน")

pin_mode = st.sidebar.radio("📍 โหมดปักหมุด",["จุดตรวจวัด","โรงงาน"])

# ---------------- MAP ----------------
map_center = st.session_state.station if st.session_state.station else [center_lat,center_lon]

m = folium.Map(location=map_center, zoom_start=12)

folium.TileLayer(
    tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    name="ดาวเทียม",
    attr="Google"
).add_to(m)

folium.TileLayer("OpenStreetMap", name="แผนที่").add_to(m)
folium.LayerControl().add_to(m)

if st.session_state.station:
    folium.Marker(st.session_state.station, tooltip="จุดตรวจวัด",
                  icon=folium.Icon(color="green")).add_to(m)

for i,f in enumerate(st.session_state.factories):
    folium.Marker(f, tooltip=f"โรงงาน {i+1}",
                  icon=folium.Icon(color="red")).add_to(m)

map_data = st_folium(m,height=500)

if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    if pin_mode == "จุดตรวจวัด":
        st.session_state.station = (lat,lon)
    else:
        st.session_state.factories.append((lat,lon))

    st.rerun()

# ---------------- API FUNCTIONS ----------------
def safe_request(url, params, retries=3):
    for _ in range(retries):
        try:
            res = requests.get(url, params=params, timeout=10)
            if res.status_code == 200:
                return res.json()
        except:
            pass
        time.sleep(1)
    return None

def fetch_open_meteo(lat, lon, start_date, num_days):
    sd = start_date.strftime("%Y-%m-%d")
    ed = (start_date + timedelta(days=num_days-1)).strftime("%Y-%m-%d")

    weather = safe_request(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
            "start_date": sd,
            "end_date": ed,
            "timezone": "Asia/Bangkok"
        }
    )

    air = safe_request(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": "carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "start_date": sd,
            "end_date": ed,
            "timezone": "Asia/Bangkok"
        }
    )

    if not weather:
        return None

    try:
        w = weather["hourly"]

        df = pd.DataFrame({
            "time": pd.to_datetime(w["time"]),
            "Temp": w["temperature_2m"],
            "RH": w["relative_humidity_2m"],
            "WS": w["wind_speed_10m"],
            "WD": w["wind_direction_10m"]
        })

        # ถ้า air มี → ใช้จริง
        if air and "hourly" in air:
            a = air["hourly"]
            df["NO2_ref"] = a["nitrogen_dioxide"]
            df["SO2_ref"] = a["sulphur_dioxide"]
            df["CO_ref"] = a["carbon_monoxide"]
            df["O3_ref"] = a["ozone"]
        else:
            # fallback เฉพาะ air
            df["NO2_ref"] = [random.uniform(10,40)]*len(df)
            df["SO2_ref"] = [random.uniform(5,20)]*len(df)
            df["CO_ref"] = [random.uniform(200,800)]*len(df)
            df["O3_ref"] = [random.uniform(10,50)]*len(df)

        return df.dropna().reset_index(drop=True)

    except:
        return None

def fetch_openweather(lat, lon):
    try:
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
        res = requests.get(url, timeout=5).json()

        comp = res["list"][0]["components"]

        return {
            "NO2": comp["no2"],
            "SO2": comp["so2"],
            "CO": comp["co"],
            "O3": comp["o3"]
        }
    except:
        return None

# ---------------- SIM ----------------
def simulate(base):
    return base * random.uniform(0.85,1.25)

def env_factor(val, pol):
    factor = 1.0
    if near_road and pol in ["NO","NO2","CO"]: factor += 0.3
    if near_factory and pol in ["SO2","NO2"]: factor += 0.4
    if near_community and pol in ["CO","NO"]: factor += 0.2
    return val * factor

# ---------------- RUN ----------------
if st.button("🚀 เริ่มจำลอง"):

    if not st.session_state.station:
        st.warning("กรุณาปักจุดก่อน")
        st.stop()

    lat,lon = st.session_state.station

    ref_df = fetch_open_meteo(lat,lon,start_date,num_days)

    # 🔥 fallback chain
    if ref_df is None:
        st.warning("⚠ Open-Meteo ล่ม → ใช้ OpenWeather")

        backup = fetch_openweather(lat,lon)

        if backup:
            rows=[]
            for h in range(num_days*24):
                rows.append({
                    "time": datetime.now()+timedelta(hours=h),
                    "Temp": random.uniform(25,35),
                    "RH": random.uniform(50,90),
                    "WS": random.uniform(0,10),
                    "WD": random.uniform(0,360),
                    "NO2_ref": backup["NO2"],
                    "SO2_ref": backup["SO2"],
                    "CO_ref": backup["CO"],
                    "O3_ref": backup["O3"]
                })
            ref_df = pd.DataFrame(rows)

    # 🔥 fallback cache
    if ref_df is not None:
        st.session_state.last_ref = ref_df
    elif st.session_state.last_ref is not None:
        st.warning("⚠ ใช้ข้อมูลล่าสุดแทน")
        ref_df = st.session_state.last_ref

    # 🔥 fallback สุดท้าย
    if ref_df is None:
        st.warning("⚠ ใช้ simulation ทั้งหมด")
        ref_df = pd.DataFrame([{
            "time": datetime.now(),
            "Temp": 30,
            "RH": 70,
            "WS": 2,
            "WD": 180,
            "NO2_ref": 20,
            "SO2_ref": 10,
            "CO_ref": 400,
            "O3_ref": 25
        }] * (num_days*24))

    # ---------------- simulate ----------------
    rows=[]
    for i in range(len(ref_df)):
        r = ref_df.iloc[i]

        no2 = env_factor(simulate(r["NO2_ref"]),"NO2")
        so2 = env_factor(simulate(r["SO2_ref"]),"SO2")
        co  = env_factor(simulate(r["CO_ref"]),"CO")

        rows.append({
            "Hour": i,
            "NO2": no2,
            "SO2": so2,
            "CO": co,
            "O3": simulate(r["O3_ref"]),
            "Temp": r["Temp"]
        })

    df = pd.DataFrame(rows)

    st.subheader("📊 Dashboard")
    st.line_chart(df.set_index("Hour"))

    st.subheader("📄 ตาราง")
    st.dataframe(df)

    st.subheader("📡 Reference")
    st.dataframe(ref_df.head(50))

    buf=BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as writer:
        df.to_excel(writer,index=False)
        ref_df.to_excel(writer,index=False)

    st.download_button("📥 ดาวน์โหลด",buf.getvalue(),"AirCheckTH.xlsx")
