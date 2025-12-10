import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re
import tempfile
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Form P2H Unit", layout="wide")

# Google Sheet ID
SHEET_ID = "1e9X42pvEPZP1dTQ-IY4nM3VvYRJDHuuuFoJ1maxfPZs"

# Shared Drive folder untuk foto
DRIVE_FOLDER_ID = "1OkAj7Z2D5IVCB9fHmrNFWllRGl3hcPvq"

TEMP_FOLDER = "temp_files"
os.makedirs(TEMP_FOLDER, exist_ok=True)

RIG_LIST = [
    "CNI-01","CNI-02","CNI-03","CNI-04",
    "CNI-05","CNI-06","CNI-07","CNI-08",
    "CNI-09","CNI-10","CNI-11","CNI-12",
    "CNI-13","CNI-14","CNI-15","CNI-16"
]

ITEMS = [
    "Oli mesin","Air Radiator","Vanbelt","Tangki solar","Oli hidraulik",
    "Oil seal Hidraulik","Baut Skor menara","Wire line","Clamp terpasang",
    "Eye bolt","Lifting dg dos","Hostplug bering","Spearhead point",
    "Guarding pipa berputar","Safety inner","Guarding vanbelt pompa rig",
    "Jergen krisbow solar","APAR"
]

# =========================
# AUTH GOOGLE SHEET & DRIVE
# =========================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["gdrive"],
    scopes=SCOPES
)

# Google Sheets client
gc = gspread.authorize(creds)

# Google Drive client
drive_service = build('drive', 'v3', credentials=creds)

# =========================
# DELETE LOCAL FILE
# =========================
def delete_local_file(path):
    if os.path.exists(path):
        os.remove(path)

# =========================
# SAVE FOTO KE DRIVE
# =========================
def save_photos_to_drive(fotos, unit_rig, item, timestamp_str):
    saved_links = []
    for idx, foto in enumerate(fotos, start=1):
        ext = os.path.splitext(foto.name)[1]
        filename = f"{unit_rig}_{timestamp_str}_{item.replace(' ','_')}_{idx}{ext}"
        temp_path = os.path.join(tempfile.gettempdir(), filename)

        # Simpan sementara
        with open(temp_path, "wb") as f:
            f.write(foto.getbuffer())

        # Upload ke Drive
        file_metadata = {
            'name': filename,
            'parents': [DRIVE_FOLDER_ID]
        }
        media = MediaFileUpload(temp_path, resumable=False)

        try:
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"
            ).execute()
            file_id = file.get("id")
            link = f'=HYPERLINK("https://drive.google.com/file/d/{file_id}/view","Foto")'
            saved_links.append(link)
        except HttpError as e:
            st.error(f"Gagal upload foto {filename}: {e}")
        finally:
            delete_local_file(temp_path)

    return "\n".join(saved_links)

# =========================
# APPEND KE SHEET
# =========================
def append_to_sheet(row):
    try:
        sheet = gc.open_by_key(SHEET_ID).sheet1
        sheet.append_row(list(row.values()), value_input_option='USER_ENTERED')
    except Exception as e:
        st.error(f"Gagal append ke Sheet: {e}")
        st.stop()

# =========================
# SESSION STATE
# =========================
if "submitted" not in st.session_state:
    st.session_state.submitted = False

if st.session_state.submitted:
    st.success("✅ Data berhasil disimpan ke Google Sheet!")
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
photo_results = {}
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
        kondisi = st.radio("", ["Normal","Tidak Normal"],
                           key=f"{item}_kondisi", horizontal=True)
    with c3:
        keterangan = ""
        if kondisi == "Tidak Normal":
            keterangan = st.text_input(
                "", key=f"{item}_keterangan",
                placeholder="Isi keterangan",
                label_visibility="collapsed"
            )
    fotos = []
    if kondisi == "Tidak Normal":
        fotos = st.file_uploader(
            f"Upload Foto – {item} (min 1, max 3 foto)",
            type=["jpg","jpeg","png"],
            accept_multiple_files=True,
            key=f"{item}_foto"
        )
        if len(fotos) == 0:
            error_messages.append(f"{item}: wajib upload minimal 1 foto")
        elif len(fotos) > 3:
            error_messages.append(f"{item}: maksimal 3 foto")

    results[item] = {"Kondisi": kondisi, "Keterangan": keterangan}
    photo_results[item] = fotos

    if kondisi == "Tidak Normal" and not keterangan.strip():
        error_messages.append(f"{item} wajib diisi keterangannya")

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

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # PROSES PER ITEM
    for item, value in results.items():
        kondisi = value["Kondisi"]
        keterangan = value["Keterangan"]
        foto_hyperlinks = ""

        if kondisi == "Tidak Normal":
            fotos = photo_results.get(item, [])
            foto_hyperlinks = save_photos_to_drive(fotos, unit_rig, item, timestamp_str)

        new_row = {
            "Tanggal": tanggal.strftime("%Y-%m-%d"),
            "Unit Rig": unit_rig,
            "Geologist": geologist,
            "Item": item,
            "Kondisi": kondisi,
            "Keterangan": keterangan,
            "Foto": foto_hyperlinks,
            "Waktu Submit": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        append_to_sheet(new_row)

    st.success("✅ Semua data berhasil tersimpan di Google Sheet!")
    st.session_state.submitted = True
    st.rerun()
