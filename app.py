# app.py — FINAL (navigation fix: query-param + rerun + js redirect)
import streamlit as st
from datetime import datetime, timedelta
import os
import re
import tempfile

# try zoneinfo for Asia/Jakarta
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import streamlit.components.v1 as components

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Form P2H Unit", layout="wide")
TEMP_FOLDER = "temp_files"
os.makedirs(TEMP_FOLDER, exist_ok=True)

# ====== CONFIG YOU CAN EDIT ======
SHEET_ID = "1e9X42pvEPZP1dTQ-IY4nM3VvYRJDHuuuFoJ1maxfPZs"
DRIVE_FOLDER_ID = "1OkAj7Z2D5IVCB9fHmrNFWllRGl3hcPvq"
MAX_PHOTOS = 3
# ==================================

RIG_LIST = [f"CNI-{str(i).zfill(2)}" for i in range(1, 17)]
ITEMS = [
    "Oli mesin","Air Radiator","Vanbelt","Tangki solar","Oli hidraulik",
    "Oil seal Hidraulik","Baut Skor menara","Wire line","Clamp terpasang",
    "Eye bolt","Lifting dg dos","Hostplug bering","Spearhead point",
    "Guarding pipa berputar","Safety inner","Guarding vanbelt pompa rig",
    "Jergen krisbow solar","APAR"
]

# =========================
# AUTH
# =========================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gdrive"], scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)
sheets_service = build('sheets', 'v4', credentials=creds)

# =========================
# HELPERS
# =========================
def safe_fname_component(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9_-]+', '_', s)

def delete_local_file(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass

def save_temp_file(content, filename):
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    with open(temp_path, "wb") as f:
        if isinstance(content, (bytes, bytearray)):
            f.write(content)
        else:
            try:
                f.write(content.tobytes())
            except Exception:
                try:
                    f.write(bytes(content))
                except Exception:
                    f.write(b"")
    return temp_path

def upload_file_to_drive(local_path, drive_filename):
    file_metadata = {'name': drive_filename, 'parents': [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(local_path, resumable=False)
    try:
        uploaded = drive_service.files().create(
            body=file_metadata, media_body=media, fields="id", supportsAllDrives=True
        ).execute()
        return uploaded.get("id")
    except HttpError as e:
        st.warning(f"Gagal upload {drive_filename}: {e}")
        return None

def append_to_sheet_row_and_get_index(values_list, sheet_name="Sheet1"):
    """
    Append row ke Sheet1 dan kembalikan tuple (ok_bool, appended_row_zero_based or None).
    Uses response['updates']['updatedRange'] to find exact row.
    """
    try:
        body = {"values": [values_list]}
        resp = sheets_service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
        updates = resp.get("updates", {})
        updated_range = updates.get("updatedRange")
        if updated_range:
            try:
                last_part = updated_range.split("!")[1]
                row_part = last_part.split(":")[-1]
                row_num = int(re.sub(r'[^0-9]', '', row_part))
                return True, row_num - 1
            except Exception:
                pass
        cnt = get_sheet_row_count(sheet_name)
        if cnt is not None:
            return True, cnt - 1
        return True, None
    except Exception as e:
        st.warning(f"Gagal append ke Sheet: {e}")
        return False, None

def get_sheet_row_count(sheet_name="Sheet1"):
    try:
        resp = sheets_service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=f"{sheet_name}!A:A").execute()
        values = resp.get("values", [])
        return len(values)
    except Exception:
        return None

def highlight_row_by_index(row_index_zero_based, color=(1.0, 1.0, 0.88), sheet_name="Sheet1"):
    try:
        ss = sheets_service.spreadsheets().get(spreadsheetId=SHEET_ID,
                                              fields="sheets(properties(sheetId,title,gridProperties(columnCount)))").execute()
        sheet_id = None
        col_count = 10
        for s in ss.get("sheets", []):
            props = s.get("properties", {})
            if props.get("title") == sheet_name:
                sheet_id = props.get("sheetId")
                grid = props.get("gridProperties", {})
                col_count = grid.get("columnCount", 10)
                break
        if sheet_id is None:
            first = ss.get("sheets", [])[0].get("properties", {})
            sheet_id = first.get("sheetId")
            col_count = first.get("gridProperties", {}).get("columnCount", 10)

        r, g, b = color
        requests = [{
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_index_zero_based, "endRowIndex": row_index_zero_based + 1,
                          "startColumnIndex": 0, "endColumnIndex": col_count},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": r, "green": g, "blue": b}}},
                "fields": "userEnteredFormat.backgroundColor"
            }
        }]
        sheets_service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": requests}).execute()
        return True
    except Exception as e:
        st.warning(f"Gagal memberi warna pada baris: {e}")
        return False

def clear_all_highlights(sheet_name="Sheet1"):
    try:
        ss = sheets_service.spreadsheets().get(spreadsheetId=SHEET_ID,
                                              fields="sheets(properties(sheetId,title,gridProperties(columnCount)))").execute()
        sheet_id = None
        col_count = 10
        for s in ss.get("sheets", []):
            props = s.get("properties", {})
            if props.get("title") == sheet_name:
                sheet_id = props.get("sheetId")
                grid = props.get("gridProperties", {})
                col_count = grid.get("columnCount", 10)
                break
        if sheet_id is None:
            first = ss.get("sheets", [])[0].get("properties", {})
            sheet_id = first.get("sheetId")
            col_count = first.get("gridProperties", {}).get("columnCount", 10)

        requests = [{
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 10000,
                          "startColumnIndex": 0, "endColumnIndex": col_count},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": 1, "blue": 1}}},
                "fields": "userEnteredFormat.backgroundColor"
            }
        }]
        sheets_service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": requests}).execute()
        return True
    except Exception as e:
        st.warning(f"Gagal menghapus highlight: {e}")
        return False

# =========================
# SESSION & query-param handling
# =========================
if "photo_results" not in st.session_state:
    st.session_state.photo_results = {}
if "show_success" not in st.session_state:
    st.session_state.show_success = False

# If URL query param ?submitted exists, consider it success and show success UI
qparams = st.experimental_get_query_params()
if "submitted" in qparams and qparams.get("submitted"):
    st.session_state.show_success = True

def reset_form_state():
    for key in list(st.session_state.keys()):
        if key in ("photo_results", "show_success"):
            continue
        if any(key.startswith(f"{it}_") for it in ITEMS) or key in ("unit_rig", "geologist", "tanggal"):
            try:
                del st.session_state[key]
            except Exception:
                pass
    st.session_state.photo_results = {}
    st.session_state.show_success = False
    # clear query params so subsequent visits not treated as submitted
    try:
        st.experimental_set_query_params()
    except Exception:
        pass

# If show_success flag set, render success page and stop
if st.session_state.show_success:
    st.success("✅ Data berhasil disimpan ke Google Sheet!")
    if st.button("➕ Isi Form Baru"):
        reset_form_state()
        try:
            st.experimental_rerun()
        except Exception:
            st.info("Jika halaman belum kembali, silakan refresh manual.")
    st.stop()

# =========================
# UI: form
# =========================
st.title("Form P2H Unit")

col_h1, col_h2 = st.columns([1, 6])
with col_h1:
    if st.button("Clear all highlights"):
        ok = clear_all_highlights("Sheet1")
        if ok:
            st.success("Semua highlight dihapus.")
        else:
            st.warning("Gagal menghapus highlight.")

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
        kondisi = st.radio("Kondisi", ["Normal", "Tidak Normal"], key=f"{item}_kondisi", horizontal=True)
        keterangan = ""
        fotos = []
        if kondisi == "Tidak Normal":
            keterangan = st.text_input("Keterangan", key=f"{item}_keterangan", placeholder="Isi keterangan")
            fotos = st.file_uploader("Upload Foto (min 1, max 3)", type=["jpg","jpeg","png"], accept_multiple_files=True, key=f"{item}_foto")
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
    # validation
    if not unit_rig:
        st.error("Unit rig wajib dipilih!"); st.stop()
    if not geologist.strip():
        st.error("Geologist wajib diisi!"); st.stop()
    if error_messages:
        st.error("Masih ada kesalahan:")
        for e in error_messages:
            st.warning(e)
        st.stop()

    # timestamp Asia/Jakarta
    try:
        if ZoneInfo is not None:
            now_local = datetime.now(ZoneInfo("Asia/Jakarta"))
        else:
            now_local = datetime.utcnow() + timedelta(hours=7)
    except Exception:
        now_local = datetime.now()
    timestamp_str = now_local.strftime("%Y%m%d_%H%M%S")

    # compute total uploads for progress
    total_uploads = sum(min(len(st.session_state.photo_results.get(it, [])), MAX_PHOTOS) for it in ITEMS if results[it]["Kondisi"] == "Tidak Normal")

    progress_bar = st.progress(0)
    progress_text = st.empty()
    uploaded_count = 0
    all_ok = True
    oli_row_index = None  # row index (0-based) of appended 'Oli mesin' for this submit

    with st.spinner("Sedang mengupload foto dan menyimpan ke Google Sheet..."):
        for item in ITEMS:
            kondisi = results[item]["Kondisi"]
            keterangan = results[item]["Keterangan"]
            foto_links = []
            if kondisi == "Tidak Normal":
                fotos = st.session_state.photo_results.get(item, [])
                item_safe = safe_fname_component(item.replace(" ", "_"))
                for idx, foto in enumerate(fotos, start=1):
                    if idx > MAX_PHOTOS:
                        break
                    try:
                        content = foto.getbuffer() if hasattr(foto, "getbuffer") else foto.read()
                    except Exception:
                        try:
                            content = foto.read()
                        except Exception:
                            content = b""
                    orig_ext = os.path.splitext(foto.name)[1] or ".jpg"
                    drive_filename = f"{timestamp_str}_{unit_rig}_{item_safe}_{idx}{orig_ext}"
                    local_temp = save_temp_file(content, drive_filename)
                    file_id = upload_file_to_drive(local_temp, drive_filename)
                    delete_local_file(local_temp)
                    if file_id:
                        foto_links.append(f'=HYPERLINK("https://drive.google.com/file/d/{file_id}/view","Foto")')
                    else:
                        foto_links.append("")
                    uploaded_count += 1
                    pct = int(uploaded_count / total_uploads * 100) if total_uploads > 0 else 100
                    progress_bar.progress(pct)
                    progress_text.markdown(f"Progress: **{pct}%** ({uploaded_count}/{total_uploads} file)")
            else:
                foto_links = [""] * MAX_PHOTOS

            while len(foto_links) < MAX_PHOTOS:
                foto_links.append("")

            row_values = [
                tanggal.strftime("%Y-%m-%d"),
                unit_rig,
                geologist,
                item,
                kondisi,
                keterangan,
                *foto_links,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]

            ok, appended_index = append_to_sheet_row_and_get_index(row_values, sheet_name="Sheet1")
            if not ok:
                all_ok = False
            else:
                if item == ITEMS[0] and appended_index is not None:
                    oli_row_index = appended_index

    # finalize progress
    progress_bar.progress(100)
    progress_text.markdown(f"Progress: **100%** ({uploaded_count}/{total_uploads} file)")

    # highlight only the oli_row_index (if we have it)
    if oli_row_index is not None:
        try:
            highlight_row_by_index(oli_row_index, color=(1.0, 1.0, 0.88), sheet_name="Sheet1")
        except Exception:
            pass

    # render success: set query param + set show_success and attempt rerun; also JS redirect fallback
    if all_ok:
        # create a unique token to set as query param (timestamp_str is fine)
        try:
            st.experimental_set_query_params(submitted=timestamp_str)
        except Exception:
            pass
        st.session_state.show_success = True

        # try server rerun first
        try:
            st.experimental_rerun()
        except Exception:
            # fallback: force client reload to URL with ?submitted=timestamp
            try:
                components.html(f"""<script>window.location.search = '?submitted={timestamp_str}';</script>""", height=0)
            except Exception:
                # final fallback: show success message here
                st.success("✅ Data berhasil disimpan ke Google Sheet!")
                if st.button("➕ Isi Form Baru"):
                    reset_form_state()
                    try:
                        st.experimental_rerun()
                    except Exception:
                        st.info("Jika halaman belum kembali, silakan refresh manual.")
                st.stop()
    else:
        st.error("Proses selesai dengan beberapa peringatan (cek warning). Periksa konfigurasi API/akses dan ulangi jika perlu.")
