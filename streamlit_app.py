import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random
import os
import requests
from io import BytesIO

# ---------------------- Input User Name ----------------------
st.set_page_config(page_title="AirCheck TH (Web)", layout="wide")

if "username" not in st.session_state:
    st.session_state.username = ""
    st.session_state.role = ""

if st.session_state.username == "":
    st.title("🔐 กรุณากรอกชื่อผู้ใช้งาน")
    input_user = st.text_input("ชื่อผู้ใช้งาน")
    if st.button("เข้าสู่ระบบ"):
        if input_user.strip() == "":
            st.warning("⚠️ กรุณากรอกชื่อ")
            st.stop()
        else:
            st.session_state.username = input_user.strip()
            if input_user.strip().lower() == "siwanon":
                st.session_state.role = "admin"
            else:
                st.session_state.role = "user"

            log_entry = {
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user": st.session_state.username,
                "role": st.session_state.role
            }
            try:
                if os.path.exists("user_log.csv"):
                    df_log = pd.read_csv("user_log.csv")
                    df_log = pd.concat([df_log, pd.DataFrame([log_entry])], ignore_index=True)
                else:
                    df_log = pd.DataFrame([log_entry])
                df_log.to_csv("user_log.csv", index=False)
            except:
                pass

            st.success("✅ เข้าสู่ระบบเรียบร้อยแล้ว")
            st.experimental_rerun()
    st.stop()

# ---------------------- Header ----------------------
st.sidebar.success(f"👋 ยินดีต้อนรับ {st.session_state.username} ({st.session_state.role})")

if st.session_state.role == "admin":
    st.markdown("## 🛡️ Log ผู้ใช้งาน")
    try:
        df_log = pd.read_csv("user_log.csv")
        st.dataframe(df_log.tail(100), use_container_width=True)
    except:
        st.info("ยังไม่มี log หรือโหลด log ไม่ได้")

st.title("AirCheck TH - Web Version")

st.markdown("""
⚙️ ที่นี่สามารถเริ่มสร้างข้อมูลมลพิษอากาศจำลองได้ตามสถานการณ์ โดยมีการดึงข้อมูลอ้างอิงจากแหล่งจริง
""")

# ---------------------- จังหวัดและพารามิเตอร์ ----------------------
st.subheader("🔍 เลือกจังหวัดและพารามิเตอร์ที่ต้องการ")
province = st.selectbox("เลือกจังหวัด", ["ระยอง", "กรุงเทพมหานคร", "พระนครศรีอยุธยา", "สระบุรี", "ราชบุรี", "ชลบุรี", "จันทบุรี", "เชียงใหม่", "ขอนแก่น", "สงขลา"])
params_to_calculate = st.multiselect("เลือกพารามิเตอร์ที่ต้องการคำนวณ", ["NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"], default=["NO", "NO2", "NOx"])

# ---------------------- ดึงข้อมูลอ้างอิง ----------------------
st.subheader("📥 ข้อมูลอ้างอิงจากสถานีในจังหวัด")
ref_data = {}
ref_source = ""
openweather_ref = {}

# Air4Thai
station_mapping = {
    "ระยอง": ["71t", "73t"],
    "กรุงเทพมหานคร": ["11t", "13t", "17t", "19t"],
    "พระนครศรีอยุธยา": ["14t"],
    "สระบุรี": ["16t"],
    "ราชบุรี": ["70t"],
    "ชลบุรี": ["20t", "21t"],
    "จันทบุรี": ["74t"],
    "เชียงใหม่": ["50t"],
    "ขอนแก่น": ["43t"],
    "สงขลา": ["90t"]
}

station_list = station_mapping.get(province, [])
data_loaded = False

for station in station_list:
    try:
        url = f"https://air4thai.pcd.go.th/webV2/history/api/data.php?station={station}&param=O3&year=2024&month=07&day=16"
        res = requests.get(url)
        if res.status_code == 200:
            ref_data = res.json()
            ref_source = f"Air4Thai ({station})"
            st.success(f"✅ ใช้ข้อมูลจาก Air4Thai สถานี {station}")
            data_loaded = True
            break
    except:
        continue

# OpenWeather
openweather_api_key = "83381fd2dfb9760f22710f0a419897c0"
try:
    ow_url = f"http://api.openweathermap.org/data/2.5/weather?q={province},TH&appid={openweather_api_key}&units=metric"
    res = requests.get(ow_url)
    if res.status_code == 200:
        ow_json = res.json()
        openweather_ref = {
            "Temp": ow_json["main"]["temp"],
            "RH": ow_json["main"]["humidity"],
            "WS": ow_json["wind"]["speed"]
        }
        st.success("✅ ใช้ข้อมูลร่วมจาก OpenWeather")
        if not data_loaded:
            ref_source = "OpenWeather"
            data_loaded = True
except:
    st.warning("⚠️ โหลด OpenWeather ไม่สำเร็จ")

if not data_loaded:
    st.warning("⚠️ ไม่สามารถโหลดข้อมูลอ้างอิงได้จากสถานีในจังหวัดนี้ — จะใช้การคำนวณจำลองแทน")

# ---------------------- ส่วนเพิ่ม: UI สถานการณ์, คำนวณ, สร้าง Excel ----------------------
st.subheader("📆 เลือกวันที่และสถานการณ์")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("วันที่เริ่มต้น", datetime.today())
    num_days = st.slider("จำนวนวัน (1–7)", 1, 7, 2)
    factory_direction = st.selectbox("ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])

with col2:
    st.markdown("### สภาพแวดล้อม")
    near_road = st.checkbox("ใกล้ถนน")
    near_factory = st.checkbox("ใกล้โรงงาน")

sit_options = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["ไม่มี", "นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "กลิ่น": ["ไม่มี", "มีกลิ่น", "ไม่มีกลิ่น"],
    "อุณหภูมิ": ["ไม่มี", "หนาวจัด", "หนาว", "เย็น", "ปกติ", "ร้อน", "ร้อนจัด"],
    "ท้องฟ้า": ["ไม่มี", "แจ่มใส", "มีเมฆบางส่วน", "เมฆมาก"],
    "ฝน": ["ไม่มี", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "อื่นๆ": ["ไม่มี", "รถเยอะ", "มีการเผาขยะ"]
}

st.markdown("### สถานการณ์รายวัน")
day_situations = []

for i in range(num_days):
    with st.expander(f"วันที่ {i+1}"):
        day_sit = {}
        wind = st.selectbox(f"ทิศลม (วันที่ {i+1})", ["NE", "NW", "SE", "SW"], key=f"wind_{i}")
        day_sit["ทิศลม"] = wind
        for key, options in sit_options.items():
            day_sit[key] = st.selectbox(f"{key} (วันที่ {i+1})", options, key=f"{key}_{i}")
        day_situations.append(day_sit)

# ✅ ต่อส่วน simulate, generate, download Excel ได้เลยถัดจากนี้
...

... (ตัดเนื้อหาส่วนต้นออกเพื่อความชัดเจน)

# ---------------------- SIMULATION FUNCTION ----------------------
def simulate(var, day_sit, hour, wind_dir, factory_dir):
    base = random.uniform(2, 6)
    multiplier = 1.0
    add = 0.0

    if day_sit.get("ฝน") in ["ตกปานกลาง", "ตกหนัก"]:
        multiplier *= 0.6
        add -= 1
    elif day_sit.get("ฝน") == "ตกเล็กน้อย":
        multiplier *= 0.85

    if day_sit.get("แดด") == "แดดแรง":
        add += 4
        multiplier *= 1.1
    elif day_sit.get("แดด") == "แดดอ่อน":
        add += 2

    if day_sit.get("ลม") == "แรง":
        if var == "WS": add += 3
        else: multiplier *= 0.7
    elif day_sit.get("ลม") == "ปานกลาง":
        if var == "WS": add += 1.5
    elif day_sit.get("ลม") == "นิ่ง/ไม่มีลม":
        multiplier *= 1.3
        add -= 0.5

    if day_sit.get("อุณหภูมิ") == "ร้อนจัด":
        if var == "Temp": add += 4
    elif day_sit.get("อุณหภูมิ") == "หนาวจัด":
        if var == "Temp": add -= 4

    if day_sit.get("กลิ่น") == "มีกลิ่น" and var in ["NO2", "SO2", "CO"]:
        multiplier *= 1.2

    if day_sit.get("อื่นๆ") == "รถเยอะ" and var in ["NO", "NO2", "CO"]:
        multiplier *= 1.4

    if day_sit.get("อื่นๆ") == "มีการเผาขยะ" and var in ["CO", "O3", "SO2"]:
        multiplier *= 1.3

    if near_road and var in ["NO", "NO2", "CO"]:
        multiplier *= 1.25

    if near_factory and wind_dir == factory_dir and var in ["NO2", "SO2"]:
        multiplier *= 1.5

    if var == "NO": return round(base * multiplier + add + random.uniform(0.5, 2.5), 2)
    if var == "NO2": return round(min(20, base * multiplier + add + random.uniform(0.8, 2.8)), 2)
    if var == "NOx": return None
    if var == "Temp": return round(openweather_ref.get("Temp", 27) + add + random.uniform(-2, 2), 2)
    if var == "RH": return round(openweather_ref.get("RH", 65) + add + random.uniform(-12, 15), 2)
    if var == "WS": return round(min(4, openweather_ref.get("WS", 2.5) + add + random.uniform(-1.5, 1.5)), 2)
    if var == "Pressure": return round(1010 + random.uniform(-6, 6), 2)
    if var == "SO2": return round(base * multiplier + add + random.uniform(0.6, 2.2), 2)
    if var == "CO": return round(base * multiplier + add + random.uniform(0.1, 1.0), 2)
    if var == "O3": return round(30 + add + random.uniform(5, 25), 2)
    return round(base * multiplier + add, 2)

# ---------------------- GENERATE + EXPORT ----------------------
if st.button("สร้างตารางข้อมูลและดาวน์โหลด Excel"):
    records = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = day_situations[i]
        wind_dir = sit.get("ทิศลม", "NE")

        for hour in range(24):
            row = {"Date": date.strftime("%Y-%m-%d"), "Hour": f"{hour:02d}:00"}
            no = simulate("NO", sit, hour, wind_dir, factory_direction) if "NO" in params_to_calculate else None
            no2 = simulate("NO2", sit, hour, wind_dir, factory_direction) if "NO2" in params_to_calculate else None
            nox = no + no2 if (no is not None and no2 is not None and "NOx" in params_to_calculate) else None

            for var in ["Temp", "RH", "WS", "Pressure", "SO2", "CO", "O3"]:
                if var in params_to_calculate:
                    row[var] = simulate(var, sit, hour, wind_dir, factory_direction)

            row["NO"] = no if "NO" in params_to_calculate else None
            row["NO2"] = no2 if "NO2" in params_to_calculate else None
            row["NOx"] = nox if "NOx" in params_to_calculate else None
            row["WD"] = wind_dir
            records.append(row)

    df = pd.DataFrame(records)
    st.success("✅ สร้างข้อมูลสำเร็จแล้ว")
    st.dataframe(df.head(50))

    df_env = df[[col for col in ["Date", "Hour", "WS", "WD", "Temp", "RH", "Pressure"] if col in df.columns]]
    df_env["WD_degree"] = [f'=IF(D{i+2}="NE",RANDBETWEEN(0,90),IF(D{i+2}="SE",RANDBETWEEN(91,180),IF(D{i+2}="SW",RANDBETWEEN(181,270),RANDBETWEEN(271,359))))' for i in range(len(df_env))]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if "NO" in df.columns or "NO2" in df.columns or "NOx" in df.columns:
            df[["Date", "Hour", "NO", "NO2", "NOx"]].to_excel(writer, index=False, sheet_name="NOx Group")
        if not df_env.empty:
            df_env.to_excel(writer, index=False, sheet_name="ENV")
        for param in ["SO2", "CO", "O3"]:
            if param in df.columns:
                df[["Date", "Hour", param]].to_excel(writer, index=False, sheet_name=param)

    file_name = f"AirCheckTH_{'_'.join(params_to_calculate)}_{start_date.strftime('%Y%m%d')}_{(start_date + timedelta(days=num_days-1)).strftime('%Y%m%d')}.xlsx"
    st.download_button("📥 ดาวน์โหลดไฟล์ Excel", data=output.getvalue(), file_name=file_name)
