import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime, timedelta
from io import BytesIO
import os

# ---------------- CONFIG ----------------
st.set_page_config(page_title="AirCheck TH", layout="wide", page_icon="static/logo.ico")

# --------------- LOGO + TITLE ----------------
st.image("static/logo.ico", width=60)
st.markdown("<h2>🌏 AirCheck TH - Web Version</h2>", unsafe_allow_html=True)

# -------------- Login ----------------
if "user" not in st.session_state:
    st.session_state.user = ""
    st.session_state.role = ""

if st.session_state.user == "":
    st.markdown("### 🔐 เข้าสู่ระบบ")
    user_input = st.text_input("ชื่อผู้ใช้")
    if st.button("เข้าสู่ระบบ"):
        st.session_state.user = user_input
        st.session_state.role = "admin" if user_input.lower() == "siwanon" else "user"

        # Log login
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("user_log.csv", "a", encoding="utf-8") as f:
            f.write(f"{now},{user_input},{st.session_state.role}\n")
        st.experimental_set_query_params(login="1")
        st.experimental_rerun()
    st.stop()

# -------------- Header Info ----------------
st.sidebar.success(f"👤 ผู้ใช้งาน: {st.session_state.user} ({st.session_state.role})")
if st.session_state.role == "admin":
    st.sidebar.markdown("📋 ประวัติการเข้าใช้งาน:")
    try:
        df_log = pd.read_csv("user_log.csv", names=["เวลา", "ชื่อผู้ใช้", "สิทธิ์"])
        st.sidebar.dataframe(df_log.tail(10), use_container_width=True)
    except:
        st.sidebar.info("ยังไม่มีประวัติ")

# -------------- Input Parameters ----------------
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📆 วันที่เริ่มต้น", datetime.today())
    num_days = st.slider("จำนวนวัน", 1, 8, 3)
    factory_dir = st.selectbox("ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])
with col2:
    st.markdown("### 🏙️ จังหวัดที่ต้องการดึงข้อมูล")
    province = st.selectbox("เลือกจังหวัด", [
        "ระยอง", "กรุงเทพมหานคร", "อยุธยา", "สระบุรี", "ราชบุรี", "ชลบุรี", "จันทบุรี"
    ])
    st.markdown("### 🌿 สภาพแวดล้อม")
    near_road = st.checkbox("ใกล้ถนน")
    near_factory = st.checkbox("ใกล้โรงงาน")

params_selected = st.multiselect("เลือกพารามิเตอร์ที่ต้องคำนวณ", [
    "NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"
], default=["NO", "NO2", "NOx", "WS", "WD", "Temp", "RH", "Pressure"])

# -------------- สถานการณ์รายวัน ----------------
sit_options = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["ไม่มี", "นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "กลิ่น": ["ไม่มี", "มีกลิ่น"],
    "อุณหภูมิ": ["ไม่มี", "หนาวจัด", "หนาว", "เย็น", "ปกติ", "ร้อน", "ร้อนจัด"],
    "ท้องฟ้า": ["ไม่มี", "แจ่มใส", "มีเมฆบางส่วน", "เมฆมาก"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "มีการเผาขยะ"]
}

st.markdown("### 🌦️ สถานการณ์รายวัน")
day_situations = []
for i in range(num_days):
    with st.expander(f"วันที่ {i+1}"):
        sit = {"ทิศลม": st.selectbox(f"ทิศลม (วัน {i+1})", ["NE", "NW", "SE", "SW"], key=f"wd_{i}")}
        for key, opts in sit_options.items():
            sit[key] = st.selectbox(f"{key} (วัน {i+1})", opts, key=f"{key}_{i}")
        day_situations.append(sit)

# -------------- ดึงข้อมูลจาก API ----------------
def fetch_openweather(province):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={province},TH&appid=api = st.secrets["OPENWEATHER_API"]
&units=metric"
    try:
        res = requests.get(url, timeout=10).json()
        return {
            "Temp": res["main"]["temp"],
            "RH": res["main"]["humidity"],
            "WS": res["wind"].get("speed", 2.0)
        }
    except:
        return {"Temp": 27, "RH": 65, "WS": 2.5}

open_ref = fetch_openweather(province)

# -------------- ฟังก์ชันจำลอง ----------------
def simulate(var, sit, wind_dir):
    base = random.uniform(2, 6)
    add, mul = 0.0, 1.0

    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]: mul *= 0.6; add -= 1
    if sit["ฝน"] == "ตกเล็กน้อย": mul *= 0.85
    if sit["แดด"] == "แดดแรง": add += 4; mul *= 1.1
    if sit["แดด"] == "แดดอ่อน": add += 2
    if sit["ลม"] == "แรง": mul *= 0.7; add += 1.5 if var == "WS" else 0
    if sit["ลม"] == "ปานกลาง": add += 1 if var == "WS" else 0
    if sit["ลม"] == "นิ่ง/ไม่มีลม": mul *= 1.3
    if sit["อุณหภูมิ"] == "ร้อนจัด" and var == "Temp": add += 4
    if sit["อุณหภูมิ"] == "หนาวจัด" and var == "Temp": add -= 4
    if sit["กลิ่น"] == "มีกลิ่น" and var in ["NO2", "SO2", "CO"]: mul *= 1.2
    if sit["อื่นๆ"] == "รถเยอะ" and var in ["NO", "NO2", "CO"]: mul *= 1.4
    if sit["อื่นๆ"] == "มีการเผาขยะ" and var in ["CO", "O3", "SO2"]: mul *= 1.3
    if near_road and var in ["NO", "NO2", "CO"]: mul *= 1.25
    if near_factory and wind_dir == factory_dir and var in ["NO2", "SO2"]: mul *= 1.5

    if var == "NO": return round(base * mul + add + random.uniform(0.5, 2.5), 2)
    if var == "NO2": return round(min(20, base * mul + add + random.uniform(0.8, 2.8)), 2)
    if var == "NOx": return None
    if var == "Temp": return round(open_ref["Temp"] + add + random.uniform(-2, 2), 2)
    if var == "RH": return round(open_ref["RH"] + random.uniform(-12, 15), 2)
    if var == "WS": return round(min(4, open_ref["WS"] + random.uniform(-1.5, 1.5)), 2)
    if var == "Pressure": return round(1010 + random.uniform(-6, 6), 2)
    if var == "SO2": return round(base * mul + add + random.uniform(0.6, 2.2), 2)
    if var == "CO": return round(base * mul + add + random.uniform(0.1, 1.0), 2)
    if var == "O3": return round(30 + add + random.uniform(5, 25), 2)
    return 0

# -------------- สร้างข้อมูล + Excel ----------------
if st.button("📊 สร้างตารางและดาวน์โหลด Excel"):
    data = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = day_situations[i]
        wind = sit["ทิศลม"]
        for h in range(24):
            row = {
                "Date": date.strftime("%Y-%m-%d"),
                "Time": f"{h:02d}:00:00",
                "WD": wind
            }
            no = simulate("NO", sit, wind) if "NO" in params_selected else None
            no2 = simulate("NO2", sit, wind) if "NO2" in params_selected else None
            row.update({
                "NO": no, "NO2": no2,
                "NOx": no + no2 if (no is not None and no2 is not None and "NOx" in params_selected) else None
            })
            for p in ["Temp", "RH", "WS", "Pressure", "SO2", "CO", "O3"]:
                if p in params_selected:
                    row[p] = simulate(p, sit, wind)
            data.append(row)

    df = pd.DataFrame(data)
    st.success("✅ สร้างข้อมูลสำเร็จ")
    st.dataframe(df.head(48))

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as w:
        if any(p in df.columns for p in ["NO", "NO2", "NOx"]):
            df[["Date", "Time", "NO", "NO2", "NOx"]].to_excel(w, index=False, sheet_name="NOx Group")
        df_env = df[["Date", "Time", "WS", "WD", "Temp", "RH", "Pressure"]].copy()
        df_env["WD_degree"] = [
            f'=IF(D{i+2}="NE",RANDBETWEEN(0,90),IF(D{i+2}="SE",RANDBETWEEN(91,180),IF(D{i+2}="SW",RANDBETWEEN(181,270),RANDBETWEEN(271,359))))'
            for i in range(len(df_env))
        ]
        df_env.to_excel(w, index=False, sheet_name="ENV")
        for p in ["SO2", "CO", "O3"]:
            if p in df.columns:
                df[["Date", "Time", p]].to_excel(w, index=False, sheet_name=p)

    filename = f"AirCheck_{province}_{start_date.strftime('%Y%m%d')}_{(start_date + timedelta(days=num_days-1)).strftime('%Y%m%d')}.xlsx"
    st.download_button("📥 ดาวน์โหลดไฟล์ Excel", data=output.getvalue(), file_name=filename)
