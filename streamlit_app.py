import streamlit as st
import pandas as pd
import numpy as np
import datetime
from meteostat import Point, Hourly
import random
import openpyxl

# ตั้งค่าพิกัดพื้นที่ (กรุงเทพฯ)
location = Point(13.7563, 100.5018)

# ตัวเลือกสถานการณ์
situation_options = {
    "ฝน": ["ไม่มีฝน", "ตกเล็กน้อย", "ตกปานกลาง", "ตกหนัก"],
    "แดด": ["ไม่มีแดด", "แดดอ่อน", "แดดแรง"],
    "ลม": ["นิ่ง/ไม่มีลม", "ลมเบา", "แรง"],
    "อุณหภูมิ": ["ปกติ", "ร้อนจัด", "หนาวจัด"],
    "กลิ่น": ["ไม่มีกลิ่น", "มีกลิ่น"],
    "อื่นๆ": ["-", "รถเยอะ", "มีการเผาขยะ"]
}

@st.cache_data
def get_weather_data(date):
    start = datetime.datetime.combine(date, datetime.time(0, 0))
    end = datetime.datetime.combine(date, datetime.time(23, 59))
    data = Hourly(location, start, end)
    return data.fetch()

def simulate(var, sit, hour, wind_dir, ref):
    multiplier = 1.0
    add = 0.0

    # ปรับสถานการณ์
    if sit["ฝน"] in ["ตกปานกลาง", "ตกหนัก"]:
        multiplier *= 0.6
        add -= 1
    elif sit["ฝน"] == "ตกเล็กน้อย":
        multiplier *= 0.85

    if sit["แดด"] == "แดดแรง":
        multiplier *= 1.1
        add += 4
    elif sit["แดด"] == "แดดอ่อน":
        add += 2

    if sit["ลม"] == "แรง":
        if var == "WS":
            add += 3
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

    base = ref if ref is not None else (random.uniform(2, 6) if var not in ["Temp", "RH", "WS"] else 27)

    if var == "NO":
        return round(base * multiplier + add + random.uniform(0.5, 2.5), 2)
    if var == "NO2":
        return round(min(20, base * multiplier + add + random.uniform(0.8, 2.8)), 2)
    if var == "NOx":
        return None
    if var == "WS":
        val = ref * multiplier + add + random.uniform(0.1, 0.5) if ref is not None else random.uniform(0.5, 4)
        return round(val * 0.15, 2)  # ลดลง 85%
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

# UI
st.title("จำลองคุณภาพอากาศจากสถานการณ์จำลอง")

date = st.date_input("เลือกวันที่อ้างอิง", datetime.date(2025, 7, 15))
meteo_data = get_weather_data(date)

st.header("สถานการณ์")
situation = {k: st.selectbox(k, v, key=k) for k, v in situation_options.items()}

results = []
for hour in range(24):
    ref_row = meteo_data.iloc[hour] if hour < len(meteo_data) else None
    wind_dir = int(ref_row["wdir"]) if ref_row is not None and not np.isnan(ref_row["wdir"]) else 90

    data_point = {
        "Hour": f"{hour:02d}:00",
        "NO": simulate("NO", situation, hour, wind_dir, None),
        "NO2": simulate("NO2", situation, hour, wind_dir, None),
        "SO2": simulate("SO2", situation, hour, wind_dir, None),
        "CO": simulate("CO", situation, hour, wind_dir, None),
        "O3": simulate("O3", situation, hour, wind_dir, None),
        "WS": simulate("WS", situation, hour, wind_dir, ref_row["wspd"] if ref_row is not None else None),
        "WD": wind_dir,
        "Temp": simulate("Temp", situation, hour, wind_dir, ref_row["temp"] if ref_row is not None else None),
        "RH": simulate("RH", situation, hour, wind_dir, ref_row["rhum"] if ref_row is not None else None),
    }
    results.append(data_point)

df = pd.DataFrame(results)
st.dataframe(df)

# Export to Excel
def to_excel(df1, df2):
    from io import BytesIO
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df1.to_excel(writer, index=False, sheet_name='Simulated')
    df2.to_excel(writer, index=False, sheet_name='Reference')
    writer.save()
    return output.getvalue()

ref_df = meteo_data.reset_index()[["time", "temp", "rhum", "wspd", "wdir"]].rename(
    columns={"time": "Time", "temp": "Temp", "rhum": "RH", "wspd": "WS", "wdir": "WD"}
)
excel = to_excel(df, ref_df)

st.download_button("📥 ดาวน์โหลดผลลัพธ์ (Excel)", data=excel, file_name="air_quality_simulation.xlsx")
