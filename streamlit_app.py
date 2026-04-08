import streamlit as st
import pandas as pd
import random
import requests
import math
from datetime import datetime, timedelta
from io import BytesIO
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="AirCheck TH", layout="wide")

st.title("🌏 AirCheck TH")
st.caption("ระบบจำลองคุณภาพอากาศ")

# ---------------- จังหวัด ----------------

province_coords = {
    "กรุงเทพมหานคร": (13.7563, 100.5018),
    "ระยอง": (12.6814, 101.2770),
    "ชลบุรี": (13.3611, 100.9847),
    "สระบุรี": (14.5289, 100.9105),
    "อยุธยา": (14.3532, 100.5689),
    "ราชบุรี": (13.5360, 99.8171),
    "จันทบุรี": (12.6112, 102.1035)
}

# ---------------- Sidebar ----------------

st.sidebar.header("⚙ การตั้งค่า")

province = st.sidebar.selectbox("📍 เลือกจังหวัด", list(province_coords.keys()))
center_lat, center_lon = province_coords[province]

start_date = st.sidebar.date_input("📅 วันที่เริ่มต้น", datetime.now().date())
num_days = st.sidebar.slider("จำนวนวัน", 1, 8, 1)

near_road = st.sidebar.checkbox("🚗 ใกล้ถนนใหญ่")
near_factory = st.sidebar.checkbox("🏭 ใกล้โรงงาน")
near_community = st.sidebar.checkbox("🏘 ใกล้ชุมชน")

station_type = st.sidebar.selectbox(
    "🏫 ประเภทสถานี",
    ["วัด", "โรงเรียน", "ชุมชน", "โรงพยาบาล", "อุตสาหกรรม"]
)

st.sidebar.subheader("📍 โหมดปักหมุด")

pin_mode = st.sidebar.radio("เลือกประเภทหมุด", ["จุดตรวจวัด", "โรงงาน"])

# ---------------- ลบหมุด ----------------

if st.sidebar.button("ลบจุดตรวจวัด"):
    st.session_state.pop("station", None)

if st.sidebar.button("ลบโรงงานทั้งหมด"):
    st.session_state.pop("factories", None)

# ---------------- Distance ----------------

def distance_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

# ---------------- Map ----------------

map_center = st.session_state.get("station", [center_lat, center_lon])

m = folium.Map(location=map_center, zoom_start=12)

# marker
if "station" in st.session_state:
    folium.Marker(
        st.session_state.station,
        tooltip="🟢 จุดตรวจวัด",
        icon=folium.Icon(color="green")
    ).add_to(m)

if "factories" in st.session_state:
    for i, f in enumerate(st.session_state.factories):

        folium.Marker(
            f,
            tooltip=f"🔴 โรงงาน {i+1}",
            icon=folium.Icon(color="red")
        ).add_to(m)

        if "station" in st.session_state:
            dist = distance_km(
                st.session_state.station[0],
                st.session_state.station[1],
                f[0],
                f[1]
            )

            folium.PolyLine(
                [st.session_state.station, f],
                color="blue",
                tooltip=f"{dist:.2f} km"
            ).add_to(m)

map_data = st_folium(m, height=500)

# ✅ FIX: คลิกแล้วต้อง rerun
if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    if pin_mode == "จุดตรวจวัด":
        st.session_state.station = (lat, lon)
    else:
        st.session_state.setdefault("factories", []).append((lat, lon))

    st.rerun()

# ---------------- API ----------------

@st.cache_data
def fetch_api(lat, lon, start_date, num_days):

    sd = start_date.strftime("%Y-%m-%d")
    ed = (start_date + timedelta(days=num_days-1)).strftime("%Y-%m-%d")

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        weather_res = requests.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok",
            headers=headers,
            timeout=15
        )

        air_res = requests.get(
            f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok",
            headers=headers,
            timeout=15
        )

        # ❗ เช็คก่อน
        if weather_res.status_code != 200 or air_res.status_code != 200:
            st.error("API ตอบกลับผิดปกติ")
            return pd.DataFrame()

        weather = weather_res.json()
        air = air_res.json()

        # ❗ กัน key หาย
        if "hourly" not in weather or "hourly" not in air:
            st.error("API ไม่มีข้อมูล hourly")
            return pd.DataFrame()

        w = weather["hourly"]
        a = air["hourly"]

        df = pd.DataFrame({
            "time": pd.to_datetime(w["time"]),
            "Temp": w["temperature_2m"],
            "RH": w["relative_humidity_2m"],
            "WS": w["wind_speed_10m"],
            "WD": w["wind_direction_10m"],
            "NO2_ref": a.get("nitrogen_dioxide", []),
            "SO2_ref": a.get("sulphur_dioxide", []),
            "CO_ref": a.get("carbon_monoxide", []),
            "O3_ref": a.get("ozone", [])
        })

        return df

    except Exception as e:
        st.error(f"โหลด API ไม่ได้: {e}")
        return pd.DataFrame()

# ---------------- Simulation ----------------

def simulate(base):
    return base * random.uniform(0.8, 1.3)

# ---------------- Run ----------------

if st.button("🚀 เริ่มจำลองข้อมูล"):

    if "station" not in st.session_state:
        st.warning("กรุณาปักจุดก่อน")
        st.stop()

    station = st.session_state.station

    ref_df = fetch_api(station[0], station[1], start_date, num_days)

    # ✅ วางตรงนี้ (ต้องเยื้อง 4 ช่อง)
    if ref_df.empty or len(ref_df) < 10:
        st.warning("ข้อมูลจาก API ไม่พอ → ใช้ข้อมูลสุ่มแทน")

        ref_df = pd.DataFrame({
            "time": pd.date_range(start=start_date, periods=24*num_days, freq="H"),
            "Temp": [30]*24*num_days,
            "RH": [70]*24*num_days,
            "WS": [2]*24*num_days,
            "WD": [180]*24*num_days,
            "NO2_ref": [20]*24*num_days,
            "SO2_ref": [5]*24*num_days,
            "CO_ref": [200]*24*num_days,
            "O3_ref": [30]*24*num_days
        })

    if ref_df.empty:
        st.stop()

    rows = []

    for i, row in ref_df.iterrows():

        rows.append({
            "Datetime": row["time"],
            "NO": random.uniform(5, 20),
            "NO2": simulate(row["NO2_ref"]),
            "NOx": simulate(row["NO2_ref"] + random.uniform(2, 5)),
            "SO2": simulate(row["SO2_ref"]),
            "CO": simulate(row["CO_ref"]),
            "O3": simulate(row["O3_ref"]),
            "WS": row["WS"],
            "WD": row["WD"],
            "Temp": row["Temp"],
            "RH": row["RH"],
            "Pressure": 1010 + random.uniform(-5, 5)
        })

    df = pd.DataFrame(rows)

    st.subheader("📊 Dashboard")
    st.line_chart(df.set_index("Datetime")[["NO2", "SO2", "CO", "O3"]])

    st.subheader("📄 ตารางข้อมูล")
    st.dataframe(df)

    buf = BytesIO()

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Simulated")
        ref_df.to_excel(writer, index=False, sheet_name="Reference")

    st.download_button(
        "📥 ดาวน์โหลด Excel",
        buf.getvalue(),
        file_name="AirCheckTH.xlsx"
    )
