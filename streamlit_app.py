import streamlit as st
import pandas as pd
from datetime import datetime

import streamlit as st
import pandas as pd
from datetime import datetime

import streamlit as st
import pandas as pd
from datetime import datetime

import streamlit as st
import pandas as pd
from datetime import datetime

USERS = {
    "user01": {"password": "userpass", "role": "user"},
    "user02": {"password": "abc123", "role": "user"},
    "siwanon": {"password": "036623054", "role": "admin"}
}
import streamlit as st
import pandas as pd
from datetime import datetime
import os

import pandas as pd
import os

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
if st.session_state.role == "admin":
    st.write("คุณคือแอดมิน 🛡️")


# (ต่อส่วน UI เดิมของคุณจากตรงนี้ เช่น เลือกวันที่, สร้างตาราง, สร้าง Excel ฯลฯ)


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

if st.session_state.role == "admin":
    with st.expander("📋 ดูประวัติการเข้าใช้งาน (admin เท่านั้น)"):
        try:
            df_log = pd.read_csv("user_log.csv")
            st.dataframe(df_log.tail(100))  # แสดงรายการล่าสุด 100 แถว
        except:
            st.info("ยังไม่มี log หรือโหลด log ไม่ได้")

