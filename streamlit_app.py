import streamlit as st
import pandas as pd
import random
import requests
import time
from datetime import datetime, timedelta
from io import BytesIO
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="AirCheck TH", layout="wide")

st.title("🌏 AirCheck TH")
st.caption("ระบบจำลองคุณภาพอากาศ (Hybrid: API + Simulation)")

# ---------------- SESSION ----------------
if "factories" not in st.session_state:
    st.session_state.factories = []

if "station" not in st.session_state:
    st.session_state.station = None

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

# ดาวเทียม
folium.TileLayer(
    tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    name="ดาวเทียม",
    attr="Google"
).add_to(m)

folium.TileLayer("OpenStreetMap", name="แผนที่").add_to(m)
folium.LayerControl().add_to(m)

# station
if st.session_state.station:
    folium.Marker(st.session_state.station, tooltip="จุดตรวจวัด",
                  icon=folium.Icon(color="green")).add_to(m)

# factories
for i,f in enumerate(st.session_state.factories):
    folium.Marker(f, tooltip=f"โรงงาน {i+1}",
                  icon=folium.Icon(color="red")).add_to(m)

map_data = st_folium(m,height=500)

# click map
if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    if pin_mode == "จุดตรวจวัด":
        st.session_state.station = (lat,lon)
    else:
        st.session_state.factories.append((lat,lon))

    st.rerun()

# ---------------- API ----------------
@st.cache_data(ttl=1800)
def fetch_api(lat, lon, start_date, num_days):

    sd = start_date.strftime("%Y-%m-%d")
    ed = (start_date + timedelta(days=num_days-1)).strftime("%Y-%m-%d")

    def safe_request(url, params, retries=3):
        for i in range(retries):
            try:
                res = requests.get(url, params=params, timeout=10)
                if res.status_code == 200:
                    return res.json()
            except Exception as e:
                print(f"Retry {i+1}:", e)
            time.sleep(1)
        return None

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

    if not weather or not air:
        return None

    try:
        w = weather.get("hourly", {})
        a = air.get("hourly", {})

        df = pd.DataFrame({
            "time": pd.to_datetime(w.get("time", [])),
            "Temp": w.get("temperature_2m", []),
            "RH": w.get("relative_humidity_2m", []),
            "WS": w.get("wind_speed_10m", []),
            "WD": w.get("wind_direction_10m", []),
            "NO2_ref": a.get("nitrogen_dioxide", []),
            "SO2_ref": a.get("sulphur_dioxide", []),
            "CO_ref": a.get("carbon_monoxide", []),
            "O3_ref": a.get("ozone", [])
        })

        df = df.dropna().reset_index(drop=True)

        if df.empty:
            return None

        return df

    except:
        return None

# ---------------- SIM ----------------
def simulate(base):
    if base is None:
        base = random.uniform(10,50)
    return base * random.uniform(0.85,1.25)

def env_factor(val, pol):
    factor = 1.0
    if near_road and pol in ["NO","NO2","CO"]: factor += 0.3
    if near_factory and pol in ["SO2","NO2"]: factor += 0.4
    if near_community and pol in ["CO","NO"]: factor += 0.2
    return val * factor

def air_status(no2):
    if no2 < 20: return "ดี 🟢"
    elif no2 < 40: return "ปานกลาง 🟡"
    else: return "เริ่มมีผลกระทบ 🔴"

# ---------------- RUN ----------------
if st.button("🚀 เริ่มจำลอง"):

    if not st.session_state.station:
        st.warning("กรุณาปักจุดก่อน")
        st.stop()

    lat,lon = st.session_state.station

    ref_df = fetch_api(lat,lon,start_date,num_days)

    # fallback
    if ref_df is None:
        st.warning("⚠ API ไม่พร้อม → ใช้ข้อมูลจำลอง")

        rows=[]
        for i in range(num_days):
            date=start_date+timedelta(days=i)
            for h in range(24):
                rows.append({
                    "time": datetime.combine(date, datetime.min.time())+timedelta(hours=h),
                    "Temp": random.uniform(25,35),
                    "RH": random.uniform(50,90),
                    "WS": random.uniform(0,10),
                    "WD": random.uniform(0,360),
                    "NO2_ref": random.uniform(10,40),
                    "SO2_ref": random.uniform(5,20),
                    "CO_ref": random.uniform(200,800),
                    "O3_ref": random.uniform(10,50)
                })
        ref_df = pd.DataFrame(rows)

    total = num_days*24
    if len(ref_df) < total:
        for _ in range(total-len(ref_df)):
            ref_df.loc[len(ref_df)] = ref_df.iloc[-1]

    rows=[]
    for i in range(num_days):
        date=start_date+timedelta(days=i)

        for h in range(24):
            r = ref_df.iloc[i*24+h]

            no2 = env_factor(simulate(r["NO2_ref"]),"NO2")
            so2 = env_factor(simulate(r["SO2_ref"]),"SO2")
            co  = env_factor(simulate(r["CO_ref"]),"CO")

            rows.append({
                "Date":date,
                "Hour":h,
                "NO":env_factor(random.uniform(5,20),"NO"),
                "NO2":no2,
                "NOx":no2+random.uniform(2,5),
                "SO2":so2,
                "CO":co,
                "O3":simulate(r["O3_ref"]),
                "Temp":r["Temp"],
                "RH":r["RH"],
                "WS":r["WS"],
                "WD":r["WD"],
                "Pressure":1010+random.uniform(-5,5)
            })

    df = pd.DataFrame(rows)
    df["สถานะ"] = df["NO2"].apply(air_status)

    # ---------------- UI ----------------
    st.subheader("📌 สถานการณ์พื้นที่")

    info=[]
    if near_road: info.append("ใกล้ถนน")
    if near_factory: info.append("ใกล้โรงงาน")
    if near_community: info.append("ใกล้ชุมชน")

    st.info(" | ".join(info) if info else "พื้นที่ทั่วไป")

    st.subheader("📊 Dashboard")
    st.line_chart(df.set_index("Hour")[["NO2","SO2","CO","O3"]])

    st.subheader("📄 ตารางข้อมูล")
    st.dataframe(df)

    st.subheader("📡 ข้อมูลอ้างอิง")
    st.dataframe(ref_df.head(50))

    buf=BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as writer:
        df.to_excel(writer,index=False,sheet_name="Simulation")
        ref_df.to_excel(writer,index=False,sheet_name="Reference")

    st.download_button("📥 ดาวน์โหลด Excel",buf.getvalue(),"AirCheckTH.xlsx")
