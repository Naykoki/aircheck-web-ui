import streamlit as st
import pandas as pd
import random
import requests
import math
from datetime import datetime, timedelta
from io import BytesIO
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="AirCheck TH",layout="wide")

st.title("🌏 AirCheck TH")
st.caption("ระบบจำลองคุณภาพอากาศ")

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
"📍 จังหวัด",
list(province_coords.keys())
)

center_lat,center_lon = province_coords[province]

start_date = st.sidebar.date_input(
"📅 วันที่เริ่มต้น",
datetime.now().date()
)

num_days = st.sidebar.slider(
"จำนวนวัน",
1,8,1
)

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

# ================= MAP =================

st.subheader("🗺 แผนที่")

m = folium.Map(location=[center_lat,center_lon],zoom_start=10)

if "station" in st.session_state:
    folium.Marker(
        st.session_state.station,
        tooltip="จุดตรวจวัด",
        icon=folium.Icon(color="green")
    ).add_to(m)

if "factory" in st.session_state:
    folium.Marker(
        st.session_state.factory,
        tooltip="โรงงาน",
        icon=folium.Icon(color="red")
    ).add_to(m)

map_data = st_folium(m,height=500,width=1200)

if map_data["last_clicked"]:

    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    if pin_mode=="ปักจุดตรวจวัด":
        st.session_state.station=(lat,lon)

    if pin_mode=="ปักโรงงาน":
        st.session_state.factory=(lat,lon)

station = st.session_state.get("station")
factory = st.session_state.get("factory")

# ================= ค้นหาตำแหน่ง =================

st.subheader("🔎 ค้นหาตำแหน่ง")

def search_location(query):

    url="https://nominatim.openstreetmap.org/search"

    params={
    "q":query,
    "format":"json",
    "limit":1
    }

    headers={"User-Agent":"aircheck"}

    res=requests.get(url,params=params,headers=headers).json()

    if res:
        lat=float(res[0]["lat"])
        lon=float(res[0]["lon"])
        return lat,lon

    return None


col1,col2=st.columns(2)

with col1:

    station_search=st.text_input("ค้นหาจุดตรวจวัด")

    if st.button("ปักจุดตรวจวัดจากการค้นหา"):

        loc=search_location(station_search)

        if loc:
            st.session_state.station=loc
            st.success("ตั้งค่าจุดตรวจวัดแล้ว")

with col2:

    factory_search=st.text_input("ค้นหาโรงงาน")

    if st.button("ปักโรงงานจากการค้นหา"):

        loc=search_location(factory_search)

        if loc:
            st.session_state.factory=loc
            st.success("ตั้งค่าโรงงานแล้ว")

# ================= Bearing =================

def calculate_bearing(lat1,lon1,lat2,lon2):

    lat1=math.radians(lat1)
    lat2=math.radians(lat2)

    diffLong=math.radians(lon2-lon1)

    x=math.sin(diffLong)*math.cos(lat2)

    y=math.cos(lat1)*math.sin(lat2)-(
        math.sin(lat1)*math.cos(lat2)*math.cos(diffLong)
    )

    bearing=math.degrees(math.atan2(x,y))
    bearing=(bearing+360)%360

    return bearing

bearing=None

if station and factory:

    bearing=calculate_bearing(
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

# ================= Simulation =================

def simulate(var,hour,row):

    multiplier=1

    ws=row.get("WS",random.uniform(0.5,5))
    wd=row.get("WD",random.uniform(0,360))
    temp=row.get("Temp",random.uniform(25,35))

    if ws<1.5:
        multiplier*=1.3

    if near_road and var in ["NO","NO2","CO"]:
        multiplier*=1.4

    if near_community and var in ["NO2","CO"]:
        multiplier*=1.2

    if near_factory and bearing and abs(wd-bearing)<20:
        multiplier*=1.6

    if hour in range(7,10) or hour in range(16,20):
        if var in ["NO","NO2","CO"]:
            multiplier*=1.3

    station_factor={
"วัด":0.85,
"โรงเรียน":1.05,
"ชุมชน":1.0,
"โรงพยาบาล":0.9,
"อุตสาหกรรม":1.2
}

    multiplier*=station_factor[station_type]

    if var=="NO":
        base=random.uniform(5,20)

    elif var in ["NO2","SO2","CO","O3"]:
        base=row.get(f"{var}_ref",random.uniform(5,20))

    elif var=="WS":
        base=ws

    elif var=="WD":
        base=wd

    elif var=="Temp":
        base=temp

    elif var=="RH":
        base=row.get("RH",random.uniform(40,90))

    elif var=="Pressure":
        base=1010+random.uniform(-5,5)

    else:
        base=random.uniform(5,20)

    return round(base*multiplier,2)

# ================= Generate =================

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

            row={"Date":date,"Hour":h}

            for p in params:

                if p=="NOx":
                    continue

                row[p]=simulate(p,h,r)

            if "NOx" in params:
                row["NOx"]=round(row.get("NO",0)+row.get("NO2",0),2)

            rows.append(row)

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
