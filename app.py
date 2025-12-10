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

# =========================
# DELETE LOCAL FILE
# =========================
def delete_local_file(path):
    """Menghapus file lokal jika ada."""
    if os.path.exists(path):
        os.remove(path)


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Form P2H Unit", layout="wide")

TEMP_FOLDER = "temp_files"
os.makedirs(TEMP_FOLDER, exist_ok=True)

DRIVE_FOLDER_ID = "0ACXw55dYg6NkUk9PVA"  # Shared Drive folder

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
# GENERATE NAMA FILE
# =========================
def generate_filename(prefix="file", ext="jpg", custom_text=""):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if custom_text:
        custom_text = re.sub(r'[^A-Za-z0-9_-]+', '_', custom_text)

    if custom_text:
        return f"{prefix}_{custom_text}_{timestamp}.{ext}"
    return f"{prefix}_{timestamp}.{ext}"


# =========================
# SAVE TEMP FILE
# =========================
def save_temp_file(content, filename):
    temp_dir = tempfile.gettempdir()
    filepath = os.path.join(temp_dir, filename)

    with open(filepath, "wb") as f:
        f.write(content)

    return filepath


# =========================
# FIND & DELETE EXISTING EXCEL
# =========================
def find_existing_excel(service):
    query = f"name='DATA_P2H.xlsx' and '{DRIVE_FOLDER_ID}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def delete_file_from_drive(service, file_id):
    service.files().delete(fileId=file_id).execute()


# =========================
# GOOGLE DRIVE UPLOAD (Shared Drive)
# =========================
def upload_to_drive(filepath, filename):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(
        st.secrets["gdrive"],
        scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=creds)

    # Replace Excel lama jika nama "DATA_P2H.xlsx"
    if filename == "DATA_P2H.xlsx":
        try:
            existing_id = find_existing_excel(service)
            if existing_id:
                delete_file_from_drive(service, existing_id)
                st.info(f"File lama DATA_P2H.xlsx dihapus (ID: {existing_id})")
        except HttpError as e:
            st.error(f"Gagal cek/hapus file lama: {e}")
            print("HTTPError saat cek/hapus file lama:")
            print("Status code:", e.resp.status)
            print("Content:", e.content.decode() if isinstance(e.content, bytes) else e.content)
            raise

    file_metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(filepath, resumable=False)

    try:
        uploaded = service.files().create(
            body=file_metadata, media_body=media, fields="id, parents"
        ).execute()

        # Debug info
        print(f"[DEBUG] File '{filename}' berhasil di-upload!")
        print("File ID:", uploaded.get("id"))
        print("Parents:", uploaded.get("parents"))

        st.info(f"File '{filename}' berhasil di-upload ke Shared Drive!")
        st.info(f"File ID: {uploaded.get('id')}")
        st.info(f"Parent folder ID: {uploaded.get('parents')}")

        return uploaded.get("id")

    except HttpError as e:
        st.error("Terjadi error saat upload ke Shared Drive!")
        st.error(f"Status code: {e.resp.status}")
        st.error(f"Detail: {e.content.decode() if isinstance(e.content, bytes) else e.content}")
        print("==== DEBUG HTTPError ====")
        print("Status code:", e.resp.status)
        print("Content:", e.content.decode() if isinstance(e.content, bytes) else e.content)
        raise


# =========================
# SIMPAN FOTO LOKAL
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
# APPEND EXCEL
# =========================
EXCEL_FILE = "DATA_P2H.xlsx"

def append_to_excel(row):
    df_new = pd.DataFrame([row])

    if not os.path.exists(EXCEL_FILE):
        df_new.to_excel(EXCEL_FILE, index=False)
    else:
        df_existing = pd.read_excel(EXCEL_FILE)
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
        df_all.to_excel(EXCEL_FILE, index=False)


# =========================
# SESSION STATE
# =========================
if "submitted" not in st.session_state:
    st.session_state.submitted = False

if st.session_state.submitted:
    st.success("✅ Data berhasil disimpan ke Shared Drive!")
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
            f"Upload Foto – {item} (max 3 foto)",
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

    # ------------------------------------
    # PROSES PER ITEM
    # ------------------------------------
    for item, value in results.items():

        kondisi = value["Kondisi"]
        keterangan = value["Keterangan"]
        foto_hyperlinks = ""

        if kondisi == "Tidak Normal":
            fotos = photo_results.get(item, [])
            saved_paths = save_photos(item, fotos, unit_rig, timestamp_str)

            foto_links = []
            for p in saved_paths:

                drive_filename = generate_filename(
                    prefix=unit_rig,
                    custom_text=item.replace(" ", "_"),
                    ext=p.split(".")[-1]
                )

                with open(p, "rb") as f:
                    temp_path = save_temp_file(f.read(), drive_filename)

                gfile_id = upload_to_drive(temp_path, drive_filename)

                # hapus temp foto
                delete_local_file(temp_path)

                # hapus file lokal P2H-UPLOAD
                delete_local_file(p)

                foto_links.append(
                    f'=HYPERLINK("https://drive.google.com/file/d/{gfile_id}/view","Foto")'
                )

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

        append_to_excel(new_row)


    # ============================
    # UPLOAD EXCEL BARU KE DRIVE
    # ============================
    with open(EXCEL_FILE, "rb") as f:
        temp_xlsx = save_temp_file(f.read(), EXCEL_FILE)

    upload_to_drive(temp_xlsx, "DATA_P2H.xlsx")

    # hapus temp excel
    delete_local_file(temp_xlsx)

    st.success("Data berhasil disimpan ke Shared Drive!")
    st.session_state.submitted = True
    st.rerun()

