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

# ---------------- Google API ----------------

GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY","")

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

# ---------------- Google Search ----------------

def google_search(place):

    if GOOGLE_API_KEY == "":
        return None

    url="https://maps.googleapis.com/maps/api/geocode/json"

    params={
        "address":place,
        "key":GOOGLE_API_KEY
    }

    try:

        res=requests.get(url,params=params,timeout=10).json()

        if res["results"]:

            loc=res["results"][0]["geometry"]["location"]

            return loc["lat"],loc["lng"]

    except:
        pass

    return None

# ---------------- Search UI ----------------

st.subheader("🔎 ค้นหาสถานที่")

col1,col2 = st.columns(2)

with col1:

    station_search = st.text_input("ค้นหาจุดตรวจวัด")

    if st.button("📍 ปักจุดตรวจวัด"):

        loc = google_search(station_search)

        if loc:
            st.session_state.station = loc
            st.rerun()
        else:
            st.warning("ไม่พบสถานที่")

with col2:

    factory_search = st.text_input("ค้นหาโรงงาน")

    if st.button("🏭 เพิ่มโรงงาน"):

        loc = google_search(factory_search)

        if loc:

            if "factories" not in st.session_state:
                st.session_state.factories = []

            st.session_state.factories.append(loc)

            st.rerun()

# ---------------- Map ----------------

if "station" in st.session_state:
    map_center = st.session_state.station
else:
    map_center = [center_lat,center_lon]

m = folium.Map(
location=map_center,
zoom_start=12,
tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
attr="Google"
)

if "station" in st.session_state:

    folium.Marker(
        st.session_state.station,
        tooltip="Station",
        icon=folium.Icon(color="green")
    ).add_to(m)

if "factories" in st.session_state:

    for f in st.session_state.factories:

        folium.Marker(
            f,
            tooltip="Factory",
            icon=folium.Icon(color="red")
        ).add_to(m)

map_data = st_folium(m,height=500,width=1200)

# ---------------- click map ----------------

if map_data["last_clicked"]:

    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    if "station" not in st.session_state:
        st.session_state.station=(lat,lon)

    else:

        if "factories" not in st.session_state:
            st.session_state.factories=[]

        st.session_state.factories.append((lat,lon))

# ---------------- Distance ----------------

def distance_km(lat1,lon1,lat2,lon2):

    R=6371

    dlat=math.radians(lat2-lat1)
    dlon=math.radians(lon2-lon1)

    a=math.sin(dlat/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2

    c=2*math.atan2(math.sqrt(a),math.sqrt(1-a))

    return R*c

station = st.session_state.get("station")
factories = st.session_state.get("factories",[])

if station and factories:

    st.subheader("📏 ระยะโรงงาน")

    for i,f in enumerate(factories):

        dist = distance_km(
            station[0],station[1],
            f[0],f[1]
        )

        st.write(f"โรงงาน {i+1}: {dist:.2f} km")

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

    if not station:
        st.warning("กรุณาปักจุดตรวจวัดก่อน")
        st.stop()

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
