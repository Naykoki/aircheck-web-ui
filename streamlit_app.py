import streamlit as st
import pandas as pd
import random
import requests
import math
from datetime import datetime, timedelta
from io import BytesIO
import folium
from streamlit_folium import st_folium

st.set_page_config(
    page_title="AirCheck TH",
    page_icon="🌏",
    layout="wide"
)

st.title("🌏 AirCheck TH")
st.caption("ระบบจำลองคุณภาพอากาศแบบ Interactive")

# ================= จังหวัด =================

province_coords = {
"กรุงเทพมหานคร":(13.7563,100.5018),
"ระยอง":(12.6814,101.2770),
"อยุธยา":(14.3532,100.5689),
"สระบุรี":(14.5289,100.9105),
"ราชบุรี":(13.5360,99.8171),
"ชลบุรี":(13.3611,100.9847),
"จันทบุรี":(12.6112,102.1035)
}

# ================= SIDEBAR =================

st.sidebar.header("⚙ การตั้งค่า")

province = st.sidebar.selectbox(
"📍 เลือกจังหวัด",
list(province_coords.keys())
)

center_lat,center_lon = province_coords[province]

start_date = st.sidebar.date_input("📅 วันที่เริ่มต้น",datetime.now().date())

num_days = st.sidebar.slider("จำนวนวัน",1,7,1)

st.sidebar.divider()

st.sidebar.subheader("🏙 ลักษณะพื้นที่")

near_road = st.sidebar.checkbox("ใกล้ถนนใหญ่")
near_community = st.sidebar.checkbox("ใกล้ชุมชน")

station_type = st.sidebar.selectbox(
"ประเภทสถานี",
["วัด","โรงเรียน","ชุมชน","โรงพยาบาล","อุตสาหกรรม"]
)

st.sidebar.divider()

pin_mode = st.sidebar.radio(
"📌 โหมดปักหมุด",
["ปักจุดตรวจวัด","ปักโรงงาน"]
)

# ================= MAP =================

st.subheader("🗺 แผนที่")

m = folium.Map(location=[center_lat,center_lon],zoom_start=10)

if "station" in st.session_state:
    folium.Marker(
        st.session_state.station,
        tooltip="จุดตรวจวัด",
        icon=folium.Icon(color="green",icon="info-sign")
    ).add_to(m)

if "factory" in st.session_state:
    folium.Marker(
        st.session_state.factory,
        tooltip="โรงงาน",
        icon=folium.Icon(color="red",icon="industry")
    ).add_to(m)

map_data = st_folium(m,height=500,width=1200)

if map_data["last_clicked"]:

    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    if pin_mode=="ปักจุดตรวจวัด":
        st.session_state.station=(lat,lon)
        st.success("ตั้งค่าจุดตรวจวัดแล้ว")

    if pin_mode=="ปักโรงงาน":
        st.session_state.factory=(lat,lon)
        st.success("ตั้งค่าตำแหน่งโรงงานแล้ว")

station = st.session_state.get("station")
factory = st.session_state.get("factory")

# ================= ทิศโรงงาน =================

def calculate_bearing(lat1, lon1, lat2, lon2):

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    diffLong = math.radians(lon2 - lon1)

    x = math.sin(diffLong) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (
        math.sin(lat1) * math.cos(lat2) * math.cos(diffLong)
    )

    bearing = math.degrees(math.atan2(x, y))
    bearing = (bearing + 360) % 360

    return bearing

bearing=None

if station and factory:

    bearing = calculate_bearing(
        station[0],station[1],
        factory[0],factory[1]
    )

    st.info(f"🧭 โรงงานอยู่ทิศ {bearing:.1f}° จากจุดตรวจวัด")

# ================= API =================

@st.cache_data
def fetch_api(lat,lon,start_date,num_days):

    sd=start_date.strftime("%Y-%m-%d")
    ed=(start_date+timedelta(days=num_days-1)).strftime("%Y-%m-%d")

    weather=requests.get(
f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=wind_speed_10m,wind_direction_10m&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
).json()

    air=requests.get(
f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
).json()

    w=weather["hourly"]
    a=air["hourly"]

    df=pd.DataFrame({
"time":pd.to_datetime(w["time"]),
"WS":w["wind_speed_10m"],
"WD":w["wind_direction_10m"],
"NO2_ref":a["nitrogen_dioxide"],
"SO2_ref":a["sulphur_dioxide"],
"CO_ref":a["carbon_monoxide"],
"O3_ref":a["ozone"]
})

    return df

# ================= Simulation =================

def simulate(var,hour,row):

    multiplier=1

    ws=row["WS"]
    wd=row["WD"]

    if ws<1.5:
        multiplier*=1.3

    if near_road and var in ["NO2","CO"]:
        multiplier*=1.4

    if near_community and var in ["NO2","CO"]:
        multiplier*=1.2

    if bearing and abs(wd-bearing)<20:
        multiplier*=1.6

    if hour in range(7,10) or hour in range(16,20):
        multiplier*=1.3

    station_factor={
"วัด":0.85,
"โรงเรียน":1.05,
"ชุมชน":1.0,
"โรงพยาบาล":0.9,
"อุตสาหกรรม":1.2
}

    multiplier*=station_factor[station_type]

    ref=row.get(f"{var}_ref",random.uniform(5,20))

    return round(ref*multiplier,2)

# ================= RUN =================

if st.button("🚀 เริ่มจำลองข้อมูล"):

    if not station:
        st.warning("กรุณาปักจุดตรวจวัดก่อน")
        st.stop()

    ref_df=fetch_api(station[0],station[1],start_date,num_days)

    rows=[]

    for i in range(num_days):

        date=start_date+timedelta(days=i)

        for h in range(24):

            t=datetime.combine(date,datetime.min.time())+timedelta(hours=h)

            match=ref_df.loc[ref_df["time"]==t]

            if match.empty:
                continue

            r=match.iloc[0]

            rows.append({
"Date":date,
"Hour":h,
"NO2":simulate("NO2",h,r),
"SO2":simulate("SO2",h,r),
"CO":simulate("CO",h,r),
"O3":simulate("O3",h,r)
})

    df=pd.DataFrame(rows)

    st.subheader("📊 Dashboard")

    col1,col2=st.columns(2)

    with col1:
        st.line_chart(df.set_index("Hour")[["NO2","SO2"]])

    with col2:
        st.line_chart(df.set_index("Hour")[["CO","O3"]])

    st.subheader("📄 ตารางข้อมูล")

    st.dataframe(df)

    buf=BytesIO()

    with pd.ExcelWriter(buf,engine="openpyxl") as writer:
        df.to_excel(writer,index=False)

    st.download_button(
"📥 ดาวน์โหลด Excel",
buf.getvalue(),
file_name="AirCheckTH.xlsx"
)
