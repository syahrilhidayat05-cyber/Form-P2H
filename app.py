import streamlit as st
from datetime import datetime
import os
import re
import tempfile
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Form P2H Unit", layout="wide")
TEMP_FOLDER = "temp_files"
os.makedirs(TEMP_FOLDER, exist_ok=True)
SHEET_ID = "1e9X42pvEPZP1dTQ-IY4nM3VvYRJDHuuuFoJ1maxfPZs"
DRIVE_FOLDER_ID = "1OkAj7Z2D5IVCB9fHmrNFWllRGl3hcPvq"

RIG_LIST = [f"CNI-{str(i).zfill(2)}" for i in range(1,17)]
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

creds = Credentials.from_service_account_info(st.secrets["gdrive"], scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)
sheets_service = build('sheets', 'v4', credentials=creds)

# =========================
# UTILS
# =========================
def delete_local_file(path):
    if os.path.exists(path):
        os.remove(path)

def generate_filename(prefix="file", ext="jpg", custom_text=""):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    custom_text = re.sub(r'[^A-Za-z0-9_-]+', '_', custom_text)
    return f"{prefix}_{custom_text}_{timestamp}.{ext}" if custom_text else f"{prefix}_{timestamp}.{ext}"

def save_temp_file(content, filename):
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    with open(temp_path, "wb") as f:
        f.write(content)
    return temp_path

def upload_to_drive(filepath, filename):
    file_metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(filepath, resumable=False)
    try:
        uploaded = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True
        ).execute()
        return uploaded.get("id")
    except HttpError as e:
        st.error(f"Gagal upload {filename}: {e}")
        return None

def save_photos(item, fotos, unitrig, timestamp_str):
    folder = "P2H-UPLOAD"
    os.makedirs(folder, exist_ok=True)
    saved_paths = []
    for idx, foto in enumerate(fotos, 1):
        ext = os.path.splitext(foto.name)[1]
        filename = f"{unitrig}_{timestamp_str}_{item.replace(' ','_')}_{idx}{ext}"
        path = os.path.join(folder, filename)
        with open(path, "wb") as f:
            f.write(foto.getbuffer())
        saved_paths.append(path)
    return saved_paths

def append_to_sheet(row):
    try:
        body = {"values": [list(row.values())]}
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range="Sheet1!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
    except Exception as e:
        st.warning(f"Gagal append ke Sheet untuk item {row['Item']}: {e}")

# =========================
# SESSION STATE
# =========================
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "photo_results" not in st.session_state:
    st.session_state.photo_results = {}

if st.session_state.submitted:
    st.success("✅ Data berhasil disimpan ke Google Sheet!")
    if st.button("➕ Isi Form Baru"):
        st.session_state.submitted = False
        st.session_state.photo_results = {}
        st.rerun()
    st.stop()

# =========================
# FORM HEADER
# =========================
st.title("Form P2H Unit")
col1, col2, col3 = st.columns(3)
with col1: tanggal = st.date_input("Tanggal")
with col2: unit_rig = st.selectbox("Unit Rig", options=[""] + RIG_LIST)
with col3: geologist = st.text_input("Geologist")

# =========================
# CHECKLIST (ACCORDION PER ITEM)
# =========================
st.subheader("Checklist Kondisi")
results = {}
error_messages = []

for item in ITEMS:
    with st.expander(item):
        kondisi = st.radio("Kondisi", ["Normal","Tidak Normal"], key=f"{item}_kondisi", horizontal=True)
        keterangan = ""
        fotos = []

        if kondisi == "Tidak Normal":
            keterangan = st.text_input("Keterangan", key=f"{item}_keterangan", placeholder="Isi keterangan")
            fotos = st.file_uploader("Upload Foto (max 3)", type=["jpg","jpeg","png"], accept_multiple_files=True, key=f"{item}_foto")
            if fotos: st.session_state.photo_results[item] = fotos
            fotos = st.session_state.photo_results.get(item, [])

            if fotos:
                st.image([f.read() for f in fotos], width=200)

            if not keterangan.strip():
                error_messages.append(f"{item}: keterangan wajib diisi")
            if not fotos:
                error_messages.append(f"{item}: wajib upload minimal 1 foto")
            elif len(fotos) > 3:
                error_messages.append(f"{item}: maksimal 3 foto")

        results[item] = {"Kondisi": kondisi, "Keterangan": keterangan}

# =========================
# SUBMIT
# =========================
if st.button("✅ Submit"):
    if not unit_rig:
        st.error("Unit rig wajib dipilih!"); st.stop()
    if not geologist.strip():
        st.error("Geologist wajib diisi!"); st.stop()
    if error_messages:
        st.error("Masih ada kesalahan:")
        for e in error_messages: st.warning(e)
        st.stop()

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    for item, value in results.items():
        kondisi = value["Kondisi"]
        keterangan = value["Keterangan"]
        foto_hyperlinks = ""

        if kondisi == "Tidak Normal":
            fotos = st.session_state.photo_results.get(item, [])
            saved_paths = save_photos(item, fotos, unit_rig, timestamp_str)
            foto_links = []

            for p in saved_paths:
                drive_filename = generate_filename(prefix=unit_rig, custom_text=item.replace(" ","_"), ext=p.split(".")[-1])
                temp_path = save_temp_file(open(p, "rb").read(), drive_filename)
                gfile_id = upload_to_drive(temp_path, drive_filename)
                delete_local_file(temp_path)
                delete_local_file(p)
                if gfile_id:
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

    st.session_state.submitted = True
    st.rerun()
