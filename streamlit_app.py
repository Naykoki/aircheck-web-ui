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

st.title("🌏 AirCheck TH – Air Quality Simulation Platform")

# ================= Sidebar =================

st.sidebar.header("⚙ Simulation Settings")

start_date = st.sidebar.date_input("Start Date", datetime.now().date())
num_days = st.sidebar.slider("Days",1,7,1)

near_road = st.sidebar.checkbox("Near Major Road")
near_community = st.sidebar.checkbox("Near Community")

station_type = st.sidebar.selectbox(
"Station Type",
["Temple","School","Community","Hospital","Industrial"]
)

# ================= Map =================

st.subheader("🗺 Select Locations")

st.write("Click map to choose **Station** and **Factory**")

map_center = [13.75,100.50]

m = folium.Map(location=map_center, zoom_start=10)

map_data = st_folium(m,height=500,width=900)

station = None
factory = None

if map_data["last_clicked"]:

    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    if "station_set" not in st.session_state:
        st.session_state.station = (lat,lon)
        st.session_state.station_set = True
        st.success("Station location set")

    else:
        st.session_state.factory = (lat,lon)
        st.success("Factory location set")

station = st.session_state.get("station")
factory = st.session_state.get("factory")

if station:
    st.write("Station:",station)

if factory:
    st.write("Factory:",factory)

# ================= Distance + Bearing =================

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

def distance_km(lat1,lon1,lat2,lon2):

    R=6371

    dlat=math.radians(lat2-lat1)
    dlon=math.radians(lon2-lon1)

    a=math.sin(dlat/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2

    c=2*math.atan2(math.sqrt(a),math.sqrt(1-a))

    return R*c

bearing=None
distance=None

if station and factory:

    bearing=calculate_bearing(
        station[0],station[1],
        factory[0],factory[1]
    )

    distance=distance_km(
        station[0],station[1],
        factory[0],factory[1]
    )

    st.info(f"Factory direction: {bearing:.1f}°")
    st.info(f"Distance: {distance:.2f} km")

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

    multiplier=1.0

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
"Temple":0.85,
"Hospital":0.9,
"Community":1.0,
"School":1.05,
"Industrial":1.2
}

    multiplier*=station_factor[station_type]

    ref=row.get(f"{var}_ref",random.uniform(5,20))

    return round(ref*multiplier,2)

# ================= Generate =================

if st.button("🚀 Run Simulation"):

    if not station:
        st.warning("Please select station on map")
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

    st.subheader("📊 Pollution Dashboard")

    st.line_chart(df.set_index("Hour")[["NO2","SO2","CO","O3"]])

    st.dataframe(df.head(48))

    buf=BytesIO()

    with pd.ExcelWriter(buf,engine="openpyxl") as writer:
        df.to_excel(writer,index=False)

    st.download_button(
"📥 Download Excel",
buf.getvalue(),
file_name="AirCheckTH_v5.xlsx"
)
