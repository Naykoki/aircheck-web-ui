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

province = st.sidebar.selectbox(
"📍 เลือกจังหวัด",
list(province_coords.keys())
)

center_lat,center_lon = province_coords[province]

start_date = st.sidebar.date_input(
"📅 วันที่เริ่มต้น",
datetime.now().date()
)

num_days = st.sidebar.slider(
"จำนวนวัน",
1,7,1
)

near_road = st.sidebar.checkbox("🚗 ใกล้ถนนใหญ่")
near_factory = st.sidebar.checkbox("🏭 ใกล้โรงงาน")
near_community = st.sidebar.checkbox("🏘 ใกล้ชุมชน")

station_type = st.sidebar.selectbox(
"🏫 ประเภทสถานี",
["วัด","โรงเรียน","ชุมชน","โรงพยาบาล","อุตสาหกรรม"]
)

st.sidebar.subheader("📍 โหมดปักหมุด")

pin_mode = st.sidebar.radio(
"เลือกประเภทหมุด",
["จุดตรวจวัด","โรงงาน"]
)

# ---------------- Map ----------------

if "station" in st.session_state:
    map_center = st.session_state.station
else:
    map_center = [center_lat,center_lon]

m = folium.Map(
location=map_center,
zoom_start=12,
tiles="CartoDB positron"
)

# ---------------- จุดตรวจวัด ----------------

if "station" in st.session_state:

    folium.Marker(
        st.session_state.station,
        tooltip="🟢 จุดตรวจวัด",
        icon=folium.Icon(color="green")
    ).add_to(m)

# ---------------- โรงงาน ----------------

if "factories" in st.session_state:

    for i,f in enumerate(st.session_state.factories):

        folium.Marker(
            f,
            tooltip=f"🔴 โรงงาน {i+1}",
            icon=folium.Icon(color="red")
        ).add_to(m)

        if "station" in st.session_state:

            dist = math.dist(
                st.session_state.station,
                f
            ) * 111

            folium.PolyLine(
                [st.session_state.station,f],
                color="blue",
                weight=2,
                tooltip=f"{dist:.2f} km"
            ).add_to(m)

# ---------------- Legend ----------------

legend_html = """
<div style="
position: fixed;
bottom: 40px;
left: 40px;
width: 200px;
background-color: white;
border:2px solid grey;
z-index:9999;
padding:10px;
border-radius:8px;
font-size:14px;
">

<b>คำอธิบายแผนที่</b><br><br>

🟢 จุดตรวจวัด<br>
🔴 โรงงาน<br>
🔵 เส้นระยะทาง

</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))

map_data = st_folium(m,height=520,width=1200)

# ---------------- คลิกแผนที่ ----------------

if map_data["last_clicked"]:

    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    if pin_mode == "จุดตรวจวัด":

        st.session_state.station=(lat,lon)

    else:

        if "factories" not in st.session_state:
            st.session_state.factories=[]

        st.session_state.factories.append((lat,lon))

# ---------------- API ----------------

@st.cache_data
def fetch_api(lat,lon,start_date,num_days):

    sd=start_date.strftime("%Y-%m-%d")
    ed=(start_date+timedelta(days=num_days-1)).strftime("%Y-%m-%d")

    weather=requests.get(
f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
).json()

    air=requests.get(
f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
).json()

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

# ---------------- Run Simulation ----------------

if st.button("🚀 เริ่มจำลองข้อมูล"):

    if "station" not in st.session_state:
        st.warning("กรุณาปักจุดตรวจวัดก่อน")
        st.stop()

    station = st.session_state.station

    ref_df = fetch_api(station[0],station[1],start_date,num_days)

    rows=[]

    for i in range(num_days):

        date=start_date+timedelta(days=i)

        for h in range(24):

            r=ref_df.iloc[h]

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

        df.to_excel(writer,index=False,sheet_name="Simulated Data")
        ref_df.to_excel(writer,index=False,sheet_name="Reference Data")

    st.download_button(
        "📥 ดาวน์โหลด Excel",
        buf.getvalue(),
        file_name="AirCheckTH.xlsx"
    )
