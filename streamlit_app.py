import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math

st.set_page_config(layout="wide")

st.title("🌏 AirCheck TH (Google Map ทดลอง)")

# ---------------- Google API ----------------

GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY","")

# ---------------- จังหวัด ----------------

province_coords = {
"กรุงเทพมหานคร":(13.7563,100.5018),
"ระยอง":(12.6814,101.2770),
"ชลบุรี":(13.3611,100.9847),
"สระบุรี":(14.5289,100.9105)
}

province = st.sidebar.selectbox(
"เลือกจังหวัด",
list(province_coords.keys())
)

center_lat,center_lon = province_coords[province]

# ---------------- Google Geocode ----------------

def google_search(place):

    url="https://maps.googleapis.com/maps/api/geocode/json"

    params={
        "address":place,
        "key":GOOGLE_API_KEY
    }

    res=requests.get(url,params=params).json()

    if res["results"]:

        loc=res["results"][0]["geometry"]["location"]

        return loc["lat"],loc["lng"]

    return None

# ---------------- Search UI ----------------

st.subheader("🔎 ค้นหาสถานที่")

col1,col2=st.columns(2)

with col1:

    station_search=st.text_input("ค้นหาจุดตรวจวัด")

    if st.button("ปักจุดตรวจวัด"):

        loc=google_search(station_search)

        if loc:
            st.session_state.station=loc
            st.rerun()

with col2:

    factory_search=st.text_input("ค้นหาโรงงาน")

    if st.button("เพิ่มโรงงาน"):

        loc=google_search(factory_search)

        if loc:

            if "factories" not in st.session_state:
                st.session_state.factories=[]

            st.session_state.factories.append(loc)

            st.rerun()

# ---------------- Map ----------------

if "station" in st.session_state:
    map_center=st.session_state.station
else:
    map_center=[center_lat,center_lon]

m=folium.Map(
location=map_center,
zoom_start=12,
tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
attr="Google"
)

# station marker

if "station" in st.session_state:

    folium.Marker(
        st.session_state.station,
        tooltip="Station",
        icon=folium.Icon(color="green")
    ).add_to(m)

# factory markers

if "factories" in st.session_state:

    for f in st.session_state.factories:

        folium.Marker(
            f,
            tooltip="Factory",
            icon=folium.Icon(color="red")
        ).add_to(m)

map_data=st_folium(m,height=500,width=1200)

# click map

if map_data["last_clicked"]:

    lat=map_data["last_clicked"]["lat"]
    lon=map_data["last_clicked"]["lng"]

    if "station" not in st.session_state:
        st.session_state.station=(lat,lon)

    else:

        if "factories" not in st.session_state:
            st.session_state.factories=[]

        st.session_state.factories.append((lat,lon))

# ---------------- Distance ----------------

def distance_km(lat1,lon1,lat2,lon2):

    R=6371

    dlat=math.radians(lat2-lat1)
    dlon=math.radians(lon2-lon1)

    a=math.sin(dlat/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2

    c=2*math.atan2(math.sqrt(a),math.sqrt(1-a))

    return R*c

station=st.session_state.get("station")
factories=st.session_state.get("factories",[])

if station and factories:

    st.subheader("ระยะโรงงาน")

    for i,f in enumerate(factories):

        dist=distance_km(
            station[0],station[1],
            f[0],f[1]
        )

        st.write(f"โรงงาน {i+1} : {dist:.2f} km")
