import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime, timedelta
from io import BytesIO

# ---------------- CONFIG ----------------
st.set_page_config(page_title="AirCheck TH", layout="wide")
st.image("logo.png", width=120)
st.title("🌍 AirCheck TH - ระบบประเมินคุณภาพอากาศจำลอง")

# ---------------- Login ----------------
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None

with st.sidebar:
    st.header("🔐 เข้าสู่ระบบ")
    username = st.text_input("ชื่อผู้ใช้งาน")
    if st.button("เข้าสู่ระบบ"):
        if username.strip() == "":
            st.warning("กรุณากรอกชื่อผู้ใช้งาน")
            st.stop()
        st.session_state.user = username
        st.session_state.role = "admin" if username.lower() == "siwanon" else "user"
        st.rerun()  # ✅ ใช้ st.rerun() แทน experimental

if not st.session_state.user:
    st.stop()

# ---------------- Header ----------------
st.sidebar.success(f"ยินดีต้อนรับ: {st.session_state.user} ({st.session_state.role})")

# ---------------- Province + API ----------------
province = st.selectbox("📍 จังหวัดที่ต้องการดึงข้อมูลอ้างอิง", [
    "กรุงเทพมหานคร", "ระยอง", "อยุธยา", "สระบุรี", "ราชบุรี", "ชลบุรี", "จันทบุรี"
])

def get_openweather(province):
    try:
        api_key = st.secrets["OPENWEATHER_API"]
        url = f"https://api.openweathermap.org/data/2.5/weather?q={province},TH&appid={api_key}&units=metric"
        res = requests.get(url)
        if res.status_code != 200:
            st.warning("⚠️ ไม่สามารถเชื่อมต่อ OpenWeather ได้ ใช้ค่าจำลองแทน")
            return {"WS": 2.5, "WD": 90, "Temp": 27.0, "RH": 65.0}
        data = res.json()
        return {
            "WS": data["wind"]["speed"],
            "WD": data["wind"].get("deg", 0),
            "Temp": data["main"]["temp"],
            "RH": data["main"]["humidity"]
        }
    except Exception as e:
        st.warning(f"⚠️ Error: {e}")
        return {"WS": 2.5, "WD": 90, "Temp": 27.0, "RH": 65.0}

ref_data = get_openweather(province)
st.info(f"📡 อ้างอิงข้อมูลจาก OpenWeather: Temp={ref_data['Temp']}°C, RH={ref_data['RH']}%, WS={ref_data['WS']} m/s")

# ---------------- INPUTS ----------------
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📆 วันที่เริ่มต้น", datetime.today())
    num_days = st.slider("จำนวนวัน (1–8)", 1, 8, 3)
    factory_direction = st.selectbox("ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])
with col2:
    st.markdown("### 🏞️ สภาพแวดล้อม")
    near_road = st.checkbox("ใกล้ถนน")
    near_factory = st.checkbox("ใกล้โรงงาน")

params = st.multiselect("📌 พารามิเตอร์ที่ต้องการคำนวณ", [
    "NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"
], default=["NO", "NO2", "NOx", "WS", "WD", "Temp", "RH", "Pressure"])

sit_options = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["ไม่มี", "นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "กลิ่น": ["ไม่มี", "มีกลิ่น"],
    "อุณหภูมิ": ["ไม่มี", "หนาวจัด", "หนาว", "เย็น", "ปกติ", "ร้อน", "ร้อนจัด"],
    "ท้องฟ้า": ["ไม่มี", "แจ่มใส", "มีเมฆบางส่วน", "เมฆมาก"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "มีการเผาขยะ"]
}

st.markdown("### 🌤️ สถานการณ์รายวัน")
day_situations = []
for i in range(num_days):
    with st.expander(f"📅 วันที่ {i+1}"):
        sit = {}
        wind_dir = st.selectbox(f"ทิศลม (วันที่ {i+1})", ["NE", "NW", "SE", "SW"], key=f"wd_{i}")
        sit["ทิศลม"] = wind_dir
        for key, opts in sit_options.items():
            sit[key] = st.selectbox(f"{key} (วันที่ {i+1})", opts, key=f"{key}_{i}")
        day_situations.append(sit)

# ---------------- SIMULATE ----------------
def simulate(var, sit, hour, wind_dir):
    ref = ref_data.get(var, 0)
    base = ref if ref else random.uniform(2, 6)
    multiplier = 1.0
    add = 0.0

    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]: multiplier *= 0.6; add -= 1
    elif sit["ฝน"] == "ตกเล็กน้อย": multiplier *= 0.85
    if sit["แดด"] == "แดดแรง": add += 4; multiplier *= 1.1
    elif sit["แดด"] == "แดดอ่อน": add += 2
    if sit["ลม"] == "แรง": add += 3 if var == "WS" else 0; multiplier *= 0.7
    elif sit["ลม"] == "นิ่ง/ไม่มีลม": multiplier *= 1.3; add -= 0.5
    if sit["อุณหภูมิ"] == "ร้อนจัด" and var == "Temp": add += 4
    if sit["อุณหภูมิ"] == "หนาวจัด" and var == "Temp": add -= 4
    if sit["กลิ่น"] == "มีกลิ่น" and var in ["NO2", "SO2", "CO"]: multiplier *= 1.2
    if sit["อื่นๆ"] == "รถเยอะ" and var in ["NO", "NO2", "CO"]: multiplier *= 1.4
    if sit["อื่นๆ"] == "มีการเผาขยะ" and var in ["CO", "O3", "SO2"]: multiplier *= 1.3
    if near_road and var in ["NO", "NO2", "CO"]: multiplier *= 1.25
    if near_factory and wind_dir == factory_direction and var in ["NO2", "SO2"]: multiplier *= 1.5

    if var == "NO": return round(base * multiplier + add + random.uniform(0.5, 2.5), 2)
    if var == "NO2": return round(min(20, base * multiplier + add + random.uniform(0.8, 2.8)), 2)
    if var == "NOx": return None
    if var == "WS": return round(min(4, base + add + random.uniform(-1.0, 1.5)), 2)
    if var == "WD": return wind_dir
    if var == "Temp": return round(base + add + random.uniform(-2, 2), 2)
    if var == "RH": return round(min(100, base + add + random.uniform(-8, 10)), 2)
    if var == "Pressure": return round(1010 + random.uniform(-5, 5), 2)
    if var == "SO2": return round(base * multiplier + add + random.uniform(0.5, 2.5), 2)
    if var == "CO": return round(base * multiplier + add + random.uniform(0.1, 1.2), 2)
    if var == "O3": return round(30 + add + random.uniform(5, 25), 2)
    return round(base * multiplier + add, 2)

# ---------------- GENERATE ----------------
if st.button("📊 สร้างข้อมูลและดาวน์โหลด Excel"):
    records = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = day_situations[i]
        wind_dir = sit["ทิศลม"]
        for hour in range(24):
            time_str = f"{hour:02d}:00:00"
            row = {"Date": date.strftime("%Y-%m-%d"), "Time": time_str}
            no = simulate("NO", sit, hour, wind_dir) if "NO" in params else None
            no2 = simulate("NO2", sit, hour, wind_dir) if "NO2" in params else None
            row["NO"] = no
            row["NO2"] = no2
            if "NOx" in params and no is not None and no2 is not None:
                row["NOx"] = round(no + no2, 2)
            else:
                row["NOx"] = None
            for var in ["WS", "WD", "Temp", "RH", "Pressure", "SO2", "CO", "O3"]:
                if var in params:
                    row[var] = simulate(var, sit, hour, wind_dir)
            records.append(row)

    df = pd.DataFrame(records)
    st.success("✅ สร้างข้อมูลสำเร็จแล้ว")
    st.dataframe(df.head(48))

    # ---------------- EXCEL EXPORT ----------------
    df_env = df[[c for c in ["Date", "Time", "WS", "WD", "Temp", "RH", "Pressure"] if c in df.columns]]
    df_nox = df[["Date", "Time", "NO", "NO2", "NOx"]] if "NO" in df.columns else pd.DataFrame()
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if not df_nox.empty:
            df_nox.to_excel(writer, index=False, sheet_name="NOx Group")
        if not df_env.empty:
            df_env.to_excel(writer, index=False, sheet_name="ENV")
        for p in ["SO2", "CO", "O3"]:
            if p in df.columns:
                df[["Date", "Time", p]].to_excel(writer, index=False, sheet_name=p)

    output.seek(0)
    file_name = f"AirCheckTH_{province}_{start_date.strftime('%Y%m%d')}.xlsx"
    st.download_button("📥 ดาวน์โหลดไฟล์ Excel", output.getvalue(), file_name=file_name)
