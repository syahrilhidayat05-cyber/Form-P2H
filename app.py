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

# === Edit sesuai environment jika perlu ===
SHEET_ID = "1e9X42pvEPZP1dTQ-IY4nM3VvYRJDHuuuFoJ1maxfPZs"
DRIVE_FOLDER_ID = "1OkAj7Z2D5IVCB9fHmrNFWllRGl3hcPvq"
MAX_PHOTOS = 3  # ubah jika ingin mendukung lebih banyak foto per item

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
# HELPERS
# =========================
def safe_fname_component(s: str) -> str:
    """Bersihkan string sehingga aman untuk nama file."""
    return re.sub(r'[^A-Za-z0-9_-]+', '_', s)

def delete_local_file(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass

def save_temp_file(content, filename):
    """Simpan bytes content ke file temp dan kembalikan path."""
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    with open(temp_path, "wb") as f:
        # content bisa berupa bytes atau memoryview; pastikan bytes
        if isinstance(content, (bytes, bytearray)):
            f.write(content)
        else:
            # beberapa UploadedFile menyediakan getbuffer() atau read(); handle gracefully
            f.write(bytes(content))
    return temp_path

def upload_file_to_drive(local_path, drive_filename):
    """
    Upload local file ke Shared Drive dengan nama drive_filename.
    Kembalikan file_id jika sukses, None jika gagal.
    """
    file_metadata = {'name': drive_filename, 'parents': [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(local_path, resumable=False)
    try:
        uploaded = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True
        ).execute()
        return uploaded.get("id")
    except HttpError as e:
        st.warning(f"Gagal upload {drive_filename} ke Drive: {e}")
        return None

def save_photos_locally_and_upload(fotos, unit_rig, item, timestamp_str):
    """
    Simpan foto temporer, upload ke Drive dengan nama konsisten:
      unit_rig_timestamp_item_safe_index.ext
    Kembalikan list of hyperlink formulas (length <= MAX_PHOTOS).
    Jika upload gagal, entry akan menjadi "" sehingga kolom sheet kosong.
    """
    foto_links = []
    if not fotos:
        return []

    item_safe = safe_fname_component(item.replace(' ', '_'))

    for idx, foto in enumerate(fotos, start=1):
        if idx > MAX_PHOTOS:
            break
        # Dapatkan ekstensi asli (jika tidak ada, default .jpg)
        orig_ext = os.path.splitext(foto.name)[1] or ".jpg"
        drive_filename = f"{unit_rig}_{timestamp_str}_{item_safe}_{idx}{orig_ext}"

        # baca konten file (UploadedFile)
        try:
            # beberapa objek punya getbuffer(), beberapa punya read()
            if hasattr(foto, "getbuffer"):
                content = foto.getbuffer()
            else:
                content = foto.read()
        except Exception:
            # fallback
            try:
                content = foto.read()
            except Exception:
                content = b""

        # simpan temp lalu upload
        local_temp = save_temp_file(content, drive_filename)
        file_id = upload_file_to_drive(local_temp, drive_filename)
        delete_local_file(local_temp)

        if file_id:
            # kirim formula HYPERLINK agar diinterpretasikan oleh Sheets saat valueInputOption USER_ENTERED
            foto_links.append(f'=HYPERLINK("https://drive.google.com/file/d/{file_id}/view","Foto")')
        else:
            foto_links.append("")

    return foto_links

def append_to_sheet_row(values_list):
    """
    Append row ke Sheet1 dengan urutan kolom:
    [Tanggal, Unit Rig, Geologist, Item, Kondisi, Keterangan, Foto1, Foto2, Foto3, Waktu Submit]
    Pastikan header di Google Sheet sesuai urutan ini.
    """
    try:
        body = {"values": [values_list]}
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range="Sheet1!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
        return True
    except Exception as e:
        st.warning(f"Gagal append ke Sheet: {e}")
        return False

# =========================
# SESSION STATE
# =========================
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "photo_results" not in st.session_state:
    st.session_state.photo_results = {}

# Jika sudah submit, tampilkan halaman sukses + tombol isi baru (UX seperti kode awal)
if st.session_state.submitted:
    st.success("✅ Data berhasil disimpan ke Google Sheet!")
    if st.button("➕ Isi Form Baru"):
        st.session_state.submitted = False
        st.session_state.photo_results = {}
        # safe rerun setelah reset
        st.experimental_rerun()
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
# CHECKLIST (ACCORDION PER ITEM)
# =========================
st.subheader("Checklist Kondisi")
results = {}
error_messages = []

for item in ITEMS:
    with st.expander(item, expanded=False):
        kondisi = st.radio("Kondisi", ["Normal", "Tidak Normal"],
                           key=f"{item}_kondisi", horizontal=True)
        keterangan = ""
        fotos = []

        if kondisi == "Tidak Normal":
            keterangan = st.text_input("Keterangan", key=f"{item}_keterangan", placeholder="Isi keterangan")
            fotos = st.file_uploader("Upload Foto (min 1, max 3)", type=["jpg","jpeg","png"],
                                     accept_multiple_files=True, key=f"{item}_foto")
            # simpan uploader ke session_state agar tidak hilang across reruns
            if fotos:
                st.session_state.photo_results[item] = fotos

            fotos = st.session_state.photo_results.get(item, [])
            if fotos:
                # Preview foto (baca content; note: reading consumes buffer; but uploader object remains in session_state)
                try:
                    st.image([f.read() for f in fotos], width=200)
                except Exception:
                    # some environments may need to seek back; safe approach: re-open via bytes from getbuffer if available
                    try:
                        imgs = []
                        for fobj in fotos:
                            if hasattr(fobj, "getbuffer"):
                                imgs.append(fobj.getbuffer())
                            else:
                                imgs.append(fobj.read())
                        st.image(imgs, width=200)
                    except Exception:
                        pass

            # validasi
            if not keterangan.strip():
                error_messages.append(f"{item}: keterangan wajib diisi")
            if not fotos:
                error_messages.append(f"{item}: wajib upload minimal 1 foto")
            elif len(fotos) > MAX_PHOTOS:
                error_messages.append(f"{item}: maksimal {MAX_PHOTOS} foto")

        results[item] = {"Kondisi": kondisi, "Keterangan": keterangan}

# =========================
# SUBMIT
# =========================
if st.button("✅ Submit"):
    # header validation
    if not unit_rig:
        st.error("Unit rig wajib dipilih!"); st.stop()
    if not geologist.strip():
        st.error("Geologist wajib diisi!"); st.stop()
    if error_messages:
        st.error("Masih ada kesalahan:")
        for e in error_messages:
            st.warning(e)
        st.stop()

    # konsisten timestamp untuk semua foto di satu submit
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_ok = True
    for item, value in results.items():
        kondisi = value["Kondisi"]
        keterangan = value["Keterangan"]

        if kondisi == "Tidak Normal":
            fotos = st.session_state.photo_results.get(item, [])
            foto_links = save_photos_locally_and_upload(fotos, unit_rig, item, timestamp_str)
            # pad agar selalu length == MAX_PHOTOS
            while len(foto_links) < MAX_PHOTOS:
                foto_links.append("")
            if len(foto_links) > MAX_PHOTOS:
                foto_links = foto_links[:MAX_PHOTOS]
        else:
            foto_links = [""] * MAX_PHOTOS

        # susun row – pastikan urutan ini sesuai header di Google Sheet
        row_values = [
            tanggal.strftime("%Y-%m-%d"),
            unit_rig,
            geologist,
            item,
            kondisi,
            keterangan,
            *foto_links,  # Foto1..FotoN
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]

        ok = append_to_sheet_row(row_values)
        if not ok:
            all_ok = False
            # lanjutkan ke item lain meskipun ada kegagalan (warning sudah di-emit)

    if all_ok:
        st.session_state.submitted = True
        # tampilkan halaman sukses (kondisi di atas)
        st.experimental_rerun()
    else:
        st.error("Proses selesai dengan beberapa peringatan (cek warning). Periksa konfigurasi API/akses dan ulangi jika perlu.")
