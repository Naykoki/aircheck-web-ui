import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="AirCheck TH v2", layout="wide")

st.title("🌏 AirCheck TH v2")
st.caption("Air Quality Scenario Generator")

# ================= Province =================

province = st.selectbox("📍 จังหวัด",[
"กรุงเทพมหานคร","ระยอง","อยุธยา","สระบุรี",
"ราชบุรี","ชลบุรี","จันทบุรี"
])

coords = {
"กรุงเทพมหานคร":(13.7563,100.5018),
"ระยอง":(12.6814,101.2770),
"อยุธยา":(14.3532,100.5689),
"สระบุรี":(14.5289,100.9105),
"ราชบุรี":(13.5360,99.8171),
"ชลบุรี":(13.3611,100.9847),
"จันทบุรี":(12.6112,102.1035)
}

lat,lon = coords[province]

start_date = st.date_input("📅 วันที่เริ่มต้น",datetime.now().date())
num_days = st.slider("จำนวนวัน",1,7,1)

st.divider()

# ================= Area =================

st.subheader("📍 ลักษณะพื้นที่")

col1,col2,col3 = st.columns(3)

with col1:
    near_road = st.checkbox("🚗 ใกล้ถนนใหญ่")

with col2:
    near_factory = st.checkbox("🏭 ใกล้โรงงาน")

with col3:
    near_community = st.checkbox("🏘 ใกล้ชุมชน")

factory_direction = st.selectbox(
"🏭 โรงงานอยู่ทิศอะไรจากจุดตรวจ",
["N","NE","E","SE","S","SW","W","NW"]
)

station_type = st.selectbox(
"🏫 ประเภทสถานี",
["วัด","โรงเรียน","ชุมชน","โรงพยาบาล","อุตสาหกรรม"]
)

params = st.multiselect(
"📌 Parameter",
["NO","NO2","NOx","SO2","CO","O3","WS","WD","Temp","RH","Pressure"],
default=["NO","NO2","NOx","SO2","CO","O3","WS","WD","Temp","RH"]
)

# ================= API =================

@st.cache_data
def fetch_api(lat,lon,start_date,num_days):

    sd = start_date.strftime("%Y-%m-%d")
    ed = (start_date+timedelta(days=num_days-1)).strftime("%Y-%m-%d")

    weather = requests.get(
f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
).json()["hourly"]

    air = requests.get(
f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
).json()["hourly"]

    df = pd.DataFrame({
"time":pd.to_datetime(weather["time"]),
"Temp":weather["temperature_2m"],
"RH":weather["relative_humidity_2m"],
"WS":weather["wind_speed_10m"],
"WD":weather["wind_direction_10m"],
"NO2_ref":air["nitrogen_dioxide"],
"SO2_ref":air["sulphur_dioxide"],
"CO_ref":air["carbon_monoxide"],
"O3_ref":air["ozone"]
})

    return df

ref_df = fetch_api(lat,lon,start_date,num_days)

# ================= Wind check =================

def wind_hits_factory(wd,dir):

    sector={
"N":(337.5,22.5),
"NE":(22.5,67.5),
"E":(67.5,112.5),
"SE":(112.5,157.5),
"S":(157.5,202.5),
"SW":(202.5,247.5),
"W":(247.5,292.5),
"NW":(292.5,337.5)
}

    low,high=sector[dir]

    if low<high:
        return low<=wd<high
    else:
        return wd>=low or wd<high

# ================= Simulation =================

def simulate(var,hour,row):

    multiplier=1.0

    ws=row["WS"]
    wd=row["WD"]
    temp=row["Temp"]

    if ws<1.5:
        multiplier*=1.3

    if ws>5:
        multiplier*=0.8

    if near_road and var in ["NO","NO2","CO"]:
        multiplier*=random.uniform(1.2,1.5)

    if near_community and var in ["NO2","CO"]:
        multiplier*=random.uniform(1.1,1.3)

    if near_factory and wind_hits_factory(wd,factory_direction):
        if var in ["SO2","NO2"]:
            multiplier*=random.uniform(1.3,2.0)

    if hour in range(7,10) or hour in range(16,20):
        if var in ["NO","NO2","CO"]:
            multiplier*=random.uniform(1.2,1.6)

    station_factor={
"วัด":0.85,
"โรงพยาบาล":0.9,
"ชุมชน":1.0,
"โรงเรียน":1.05,
"อุตสาหกรรม":1.2
}

    multiplier*=station_factor[station_type]

    ref=row.get(f"{var}_ref",row.get(var))

    return round(ref*multiplier,2)

# ================= Generate =================

if st.button("📊 Generate Data"):

    rows=[]

    for i in range(num_days):

        date=start_date+timedelta(days=i)

        for h in range(24):

            t=datetime.combine(date,datetime.min.time())+timedelta(hours=h)

            match=ref_df.loc[ref_df["time"]==t]

            if match.empty:
                continue

            r=match.iloc[0]

            row={"Date":date,"Time":f"{h:02d}:00"}

            for p in params:

                if p=="NOx":
                    continue

                row[p]=simulate(p,h,r)

            if "NOx" in params:
                row["NOx"]=round(row.get("NO",0)+row.get("NO2",0),2)

            rows.append(row)

    df=pd.DataFrame(rows)

    st.dataframe(df.head(48))

    buf=BytesIO()

    with pd.ExcelWriter(buf,engine="openpyxl") as writer:

        df.to_excel(writer,index=False,sheet_name="Simulated")

        ref_df.to_excel(writer,index=False,sheet_name="Reference")

    st.download_button(
"📥 Download Excel",
buf.getvalue(),
file_name="AirCheckTH_v2.xlsx"
)
