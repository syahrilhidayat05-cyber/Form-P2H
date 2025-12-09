import streamlit as st
import pandas as pd
from datetime import datetime
import os

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Form P2H Unit", layout="wide")

SAVE_FOLDER = r"\\172.18.0.230\exploration\Hasil P2H"  # folder di server / laptop
os.makedirs(SAVE_FOLDER, exist_ok=True)

# =========================
# DAFTAR ITEM CHECKLIST
# =========================
ITEMS = [
    "Oli mesin", "Air Radiator", "Vanbelt", "Tangki solar", "Oli hidraulik",
    "Oil seal Hidraulik", "Baut Skor menara", "Wire line", "Clamp terpasang",
    "Eye bolt", "Lifting dg dos", "Hostplug bering", "Spearhead point",
    "Guarding pipa berputar", "Safety inner", "Guarding vanbelt pompa rig",
    "Jergen krisbow solar", "APAR"
]


# =========================
# DAFTAR RIG
# =========================
RIG_LIST = [
    "CNI-01", "CNI-02", "CNI-03", "CNI-04",
    "CNI-05", "CNI-06", "CNI-07", "CNI-08",
    "CNI-09", "CNI-10", "CNI-11", "CNI-12",
    "CNI-13", "CNI-14", "CNI-15", "CNI-16"
]



# =========================
# SESSION STATE
# =========================
if "submitted" not in st.session_state:
    st.session_state.submitted = False

if "form_data" not in st.session_state:
    st.session_state.form_data = {}

# =========================
# JIKA SUDAH SUBMIT
# =========================
if st.session_state.submitted:
    st.success("✅ Data berhasil disubmit!")

    if st.button("➕ Isi Form Baru"):
        st.session_state.submitted = False
        st.session_state.form_data = {}
        st.rerun()

    st.stop()

# =========================
# FORM UTAMA
# =========================
st.title("Form P2H Unit")

st.subheader("Informasi Unit")

col1, col2, col3 = st.columns(3)

with col1:
    tanggal = st.date_input("Tanggal")
with col2:
    unit_rig = st.selectbox(
        "Unit Rig",
        options=[""] + RIG_LIST
    )
with col3:
    geologist = st.text_input("Geologist")


st.subheader("Checklist Kondisi")

results = {}
error_messages = []

# Header tabel
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

    # validasi
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
if st.button("✅ Submit Checklist"):

    # Validasi field wajib
    if not unit_rig.strip():
        st.error("❌ Unit Rig wajib diisi!")
        st.stop()

    if not geologist.strip():
        st.error("❌ Geologist wajib diisi!")
        st.stop()

    if len(error_messages) > 0:
        st.error("❌ Masih ada kesalahan berikut:")
        for msg in error_messages:
            st.warning(msg)
        st.stop()

    # =========================
    # SIMPAN KE EXCEL
    # =========================
    data_rows = []

    for item, value in results.items():
        data_rows.append({
            "Tanggal": tanggal,
            "Unit Rig": unit_rig,
            "Geologist": geologist,
            "Item": item,
            "Kondisi": value["Kondisi"],
            "Keterangan": value["Keterangan"],
            "Waktu Submit": datetime.now()
        })

    df = pd.DataFrame(data_rows)

    now = datetime.now()
    filename = f"P2H_{unit_rig}_{now.strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(SAVE_FOLDER, filename)

    df.to_excel(filepath, index=False)

    st.session_state.submitted = True
    st.rerun()

