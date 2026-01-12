import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime, timedelta
from io import BytesIO

# ---------- SAFE IMPORT ----------
try:
    from meteostat import Point, Hourly
    METEOSTAT_OK = True
except ImportError:
    METEOSTAT_OK = False

# ---------- CONFIG ----------
st.set_page_config(page_title="AirCheck TH", layout="wide")
st.title("🌍 AirCheck TH - ระบบประเมินคุณภาพอากาศจำลอง (รายชั่วโมง)")

if not METEOSTAT_OK:
    st.error("❌ ไม่พบ library 'meteostat' กรุณาตรวจสอบ requirements.txt")
    st.stop()

# ---------- PROVINCE ----------
province = st.selectbox(
    "📍 จังหวัด",
    ["กรุงเทพมหานคร", "ระยอง", "อยุธยา", "สระบุรี", "ราชบุรี", "ชลบุรี", "จันทบุรี"]
)

province_coords = {
    "กรุงเทพมหานคร": (13.7563, 100.5018),
    "ระยอง": (12.6814, 101.2770),
    "อยุธยา": (14.3532, 100.5689),
    "สระบุรี": (14.5289, 100.9105),
    "ราชบุรี": (13.5360, 99.8171),
    "ชลบุรี": (13.3611, 100.9847),
    "จันทบุรี": (12.6112, 102.1035),
}
lat, lon = province_coords[province]

# ---------- USER INPUT ----------
start_date = st.date_input("📅 วันที่เริ่มต้น", datetime.now().date())
num_days = st.slider("จำนวนวัน (1–8)", 1, 8, 1)

factory_direction = st.selectbox("🏭 ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])
near_road = st.checkbox("ใกล้ถนน")
near_factory = st.checkbox("ใกล้โรงงาน")

params = st.multiselect(
    "พารามิเตอร์",
    ["NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"],
    default=["NO", "NO2", "NOx", "WS", "WD", "Temp", "RH"]
)

# ---------- DAILY SITUATION ----------
sit_options = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "มีการเผาขยะ"]
}

day_situations = []
for i in range(num_days):
    with st.expander(f"วันที่ {i+1}"):
        sit = {"ทิศลม": st.selectbox("ทิศลม", ["NE", "NW", "SE", "SW"], key=f"wd_{i}")}
        for k, v in sit_options.items():
            sit[k] = st.selectbox(k, v, key=f"{k}_{i}")
        day_situations.append(sit)

# ---------- FETCH METEOSTAT ----------
@st.cache_data(show_spinner=False)
def get_weather(lat, lon, start_date, num_days):
    loc = Point(lat, lon)
    start = datetime.combine(start_date, datetime.min.time())
    end = start + timedelta(days=num_days)
    df = Hourly(loc, start, end).fetch()

    df["wspd"].fillna(2.5, inplace=True)
    df["wdir"].fillna(90, inplace=True)
    df["temp"].fillna(27, inplace=True)
    df["rhum"].fillna(65, inplace=True)
    return df

# ---------- FETCH OPEN-METEO AQ ----------
@st.cache_data(show_spinner=False)
def get_aq(lat, lon, start_date, num_days):
    sd = start_date.strftime("%Y-%m-%d")
    ed = (start_date + timedelta(days=num_days - 1)).strftime("%Y-%m-%d")

    url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={sd}&end_date={ed}"
        f"&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
    )
    r = requests.get(url, timeout=20)
    if not r.ok:
        return pd.DataFrame()

    j = r.json()["hourly"]
    return pd.DataFrame({
        "time": pd.to_datetime(j["time"]),
        "NO2": j["nitrogen_dioxide"],
        "SO2": j["sulphur_dioxide"],
        "CO": j["carbon_monoxide"],
        "O3": j["ozone"]
    }).set_index("time")

weather = get_weather(lat, lon, start_date, num_days)
aq_ref = get_aq(lat, lon, start_date, num_days)

# ---------- SIMULATE ----------
wd_map = {"NE": 45, "SE": 135, "SW": 225, "NW": 315}

def simulate(var, sit, hour, ref, aq):
    mult = 1.0
    add = 0.0

    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]:
        mult *= 0.6

    if sit["ลม"] == "นิ่ง/ไม่มีลม":
        mult *= 1.3

    if sit["อื่นๆ"] == "รถเยอะ" and var in ["NO", "NO2", "CO"]:
        mult *= 1.4

    # rush hour
    if hour in range(7, 10) or hour in range(16, 20):
        if var in ["NO", "NO2", "CO"]:
            mult *= 1.3

    if var == "NO":
        base = random.uniform(5, 20)
        return round(base * mult, 2)

    if var in ["NO2", "SO2", "CO", "O3"]:
        base = aq if aq is not None else random.uniform(5, 30)
        return round(base * mult, 2)

    if var == "WS":
        return round(max(0.5, ref * random.uniform(0.6, 0.9)), 2)

    if var == "WD":
        return wd_map[sit["ทิศลม"]]

    if var == "Temp":
        return round(ref + random.uniform(-2, 2), 2)

    if var == "RH":
        return round(min(100, ref + random.uniform(-10, 10)), 2)

    if var == "Pressure":
        return round(1010 + random.uniform(-5, 5), 2)

# ---------- GENERATE ----------
if st.button("📊 สร้างข้อมูลและดาวน์โหลด Excel"):
    rows = []

    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = day_situations[i]

        for h in range(24):
            t = datetime.combine(date, datetime.min.time()) + timedelta(hours=h)

            w = weather.loc[t] if t in weather.index else None
            aq = aq_ref.loc[t] if t in aq_ref.index else None

            row = {"Date": date, "Hour": h}

            for p in params:
                if p == "NOx":
                    continue
                ref = w["wspd"] if w is not None and p == "WS" else \
                      w["wdir"] if w is not None and p == "WD" else \
                      w["temp"] if w is not None and p == "Temp" else \
                      w["rhum"] if w is not None and p == "RH" else None

                aqv = aq[p] if aq is not None and p in aq else None
                row[p] = simulate(p, sit, h, ref, aqv)

            if "NOx" in params:
                row["NOx"] = round(row.get("NO", 0) + row.get("NO2", 0), 2)

            rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df.head(48))

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)

    st.download_button(
        "📥 ดาวน์โหลด Excel",
        buf.getvalue(),
        file_name="AirCheckTH.xlsx"
    )
