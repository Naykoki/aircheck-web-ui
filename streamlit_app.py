import streamlit as st
import pandas as pd
from datetime import datetime

import streamlit as st
import pandas as pd
from datetime import datetime

import streamlit as st
import pandas as pd
from datetime import datetime

# --------------------- LOGIN SYSTEM ---------------------
if "username" not in st.session_state:
    st.session_state.username = ""

if st.session_state.username == "":
    st.title("👤 ยินดีต้อนรับสู่ AirCheck TH")
    name = st.text_input("กรุณาใส่ชื่อของคุณเพื่อเข้าใช้งาน:")
    if st.button("เข้าสู่ระบบ"):
        if name.strip() == "":
            st.warning("⚠️ กรุณากรอกชื่อก่อนเข้าสู่ระบบ")
        else:
            st.session_state.username = name.strip()
            # บันทึก log
            try:
                with open("user_log.csv", "a", encoding="utf-8") as f:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"{now},{name.strip()}\n")
            except:
                pass
            st.success("✅ เข้าสู่ระบบสำเร็จแล้ว!")
            st.experimental_rerun()

# ✅ ถ้ายังไม่ login → ไม่ให้แสดงเนื้อหาอื่น
if st.session_state.username == "":
    st.stop()

st.sidebar.success(f"👋 สวัสดีคุณ {st.session_state.username}")
# ---------------------- UI CONFIG ----------------------
st.set_page_config(page_title="AirCheck TH (Web)", layout="wide")
st.title("AirCheck TH - Web Version")

# ---------------------- INPUTS ----------------------
col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input("วันที่เริ่มต้น", datetime.today())
    num_days = st.slider("จำนวนวัน (1-8)", 1, 8, 3)
    factory_direction = st.selectbox("ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])

with col2:
    st.markdown("### สภาพแวดล้อม")
    near_road = st.checkbox("ใกล้ถนน")
    near_factory = st.checkbox("ใกล้โรงงาน")

# ---------------------- SITUATIONS ----------------------
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

# ---------------------- SIMULATE FUNCTION ----------------------
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

    if near_factory and wind_dir == factory_direction and var in ["NO2", "SO2"]:
        multiplier *= 1.5

    if var == "NO": return round(base * multiplier + add + random.uniform(0.5, 2.5), 2)
    if var == "NO2": return round(base * multiplier + add + random.uniform(0.8, 2.8), 2)
    if var == "NOx": return None
    if var == "Temp": return round(27 + add + random.uniform(-2, 2), 2)
    if var == "RH": return round(65 + add + random.uniform(-12, 15), 2)
    if var == "WS": return round(min(4, 2.5 + add + random.uniform(-1.5, 1.5)), 2)
    if var == "Pressure": return round(1010 + random.uniform(-6, 6), 2)
    if var == "SO2": return round(base * multiplier + add + random.uniform(0.6, 2.2), 2)
    if var == "CO": return round(base * multiplier + add + random.uniform(0.1, 1.0), 2)
    if var == "O3": return round(30 + add + random.uniform(5, 25), 2)
    return round(base * multiplier + add, 2)

# ---------------------- GENERATE ----------------------
if st.button("สร้างตารางข้อมูล"):
    records = []
    for i in range(num_days):
        date = start_date + timedelta(days=i)
        sit = day_situations[i]
        wind_dir = sit.get("ทิศลม", "NE")

        for hour in range(24):
            no = simulate("NO", sit, hour, wind_dir, factory_direction)
            no2 = simulate("NO2", sit, hour, wind_dir, factory_direction)
            nox = no + no2
            temp = simulate("Temp", sit, hour, wind_dir, factory_direction)
            rh = simulate("RH", sit, hour, wind_dir, factory_direction)
            ws = simulate("WS", sit, hour, wind_dir, factory_direction)
            pres = simulate("Pressure", sit, hour, wind_dir, factory_direction)
            so2 = simulate("SO2", sit, hour, wind_dir, factory_direction)
            co = simulate("CO", sit, hour, wind_dir, factory_direction)
            o3 = simulate("O3", sit, hour, wind_dir, factory_direction)

            records.append({
                "Date": date.strftime("%Y-%m-%d"), "Hour": f"{hour:02d}:00",
                "NO": no, "NO2": no2, "NOx": nox,
                "Temp": temp, "RH": rh, "WS": ws, "WD": wind_dir, "Pressure": pres,
                "SO2": so2, "CO": co, "O3": o3
            })

    df = pd.DataFrame(records)
    st.success("สร้างข้อมูลสำเร็จแล้ว!")
    st.dataframe(df)

    df_nox = df[["Date", "Hour", "NO", "NO2", "NOx"]]
    df_env = df[["Date", "Hour", "WS", "WD", "Temp", "RH", "Pressure"]]
    df_so2 = df[["Date", "Hour", "SO2"]]
    df_co = df[["Date", "Hour", "CO"]]
    df_o3 = df[["Date", "Hour", "O3"]]

    df_env["WD_degree"] = [f'=IF(D{i+2}="NE",RANDBETWEEN(0,90),IF(D{i+2}="SE",RANDBETWEEN(91,180),IF(D{i+2}="SW",RANDBETWEEN(181,270),IF(D{i+2}="NW",RANDBETWEEN(271,359),""))))' for i in range(len(df_env))]

    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_nox.to_excel(writer, index=False, sheet_name="NOx Group")
        df_env.to_excel(writer, index=False, sheet_name="ENV")
        df_so2.to_excel(writer, index=False, sheet_name="SO2")
        df_co.to_excel(writer, index=False, sheet_name="CO")
        df_o3.to_excel(writer, index=False, sheet_name="O3")

    st.download_button("📥 ดาวน์โหลดเป็น Excel", data=output.getvalue(), file_name="AirCheckTH_Web.xlsx")
