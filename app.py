import streamlit as st
from datetime import datetime, timedelta
import os
import re
import tempfile

# timezone: try zoneinfo first (Python 3.9+), fallback to manual UTC+7
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

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

RIG_LIST = [f"CNI-{str(i).zfill(2)}" for i in range(1, 17)]
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
        if isinstance(content, (bytes, bytearray)):
            f.write(content)
        else:
            # fallback: try to get bytes-like
            try:
                f.write(content.tobytes())
            except Exception:
                try:
                    f.write(bytes(content))
                except Exception:
                    f.write(b"")
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

def append_to_sheet_row(values_list):
    """
    Append row ke Sheet1 dengan urutan kolom:
    [Tanggal, Unit Rig, Geologist, Item, Kondisi, Keterangan, Foto1..FotoN, Waktu Submit]
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
# SESSION STATE & RESET LOGIC
# =========================
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "photo_results" not in st.session_state:
    st.session_state.photo_results = {}

# Reset handler: jika user menekan Isi Form Baru kita set reset=True lalu rerun;
# di awal run kita akan membersihkan session state jika reset flag aktif.
if st.session_state.get("reset", False):
    # Hapus semua dynamic keys yang mungkin tersisa
    keys_to_remove = [k for k in st.session_state.keys() if k.startswith(tuple([f"{it}_" for it in ITEMS]))]
    for k in keys_to_remove:
        del st.session_state[k]
    # juga kosongkan photo_results
    st.session_state.photo_results = {}
    st.session_state.submitted = False
    st.session_state.reset = False
    # continue rendering form on this rerun

# Main container: kita render seluruh form di dalam container ini.
main = st.container()

# Jika sudah submit (dari sesi sebelumnya) — tampilkan halaman sukses di luar container
if st.session_state.submitted:
    st.success("✅ Data berhasil disimpan ke Google Sheet!")
    if st.button("➕ Isi Form Baru"):
        # set reset flag and try to rerun; this should require only one click
        st.session_state.reset = True
        try:
            st.experimental_rerun()
        except Exception:
            st.info("Proses reset gagal otomatis — silakan refresh halaman jika tidak kembali ke form.")
    st.stop()

# =========================
# RENDER FORM DI DALAM CONTAINER
# =========================
with main:
    st.title("Form P2H Unit")
    col1, col2, col3 = st.columns(3)
    with col1:
        tanggal = st.date_input("Tanggal")
    with col2:
        unit_rig = st.selectbox("Unit Rig", options=[""] + RIG_LIST)
    with col3:
        geologist = st.text_input("Geologist")

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
                    try:
                        st.image([f.read() for f in fotos], width=200)
                    except Exception:
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
    # SUBMIT BUTTON & LOGIC
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

        # konsisten timestamp untuk semua foto di satu submit (Asia/Jakarta)
        try:
            if ZoneInfo is not None:
                now_local = datetime.now(ZoneInfo("Asia/Jakarta"))
            else:
                now_local = datetime.utcnow() + timedelta(hours=7)
        except Exception:
            now_local = datetime.now()
        timestamp_str = now_local.strftime("%Y%m%d_%H%M%S")

        # Hitung total upload untuk progress bar
        total_uploads = 0
        for item, value in results.items():
            if value["Kondisi"] == "Tidak Normal":
                fotos = st.session_state.photo_results.get(item, [])
                total_uploads += min(len(fotos), MAX_PHOTOS)

        # siapkan UI progress
        progress_bar = st.progress(0)
        progress_text = st.empty()
        uploaded_count = 0
        all_ok = True

        # gunakan spinner selama proses berjalan
        with st.spinner("Sedang mengupload foto dan menyimpan ke Google Sheet..."):
            # proses per item, upload per foto agar bisa update progress
            for item, value in results.items():
                kondisi = value["Kondisi"]
                keterangan = value["Keterangan"]

                foto_links = []
                if kondisi == "Tidak Normal":
                    fotos = st.session_state.photo_results.get(item, [])
                    item_safe = safe_fname_component(item.replace(' ', '_'))

                    for idx, foto in enumerate(fotos, start=1):
                        if idx > MAX_PHOTOS:
                            break
                        # baca content (prefer getbuffer)
                        try:
                            content = foto.getbuffer() if hasattr(foto, "getbuffer") else foto.read()
                        except Exception:
                            try:
                                content = foto.read()
                            except Exception:
                                content = b""

                        # **UBAHAN UTAMA untuk ordering**:
                        # letakkan timestamp di awal sehingga nama file berurut sesuai waktu submit
                        # Format filename: YYYYMMDD_HHMMSS_unitrig_item_index.ext
                        orig_ext = os.path.splitext(foto.name)[1] or ".jpg"
                        drive_filename = f"{timestamp_str}_{unit_rig}_{item_safe}_{idx}{orig_ext}"

                        # simpan temp, upload, hapus temp
                        local_temp = save_temp_file(content, drive_filename)
                        file_id = upload_file_to_drive(local_temp, drive_filename)
                        delete_local_file(local_temp)

                        if file_id:
                            foto_links.append(f'=HYPERLINK("https://drive.google.com/file/d/{file_id}/view","Foto")')
                        else:
                            foto_links.append("")

                        # update progress
                        uploaded_count += 1
                        if total_uploads > 0:
                            pct = int(uploaded_count / total_uploads * 100)
                        else:
                            pct = 100
                        progress_bar.progress(pct)
                        progress_text.markdown(f"Progress: **{pct}%** ({uploaded_count}/{total_uploads} file)")
                else:
                    foto_links = [""] * MAX_PHOTOS

                # pad foto_links agar selalu sesuai MAX_PHOTOS
                while len(foto_links) < MAX_PHOTOS:
                    foto_links.append("")

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
                    # lanjutkan ke item lain meskipun ada kegagalan

        # pastikan progress 100% kalau semua upload selesai
        progress_bar.progress(100)
        progress_text.markdown(f"Progress: **100%** ({uploaded_count}/{total_uploads} file)")

        # Setelah semua selesai: tampilkan halaman sukses langsung dan siapkan reset sekali klik
        if all_ok:
            st.session_state.submitted = True

            # kosongkan container (menghapus form UI dari page)
            main.empty()

            # Coba rerun supaya top-of-file menampilkan halaman sukses; jika gagal, tampilkan fallback
            try:
                st.experimental_rerun()
            except Exception:
                st.success("✅ Data berhasil disimpan ke Google Sheet!")
                if st.button("➕ Isi Form Baru"):
                    st.session_state.reset = True
                    try:
                        st.experimental_rerun()
                    except Exception:
                        st.info("Jika halaman belum berubah otomatis, silakan refresh halaman.")
                st.stop()
        else:
            st.error("Proses selesai dengan beberapa peringatan (cek warning). Periksa konfigurasi API/akses dan ulangi jika perlu.")
