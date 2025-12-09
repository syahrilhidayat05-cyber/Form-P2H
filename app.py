import streamlit as st
import pandas as pd
from datetime import datetime
import os

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Form P2H Unit", layout="wide")

TEMP_FOLDER = "temp_files"
os.makedirs(TEMP_FOLDER, exist_ok=True)

# folder Google Drive
DRIVE_FOLDER_ID = "1uENtDsPGpoAKelLL2Gj-0qBE7-zhhUQg"

RIG_LIST = [
    "CNI-01", "CNI-02", "CNI-03", "CNI-04",
    "CNI-05", "CNI-06", "CNI-07", "CNI-08",
    "CNI-09", "CNI-10", "CNI-11", "CNI-12",
    "CNI-13", "CNI-14", "CNI-15", "CNI-16"
]

ITEMS = [
    "Oli mesin", "Air Radiator", "Vanbelt", "Tangki solar", "Oli hidraulik",
    "Oil seal Hidraulik", "Baut Skor menara", "Wire line", "Clamp terpasang",
    "Eye bolt", "Lifting dg dos", "Hostplug bering", "Spearhead point",
    "Guarding pipa berputar", "Safety inner", "Guarding vanbelt pompa rig",
    "Jergen krisbow solar", "APAR"
]

# =========================
# GOOGLE DRIVE UPLOAD
# =========================
def upload_to_drive(filepath, filename):
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    creds = Credentials.from_service_account_info(
        st.secrets["gdrive"],
        scopes=SCOPES
    )

    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': filename,
        'parents': [DRIVE_FOLDER_ID]
    }

    media = MediaFileUpload(
        filepath,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

# =========================
# SESSION STATE
# =========================
if "submitted" not in st.session_state:
    st.session_state.submitted = False

if st.session_state.submitted:
    st.success("✅ Data berhasil disimpan ke Google Drive!")

    if st.button("➕ Isi Form Baru"):
        st.session_state.submitted = False
        st.rerun()

    st.stop()

# =========================
# FORM HEADER
# =========================
st.title("Form P2H Unit")

col1, col2, col3 = st.columns(3)

with col1:
    tanggal = st.date_input("Tanggal")

with col2:
    unit_rig = st.selectbox("Unit Rig", options=[""] + RIG_LIST)

with col3:
    geologist = st.text_input("Geologist")

# =========================
# CHECKLIST
# =========================
st.subheader("Checklist Kondisi")

results = {}
error_messages = []

h1, h2, h3 = st.columns([2,3,3])
with h1: st.markdown("**Item**")
with h2: st.markdown("**Kondisi**")
with h3: st.markdown("**Keterangan**")

st.divider()

for item in ITEMS:

    c1, c2, c3 = st.columns([2,3,3])

    with c1:
        st.write(item)

    with c2:
        kondisi = st.radio(
            "",
            ["Normal", "Tidak Normal", "Perbaikan"],
            key=f"{item}_kondisi",
            horizontal=True
        )

    with c3:
        keterangan = ""
        if kondisi in ["Tidak Normal", "Perbaikan"]:
            keterangan = st.text_input(
                "",
                key=f"{item}_keterangan",
                placeholder="Isi keterangan",
                label_visibility="collapsed"
            )

    if kondisi in ["Tidak Normal", "Perbaikan"] and not keterangan.strip():
        error_messages.append(f"{item} wajib diisi keterangannya")

    results[item] = {
        "Kondisi": kondisi,
        "Keterangan": keterangan
    }

    st.divider()

# =========================
# SUBMIT
# =========================
if st.button("✅ Submit"):

    if not unit_rig:
        st.error("Unit rig wajib dipilih!")
        st.stop()

    if not geologist.strip():
        st.error("Geologist wajib diisi!")
        st.stop()

    if error_messages:
        st.error("Masih ada kesalahan:")
        for e in error_messages:
            st.warning(e)
        st.stop()

    # Buat DataFrame
    rows = []
    for item, value in results.items():
        rows.append({
            "Tanggal": tanggal.strftime("%Y-%m-%d"),
            "Unit Rig": unit_rig,
            "Geologist": geologist,
            "Item": item,
            "Kondisi": value["Kondisi"],
            "Keterangan": value["Keterangan"],
            "Waktu Submit": datetime.now()
        })

    df = pd.DataFrame(rows)

    # Nama file
    now = datetime.now()
    filename = f"P2H_{unit_rig}_{now.strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(TEMP_FOLDER, filename)

    # Simpan Excel
    df.to_excel(filepath, index=False)

    # Upload ke Google Drive
    upload_to_drive(filepath, filename)

    st.session_state.submitted = True
    st.rerun()
