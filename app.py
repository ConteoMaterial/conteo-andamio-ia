import streamlit as st
from PIL import Image, ImageDraw
import numpy as np
from ultralytics import YOLO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import datetime
import io
import json
import os

SHEET_ID = "1ew4P9dsQWrINTCfEc5bg-qlcUmvSfZDPXUEq6hFxlOg"
DRIVE_FOLDER_ID = "1K1Q3d4KV_b4RzhQsFVxN_cf9u8F0Wuae"
PATENTE_LIST = [
    "HSFC-61",
    "HSFC-62",
    "LPXV-25",
    "LPXV-87",
    "TKXD-17",
    "LPXV-12",
    "GTCP-49",
    "CYGY-25",
    "SLPX-67",
    "THXX-18",
    "TVJD-17",
    "SPXW-90",
]

st.set_page_config(page_title="AI-Count Auditoría Andamios", page_icon="🏗️", layout="wide")

@st.cache_resource
def load_model():
    return YOLO("yolov8n.pt")

@st.cache_resource
def load_service_account_credentials():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if "GOOGLE_CREDENTIALS" in st.secrets:
        creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        return ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    if os.path.exists("credentials.json"):
        return ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    raise FileNotFoundError(
        "No se encontró credentials.json ni GOOGLE_CREDENTIALS en Streamlit secrets."
    )

@st.cache_resource
def connect_to_sheets():
    creds = load_service_account_credentials()
    return gspread.authorize(creds)

@st.cache_resource
def build_drive_service():
    creds = load_service_account_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)

@st.cache_resource
def get_model():
    return load_model()

model = get_model()


def upload_image_to_drive(file_bytes, filename, folder_id, drive_service, mime_type="image/jpeg"):
    try:
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
        file_metadata = {"name": filename, "parents": [folder_id]}
        created_file = (
            drive_service.files()
            .create(body=file_metadata, media_body=media, fields="id,webViewLink")
            .execute()
        )
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


def process_image(uploaded_file, tipo_material):
    file_bytes = uploaded_file.getvalue()
    try:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    except Exception:
        raise ValueError("No se pudo leer la imagen. Intente con otro archivo.")

    img_np = np.array(img)
    results = model(img_np)
    detections = []
    for result in results:
        for box in result.boxes:
            conf = float(box.conf[0]) if hasattr(box, "conf") else float(box.conf)
            if conf < 0.35:
                continue
            xyxy = box.xyxy[0].tolist()
            detections.append([int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])])

    annotated_img = img.copy()
    draw = ImageDraw.Draw(annotated_img)
    for x1, y1, x2, y2 in detections:
        draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
        draw.ellipse([x1, y1, x1 + 10, y1 + 10], fill="red")

    total_detectado = len(detections)
    return annotated_img, total_detectado, file_bytes


st.title("🏗️ AI-Count: Auditoría de Andamios")
st.markdown("Sistema de auditoría logística para contar piezas de andamiaje desde el celular.")

if "analysis" not in st.session_state:
    st.session_state.analysis = {}

patente = st.selectbox("Seleccione la Patente del Camión:", PATENTE_LIST)
uploaded_file = st.file_uploader("Suba una foto del material:", type=["jpg", "jpeg", "png"])

col1, col2 = st.columns(2)
count_button = None
if uploaded_file is not None:
    with col1:
        if st.button("Contar Horizontales"):
            count_button = "Horizontales"
    with col2:
        if st.button("Contar Verticales"):
            count_button = "Verticales"

    if count_button:
        try:
            annotated_img, total, file_bytes = process_image(uploaded_file, count_button)
            st.session_state.analysis = {
                "tipo_material": count_button,
                "annotated_img": annotated_img,
                "total": total,
                "file_bytes": file_bytes,
            }
            st.success(f"Detección completada para {count_button}. Total: {total}")
        except Exception as exc:
            st.error(f"Error al procesar la imagen: {exc}")

if st.session_state.analysis:
    analysis = st.session_state.analysis
    st.markdown("### Resultado de la detección")
    st.image(analysis["annotated_img"], caption=f"Resultado: {analysis['total']} piezas detectadas", use_column_width=True)
    st.write(f"**Patente:** {patente}")
    st.write(f"**Tipo de material:** {analysis['tipo_material']}")
    st.write(f"**Conteo de piezas:** {analysis['total']}")

    if st.button("Confirmar y Guardar Auditoría"):
        try:
            client = connect_to_sheets()
            sheet = client.open_by_key(SHEET_ID).sheet1
            drive_service = build_drive_service()
            timestamp = datetime.datetime.now()
            filename = f"auditoria_{patente}_{analysis['tipo_material']}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            mime_type = uploaded_file.type or "image/jpeg"
            photo_link = upload_image_to_drive(analysis["file_bytes"], filename, DRIVE_FOLDER_ID, drive_service, mime_type)

            fecha = timestamp.strftime("%Y-%m-%d")
            hora = timestamp.strftime("%H:%M:%S")
            row = [fecha, hora, patente, analysis["total"], photo_link]
            sheet.append_row(row)
            st.success("Auditoría guardada correctamente en Google Sheets.")
            if photo_link:
                st.markdown(f"[Ver foto en Drive]({photo_link})")
            st.session_state.analysis = {}
        except Exception as exc:
            st.error(f"No se pudo guardar la auditoría: {exc}")
else:
    st.info("Sube una foto y selecciona el tipo de conteo para comenzar.")

st.markdown("---")
st.markdown("**Notas de configuración:** Asegúrate de que la carpeta de Drive y la hoja de cálculo estén compartidas con la cuenta de servicio de Google.")
