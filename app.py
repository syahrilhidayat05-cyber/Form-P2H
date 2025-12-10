import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re
import tempfile

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
import gspread

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Form P2H Unit", layout="wide")

# Google Sheet untuk data
SHEET_ID = "1e9X42pvEPZP1dTQ-IY4nM3VvYRJDHuuuFoJ1maxfPZs"

# Shared Drive folder untuk foto
DRIVE_FOLDER_ID = "1OkAj7Z2D5IVCB9fHmrNFWllRGl3hcPvq"

# Rig & Item
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
# HELPER FUNCTIONS
# =========================
def delete_local_file(path):
    if os.path.exists(path):
        os.remove(path)

def generate_filename(prefix="file", ext="jpg", custom_text=""):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if custom_text:
        custom_text = re.sub(r'[^A-Za-z0-9_-]+', '_', custom_text)
    if custom_text:
        return f"{prefix}_{custom_text}_{timestamp}.{ext}"
    return f"{prefix}_{timestamp}.{ext}"

def save_temp_file(content, filename):
    temp_dir = tempfile.gettempdir()
    filepath = os.path.join(temp_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return filepath

# =========================
# GOOGLE DRIVE UPLOAD (foto)
# =========================
def upload_to_drive(filepath, filename):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gdrive"], scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(filepath, resumable=False)

    try:
        uploaded = service.files().create(
            body=file_metadata, media_body=media, fields="id, parents"
        ).execute()
        return uploaded.get("id")
    except HttpError as e:
        st.error("Terjadi error saat upload foto ke Shared Drive!")
        st.error(f"Status code: {e.resp.status}")
        st.error(f"Detail: {e.content.decode() if isinstance(e.content, bytes) else e.content}")
        raise

# =========================
# SAVE FOTO LOKAL
# =========================
def save_photos(item, fotos, unitrig, timestamp_str):
    folder = "P2H-UPLOAD"
    os.makedirs(folder, exist_ok=True)

    saved_paths = []
    index = 1
    for foto in fotos:
        ext = os.path.splitext(foto.name)[1]
        filename = f"{unitrig}_{timestamp_str}_{item.replace(' ','_')}_{index}{ext}"
        filepath = os.path.join(folder, filename)
        with open(filepath, "wb") as f:
            f.write(foto.getbuffer())
        saved_paths.append(filepath)
        index += 1
    return saved_paths

# =========================
# GOOGLE SHEET APPEND
# =========================
def append_to_sheet(row):
    creds = Credentials.from_service_account_info(st.secrets["gdrive"])
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    sheet.append_row(list(row.values()))

# =========================
# SESSION STATE
# =========================
if "submitted" not in st.session_state:
    st.session_state.submitted = False

if st.session_state.submitted:
    st.success("✅ Data berhasil disimpan!")
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
    with c1: st.write(item)
    with c2:
        kondisi = st.radio("", ["Normal","Tidak Normal"], key=f"{item}_kondisi", horizontal=True)
    with c3:
        keterangan = ""
        if kondisi == "Tidak Normal":
            keterangan = st.text_input("", key=f"{item}_keterangan", placeholder="Isi keterangan", label_visibility="collapsed")
    fotos = []
    if kondisi == "Tidak Normal":
        fotos = st.file_uploader(f"Upload Foto – {item} (max 3 foto)", type=["jpg","jpeg","png"], accept_multiple_files=True, key=f"{item}_foto")
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
            saved_paths = save_photos(item, fotos, unit_rig, timestamp_str)
            foto_links = []
            for p in saved_paths:
                drive_filename = generate_filename(prefix=unit_rig, custom_text=item.replace(" ", "_"), ext=p.split(".")[-1])
                with open(p, "rb") as f:
                    temp_path = save_temp_file(f.read(), drive_filename)
                gfile_id = upload_to_drive(temp_path, drive_filename)
                delete_local_file(temp_path)
                delete_local_file(p)
                foto_links.append(f'=HYPERLINK("https://drive.google.com/file/d/{gfile_id}/view","Foto")')
            foto_hyperlinks = "\n".join(foto_links)

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

    st.success("Data berhasil disimpan ke Google Sheet & foto ke Shared Drive!")
    st.session_state.submitted = True
    st.rerun()
