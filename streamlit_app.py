import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime, timedelta
from io import BytesIO

# ---------------------- CONFIG ----------------------
st.set_page_config(page_title="AirCheck TH (Web)", layout="wide")
st.image("logo.png", width=100)
st.title("AirCheck TH - Web Version")

# ---------------------- LOGIN ----------------------
if "username" not in st.session_state:
    st.session_state["username"] = ""

with st.sidebar:
    st.header("🔐 เข้าสู่ระบบ")
    username = st.text_input("ชื่อผู้ใช้")
    if st.button("เข้าสู่ระบบ"):
        st.session_state["username"] = username

if st.session_state["username"] == "":
    st.warning("กรุณาเข้าสู่ระบบก่อนใช้งาน")
    st.stop()

role = "admin" if st.session_state["username"].strip().lower() == "siwanon" else "user"
st.sidebar.success(f"👤 {st.session_state['username']} ({role})")

# ---------------------- Province Selector ----------------------
province = st.selectbox("📍 เลือกจังหวัด", [
    "กรุงเทพมหานคร", "ระยอง", "ชลบุรี", "จันทบุรี", "อยุธยา", "สระบุรี", "ราชบุรี"
])

# ---------------------- พารามิเตอร์ที่ต้องการคำนวณ ----------------------
params_to_calculate = st.multiselect("📊 เลือกพารามิเตอร์ที่ต้องการคำนวณ", [
    "NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"
], default=["NO", "NO2", "NOx", "WS", "WD", "Temp", "RH", "Pressure"])

# ---------------------- วันที่และสถานการณ์ ----------------------
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 วันที่เริ่มต้น", datetime.today())
    num_days = st.slider("จำนวนวัน (1-8)", 1, 8, 3)
    factory_direction = st.selectbox("🏭 ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])
with col2:
    near_road = st.checkbox("ใกล้ถนน")
    near_factory = st.checkbox("ใกล้โรงงาน")

# ---------------------- Get OpenWeather Reference ----------------------
def get_openweather(province):
    try:
        api_key = st.secrets["OPENWEATHER_API"]
        url = f"https://api.openweathermap.org/data/2.5/weather?q={province},TH&appid={api_key}&units=metric"
        res = requests.get(url)
        data = res.json()
        return {
            "Temp": data["main"]["temp"],
            "RH": data["main"]["humidity"],
            "WS": data["wind"]["speed"]
        }
    except:
        return {"Temp": 27.0, "RH": 65.0, "WS": 2.5}

ref_data = get_openweather(province)

# ---------------------- สถานการณ์รายวัน ----------------------
sit_options = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["ไม่มี", "นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "กลิ่น": ["ไม่มี", "มีกลิ่น"],
    "อุณหภูมิ": ["ไม่มี", "หนาวจัด", "หนาว", "เย็น", "ปกติ", "ร้อน", "ร้อนจัด"],
    "ท้องฟ้า": ["ไม่มี", "แจ่มใส", "มีเมฆบางส่วน", "เมฆมาก"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "มีการเผาขยะ"]
}

st.markdown("### 📌 สถานการณ์รายวัน")
day_situations = []

for i in range(num_days):
    with st.expander(f"วันที่ {i+1}"):
        day_sit = {}
        wind = st.selectbox(f"ทิศลม (วันที่ {i+1})", ["NE", "NW", "SE", "SW"], key=f"wind_{i}")
        day_sit["ทิศลม"] = wind
        for key, options in sit_options.items():
            day_sit[key] = st.selectbox(f"{key} (วันที่ {i+1})", options, key=f"{key}_{i}")
        day_situations.append(day_sit)

# ---------------------- SIMULATE ----------------------
def simulate(var, sit, hour, wind_dir):
    base = random.uniform(2, 6)
    multiplier = 1.0
    add = 0.0

    if sit.get("ฝน") in ["ตกปานกลาง", "ตกหนัก"]: multiplier *= 0.6; add -= 1
    elif sit.get("ฝน") == "ตกเล็กน้อย": multiplier *= 0.85
    if sit.get("แดด") == "แดดแรง": add += 4; multiplier *= 1.1
    elif sit.get("แดด") == "แดดอ่อน": add += 2
    if sit.get("ลม") == "แรง": add += 3 if var == "WS" else 0; multiplier *= 0.7
    elif sit.get("ลม") == "ปานกลาง": add += 1.5 if var == "WS" else 0
    elif sit.get("ลม") == "นิ่ง/ไม่มีลม": multiplier *= 1.3; add -= 0.5
    if sit.get("กลิ่น") == "มีกลิ่น" and var in ["NO2", "SO2", "CO"]: multiplier *= 1.2
    if sit.get("อื่นๆ") == "รถเยอะ" and var in ["NO", "NO2", "CO"]: multiplier *= 1.4
    if sit.get("อื่นๆ") == "มีการเผาขยะ" and var in ["CO", "O3", "SO2"]: multiplier *= 1.3
    if near_road and var in ["NO", "NO2", "CO"]: multiplier *= 1.25
    if near_factory and wind_dir == factory_direction and var in ["NO2", "SO2"]: multiplier *= 1.5

    if var == "NO": return round(base * multiplier + add + random.uniform(0.5, 2.5), 2)
    if var == "NO2": return round(min(20, base * multiplier + add + random.uniform(0.8, 2.8)), 2)
    if var == "NOx": return None
    if var == "Temp": return round(ref_data.get("Temp", 27) + add + random.uniform(-2, 2), 2)
    if var == "RH": return round(ref_data.get("RH", 65) + add + random.uniform(-12, 15), 2)
    if var == "WS": return round(min(4, ref_data.get("WS", 2.5) + add + random.uniform(-1.5, 1.5)), 2)
    if var == "Pressure": return round(1010 + random.uniform(-6, 6), 2)
    if var == "SO2": return round(base * multiplier + add + random.uniform(0.6, 2.2), 2)
    if var == "CO": return round(base * multiplier + add + random.uniform(0.1, 1.0), 2)
    if var == "O3": return round(30 + add + random.uniform(5, 25), 2)

# ---------------------- GENERATE ----------------------
if st.button("🚀 สร้างตารางข้อมูลและดาวน์โหลด Excel"):
    records = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = day_situations[i]
        wind_dir = sit.get("ทิศลม", "NE")
        for hour in range(24):
            row = {
                "Date": date.strftime("%Y-%m-%d"),
                "Time": f"{hour:02d}:00:00",
                "WD": wind_dir
            }
            for param in params_to_calculate:
                if param == "NOx": continue
                row[param] = simulate(param, sit, hour, wind_dir)
            if "NO" in row and "NO2" in row and "NOx" in params_to_calculate:
                row["NOx"] = round(row["NO"] + row["NO2"], 2)
            records.append(row)

    df = pd.DataFrame(records)
    st.success(f"✅ ข้อมูลจากจังหวัด {province} {'(อ้างอิงจาก API)' if ref_data else '(คำนวณจำลอง)'}")
    st.dataframe(df.head(48))

    file_name = f"AirCheck_{province}_{start_date.strftime('%Y%m%d')}_{(start_date + timedelta(days=num_days-1)).strftime('%Y%m%d')}.xlsx"
    output = BytesIO()
    df.to_excel(output, index=False)
    st.download_button("📥 ดาวน์โหลด Excel", data=output.getvalue(), file_name=file_name)

