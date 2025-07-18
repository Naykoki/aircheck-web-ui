# AirCheckTH_Web UI - Final Cloud Version (OpenWeather + Air4Thai + Login + Logo)
import streamlit as st
import pandas as pd
import requests
import random
from datetime import datetime, timedelta
from io import BytesIO
import os

# ------------------ PAGE CONFIG ------------------
st.set_page_config(page_title="AirCheck TH", layout="wide", page_icon="logo.ico")

# ------------------ LOGO ------------------
st.image("logo.ico", width=100)

# ------------------ LOGIN SYSTEM ------------------
if "username" not in st.session_state:
    st.session_state.username = ""
    st.session_state.role = ""

if st.session_state.username == "":
    st.title("🔐 เข้าสู่ระบบ")
    username = st.text_input("ชื่อผู้ใช้งาน")
    if st.button("เข้าสู่ระบบ"):
        st.session_state.username = username
        st.session_state.role = "admin" if username.lower() == "siwanon" else "user"
        st.experimental_rerun()
    st.stop()

# ------------------ USER STATUS ------------------
st.sidebar.success(f"👋 ยินดีต้อนรับ {st.session_state.username} ({st.session_state.role})")

# ------------------ LOG ACCESS ------------------
if st.session_state.role == "admin":
    log_file = "user_log.csv"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log = pd.DataFrame([{"time": now, "user": st.session_state.username}])
    if os.path.exists(log_file):
        old = pd.read_csv(log_file)
        log = pd.concat([old, log], ignore_index=True)
    log.to_csv(log_file, index=False)

    with st.expander("📋 ประวัติการเข้าใช้งาน"):
        st.dataframe(log.tail(50))

# ------------------ API CONFIG ------------------
OW_API_KEY = "83381fd2dfb9760f22710f0a419897c0"
province_list = ["ระยอง", "กรุงเทพมหานคร", "พระนครศรีอยุธยา", "สระบุรี", "ราชบุรี", "ชลบุรี", "จันทบุรี"]
selected_province = st.selectbox("เลือกจังหวัดเพื่อดึงข้อมูล", province_list)

# ------------------ API FUNCTIONS ------------------
@st.cache_data(ttl=3600)
def get_openweather(city="Bangkok"):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OW_API_KEY}&units=metric"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        return {
            "Temp": data["main"]["temp"],
            "RH": data["main"]["humidity"],
            "WS": data["wind"]["speed"]
        }
    return {}

@st.cache_data(ttl=3600)
def get_air4thai(province="ระยอง"):
    url = f"http://air4thai.pcd.go.th/webV2/history/api/data.php?province={province}&station=all"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        return data
    return {}

ref_open = get_openweather(selected_province)
ref_open = ref_open if ref_open else {"Temp": 27, "RH": 65, "WS": 2.5}

# ------------------ UI INPUT ------------------
st.title("AirCheck TH - Web Version")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("วันที่เริ่มต้น", datetime.today())
    num_days = st.slider("จำนวนวัน (1-8)", 1, 8, 3)
    factory_direction = st.selectbox("ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])
with col2:
    near_road = st.checkbox("ใกล้ถนน")
    near_factory = st.checkbox("ใกล้โรงงาน")

params_to_calculate = st.multiselect("เลือกพารามิเตอร์", [
    "NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"
], default=["NO", "NO2", "NOx", "WS", "WD", "Temp", "RH", "Pressure"])

sit_options = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["ไม่มี", "นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "กลิ่น": ["ไม่มี", "มีกลิ่น"],
    "อุณหภูมิ": ["ไม่มี", "หนาว", "เย็น", "ปกติ", "ร้อน", "ร้อนจัด"],
    "ท้องฟ้า": ["ไม่มี", "แจ่มใส", "มีเมฆ", "เมฆมาก"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "เผาขยะ"]
}

st.markdown("### สถานการณ์รายวัน")
day_situations = []
for i in range(num_days):
    with st.expander(f"วันที่ {i+1}"):
        sit = {}
        wind = st.selectbox(f"ทิศลม (วันที่ {i+1})", ["NE", "NW", "SE", "SW"], key=f"wind_{i}")
        sit["ทิศลม"] = wind
        for key, options in sit_options.items():
            sit[key] = st.selectbox(f"{key} (วันที่ {i+1})", options, key=f"{key}_{i}")
        day_situations.append(sit)

# ------------------ SIMULATION ------------------
def simulate(var, sit, wind, factory):
    base = random.uniform(2, 6)
    multi = 1.0
    add = 0.0

    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]: multi *= 0.6; add -= 1
    if sit["แดด"] == "แดดแรง": add += 3; multi *= 1.1
    if sit["ลม"] == "แรง": add += 2 if var == "WS" else 0; multi *= 0.8
    if sit["กลิ่น"] == "มีกลิ่น" and var in ["NO2", "CO", "SO2"]: multi *= 1.2
    if sit["อื่นๆ"] == "รถเยอะ" and var in ["NO", "NO2", "CO"]: multi *= 1.4
    if near_road and var in ["NO", "NO2", "CO"]: multi *= 1.2
    if near_factory and wind == factory and var in ["SO2", "NO2"]: multi *= 1.4

    if var == "NO": return round(base * multi + add + random.uniform(0.5, 2), 2)
    if var == "NO2": return round(min(20, base * multi + add + random.uniform(0.8, 2.5)), 2)
    if var == "NOx": return None
    if var == "Temp": return round(ref_open["Temp"] + add + random.uniform(-2, 2), 2)
    if var == "RH": return round(ref_open["RH"] + add + random.uniform(-10, 10), 2)
    if var == "WS": return round(min(4, ref_open["WS"] + add + random.uniform(-1, 1)), 2)
    if var == "Pressure": return round(1010 + random.uniform(-5, 5), 2)
    if var == "SO2": return round(base * multi + random.uniform(0.5, 1.5), 2)
    if var == "CO": return round(base * multi + random.uniform(0.1, 0.5), 2)
    if var == "O3": return round(30 + add + random.uniform(5, 15), 2)
    return base

# ------------------ GENERATE ------------------
if st.button("สร้างข้อมูลและดาวน์โหลด Excel"):
    rows = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = day_situations[i]
        wind = sit["ทิศลม"]
        for h in range(24):
            row = {"Date": date.strftime("%Y-%m-%d"), "Hour": f"{h:02d}:00", "WD": wind}
            no = simulate("NO", sit, wind, factory_direction) if "NO" in params_to_calculate else None
            no2 = simulate("NO2", sit, wind, factory_direction) if "NO2" in params_to_calculate else None
            nox = no + no2 if (no and no2 and "NOx" in params_to_calculate) else None
            row["NO"], row["NO2"], row["NOx"] = no, no2, nox
            for p in ["Temp", "RH", "WS", "Pressure", "SO2", "CO", "O3"]:
                if p in params_to_calculate:
                    row[p] = simulate(p, sit, wind, factory_direction)
            rows.append(row)

    df = pd.DataFrame(rows)
    st.success("✅ สร้างข้อมูลสำเร็จแล้ว")
    st.dataframe(df.head(50))

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="AirCheck Data")

    fname = f"AirCheck_{start_date.strftime('%Y%m%d')}_{(start_date + timedelta(days=num_days - 1)).strftime('%Y%m%d')}.xlsx"
    st.download_button("📥 ดาวน์โหลด Excel", data=output.getvalue(), file_name=fname)
