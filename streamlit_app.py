import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime, timedelta
from io import BytesIO

# ================= CONFIG =================
st.set_page_config(page_title="AirCheck TH", layout="wide")
st.title("🌍 AirCheck TH – ระบบจำลองคุณภาพอากาศ (Scenario-based)")

# ================= PROVINCE =================
province = st.selectbox("📍 จังหวัด", [
    "กรุงเทพมหานคร", "ระยอง", "อยุธยา", "สระบุรี",
    "ราชบุรี", "ชลบุรี", "จันทบุรี"
])

province_coords = {
    "กรุงเทพมหานคร": (13.7563, 100.5018),
    "ระยอง": (12.6814, 101.2770),
    "อยุธยา": (14.3532, 100.5689),
    "สระบุรี": (14.5289, 100.9105),
    "ราชบุรี": (13.5360, 99.8171),
    "ชลบุรี": (13.3611, 100.9847),
    "จันทบุรี": (12.6112, 102.1035),
}
lat, lon = province_coords[province]

# ================= USER INPUT =================
start_date = st.date_input("📅 วันที่เริ่มต้น", datetime.now().date())
num_days = st.slider("จำนวนวัน (1–8)", 1, 8, 1)

factory_direction = st.selectbox("🏭 ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])
near_road = st.checkbox("🚗 ใกล้ถนน")
near_factory = st.checkbox("🏭 ใกล้โรงงาน")

params = st.multiselect(
    "📌 พารามิเตอร์",
    ["NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"],
    default=["NO", "NO2", "NOx", "WS", "WD", "Temp", "RH", "Pressure"]
)

# ================= DAILY SITUATION =================
sit_options = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["ไม่มี", "นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "กลิ่น": ["ไม่มี", "มีกลิ่น"],
    "อุณหภูมิ": ["ไม่มี", "หนาวจัด", "หนาว", "เย็น", "ปกติ", "ร้อน", "ร้อนจัด"],
    "ท้องฟ้า": ["ไม่มี", "แจ่มใส", "มีเมฆบางส่วน", "เมฆมาก"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "มีการเผาขยะ"]
}

day_situations = []
for i in range(num_days):
    with st.expander(f"📅 วันที่ {i+1}"):
        sit = {}
        sit["ทิศลม"] = st.selectbox("ทิศลม", ["NE", "NW", "SE", "SW"], key=f"wd_{i}")
        for k, v in sit_options.items():
            sit[k] = st.selectbox(k, v, key=f"{k}_{i}")
        day_situations.append(sit)

# ================= FETCH OPEN-METEO =================
@st.cache_data(show_spinner=False)
def fetch_reference(lat, lon, start_date, num_days):
    sd = start_date.strftime("%Y-%m-%d")
    ed = (start_date + timedelta(days=num_days - 1)).strftime("%Y-%m-%d")

    w_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,relative_humidity_2m,"
        f"wind_speed_10m,wind_direction_10m"
        f"&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
    )

    aq_url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=carbon_monoxide,nitrogen_dioxide,"
        f"sulphur_dioxide,ozone"
        f"&start_date={sd}&end_date={ed}&timezone=Asia/Bangkok"
    )

    w = requests.get(w_url).json()["hourly"]
    aq = requests.get(aq_url).json()["hourly"]

    return pd.DataFrame({
        "time": pd.to_datetime(w["time"]),
        "Temp": w["temperature_2m"],
        "RH": w["relative_humidity_2m"],
        "WS": w["wind_speed_10m"],
        "WD": w["wind_direction_10m"],
        "NO2_ref": aq["nitrogen_dioxide"],
        "SO2_ref": aq["sulphur_dioxide"],
        "CO_ref": aq["carbon_monoxide"],
        "O3_ref": aq["ozone"]
    })

ref_df = fetch_reference(lat, lon, start_date, num_days)

# ================= SIMULATION =================
def simulate(var, sit, hour, wind_dir, ref):
    multiplier = 1.0
    add = 0.0

    # ฝน
    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]:
        multiplier *= 0.6
    elif sit["ฝน"] == "ตกเล็กน้อย":
        multiplier *= 0.85

    # ลม
    if sit["ลม"] == "นิ่ง/ไม่มีลม":
        multiplier *= 1.3
    elif sit["ลม"] == "แรง":
        multiplier *= 0.7

    # แดด
    if sit["แดด"] == "แดดแรง":
        multiplier *= 1.1
        add += 2

    # รถ
    if sit["อื่นๆ"] == "รถเยอะ" and var in ["NO", "NO2", "CO"]:
        multiplier *= 1.4

    # เผาขยะ
    if sit["อื่นๆ"] == "มีการเผาขยะ" and var in ["CO", "SO2", "O3"]:
        multiplier *= 1.3

    # กลิ่น
    if sit["กลิ่น"] == "มีกลิ่น" and var in ["NO2", "SO2", "CO"]:
        multiplier *= 1.2

    # ใกล้ถนน
    if near_road and var in ["NO", "NO2", "CO"]:
        multiplier *= 1.25

    # โรงงาน + ทิศลม
    if near_factory and wind_dir == factory_direction and var in ["NO2", "SO2"]:
        multiplier *= 1.5

    # Rush hour
    if hour in range(7, 10) or hour in range(16, 20):
        if var in ["NO", "NO2", "CO"]:
            multiplier *= 1.3

    # ---- Variable logic ----
    if var == "NO":
        return round(random.uniform(5, 20) * multiplier, 2)

    if var in ["NO2", "SO2", "CO", "O3"]:
        return round(ref * multiplier + add, 2)

    if var == "WS":
        return round(max(0.5, ref * random.uniform(0.7, 1.0)), 2)

    if var == "WD":
        return ref

    if var == "Temp":
        if sit["อุณหภูมิ"] == "ร้อนจัด":
            add += 4
        elif sit["อุณหภูมิ"] == "หนาวจัด":
            add -= 4
        return round(ref + add + random.uniform(-2, 2), 2)

    if var == "RH":
        return round(min(100, ref + random.uniform(-8, 8)), 2)

    if var == "Pressure":
        return round(1010 + random.uniform(-5, 5), 2)

# ================= GENERATE =================
if st.button("📊 สร้างข้อมูลและดาวน์โหลด"):
    rows = []

    for i in range(num_days):
        sit = day_situations[i]
        date = start_date + timedelta(days=i)

        for h in range(24):
            t = datetime.combine(date, datetime.min.time()) + timedelta(hours=h)
            r = ref_df.loc[ref_df["time"] == t].iloc[0]

            row = {"Date": date, "Time": f"{h:02d}:00"}
            wind_dir = sit["ทิศลม"]

            for p in params:
                if p == "NOx":
                    continue
                ref = r.get(f"{p}_ref", r.get(p))
                row[p] = simulate(p, sit, h, wind_dir, ref)

            if "NOx" in params:
                row["NOx"] = round(row.get("NO", 0) + row.get("NO2", 0), 2)

            rows.append(row)

    df = pd.DataFrame(rows)
    st.success("✅ สร้างข้อมูลเรียบร้อย")
    st.dataframe(df.head(48))

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Simulated Data")
        ref_df.to_excel(writer, index=False, sheet_name="Reference Data")

    st.download_button(
        "📥 ดาวน์โหลด Excel",
        buf.getvalue(),
        file_name="AirCheckTH_Final.xlsx"
    )
