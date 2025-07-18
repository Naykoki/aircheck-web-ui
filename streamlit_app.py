# streamlit_app.py

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import random
from io import BytesIO
import os

# ---------------------- CONFIG ----------------------
st.set_page_config(page_title="AirCheck TH - Web", layout="wide", page_icon="logo.ico")

# ---------------------- SHOW LOGO ----------------------
st.image("logo.ico", width=80)
st.title("AirCheck TH - Web Version")

# ---------------------- Login System ----------------------
if "username" not in st.session_state:
    st.session_state.username = ""
    st.session_state.role = ""

with st.sidebar:
    if st.session_state.username == "":
        st.subheader("🔐 เข้าสู่ระบบ")
        username = st.text_input("ชื่อผู้ใช้")
        if st.button("เข้าสู่ระบบ"):
            if username.strip() == "":
                st.warning("กรุณากรอกชื่อผู้ใช้")
            else:
                st.session_state.username = username
                st.session_state.role = "admin" if username.lower() == "siwanon" else "user"
                log = {
                    "user": username,
                    "role": st.session_state.role,
                    "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                if os.path.exists("user_log.csv"):
                    df = pd.read_csv("user_log.csv")
                    df = pd.concat([df, pd.DataFrame([log])], ignore_index=True)
                else:
                    df = pd.DataFrame([log])
                df.to_csv("user_log.csv", index=False)
                st.experimental_rerun()
    else:
        st.success(f"👋 ยินดีต้อนรับ {st.session_state.username} ({st.session_state.role})")
        if st.button("ออกจากระบบ"):
            st.session_state.username = ""
            st.session_state.role = ""
            st.experimental_rerun()

# ---------------------- SHOW LOG (admin only) ----------------------
if st.session_state.role == "admin":
    with st.expander("📋 ประวัติการใช้งาน"):
        try:
            log_df = pd.read_csv("user_log.csv")
            st.dataframe(log_df.tail(100))
        except:
            st.info("ไม่มี log หรือโหลดไม่ได้")

# ---------------------- API: OpenWeather ----------------------
def get_openweather_data(city="Bangkok"):
    api_key = "YOUR_API_KEY"  # 👈 แทนที่ด้วย API KEY จริงของคุณ
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city},TH&appid={api_key}&units=metric"
    try:
        r = requests.get(url).json()
        return {
            "Temp": r["main"]["temp"],
            "RH": r["main"]["humidity"],
            "WS": r["wind"]["speed"]
        }
    except:
        return {"Temp": 27.0, "RH": 65.0, "WS": 2.5}

# ---------------------- API: Air4Thai ----------------------
def get_air4thai_data(province):
    try:
        r = requests.get("https://data.air4thai.net/api/PCD/StationToday.json").json()
        stations = [s for s in r["stations"] if s["provinceTH"] == province]
        for s in stations:
            latest = s.get("LastUpdate")
            data = s.get("PM25")
            if data:  # มีข้อมูล
                return {
                    "PM25": float(data),
                    "source": s["stationNameTH"]
                }
        return {"PM25": None, "source": None}
    except:
        return {"PM25": None, "source": None}

# ---------------------- INPUT ----------------------
st.markdown("## 📌 ตั้งค่าการจำลอง")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("วันที่เริ่มต้น", datetime.today())
    num_days = st.slider("จำนวนวัน (1–8)", 1, 8, 3)
    factory_dir = st.selectbox("ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])
    city = st.selectbox("จังหวัด", ["กรุงเทพฯ", "ระยอง", "อยุธยา", "สระบุรี", "ราชบุรี", "ชลบุรี", "จันทบุรี"])
with col2:
    st.markdown("### สภาพแวดล้อม")
    near_road = st.checkbox("ใกล้ถนน")
    near_factory = st.checkbox("ใกล้โรงงาน")
    params = st.multiselect("พารามิเตอร์ที่ต้องคำนวณ", [
        "NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"
    ], default=["NO", "NO2", "NOx", "Temp", "RH", "WS", "Pressure"])

# ---------------------- สถานการณ์ ----------------------
situation_opts = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["ไม่มี", "นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "กลิ่น": ["ไม่มี", "มีกลิ่น"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "มีการเผาขยะ"]
}

st.markdown("## ☁️ สถานการณ์รายวัน")
daily_sits = []
for i in range(num_days):
    with st.expander(f"วันที่ {i+1}"):
        d = {}
        d["WD"] = st.selectbox(f"ทิศลม (วัน {i+1})", ["NE", "NW", "SE", "SW"], key=f"wd_{i}")
        for k, v in situation_opts.items():
            d[k] = st.selectbox(f"{k} (วัน {i+1})", v, key=f"{k}_{i}")
        daily_sits.append(d)

# ---------------------- SIMULATE ----------------------
ow_data = get_openweather_data(city)
air_data = get_air4thai_data(city)
ref_temp = ow_data["Temp"]
ref_rh = ow_data["RH"]
ref_ws = ow_data["WS"]

def simulate(var, sit, hour, wd):
    base = random.uniform(2, 6)
    mul = 1.0
    add = 0.0

    if sit["ฝน"] == "ตกหนัก":
        mul *= 0.6
    elif sit["ฝน"] == "ตกปานกลาง":
        mul *= 0.75
    elif sit["ฝน"] == "ตกเล็กน้อย":
        mul *= 0.9

    if sit["แดด"] == "แดดแรง":
        add += 3
    elif sit["แดด"] == "แดดอ่อน":
        add += 1.5

    if sit["ลม"] == "แรง" and var == "WS":
        add += 2
    elif sit["ลม"] == "ปานกลาง" and var == "WS":
        add += 1

    if sit["กลิ่น"] == "มีกลิ่น" and var in ["NO2", "SO2", "CO"]:
        mul *= 1.2

    if sit["อื่นๆ"] == "รถเยอะ" and var in ["NO", "NO2", "CO"]:
        mul *= 1.4

    if sit["อื่นๆ"] == "มีการเผาขยะ" and var in ["CO", "SO2", "O3"]:
        mul *= 1.3

    if near_road and var in ["NO", "NO2", "CO"]:
        mul *= 1.3
    if near_factory and wd == factory_dir and var in ["NO2", "SO2"]:
        mul *= 1.5

    if var == "NO":
        return round(base * mul + add + random.uniform(0.5, 2), 2)
    if var == "NO2":
        return round(min(20, base * mul + add + random.uniform(1, 3)), 2)
    if var == "NOx":
        return None
    if var == "Temp":
        return round(ref_temp + add + random.uniform(-2, 2), 2)
    if var == "RH":
        return round(ref_rh + add + random.uniform(-10, 10), 2)
    if var == "WS":
        return round(min(4, ref_ws + add + random.uniform(-1, 1)), 2)
    if var == "Pressure":
        return round(1010 + random.uniform(-5, 5), 2)
    if var == "SO2":
        return round(base * mul + add + random.uniform(0.3, 1.5), 2)
    if var == "CO":
        return round(base * mul + add + random.uniform(0.1, 1.0), 2)
    if var == "O3":
        return round(30 + add + random.uniform(5, 25), 2)

# ---------------------- GENERATE ----------------------
if st.button("สร้างข้อมูลและดาวน์โหลด Excel"):
    rows = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = daily_sits[i]
        wd = sit["WD"]
        for h in range(24):
            row = {"Date": date.strftime("%Y-%m-%d"), "Hour": f"{h:02d}:00"}
            no = simulate("NO", sit, h, wd) if "NO" in params else None
            no2 = simulate("NO2", sit, h, wd) if "NO2" in params else None
            row.update({
                "NO": no,
                "NO2": no2,
                "NOx": no + no2 if (no and no2 and "NOx" in params) else None,
                "WD": wd
            })
            for p in ["Temp", "RH", "WS", "Pressure", "SO2", "CO", "O3"]:
                if p in params:
                    row[p] = simulate(p, sit, h, wd)
            rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df.head(50))
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="AirCheckData")

    fname = f"AirCheck_{start_date.strftime('%Y%m%d')}_{(start_date + timedelta(days=num_days-1)).strftime('%Y%m%d')}.xlsx"
    st.download_button("📥 ดาวน์โหลดไฟล์ Excel", data=output.getvalue(), file_name=fname)
