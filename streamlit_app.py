import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="AirCheck TH", layout="wide")
st.title("🌍 AirCheck TH – Simulation (อ้างอิง + สถานการณ์)")

# ---------------- PROVINCE ----------------
province = st.selectbox("จังหวัด", [
    "กรุงเทพมหานคร", "ระยอง", "อยุธยา", "สระบุรี", "ราชบุรี", "ชลบุรี", "จันทบุรี"
])

coords = {
    "กรุงเทพมหานคร": (13.7563, 100.5018),
    "ระยอง": (12.6814, 101.2770),
    "อยุธยา": (14.3532, 100.5689),
    "สระบุรี": (14.5289, 100.9105),
    "ราชบุรี": (13.5360, 99.8171),
    "ชลบุรี": (13.3611, 100.9847),
    "จันทบุรี": (12.6112, 102.1035)
}
lat, lon = coords[province]

# ---------------- INPUT ----------------
start_date = st.date_input("วันที่เริ่มต้น", datetime.now().date())
num_days = st.slider("จำนวนวัน", 1, 8, 1)

params = st.multiselect(
    "พารามิเตอร์",
    ["NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH"],
    default=["NO", "NO2", "NOx", "WS", "Temp", "RH"]
)

# ---------------- DAILY SITUATION ----------------
sit_options = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "มีการเผาขยะ"]
}

day_situations = []
for i in range(num_days):
    with st.expander(f"วันที่ {i+1}"):
        sit = {}
        sit["ทิศลม"] = st.selectbox("ทิศลม", ["NE", "NW", "SE", "SW"], key=f"wd{i}")
        for k, v in sit_options.items():
            sit[k] = st.selectbox(k, v, key=f"{k}{i}")
        day_situations.append(sit)

# ---------------- FETCH OPEN-METEO ----------------
@st.cache_data(show_spinner=False)
def fetch_ref(lat, lon, start, days):
    sd = start.strftime("%Y-%m-%d")
    ed = (start + timedelta(days=days - 1)).strftime("%Y-%m-%d")

    w_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
        f"&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
    )

    aq_url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
        f"&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
    )

    w = requests.get(w_url).json()["hourly"]
    aq = requests.get(aq_url).json()["hourly"]

    return pd.DataFrame({
        "time": pd.to_datetime(w["time"]),
        "Temp": w["temperature_2m"],
        "RH": w["relative_humidity_2m"],
        "WS": w["wind_speed_10m"],
        "WD": w["wind_direction_10m"],
        "NO2_ref": aq["nitrogen_dioxide"],
        "SO2_ref": aq["sulphur_dioxide"],
        "CO_ref": aq["carbon_monoxide"],
        "O3_ref": aq["ozone"]
    })

ref_df = fetch_ref(lat, lon, start_date, num_days)

# ---------------- SIMULATION ----------------
def simulate(var, sit, hour, ref):
    mult = 1.0

    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]:
        mult *= 0.6
    if sit["ลม"] == "นิ่ง/ไม่มีลม":
        mult *= 1.3
    if sit["อื่นๆ"] == "รถเยอะ" and var in ["NO", "NO2", "CO"]:
        mult *= 1.4
    if hour in range(7,10) or hour in range(16,20):
        if var in ["NO", "NO2", "CO"]:
            mult *= 1.3

    if var == "NO":
        return round(random.uniform(5, 20) * mult, 2)

    if var in ["NO2", "SO2", "CO", "O3"]:
        return round(ref * mult, 2)

    if var == "WS":
        return round(max(0.5, ref * random.uniform(0.7, 1.0)), 2)

    if var == "Temp":
        return round(ref + random.uniform(-2, 2), 2)

    if var == "RH":
        return round(min(100, ref + random.uniform(-8, 8)), 2)

    if var == "WD":
        return ref

# ---------------- GENERATE ----------------
if st.button("📊 สร้างข้อมูล"):
    rows = []

    for i in range(num_days):
        sit = day_situations[i]
        day = start_date + timedelta(days=i)

        for h in range(24):
            t = datetime.combine(day, datetime.min.time()) + timedelta(hours=h)
            r = ref_df.loc[ref_df["time"] == t].iloc[0]

            row = {"DateTime": t}
            for p in params:
                if p == "NOx":
                    continue
                ref = r.get(f"{p}_ref", r.get(p))
                row[p] = simulate(p, sit, h, ref)

            if "NOx" in params:
                row["NOx"] = round(row.get("NO",0) + row.get("NO2",0), 2)

            rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df.head(48))

    buf = BytesIO()
    df.to_excel(buf, index=False)
    st.download_button("📥 ดาวน์โหลด Excel", buf.getvalue(), "AirCheckTH.xlsx")
