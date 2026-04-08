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

# ---------------- SESSION SAFE ----------------
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

province = st.sidebar.selectbox("📍 เลือกจังหวัด", list(province_coords.keys()))
center_lat,center_lon = province_coords[province]

start_date = st.sidebar.date_input("📅 วันที่เริ่มต้น", datetime.now().date())
num_days = st.sidebar.slider("จำนวนวัน", 1, 8, 1)

near_road = st.sidebar.checkbox("🚗 ใกล้ถนนใหญ่")
near_factory = st.sidebar.checkbox("🏭 ใกล้โรงงาน")
near_community = st.sidebar.checkbox("🏘 ใกล้ชุมชน")

station_type = st.sidebar.selectbox("🏫 ประเภทสถานี",
["วัด","โรงเรียน","ชุมชน","โรงพยาบาล","อุตสาหกรรม"])

st.sidebar.subheader("📍 โหมดปักหมุด")
pin_mode = st.sidebar.radio("เลือกประเภทหมุด",["จุดตรวจวัด","โรงงาน"])

# ---------------- ลบ ----------------
if st.sidebar.button("ลบจุดตรวจวัด"):
    st.session_state.station = None

if st.sidebar.button("ลบโรงงานทั้งหมด"):
    st.session_state.factories = []

# ---------------- Distance ----------------
def distance_km(lat1,lon1,lat2,lon2):
    R=6371
    dlat=math.radians(lat2-lat1)
    dlon=math.radians(lon2-lon1)
    a=math.sin(dlat/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R*(2*math.atan2(math.sqrt(a),math.sqrt(1-a)))

# ---------------- MAP ----------------
map_center = st.session_state.station if st.session_state.station else [center_lat,center_lon]

m = folium.Map(location=map_center, zoom_start=12)

# station
if st.session_state.station:
    folium.Marker(st.session_state.station, tooltip="🟢 จุดตรวจวัด",
                  icon=folium.Icon(color="green")).add_to(m)

# factories
for i,f in enumerate(st.session_state.factories):
    folium.Marker(f, tooltip=f"🔴 โรงงาน {i+1}",
                  icon=folium.Icon(color="red")).add_to(m)

    if st.session_state.station:
        dist = distance_km(st.session_state.station[0],st.session_state.station[1],f[0],f[1])
        folium.PolyLine([st.session_state.station,f], tooltip=f"{dist:.2f} km").add_to(m)

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
@st.cache_data(ttl=3600)
def fetch_api(lat, lon, start_date, num_days):

    sd = start_date.strftime("%Y-%m-%d")
    ed = (start_date + timedelta(days=num_days-1)).strftime("%Y-%m-%d")

    try:
        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
                "start_date": sd,
                "end_date": ed,
                "timezone": "Asia/Bangkok"
            }, timeout=10
        ).json()

        air = requests.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
                "start_date": sd,
                "end_date": ed,
                "timezone": "Asia/Bangkok"
            }, timeout=10
        ).json()

        if "hourly" not in weather or "hourly" not in air:
            return None

        w = weather["hourly"]
        a = air["hourly"]

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

        return df if not df.empty else None

    except:
        return None

# ---------------- SIM ----------------
def simulate(base):
    return base * random.uniform(0.8,1.3)

# ---------------- RUN ----------------
if st.button("🚀 เริ่มจำลองข้อมูล"):

    if not st.session_state.station:
        st.warning("กรุณาปักจุดก่อน")
        st.stop()

    station = st.session_state.station

    ref_df = fetch_api(station[0],station[1],start_date,num_days)

    # 🔥 fallback ถ้า API พัง
    if ref_df is None:
        st.warning("⚠ API ล่ม → ใช้ข้อมูลจำลอง")

        rows=[]
        for i in range(num_days):
            date=start_date+timedelta(days=i)
            for h in range(24):
                rows.append({
                    "time": datetime.combine(date, datetime.min.time()) + timedelta(hours=h),
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

    # กันข้อมูลไม่ครบ
    total = num_days * 24
    if len(ref_df) < total:
        for i in range(total - len(ref_df)):
            ref_df.loc[len(ref_df)] = ref_df.iloc[-1]

    rows=[]
    for i in range(num_days):
        date=start_date+timedelta(days=i)
        for h in range(24):

            r = ref_df.iloc[i*24 + h]

            rows.append({
                "Date":date,
                "Hour":h,
                "NO":random.uniform(5,20),
                "NO2":simulate(r["NO2_ref"]),
                "NOx":simulate(r["NO2_ref"]+random.uniform(2,5)),
                "SO2":simulate(r["SO2_ref"]),
                "CO":simulate(r["CO_ref"]),
                "O3":simulate(r["O3_ref"]),
                "WS":r["WS"],
                "WD":r["WD"],
                "Temp":r["Temp"],
                "RH":r["RH"],
                "Pressure":1010+random.uniform(-5,5)
            })

    df=pd.DataFrame(rows)

    st.subheader("📊 Dashboard")
    st.line_chart(df.set_index("Hour")[["NO2","SO2","CO","O3"]])

    st.subheader("📄 ตารางข้อมูล")
    st.dataframe(df)

    buf=BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as writer:
        df.to_excel(writer,index=False)
        ref_df.to_excel(writer,index=False,sheet_name="ref")

    st.download_button("📥 ดาวน์โหลด Excel",buf.getvalue(),"AirCheckTH.xlsx")
