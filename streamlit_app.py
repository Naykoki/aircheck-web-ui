import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="AirCheck TH", layout="wide")

st.title("🌏 AirCheck TH")
st.caption("ระบบจำลองคุณภาพอากาศ (รายชั่วโมง)")

# ---------------- จังหวัด ----------------

province_coords = {
    "กรุงเทพมหานคร":(13.7563,100.5018),
    "ระยอง":(12.6814,101.2770),
    "ชลบุรี":(13.3611,100.9847)
}

# ---------------- Sidebar ----------------

st.sidebar.header("⚙ การตั้งค่า")

province = st.sidebar.selectbox("📍 เลือกจังหวัด", list(province_coords.keys()))
lat,lon = province_coords[province]

start_date = st.sidebar.date_input("📅 วันที่เริ่มต้น", datetime.now().date())

num_days = st.sidebar.slider("จำนวนวัน",1,5,1)

# ---------------- API ----------------

@st.cache_data(show_spinner=False)
def fetch_api(lat,lon,start_date,num_days):

    sd=start_date.strftime("%Y-%m-%d")
    ed=(start_date+timedelta(days=num_days-1)).strftime("%Y-%m-%d")

    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"

    air_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"

    try:
        weather = requests.get(weather_url, timeout=10).json()
        air = requests.get(air_url, timeout=10).json()
    except:
        st.error("❌ API เชื่อมต่อไม่ได้")
        st.stop()

    # 🔥 เช็คก่อนใช้
    if "hourly" not in weather:
        st.error(f"❌ Weather API Error: {weather}")
        st.stop()

    if "hourly" not in air:
        st.error(f"❌ Air API Error: {air}")
        st.stop()

    w = weather["hourly"]
    a = air["hourly"]

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

# ---------------- Run ----------------

if st.button("🚀 เริ่มจำลองข้อมูล"):

    ref_df = fetch_api(lat,lon,start_date,num_days)

    rows=[]

    for i in range(len(ref_df)):

        r = ref_df.iloc[i]

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

    # ---------------- แสดงผล ----------------

    st.subheader("📊 Dashboard")
    st.line_chart(df.set_index("Time")[["NO2","SO2","CO","O3"]])

    st.subheader("📄 ตารางข้อมูล")
    st.dataframe(df)

    # ---------------- Export ----------------

    buf = BytesIO()

    with pd.ExcelWriter(buf,engine="openpyxl") as writer:
        df.to_excel(writer,index=False,sheet_name="Simulated")
        ref_df.to_excel(writer,index=False,sheet_name="Reference")

    st.download_button(
        "📥 ดาวน์โหลด Excel",
        buf.getvalue(),
        file_name="AirCheckTH.xlsx"
    )
