import streamlit as st
import pandas as pd
import requests
import random
from datetime import datetime, timedelta
from io import BytesIO

# ---------------------- CONFIG ----------------------
st.set_page_config(page_title="AirCheck TH", layout="wide")
st.image("logo.png", width=100)
st.title("🌍 AirCheck TH - ระบบคำนวณมลพิษบนเว็บ")

# ---------------------- LOGIN ----------------------
if "username" not in st.session_state:
    st.session_state.username = ""

if st.session_state.username == "":
    with st.form("login"):
        st.subheader("🔐 เข้าสู่ระบบ")
        username = st.text_input("ชื่อผู้ใช้")
        submitted = st.form_submit_button("เข้าสู่ระบบ")
        if submitted:
            st.session_state.username = username.strip()
            st.experimental_rerun()
    st.stop()

is_admin = st.session_state.username.lower() == "siwanon"
st.sidebar.success(f"👋 ยินดีต้อนรับ {st.session_state.username} ({'admin' if is_admin else 'user'})")

# ---------------------- GET WEATHER DATA ----------------------
@st.cache_data(ttl=1800)
def get_weather_from_openweather(province):
    api_key = st.secrets["OPENWEATHER_API"]
    url = f"https://api.openweathermap.org/data/2.5/weather?q={province},TH&appid={api_key}&units=metric"
    try:
        res = requests.get(url)
        data = res.json()
        return {
            "Temp": data["main"]["temp"],
            "RH": data["main"]["humidity"],
            "WS": data["wind"]["speed"]
        }
    except:
        return None

# ---------------------- INPUT ----------------------
col1, col2 = st.columns(2)
with col1:
    province = st.selectbox("เลือกจังหวัด", ["Bangkok", "Rayong", "Ayutthaya", "Chonburi", "Ratchaburi", "Saraburi", "Chanthaburi"])
    start_date = st.date_input("วันที่เริ่มต้น", datetime.today())
    num_days = st.slider("จำนวนวัน", 1, 8, 3)
with col2:
    factory_direction = st.selectbox("ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])
    near_road = st.checkbox("ใกล้ถนน")
    near_factory = st.checkbox("ใกล้โรงงาน")

params = st.multiselect("เลือกพารามิเตอร์ที่ต้องการคำนวณ", [
    "NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"
], default=["NO", "NO2", "NOx", "WS", "WD", "Temp", "RH", "Pressure"])

weather_data = get_weather_from_openweather(province)
if weather_data:
    st.success(f"✅ ดึงข้อมูลจาก OpenWeather สำเร็จ: Temp={weather_data['Temp']}°C, RH={weather_data['RH']}%, WS={weather_data['WS']} m/s")
else:
    st.warning("⚠️ ไม่สามารถดึงข้อมูล OpenWeather ได้ ใช้ค่าจำลองแทน")
    weather_data = {"Temp": 27.0, "RH": 65.0, "WS": 2.5}

# ---------------------- DAILY SITUATIONS ----------------------
situations = []
sit_options = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["ไม่มี", "นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "อุณหภูมิ": ["ไม่มี", "ร้อน", "เย็น", "ปกติ"],
    "กลิ่น": ["ไม่มี", "มีกลิ่น"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "มีการเผาขยะ"]
}
st.markdown("### สถานการณ์รายวัน")
for i in range(num_days):
    with st.expander(f"📆 วันที่ {i+1}"):
        sit = {"ทิศลม": st.selectbox(f"ทิศลม (วัน {i+1})", ["NE", "NW", "SE", "SW"], key=f"wind_{i}")}
        for k, opts in sit_options.items():
            sit[k] = st.selectbox(f"{k} (วัน {i+1})", opts, key=f"{k}_{i}")
        situations.append(sit)

# ---------------------- SIMULATE FUNCTION ----------------------
def simulate(var, sit, hour, wd, fd):
    base = random.uniform(2, 6)
    m, a = 1.0, 0.0
    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]: m *= 0.6; a -= 1
    if sit["แดด"] == "แดดแรง": m *= 1.1; a += 4
    if sit["แดด"] == "แดดอ่อน": a += 2
    if sit["ลม"] == "แรง" and var == "WS": a += 2
    if sit["ลม"] == "นิ่ง/ไม่มีลม": m *= 1.2
    if sit["กลิ่น"] == "มีกลิ่น" and var in ["NO2", "SO2", "CO"]: m *= 1.2
    if sit["อื่นๆ"] == "รถเยอะ" and var in ["NO", "NO2", "CO"]: m *= 1.3
    if sit["อื่นๆ"] == "มีการเผาขยะ" and var in ["SO2", "CO", "O3"]: m *= 1.2
    if near_road and var in ["NO", "NO2", "CO"]: m *= 1.2
    if near_factory and wd == fd and var in ["NO2", "SO2"]: m *= 1.3

    if var == "NO": return round(base * m + a + random.uniform(0.3, 2.0), 2)
    if var == "NO2": return round(min(15, base * m + a + random.uniform(0.3, 2.0)), 2)
    if var == "NOx": return None
    if var == "Temp": return round(weather_data["Temp"] + a + random.uniform(-1, 1.5), 2)
    if var == "RH": return round(weather_data["RH"] + a + random.uniform(-10, 10), 2)
    if var == "WS": return round(min(4, weather_data["WS"] + a + random.uniform(-1.2, 1.2)), 2)
    if var == "Pressure": return round(1010 + random.uniform(-6, 6), 2)
    if var == "SO2": return round(base * m + a + random.uniform(0.2, 1.0), 2)
    if var == "CO": return round(base * m + a + random.uniform(0.1, 0.8), 2)
    if var == "O3": return round(30 + a + random.uniform(3, 18), 2)
    return round(base * m + a, 2)

# ---------------------- GENERATE + EXPORT ----------------------
if st.button("🎯 สร้างข้อมูลและดาวน์โหลด"):
    records = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = situations[i]
        wd = sit["ทิศลม"]
        for h in range(24):
            row = {
                "Date": date.strftime("%Y-%m-%d"),
                "Hour": f"{h:02d}:00:00",
                "WD": wd
            }
            no = simulate("NO", sit, h, wd, factory_direction) if "NO" in params else None
            no2 = simulate("NO2", sit, h, wd, factory_direction) if "NO2" in params else None
            nox = no + no2 if no is not None and no2 is not None and "NOx" in params else None
            for v in ["Temp", "RH", "WS", "Pressure", "SO2", "CO", "O3"]:
                if v in params: row[v] = simulate(v, sit, h, wd, factory_direction)
            row["NO"] = no
            row["NO2"] = no2
            row["NOx"] = nox
            row["Ref"] = "OpenWeather" if weather_data else "Simulated"
            records.append(row)
    df = pd.DataFrame(records)
    st.dataframe(df.head(48))

    # Export
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="AirCheck")
    fname = f"AirCheckTH_{province}_{start_date.strftime('%Y%m%d')}_{(start_date + timedelta(days=num_days-1)).strftime('%Y%m%d')}.xlsx"
    st.download_button("📥 ดาวน์โหลด Excel", output.getvalue(), file_name=fname)

