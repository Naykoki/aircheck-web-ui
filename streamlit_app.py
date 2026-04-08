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

    try:
        weather = requests.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok",
            timeout=8
        ).json()

        air = requests.get(
            f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok",
            timeout=8
        ).json()

        # 🔥 เช็คว่า API ได้ข้อมูลจริงไหม
        if "hourly" not in weather or "hourly" not in air:
            raise Exception("API invalid")

        w = weather["hourly"]
        a = air["hourly"]

        df = pd.DataFrame({
            "time": pd.to_datetime(w["time"]),
            "Temp": w["temperature_2m"],
            "RH": w["relative_humidity_2m"],
            "WS": w["wind_speed_10m"],
            "WD": w["wind_direction_10m"],
            "NO2_ref": a["nitrogen_dioxide"],
            "SO2_ref": a["sulphur_dioxide"],
            "CO_ref": a["carbon_monoxide"],
            "O3_ref": a["ozone"]
        })

        st.success("✅ ใช้ข้อมูลจริงจาก API")

        return df

    except:
        st.warning("⚠ API ใช้งานไม่ได้ → ใช้ข้อมูลจำลองแทน")

        # ---------------- สร้างข้อมูลจำลอง ----------------

        rows = []

        total_hours = num_days * 24

        for i in range(total_hours):

            dt = start_date + timedelta(hours=i)
            hour = dt.hour

            # 🌡 อุณหภูมิ (ขึ้นกลางวัน ลงกลางคืน)
            temp = 28 + 5 * math.sin((hour-6)/24 * 2 * math.pi) + random.uniform(-1,1)

            # 💧 ความชื้น
            rh = 70 + 15 * math.sin((hour)/24 * 2 * math.pi) + random.uniform(-5,5)

            # 🌬 ลม
            ws = random.uniform(1,5)
            wd = random.uniform(0,360)

            # 🏭 มลพิษ (พีคเช้า-เย็น)
            rush_factor = 1 + 0.5 * math.sin((hour-7)/24 * 2 * math.pi)**2

            NO2 = random.uniform(10,30) * rush_factor
            SO2 = random.uniform(3,10)
            CO = random.uniform(200,500)
            O3 = random.uniform(20,60) * (1 - 0.3*rush_factor)

            rows.append({
                "time": dt,
                "Temp": temp,
                "RH": rh,
                "WS": ws,
                "WD": wd,
                "NO2_ref": NO2,
                "SO2_ref": SO2,
                "CO_ref": CO,
                "O3_ref": O3
            })

        df = pd.DataFrame(rows)

        return df

# ---------------- Simulation ----------------

def simulate(base):
    return base * random.uniform(0.8, 1.3)

# ---------------- Run ----------------

if st.button("🚀 เริ่มจำลองข้อมูล"):

    if "station" not in st.session_state:
        st.warning("กรุณาปักจุดก่อน")
        st.stop()

    ref_df = fetch_api(
        st.session_state.station[0],
        st.session_state.station[1],
        start_date,
        num_days
    )

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
