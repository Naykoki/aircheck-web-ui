import streamlit as st
import pandas as pd
import requests
import random
import folium
import math
from datetime import datetime, timedelta
from io import BytesIO
from streamlit_folium import st_folium

st.set_page_config(page_title="AirCheck TH", layout="wide")

st.title("🌏 AirCheck TH – Air Quality Simulation Dashboard")

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

st.sidebar.header("⚙ Simulation Settings")

province = st.sidebar.selectbox(
"จังหวัด",
list(province_coords.keys())
)

center_lat,center_lon = province_coords[province]

start_date = st.sidebar.date_input(
"วันที่เริ่มต้น",
datetime.now().date()
)

num_days = st.sidebar.slider(
"จำนวนวัน",
1,7,1
)

near_road = st.sidebar.checkbox("ใกล้ถนนใหญ่")
near_community = st.sidebar.checkbox("ใกล้ชุมชน")

station_type = st.sidebar.selectbox(
"ประเภทสถานี",
["วัด","โรงเรียน","ชุมชน","โรงพยาบาล","อุตสาหกรรม"]
)

# ---------------- Search ----------------

def search_places(query):

    url="https://photon.komoot.io/api/"

    params={
        "q": query + " " + province,
        "limit": 5
    }

    try:

        res=requests.get(url,params=params,timeout=10).json()

        results=[]

        for item in res["features"]:

            name=item["properties"].get("name","")
            city=item["properties"].get("city","")

            lat=item["geometry"]["coordinates"][1]
            lon=item["geometry"]["coordinates"][0]

            label=f"{name} {city}"

            results.append({
                "label":label,
                "lat":lat,
                "lon":lon
            })

        return results

    except:
        return []

st.subheader("🔎 ค้นหาสถานที่")

search_text=st.text_input("พิมพ์ชื่อสถานที่")

if len(search_text)>=2:

    results=search_places(search_text)

    options=[r["label"] for r in results]

    if options:

        choice=st.selectbox("เลือกสถานที่",options)

        col1,col2=st.columns(2)

        with col1:

            if st.button("📍 ตั้งเป็น Station"):

                for r in results:

                    if r["label"]==choice:

                        st.session_state.station=(r["lat"],r["lon"])
                        st.rerun()

        with col2:

            if st.button("🏭 เพิ่ม Factory"):

                for r in results:

                    if r["label"]==choice:

                        if "factories" not in st.session_state:
                            st.session_state.factories=[]

                        st.session_state.factories.append((r["lat"],r["lon"]))
                        st.rerun()

# ---------------- Map ----------------

if "station" in st.session_state:
    map_center=st.session_state.station
else:
    map_center=[center_lat,center_lon]

m=folium.Map(location=map_center,zoom_start=12,tiles="CartoDB positron")

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

map_data=st_folium(m,height=450,width=1200)

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

# ---------------- Run ----------------

if st.button("🚀 Run Simulation"):

    station=st.session_state.get("station")

    if not station:
        st.warning("กรุณาตั้ง Station ก่อน")
        st.stop()

    ref_df=fetch_api(station[0],station[1],start_date,num_days)

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

    # KPI

    col1,col2,col3,col4=st.columns(4)

    col1.metric("NO2 Avg",round(df["NO2"].mean(),2))
    col2.metric("SO2 Avg",round(df["SO2"].mean(),2))
    col3.metric("CO Avg",round(df["CO"].mean(),2))
    col4.metric("O3 Avg",round(df["O3"].mean(),2))

    st.subheader("📊 Pollution Dashboard")

    st.line_chart(df.set_index("Hour")[["NO2","SO2","CO","O3"]])

    st.subheader("📄 Data Table")

    st.dataframe(df)

    buf=BytesIO()

    with pd.ExcelWriter(buf,engine="openpyxl") as writer:

        df.to_excel(writer,index=False,sheet_name="Simulated Data")

        ref_df.to_excel(writer,index=False,sheet_name="Reference Data")

    st.download_button(
        "📥 Download Excel",
        buf.getvalue(),
        file_name="AirCheckTH.xlsx"
    )
