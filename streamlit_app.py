import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
from io import BytesIO
from meteostat import Point, Daily

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
        st.rerun()  # <-- แก้ไขตรงนี้

if not st.session_state.user:
    st.stop()

st.sidebar.success(f"ยินดีต้อนรับ: {st.session_state.user} ({st.session_state.role})")

# ---------------- Province ----------------
province = st.selectbox("📍 จังหวัดที่ต้องการดึงข้อมูลอ้างอิง", [
    "กรุงเทพมหานคร", "ระยอง", "อยุธยา", "สระบุรี", "ราชบุรี", "ชลบุรี", "จันทบุรี"
])

# ---------------- Meteostat API ----------------
province_coords = {
    "กรุงเทพมหานคร": (13.7563, 100.5018),
    "ระยอง": (12.6814, 101.2770),
    "อยุธยา": (14.3532, 100.5689),
    "สระบุรี": (14.5289, 100.9105),
    "ราชบุรี": (13.5360, 99.8171),
    "ชลบุรี": (13.3611, 100.9847),
    "จันทบุรี": (12.6112, 102.1035)
}

def get_meteostat(province):
    lat, lon = province_coords.get(province, (13.7563, 100.5018))
    location = Point(lat, lon)

    today = datetime.now()
    yesterday = today - timedelta(days=1)
    data = Daily(location, yesterday, yesterday)
    data = data.fetch()

    if not data.empty:
        row = data.iloc[0]
        ws = row["wspd"] or 2.5
        wd = row["wdir"] or 90
        temp = row["tavg"] or 27
        rh = row["rhum"] or 65
        return {"WS": round(ws, 2), "WD": round(wd, 2), "Temp": round(temp, 2), "RH": round(rh, 2)}
    else:
        return {"WS": 2.5, "WD": 90, "Temp": 27.0, "RH": 65.0}

ref_data = get_meteostat(province)
st.info(f"📡 อ้างอิงข้อมูลจาก Meteostat: Temp={ref_data['Temp']}°C, RH={ref_data['RH']}%, WS={ref_data['WS']} m/s")

# ---------------- INPUT ----------------
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
    base = ref if var in ["Temp", "RH", "WS"] else random.uniform(2, 6)
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
            row["NO"], row["NO2"] = no, no2
            row["NOx"] = no + no2 if "NOx" in params and no and no2 else None
            for var in ["WS", "WD", "Temp", "RH", "Pressure", "SO2", "CO", "O3"]:
                if var in params:
                    row[var] = simulate(var, sit, hour, wind_dir)
            records.append(row)

    df = pd.DataFrame(records)
    st.success("✅ สร้างข้อมูลสำเร็จแล้ว")
    st.dataframe(df.head(48))

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

    file_name = f"AirCheckTH_{province}_{start_date.strftime('%Y%m%d')}.xlsx"
    st.download_button("📥 ดาวน์โหลดไฟล์ Excel", output.getvalue(), file_name=file_name)
