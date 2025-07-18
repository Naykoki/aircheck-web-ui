import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime, timedelta
from io import BytesIO
from meteostat import Point, Hourly

# ---------------- CONFIG ----------------
st.set_page_config(page_title="AirCheck TH", layout="wide")
st.image("logo.png", width=120)
st.title("🌍 AirCheck TH - ระบบประเมินคุณภาพอากาศจำลอง (รายชั่วโมง)")

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
lat, lon = province_coords[province]

# ---------------- USER INPUT ----------------
st.markdown("### กำหนดวันที่และจำนวนวัน")
start_date = st.date_input("วันที่เริ่มต้น (ต้องไม่เกินวันปัจจุบัน)", datetime.now().date())
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

# ---------------- Fetch Meteostat Data ----------------
@st.cache_data
def get_hourly_meteostat(lat, lon, start_date, num_days):
    location = Point(lat, lon)
    start = datetime.combine(start_date, datetime.min.time())
    end = start + timedelta(days=num_days) - timedelta(seconds=1)
    data = Hourly(location, start, end).fetch()

    # เติมค่า NaN ด้วยค่ามาตรฐาน
    data["wspd"].fillna(2.5, inplace=True)
    data["wdir"].fillna(90, inplace=True)
    data["temp"].fillna(27.0, inplace=True)
    data["rhum"].fillna(65.0, inplace=True)
    return data

# ---------------- Fetch Open-Meteo Air Quality ----------------
@st.cache_data
def get_openmeteo_aq(lat, lon, start_date, num_days):
    sd = start_date.strftime("%Y-%m-%d")
    ed = (start_date + timedelta(days=num_days - 1)).strftime("%Y-%m-%d")

    url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={sd}&end_date={ed}"
        f"&hourly=carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
    )
    r = requests.get(url)
    if r.ok:
        j = r.json().get("hourly", {})
        df = pd.DataFrame({
            "time": pd.to_datetime(j.get("time", [])),
            "CO_ref": j.get("carbon_monoxide", []),
            "NO2_ref": j.get("nitrogen_dioxide", []),
            "SO2_ref": j.get("sulphur_dioxide", []),
            "O3_ref": j.get("ozone", []),
        }).set_index("time")
        return df
    else:
        st.warning("ไม่สามารถดึงข้อมูลคุณภาพอากาศจาก Open-Meteo ได้")
        return pd.DataFrame()

# ---------------- Load Data ----------------
hourly_data = get_hourly_meteostat(lat, lon, start_date, num_days)
aq_ref_data = get_openmeteo_aq(lat, lon, start_date, num_days)

# ---------------- Simulate ----------------
def simulate(var, sit, hour, wind_dir, ref, ref_aq=None):
    multiplier = 1.0
    add = 0.0

    # Rain
    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]:
        multiplier *= 0.6
        add -= 1
    elif sit["ฝน"] == "ตกเล็กน้อย":
        multiplier *= 0.85

    # Sun
    if sit["แดด"] == "แดดแรง":
        add += 4
        multiplier *= 1.1
    elif sit["แดด"] == "แดดอ่อน":
        add += 2

    # Wind
    if sit["ลม"] == "แรง":
        add += 3 if var == "WS" else 0
        multiplier *= 0.7
    elif sit["ลม"] == "นิ่ง/ไม่มีลม":
        multiplier *= 1.3
        add -= 0.5

    # Temp
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

    # ใช้ค่าอ้างอิงจาก Meteostat หรือ Open-Meteo (ถ้ามี)
    if var in ["NO2", "SO2", "CO", "O3"]:
        base = ref_aq if ref_aq is not None else random.uniform(2, 6)
    else:
        base = ref if ref is not None else random.uniform(2, 6)

    if var == "NO":
        return round(base * multiplier + add + random.uniform(0.5, 2.5), 2)
    if var == "NO2":
        return round(min(20, base * multiplier + add + random.uniform(0.8, 2.8)), 2)
    if var == "NOx":
        return None
    if var == "WS":
        val = base * 0.15  # ลด 85%
        val += add
        return round(max(0.5, val), 2)
    if var == "WD":
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

# ---------------- Generate & Export ----------------
if st.button("📊 สร้างข้อมูลและดาวน์โหลด Excel"):
    records = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = day_situations[i]
        for hour in range(24):
            time_dt = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour)
            try:
                ref_row = hourly_data.loc[time_dt]
            except KeyError:
                ref_row = None
            try:
                ref_aq_row = aq_ref_data.loc[time_dt]
            except KeyError:
                ref_aq_row = None

            wind_dir = sit["ทิศลม"]
            row = {"Date": date.strftime("%Y-%m-%d"), "Time": time_dt.strftime("%H:%M:%S")}

            refs = {
                "WS": ref_row["wspd"] if ref_row is not None else None,
                "WD": ref_row["wdir"] if ref_row is not None else None,
                "Temp": ref_row["temp"] if ref_row is not None else None,
                "RH": ref_row["rhum"] if ref_row is not None else None,
                "Pressure": None
            }
            aq_refs = {
                "NO2": ref_aq_row["NO2_ref"] if ref_aq_row is not None else None,
                "SO2": ref_aq_row["SO2_ref"] if ref_aq_row is not None else None,
                "CO": ref_aq_row["CO_ref"] if ref_aq_row is not None else None,
                "O3": ref_aq_row["O3_ref"] if ref_aq_row is not None else None
            }

            for var in params:
                if var == "NOx":
                    continue
                ref = refs.get(var, None)
                ref_aq = aq_refs.get(var, None)
                row[var] = simulate(var, sit, hour, wind_dir, ref, ref_aq)

            if "NOx" in params and "NO" in row and "NO2" in row:
                row["NOx"] = round(row["NO"] + row["NO2"], 2)

            records.append(row)

    df = pd.DataFrame(records)
    st.success("✅ สร้างข้อมูลสำเร็จแล้ว")
    st.dataframe(df.head(48))

    # Export Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Simulated Data")
        # Export reference Meteostat data
        hourly_data_reset = hourly_data.reset_index()
        hourly_data_reset.to_excel(writer, index=False, sheet_name="Meteostat Reference")

        # Export Open-Meteo Air Quality reference
        if not aq_ref_data.empty:
            aq_ref_data_reset = aq_ref_data.reset_index()
            aq_ref_data_reset.to_excel(writer, index=False, sheet_name="OpenMeteo AQ Reference")

    file_name = f"AirCheckTH_{province}_{start_date.strftime('%Y%m%d')}.xlsx"
    st.download_button("📥 ดาวน์โหลดไฟล์ Excel", output.getvalue(), file_name=file_name)
