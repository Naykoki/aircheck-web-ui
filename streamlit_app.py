import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
from io import BytesIO
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random
import os

# ---------------------- User Management ----------------------
def load_users():
    if os.path.exists("users.csv"):
        return pd.read_csv("users.csv")
    else:
        return pd.DataFrame(columns=["username", "password", "role"])

def save_user(new_user):
    df = load_users()
    df = pd.concat([df, pd.DataFrame([new_user])], ignore_index=True)
    df.to_csv("users.csv", index=False)

def get_user_info(username):
    df = load_users()
    row = df[df["username"] == username]
    if not row.empty:
        return row.iloc[0]["password"], row.iloc[0]["role"]
    return None, None

# ---------------------- Login Session ----------------------
if "username" not in st.session_state:
    st.session_state.username = ""
    st.session_state.role = ""

# ---------------------- Register Section ----------------------
with st.expander("📝 สมัครสมาชิก"):
    new_user = st.text_input("ชื่อผู้ใช้ใหม่")
    new_pass = st.text_input("รหัสผ่าน", type="password")
    if st.button("สมัครใช้งาน"):
        if new_user.strip() == "" or new_pass.strip() == "":
            st.warning("⚠️ กรุณากรอกให้ครบถ้วน")
        else:
            df_users = load_users()
            if new_user in df_users["username"].values:
                st.error("❌ ชื่อผู้ใช้นี้ถูกใช้แล้ว กรุณาเลือกชื่อใหม่")
            else:
                save_user({"username": new_user, "password": new_pass, "role": "user"})
                st.success("✅ สมัครสมาชิกเรียบร้อยแล้ว! กรุณาเข้าสู่ระบบ")

# ---------------------- Login Section ----------------------
if st.session_state.username == "":
    st.title("🔐 เข้าสู่ระบบ")
    user_input = st.text_input("Username")
    pass_input = st.text_input("Password", type="password")
    login_btn = st.button("เข้าสู่ระบบ")

    if login_btn:
        pw, role = get_user_info(user_input)
        if pw and pass_input == pw:
            st.session_state.username = user_input
            st.session_state.role = role

            # Log login
            log_entry = {
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user": user_input,
                "role": role
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
        else:
            st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    st.stop()

# ---------------------- Logged In ----------------------
st.sidebar.success(f"👋 ยินดีต้อนรับ {st.session_state.username} ({st.session_state.role})")

if st.session_state.role == "admin":
    with st.expander("📋 ดูประวัติการเข้าใช้งาน (admin เท่านั้น)"):
        try:
            df_log = pd.read_csv("user_log.csv")
            st.dataframe(df_log.tail(100))
        except:
            st.info("ยังไม่มี log หรือโหลด log ไม่ได้")

# (ต่อส่วน UI เดิมของคุณจากตรงนี้ เช่น เลือกวันที่, สร้างตาราง, สร้าง Excel ฯลฯ)

# ---------------------- PAGE CONFIG ----------------------
st.set_page_config(page_title="AirCheck TH (Web)", layout="wide")
st.title("AirCheck TH - Web Version")

# ---------------------- OPENWEATHER DEFAULT ----------------------
openweather_ref = {
    "Temp": 27.0,
    "RH": 65.0,
    "WS": 2.5
}

# ---------------------- INPUT ----------------------
col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input("วันที่เริ่มต้น", datetime.today())
    num_days = st.slider("จำนวนวัน (1-8)", 1, 8, 3)
    factory_direction = st.selectbox("ทิศทางโรงงาน", ["NE", "NW", "SE", "SW"])

with col2:
    st.markdown("### สภาพแวดล้อม")
    near_road = st.checkbox("ใกล้ถนน")
    near_factory = st.checkbox("ใกล้โรงงาน")

params_to_calculate = st.multiselect("เลือกพารามิเตอร์ที่ต้องการคำนวณ", [
    "NO", "NO2", "NOx", "SO2", "CO", "O3", "WS", "WD", "Temp", "RH", "Pressure"
], default=["NO", "NO2", "NOx", "WS", "WD", "Temp", "RH", "Pressure"])

# ---------------------- DAILY SITUATIONS ----------------------
sit_options = {
    "แดด": ["ไม่มี", "แดดอ่อน", "แดดแรง"],
    "ลม": ["ไม่มี", "นิ่ง/ไม่มีลม", "เบา", "ปานกลาง", "แรง"],
    "กลิ่น": ["ไม่มี", "มีกลิ่น"],
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
    df_env["WD_degree"] = [
        f'=IF(D{i+2}="NE",RANDBETWEEN(0,90),IF(D{i+2}="SE",RANDBETWEEN(91,180),IF(D{i+2}="SW",RANDBETWEEN(181,270),RANDBETWEEN(271,359))))'
        for i in range(len(df_env))
    ]

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
