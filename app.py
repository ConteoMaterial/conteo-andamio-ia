import streamlit as st
from PIL import Image, ImageDraw
import numpy as np
import cv2
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import datetime
import io
import os

SHEET_ID = "1ew4P9dsQWrINTCfEc5bg-qlcUmvSfZDPXUEq6hFxlOg"
DRIVE_FOLDER_ID = "1K1Q3d4KV_b4RzhQsFVxN_cf9u8F0Wuae"
PATENTE_LIST = [
    "HSFC-61", "HSFC-62", "LPXV-25", "LPXV-87",
    "TKXD-17", "LPXV-12", "GTCP-49", "CYGY-25",
    "SLPX-67", "THXX-18", "TVJD-17", "SPXW-90",
]

st.set_page_config(page_title="AI-Count Auditoría Andamios", page_icon="🏗️", layout="wide")

@st.cache_resource
def load_service_account_credentials():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        return ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    if os.path.exists("credentials.json"):
        return ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    raise FileNotFoundError("No se encontraron credenciales.")

@st.cache_resource
def connect_to_sheets():
    return gspread.authorize(load_service_account_credentials())

@st.cache_resource
def build_drive_service():
    return build("drive", "v3", credentials=load_service_account_credentials(), cache_discovery=False)

def upload_image_to_drive(file_bytes, filename, folder_id, drive_service, mime_type="image/jpeg"):
    try:
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
        file_metadata = {"name": filename, "parents": [folder_id]}
        created_file = drive_service.files().create(
            body=file_metadata, media_body=media, fields="id,webViewLink"
        ).execute()
        if created_file and created_file.get("id"):
            try:
                drive_service.permissions().create(
                    fileId=created_file["id"],
                    body={"type": "anyone", "role": "reader"},
                    fields="id",
                ).execute()
            except Exception:
                pass
            return created_file.get("webViewLink") or f"https://drive.google.com/file/d/{created_file['id']}/view"
    except Exception as e:
        st.error(f"Error al subir la foto a Drive: {e}")
    return ""

def detectar_verticales(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_np = np.array(img)
    gris = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    gris = cv2.medianBlur(gris, 5)
    alto, ancho = gris.shape
    radio_min = int(min(alto, ancho) * 0.015)
    radio_max = int(min(alto, ancho) * 0.08)
    circulos = cv2.HoughCircles(
        gris,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=radio_min * 2,
        param1=80,
        param2=35,
        minRadius=radio_min,
        maxRadius=radio_max,
    )
    resultado = img.copy()
    draw = ImageDraw.Draw(resultado)
    total = 0
    if circulos is not None:
        circulos = np.round(circulos[0, :]).astype("int")
        for (x, y, r) in circulos:
            draw.ellipse([x - r, y - r, x + r, y + r], outline="red", width=3)
            draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill="red")
            total += 1
    return resultado, total

st.title("🏗️ AI-Count: Auditoría de Andamios")
st.markdown("Sistema de auditoría logística para contar piezas de andamiaje desde el celular.")

if "conteo_asistido" not in st.session_state:
    st.session_state.conteo_asistido = 0
if "analysis" not in st.session_state:
    st.session_state.analysis = {}

patente = st.selectbox("Seleccione la Patente del Camión:", PATENTE_LIST)
tipo = st.radio("Tipo de material:", ["Verticales", "Horizontales"], horizontal=True)
uploaded_file = st.file_uploader("Suba una foto del material:", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()

    if tipo == "Verticales":
        if st.button("Contar Verticales automáticamente"):
            with st.spinner("Detectando tubos..."):
                resultado_img, total = detectar_verticales(file_bytes)
                st.session_state.analysis = {
                    "tipo_material": "Verticales",
                    "annotated_img": resultado_img,
                    "total": total,
                    "file_bytes": file_bytes,
                }
            st.success(f"Se detectaron {total} tubos verticales.")

        if st.session_state.analysis.get("tipo_material") == "Verticales":
            st.image(st.session_state.analysis["annotated_img"],
                     caption=f"Detectados: {st.session_state.analysis['total']} tubos",
                     use_column_width=True)
            st.write(f"**Conteo automático:** {st.session_state.analysis['total']} piezas")
            correccion = st.number_input(
                "¿Corregir conteo manualmente?",
                min_value=0,
                value=st.session_state.analysis["total"],
                step=1
            )
            st.session_state.analysis["total"] = correccion

    elif tipo == "Horizontales":
        st.image(file_bytes, caption="Foto cargada", use_column_width=True)
        st.markdown("### Conteo asistido — toca los botones para contar")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("➕ Sumar 1"):
                st.session_state.conteo_asistido += 1
        with col2:
            if st.button("➖ Restar 1") and st.session_state.conteo_asistido > 0:
                st.session_state.conteo_asistido -= 1
        with col3:
            if st.button("🔄 Reiniciar"):
                st.session_state.conteo_asistido = 0
        st.markdown(f"## Conteo actual: **{st.session_state.conteo_asistido}**")

        if st.session_state.conteo_asistido > 0:
            if st.button("Confirmar conteo de Horizontales"):
                st.session_state.analysis = {
                    "tipo_material": "Horizontales",
                    "annotated_img": Image.open(io.BytesIO(file_bytes)),
                    "total": st.session_state.conteo_asistido,
                    "file_bytes": file_bytes,
                }
                st.success(f"Conteo confirmado: {st.session_state.conteo_asistido} horizontales.")

if st.session_state.analysis:
    analysis = st.session_state.analysis
    st.markdown("---")
    st.write(f"**Patente:** {patente}")
    st.write(f"**Tipo:** {analysis['tipo_material']}")
    st.write(f"**Total piezas:** {analysis['total']}")

    if st.button("Confirmar y Guardar Auditoría"):
        try:
            client = connect_to_sheets()
            sheet = client.open_by_key(SHEET_ID).sheet1
            drive_service = build_drive_service()
            timestamp = datetime.datetime.now()
            filename = f"auditoria_{patente}_{analysis['tipo_material']}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            mime_type = uploaded_file.type or "image/jpeg"
            photo_link = upload_image_to_drive(
                analysis["file_bytes"], filename, DRIVE_FOLDER_ID, drive_service, mime_type
            )
            fecha = timestamp.strftime("%Y-%m-%d")
            hora = timestamp.strftime("%H:%M:%S")
            sheet.append_row([fecha, hora, patente, analysis["tipo_material"], analysis["total"], photo_link])
            st.success("Auditoría guardada correctamente en Google Sheets.")
            if photo_link:
                st.markdown(f"[Ver foto en Drive]({photo_link})")
            st.session_state.analysis = {}
            st.session_state.conteo_asistido = 0
        except Exception as exc:
            st.error(f"No se pudo guardar: {exc}")

st.markdown("---")
st.caption("AI-Count — Auditoría de Andamios")
