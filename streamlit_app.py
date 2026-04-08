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
"กรุงเทพมหานคร":(13.7563,100.5018),
"ระยอง":(12.6814,101.2770),
"ชลบุรี":(13.3611,100.9847),
"สระบุรี":(14.5289,100.9105),
"อยุธยา":(14.3532,100.5689),
"ราชบุรี":(13.5360,99.8171),
"จันทบุรี":(12.6112,102.1035)
}

# ---------------- Sidebar ----------------

st.sidebar.header("⚙ การตั้งค่า")

province = st.sidebar.selectbox("📍 เลือกจังหวัด", list(province_coords.keys()))
center_lat,center_lon = province_coords[province]

start_date = st.sidebar.date_input("📅 วันที่เริ่มต้น", datetime.now().date())
num_days = st.sidebar.slider("จำนวนวัน",1,5,1)

# ---------------- Map ----------------

if "station" not in st.session_state:
    st.session_state.station = (center_lat,center_lon)

m = folium.Map(location=st.session_state.station, zoom_start=10)

folium.Marker(
    st.session_state.station,
    tooltip="จุดตรวจวัด",
    icon=folium.Icon(color="green")
).add_to(m)

map_data = st_folium(m,height=400)

if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    st.session_state.station = (lat,lon)

# ---------------- API ----------------

@st.cache_data
def fetch_api(lat,lon,start_date,num_days):

    sd=start_date.strftime("%Y-%m-%d")
    ed=(start_date+timedelta(days=num_days-1)).strftime("%Y-%m-%d")

    weather = requests.get(
f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
).json()

    air = requests.get(
f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
).json()

    if "hourly" not in weather or "hourly" not in air:
        st.error("API Error")
        st.stop()

    w=weather["hourly"]
    a=air["hourly"]

    df=pd.DataFrame({
"time":pd.to_datetime(w["time"]),
"Temp":w["temperature_2m"],
"RH":w["relative_humidity_2m"],
"WS":w["wind_speed_10m"],
"WD":w["wind_direction_10m"],
"NO2_ref":a["nitrogen_dioxide"],
"SO2_ref":a["sulphur_dioxide"],
"CO_ref":a["carbon_monoxide"],
"O3_ref":a["ozone"]
})

    return df

# ---------------- Simulation ----------------

def simulate(base):
    return base * random.uniform(0.8,1.3)

# ---------------- 10 MIN FUNCTION ----------------

def expand_to_10min(df):

    rows = []

    for i in range(len(df)-1):

        r1 = df.iloc[i]
        r2 = df.iloc[i+1]

        t1 = r1["time"]

        for m in range(0,60,10):

            t = t1 + timedelta(minutes=m)
            frac = m/60

            # ลม (แก้ 360)
            wd1 = r1["WD"]
            wd2 = r2["WD"]
            diff = (wd2 - wd1 + 180) % 360 - 180
            wd = (wd1 + diff * frac + random.uniform(-5,5)) % 360

            rows.append({
                "Time": t,
                "NO": random.uniform(5,20),
                "NO2": simulate(r1["NO2_ref"]),
                "NOx": simulate(r1["NO2_ref"] + random.uniform(2,5)),
                "SO2": simulate(r1["SO2_ref"]),
                "CO": simulate(r1["CO_ref"]),
                "O3": simulate(r1["O3_ref"]),
                "WS": r1["WS"],
                "WD": wd,
                "Temp": r1["Temp"],
                "RH": r1["RH"],
                "Pressure": 1010 + random.uniform(-5,5)
            })

    return pd.DataFrame(rows)

# ---------------- RUN ----------------

if st.button("🚀 เริ่มจำลองข้อมูล"):

    lat,lon = st.session_state.station

    ref_df = fetch_api(lat,lon,start_date,num_days)

    rows=[]

    for i in range(len(ref_df)):

        r=ref_df.iloc[i]

        rows.append({
            "Time": r["time"],
            "NO": random.uniform(5,20),
            "NO2": simulate(r["NO2_ref"]),
            "NOx": simulate(r["NO2_ref"] + random.uniform(2,5)),
            "SO2": simulate(r["SO2_ref"]),
            "CO": simulate(r["CO_ref"]),
            "O3": simulate(r["O3_ref"]),
            "WS": r["WS"],
            "WD": r["WD"],
            "Temp": r["Temp"],
            "RH": r["RH"],
            "Pressure": 1010 + random.uniform(-5,5)
        })

    df = pd.DataFrame(rows)

    # 🔥 10 นาที
    df_10min = expand_to_10min(ref_df)

    # ---------------- SHOW ----------------

    st.subheader("📊 รายชั่วโมง")
    st.dataframe(df)

    st.subheader("⏱ ราย 10 นาที")
    st.dataframe(df_10min)

    # ---------------- EXPORT ----------------

    buf = BytesIO()

    with pd.ExcelWriter(buf,engine="openpyxl") as writer:

        df.to_excel(writer,index=False,sheet_name="Hourly_Simulated")
        ref_df.to_excel(writer,index=False,sheet_name="Hourly_Reference")
        df_10min.to_excel(writer,index=False,sheet_name="10min_Data")

    st.download_button(
        "📥 ดาวน์โหลด Excel",
        buf.getvalue(),
        file_name="AirCheckTH.xlsx"
    )
