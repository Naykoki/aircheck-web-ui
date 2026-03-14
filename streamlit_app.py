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

st.title("🌏 AirCheck TH – ระบบจำลองคุณภาพอากาศ")

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

# ================= Sidebar =================

st.sidebar.header("⚙ การตั้งค่า")

province = st.sidebar.selectbox(
"📍 เลือกจังหวัด",
list(province_coords.keys())
)

center_lat,center_lon = province_coords[province]

start_date = st.sidebar.date_input("📅 วันที่เริ่มต้น",datetime.now().date())

num_days = st.sidebar.slider("จำนวนวัน",1,8,1)

near_road = st.sidebar.checkbox("🚗 ใกล้ถนนใหญ่")
near_factory = st.sidebar.checkbox("🏭 ใกล้โรงงาน")
near_community = st.sidebar.checkbox("🏘 ใกล้ชุมชน")

station_type = st.sidebar.selectbox(
"🏫 ประเภทสถานี",
["วัด","โรงเรียน","ชุมชน","โรงพยาบาล","อุตสาหกรรม"]
)

params = st.sidebar.multiselect(
"📊 Parameter",
["NO","NO2","NOx","SO2","CO","O3","WS","WD","Temp","RH","Pressure"],
default=["NO","NO2","NOx","SO2","CO","O3","WS","WD","Temp","RH"]
)

pin_mode = st.sidebar.radio(
"📌 โหมดปักหมุด",
["ปักจุดตรวจวัด","ปักโรงงาน"]
)

# ================= SEARCH =================

def search_location(query):

    url="https://photon.komoot.io/api/"

    params={"q":query,"limit":1}

    try:

        res=requests.get(url,params=params,timeout=10)

        if res.status_code!=200:
            return None

        data=res.json()

        if "features" in data and len(data["features"])>0:

            lon,lat=data["features"][0]["geometry"]["coordinates"]

            return lat,lon

    except:
        return None

    return None


st.subheader("🔎 ค้นหาสถานที่")

col1,col2 = st.columns(2)

with col1:

    station_search = st.text_input("ค้นหาจุดตรวจวัด")

    if st.button("📍 ปักจุดตรวจวัด"):

        loc = search_location(station_search)

        if loc:
            st.session_state.station = loc
            st.rerun()
        else:
            st.warning("ไม่พบสถานที่")

with col2:

    factory_search = st.text_input("ค้นหาโรงงาน")

    if st.button("🏭 เพิ่มโรงงาน"):

        loc = search_location(factory_search)

        if loc:

            if "factories" not in st.session_state:
                st.session_state.factories=[]

            st.session_state.factories.append(loc)

            st.rerun()

        else:
            st.warning("ไม่พบสถานที่")

# ================= Map =================

if "station" in st.session_state:
    map_center = st.session_state.station
else:
    map_center = [center_lat,center_lon]

m = folium.Map(
    location=map_center,
    zoom_start=12,
    tiles="CartoDB positron"
)

if "station" in st.session_state:

    folium.Marker(
        st.session_state.station,
        tooltip="จุดตรวจวัด",
        icon=folium.Icon(color="green")
    ).add_to(m)

if "factories" in st.session_state:

    for f in st.session_state.factories:

        folium.Marker(
            f,
            tooltip="โรงงาน",
            icon=folium.Icon(color="red")
        ).add_to(m)

map_data = st_folium(m,height=500,width=1200)

# click map

if map_data["last_clicked"]:

    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    if pin_mode=="ปักจุดตรวจวัด":
        st.session_state.station=(lat,lon)

    else:

        if "factories" not in st.session_state:
            st.session_state.factories=[]

        st.session_state.factories.append((lat,lon))

# ================= Distance =================

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

# ================= API =================

@st.cache_data
def fetch_api(lat,lon,start_date,num_days):

    sd=start_date.strftime("%Y-%m-%d")

    ed=(start_date+timedelta(days=num_days-1)).strftime("%Y-%m-%d")

    weather=requests.get(
f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok",
timeout=10
).json()

    air=requests.get(
f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok",
timeout=10
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

# ================= Simulation =================

def simulate(var,hour,row):

    multiplier=1

    ws=row.get("WS",random.uniform(0.5,5))
    wd=row.get("WD",random.uniform(0,360))

    if ws<1.5:
        multiplier*=1.3

    if near_road and var in ["NO","NO2","CO"]:
        multiplier*=1.4

    if near_community and var in ["NO2","CO"]:
        multiplier*=1.2

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

    base=row.get(f"{var}_ref",random.uniform(5,20))

    return round(base*multiplier,2)

# ================= RUN =================

if st.button("🚀 เริ่มจำลองข้อมูล"):

    if not station:
        st.warning("กรุณาปักจุดตรวจวัดก่อน")
        st.stop()

    ref_df = fetch_api(station[0],station[1],start_date,num_days)

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

    st.line_chart(df.set_index("Hour")[["NO2","SO2","CO","O3"]])

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
