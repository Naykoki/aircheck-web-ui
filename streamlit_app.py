import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
from io import BytesIO
from meteostat import Point, Hourly

# ---------------- CONFIG ----------------
st.set_page_config(page_title="AirCheck TH", layout="wide")
st.image("logo.png", width=120)
st.title("🌍 AirCheck TH - ระบบประเมินคุณภาพอากาศจำลอง (รายชั่วโมง)")

# ---------------- Login ----------------
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None

with st.sidebar:
    st.header("🔐 เข้าสู่ระบบ")
    username = st.text_input("ชื่อผู้ใช้งาน")
    login_clicked = st.button("เข้าสู่ระบบ")
    if login_clicked:
        if username.strip() == "":
            st.warning("กรุณากรอกชื่อผู้ใช้งาน")
            st.stop()
        st.session_state.user = username
        st.session_state.role = "admin" if username.lower() == "siwanon" else "user"
        st.experimental_rerun()  # เรียก rerun เมื่อกดปุ่มจริง ๆ เท่านั้น


if not st.session_state.user:
    st.stop()

st.sidebar.success(f"ยินดีต้อนรับ: {st.session_state.user} ({st.session_state.role})")

# ---------------- Province ----------------
province = st.selectbox("📍 จังหวัดที่ต้องการดึงข้อมูลอ้างอิง", [
    "กรุงเทพมหานคร", "ระยอง", "อยุธยา", "สระบุรี", "ราชบุรี", "ชลบุรี", "จันทบุรี"
])

province_coords = {
    "กรุงเทพมหานคร": (13.7563, 100.5018),
    "ระยอง": (12.6814, 101.2770),
    "อยุธยา": (14.3532, 100.5689),
    "สระบุรี": (14.5289, 100.9105),
    "ราชบุรี": (13.5360, 99.8171),
    "ชลบุรี": (13.3611, 100.9847),
    "จันทบุรี": (12.6112, 102.1035)
}

# ---------------- USER INPUT ----------------
st.markdown("### กำหนดวันที่และจำนวนวัน")
start_date = st.date_input("วันที่เริ่มต้น (ต้องไม่เกินวันปัจจุบัน)", datetime(2025, 7, 15))
num_days = st.slider("จำนวนวัน (1–8)", 1, 8, 1)

if start_date > datetime.now().date():
    st.warning("เลือกวันที่ไม่ควรเกินวันที่วันนี้")
    st.stop()

factory_direction = st.selectbox("ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])

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

# ---------------- ดึงข้อมูลรายชั่วโมงจาก Meteostat ----------------
def get_hourly_meteostat(province, start_date, num_days):
    lat, lon = province_coords.get(province, (13.7563, 100.5018))
    location = Point(lat, lon)

    start = datetime.combine(start_date, datetime.min.time())
    end = start + timedelta(days=num_days) - timedelta(seconds=1)

    data = Hourly(location, start, end)
    data = data.fetch()

    data["wspd"].fillna(2.5, inplace=True)
    data["wdir"].fillna(90, inplace=True)
    data["temp"].fillna(27.0, inplace=True)
    data["rhum"].fillna(65.0, inplace=True)

    return data

hourly_data = get_hourly_meteostat(province, start_date, num_days)

# ---------------- การจำลอง ----------------
def simulate(var, sit, hour, wind_dir, ref):
    scale_factor_ws = 0.7  # ลดทอน WS เหลือประมาณ 70%
    base = ref if ref is not None else (random.uniform(2, 6) if var not in ["Temp", "RH", "WS"] else 27)
    multiplier = 1.0
    add = 0.0

    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]:
        multiplier *= 0.6
        add -= 1
    elif sit["ฝน"] == "ตกเล็กน้อย":
        multiplier *= 0.85
    if sit["แดด"] == "แดดแรง":
        add += 4
        multiplier *= 1.1
    elif sit["แดด"] == "แดดอ่อน":
        add += 2
    if sit["ลม"] == "แรง":
        add += 3 if var == "WS" else 0
        multiplier *= 0.7
    elif sit["ลม"] == "นิ่ง/ไม่มีลม":
        multiplier *= 1.3
        add -= 0.5
    if sit["อุณหภูมิ"] == "ร้อนจัด" and var == "Temp":
        add += 4
    if sit["อุณหภูมิ"] == "หนาวจัด" and var == "Temp":
        add -= 4
    if sit["กลิ่น"] == "มีกลิ่น" and var in ["NO2", "SO2", "CO"]:
        multiplier *= 1.2
    if sit["อื่นๆ"] == "รถเยอะ" and var in ["NO", "NO2", "CO"]:
        multiplier *= 1.4
    if sit["อื่นๆ"] == "มีการเผาขยะ" and var in ["CO", "O3", "SO2"]:
        multiplier *= 1.3
    if near_road and var in ["NO", "NO2", "CO"]:
        multiplier *= 1.25
    if near_factory and wind_dir == factory_direction and var in ["NO2", "SO2"]:
        multiplier *= 1.5

    if var == "NO":
        return round(base * multiplier + add + random.uniform(0.5, 2.5), 2)
    if var == "NO2":
        return round(min(20, base * multiplier + add + random.uniform(0.8, 2.8)), 2)
    if var == "NOx":
        return None
    if var == "WS":
        val = base + add + random.uniform(-1.0, 1.5)
        scaled_val = val * scale_factor_ws
        # บังคับ WS ให้อยู่ระหว่าง 0.5 - 4.0 m/s
        return round(min(max(scaled_val, 0.5), 4.0), 2)
    if var == "WD":
        # เปลี่ยน WD เป็นองศา ใช้ ref ถ้ามี
        return ref if ref is not None else 90
    if var == "Temp":
        return round(base + add + random.uniform(-2, 2), 2)
    if var == "RH":
        return round(min(100, base + add + random.uniform(-8, 10)), 2)
    if var == "Pressure":
        return round(1010 + random.uniform(-5, 5), 2)
    if var == "SO2":
        return round(base * multiplier + add + random.uniform(0.5, 2.5), 2)
    if var == "CO":
        return round(base * multiplier + add + random.uniform(0.1, 1.2), 2)
    if var == "O3":
        return round(30 + add + random.uniform(5, 25), 2)
    return round(base * multiplier + add, 2)

# ---------------- สร้างข้อมูล ----------------
if st.button("📊 สร้างข้อมูลและดาวน์โหลด Excel"):
    records = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = day_situations[i]
        for hour in range(24):
            time_dt = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour)
            time_str = time_dt.strftime("%H:%M:%S")

            try:
                ref_row = hourly_data.loc[time_dt]
            except KeyError:
                ref_row = None

            wind_dir = sit["ทิศลม"]

            row = {"Date": date.strftime("%Y-%m-%d"), "Time": time_str}

            ref_WS = ref_row["wspd"] if ref_row is not None else None
            ref_WD = ref_row["wdir"] if ref_row is not None else None
            ref_Temp = ref_row["temp"] if ref_row is not None else None
            ref_RH = ref_row["rhum"] if ref_row is not None else None

            no = simulate("NO", sit, hour, wind_dir, None) if "NO" in params else None
            no2 = simulate("NO2", sit, hour, wind_dir, None) if "NO2" in params else None
            row["NO"], row["NO2"] = no, no2
            row["NOx"] = no + no2 if "NOx" in params and no and no2 else None

            for var in ["WS", "WD", "Temp", "RH", "Pressure", "SO2", "CO", "O3"]:
                if var in params:
                    if var == "WS":
                        ref = ref_WS
                    elif var == "WD":
                        ref = ref_WD
                    elif var == "Temp":
                        ref = ref_Temp
                    elif var == "RH":
                        ref = ref_RH
                    else:
                        ref = None
                    row[var] = simulate(var, sit, hour, wind_dir, ref)

            records.append(row)

    df = pd.DataFrame(records)
    st.success("✅ สร้างข้อมูลสำเร็จแล้ว")
    st.dataframe(df.head(48))

    # เตรียม DataFrame สำหรับ Excel export
    df_env = df[[c for c in ["Date", "Time", "WS", "WD", "Temp", "RH", "Pressure"] if c in df.columns]]
    df_nox = df[["Date", "Time", "NO", "NO2", "NOx"]] if "NO" in df.columns else pd.DataFrame()

    # แปลงข้อมูล Reference Data ให้อยู่ในรูป Excel sheet
    df_ref = hourly_data.reset_index()[["time", "wspd", "wdir", "temp", "rhum"]]
    df_ref.rename(columns={
        "time": "DateTime",
        "wspd": "WS (m/s)",
        "wdir": "WD (degree)",
        "temp": "Temperature (°C)",
        "rhum": "Relative Humidity (%)"
    }, inplace=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if not df_nox.empty:
            df_nox.to_excel(writer, index=False, sheet_name="NOx Group")
        if not df_env.empty:
            df_env.to_excel(writer, index=False, sheet_name="ENV")
        for p in ["SO2", "CO", "O3"]:
            if p in df.columns:
                df[["Date", "Time", p]].to_excel(writer, index=False, sheet_name=p)

        # เพิ่ม sheet สำหรับ Reference Data
        df_ref.to_excel(writer, index=False, sheet_name="Reference Data")

    file_name = f"AirCheckTH_{province}_{start_date.strftime('%Y%m%d')}.xlsx"
    st.download_button("📥 ดาวน์โหลดไฟล์ Excel", output.getvalue(), file_name=file_name)
