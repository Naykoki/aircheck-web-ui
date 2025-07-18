# streamlit_app.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import random
from io import BytesIO
import os

# ---------------------- CONFIG ----------------------
st.set_page_config(page_title="AirCheck TH", layout="wide", page_icon="logo.ico")

# ---------------------- LOGO + LOGIN ----------------------
st.image("logo.ico", width=80)
if "user" not in st.session_state:
    with st.form("login"):
        st.subheader("🔐 เข้าสู่ระบบก่อนใช้งาน")
        user = st.text_input("ชื่อผู้ใช้")
        submit = st.form_submit_button("เข้าสู่ระบบ")
        if submit:
            st.session_state.user = user
            st.experimental_rerun()
    st.stop()

is_admin = st.session_state.user.strip().lower() == "siwanon"
st.sidebar.success(f"👋 ยินดีต้อนรับ {st.session_state.user} {'(Admin)' if is_admin else '(ผู้ใช้งาน)'}")

# ---------------------- API KEYS ----------------------
OPENWEATHER_API = "YOUR_OPENWEATHER_API_KEY"  # ใส่ API KEY ตรงนี้

# ---------------------- จังหวัด และสถานี ----------------------
province_mapping = {
    "กรุงเทพฯ": "Bangkok",
    "ระยอง": "Rayong",
    "ชลบุรี": "Chonburi",
    "อยุธยา": "PhraNakhonSiAyutthaya",
    "สระบุรี": "Saraburi",
    "ราชบุรี": "Ratchaburi",
    "จันทบุรี": "Chanthaburi"
}
province = st.selectbox("เลือกจังหวัดเพื่อดึงข้อมูล", list(province_mapping.keys()))
province_eng = province_mapping[province]

# ---------------------- ดึงข้อมูลจาก API ----------------------
def get_openweather(city="Bangkok"):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city},TH&appid={OPENWEATHER_API}&units=metric"
    try:
        r = requests.get(url)
        data = r.json()
        return {
            "Temp": data["main"]["temp"],
            "RH": data["main"]["humidity"],
            "WS": data["wind"].get("speed", 2.5),
            "WD": data["wind"].get("deg", 0)
        }, "API"
    except:
        return {
            "Temp": 27,
            "RH": 65,
            "WS": 2.5,
            "WD": 90
        }, "ประเมิน"

ref_data, source = get_openweather(province_eng)
st.caption(f"📡 ข้อมูลอ้างอิงจาก: {'OpenWeather API' if source == 'API' else 'ประเมินจากระบบ'}")

# ---------------------- INPUT ----------------------
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 วันที่เริ่มต้น", datetime.today())
    num_days = st.slider("จำนวนวัน", 1, 8, 3)
    factory_dir = st.selectbox("ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])
with col2:
    near_road = st.checkbox("ใกล้ถนน")
    near_factory = st.checkbox("ใกล้โรงงาน")
    params = st.multiselect("พารามิเตอร์ที่ต้องคำนวณ", ["NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"],
                            default=["NO", "NO2", "NOx", "WS", "WD", "Temp", "RH", "Pressure"])

# ---------------------- สถานการณ์รายวัน ----------------------
sit_opts = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["ไม่มี", "นิ่ง", "เบา", "ปานกลาง", "แรง"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "กลิ่น": ["ไม่มี", "มีกลิ่น"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "มีการเผาขยะ"]
}
daily_situations = []
st.markdown("### 🧾 สถานการณ์รายวัน")
for i in range(num_days):
    with st.expander(f"วันที่ {i+1}"):
        sit = {}
        sit["WD"] = st.selectbox(f"ทิศลม (วันที่ {i+1})", ["NE", "NW", "SE", "SW"], key=f"wd_{i}")
        for k, v in sit_opts.items():
            sit[k] = st.selectbox(f"{k} (วันที่ {i+1})", v, key=f"{k}_{i}")
        daily_situations.append(sit)

# ---------------------- SIMULATE ----------------------
def simulate(var, sit, hour, wd, factory_dir):
    base = random.uniform(2, 6)
    mult = 1.0
    add = 0.0

    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]: mult *= 0.6
    if sit["แดด"] == "แดดแรง": add += 3
    if sit["ลม"] == "แรง": mult *= 0.7
    if sit["กลิ่น"] == "มีกลิ่น" and var in ["CO", "SO2"]: mult *= 1.2
    if sit["อื่นๆ"] == "รถเยอะ" and var in ["NO", "NO2"]: mult *= 1.3
    if near_road and var in ["NO", "NO2", "CO"]: mult *= 1.25
    if near_factory and wd == factory_dir and var in ["SO2", "NO2"]: mult *= 1.4

    if var == "NO": return round(base * mult + random.uniform(0.5, 1.5), 2)
    if var == "NO2": return round(min(20, base * mult + random.uniform(1, 3)), 2)
    if var == "NOx": return None
    if var == "Temp": return round(ref_data["Temp"] + add + random.uniform(-2, 2), 2)
    if var == "RH": return round(ref_data["RH"] + random.uniform(-10, 10), 2)
    if var == "WS": return round(min(4, ref_data["WS"] + random.uniform(-1.5, 1.5)), 2)
    if var == "WD": return wd
    if var == "Pressure": return round(1010 + random.uniform(-5, 5), 2)
    if var == "CO": return round(base * mult + random.uniform(0.1, 0.8), 2)
    if var == "SO2": return round(base * mult + random.uniform(0.5, 1.5), 2)
    if var == "O3": return round(25 + add + random.uniform(5, 20), 2)

# ---------------------- GENERATE & EXPORT ----------------------
if st.button("📊 สร้างข้อมูลและดาวน์โหลด Excel"):
    data = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = daily_situations[i]
        wd = sit["WD"]

        for h in range(24):
            row = {"Date": date.strftime("%Y-%m-%d"), "Time": f"{h:02d}:00:00", "WD": wd}
            val_no = simulate("NO", sit, h, wd, factory_dir) if "NO" in params else None
            val_no2 = simulate("NO2", sit, h, wd, factory_dir) if "NO2" in params else None
            row["NO"] = val_no
            row["NO2"] = val_no2
            row["NOx"] = val_no + val_no2 if "NOx" in params and val_no and val_no2 else None

            for p in ["SO2", "CO", "O3", "Temp", "RH", "WS", "Pressure", "WD"]:
                if p in params:
                    row[p] = simulate(p, sit, h, wd, factory_dir)
            data.append(row)

    df = pd.DataFrame(data)
    st.success("✅ สร้างตารางข้อมูลเรียบร้อยแล้ว")
    st.dataframe(df.head(50))

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="AirCheck Data")
    st.download_button("📥 ดาวน์โหลด Excel", data=buffer.getvalue(),
                       file_name=f"AirCheckTH_{province}_{start_date.strftime('%Y%m%d')}.xlsx")
