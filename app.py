import streamlit as st
from PIL import Image
import numpy as np
import cv2
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from streamlit_image_coordinates import streamlit_image_coordinates
import datetime
import io
import os

SHEET_ID = "1ew4P9dsQWrINTCfEc5bg-qlcUmvSfZDPXUEq6hFxlOg"
DRIVE_FOLDER_ID = "1njn6Hp3qoaw3kYqkErseReHhA7mrvPjA"
PATENTE_LIST = [
    "HSFC-61", "HSFC-62", "LPXW-25", "LPXW-87",
    "TKXD-17", "LPXW-12", "THXX-18",
]

st.set_page_config(page_title="AI-Count Auditoría Andamios", page_icon="🏗️", layout="wide")

@st.cache_resource
def load_credentials():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if "gcp_service_account" in st.secrets:
        return ServiceAccountCredentials.from_json_keyfile_dict(
            dict(st.secrets["gcp_service_account"]), scope
        )
    if os.path.exists("credentials.json"):
        return ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    raise FileNotFoundError("No se encontraron credenciales.")

@st.cache_resource
def connect_to_sheets():
    return gspread.authorize(load_credentials())

@st.cache_resource
def build_drive_service():
    return build("drive", "v3", credentials=load_credentials(), cache_discovery=False)

def upload_image_to_drive(file_bytes, filename, folder_id, drive_service, mime_type="image/jpeg"):
    try:
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
        created = drive_service.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media, fields="id,webViewLink",
            supportsAllDrives=True
        ).execute()
        if created.get("id"):
            try:
                drive_service.permissions().create(
                    fileId=created["id"],
                    body={"type": "anyone", "role": "reader"},
                    fields="id",
                    supportsAllDrives=True
                ).execute()
            except Exception:
                pass
            return created.get("webViewLink") or f"https://drive.google.com/file/d/{created['id']}/view"
    except Exception as e:
        st.error(f"Error subiendo foto: {e}")
    return ""

def dibujar_puntos(image_bytes, puntos, tipo="horizontal", max_width=380):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
    img_np = np.array(img)
    ih, iw = img_np.shape[:2]
    radio = max(10, min(iw, ih) // 28)

    for idx, (px, py) in enumerate(puntos):
        numero = idx + 1
        if tipo == "vertical":
            tam_cruz = int(radio * 1.2)
            grosor = max(2, radio // 6)
            cv2.line(img_np, (px - tam_cruz, py), (px + tam_cruz, py), (0, 0, 0), grosor)
            cv2.line(img_np, (px, py - tam_cruz), (px, py + tam_cruz), (0, 0, 0), grosor)
            font_scale = max(0.4, radio / 18)
            thickness = max(1, radio // 10)
            text = str(numero)
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
            cv2.putText(img_np, text, (px - tw//2 - 1, py + th//2 - 1),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness + 2, cv2.LINE_AA)
            cv2.putText(img_np, text, (px - tw//2, py + th//2),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 0, 0), thickness, cv2.LINE_AA)
        else:
            cv2.circle(img_np, (px, py), radio, (220, 0, 0), -1)
            cv2.circle(img_np, (px, py), radio, (255, 255, 255), 2)
            font_scale = max(0.35, radio / 20)
            thickness = max(1, radio // 10)
            text = str(numero)
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
            cv2.putText(img_np, text, (px - tw//2, py + th//2),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return Image.fromarray(img_np)

# ── ESTADO ──────────────────────────────────────────────────────────────────
if "puntos_v" not in st.session_state:
    st.session_state.puntos_v = []
if "ultimo_click_v" not in st.session_state:
    st.session_state.ultimo_click_v = None
if "puntos_h" not in st.session_state:
    st.session_state.puntos_h = []
if "ultimo_click_h" not in st.session_state:
    st.session_state.ultimo_click_h = None

# ── UI ──────────────────────────────────────────────────────────────────────
st.title("🏗️ AI-Count: Auditoría de Andamios")
st.markdown("Sistema de auditoría logística para contar piezas de andamiaje desde el celular.")

patente = st.selectbox("Patente del Camión:", PATENTE_LIST)
tipo = st.radio("Tipo de material:", ["Verticales", "Horizontales"], horizontal=True)

if st.button("🔄 Limpiar marcas"):
    st.session_state.puntos_v = []
    st.session_state.ultimo_click_v = None
    st.session_state.puntos_h = []
    st.session_state.ultimo_click_h = None
    st.rerun()

uploaded_file = st.file_uploader("Suba una foto del material:", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()

    # ── VERTICALES ──────────────────────────────────────────────────────────
    if tipo == "Verticales":
        st.markdown("### Toca cada hoyo de tubo en la foto")
        st.caption("Cruz negra + número rojo en cada toque. Limpiar para empezar de nuevo.")

        img_display = dibujar_puntos(file_bytes, st.session_state.puntos_v, tipo="vertical")
        valor = streamlit_image_coordinates(img_display, key="coord_v")

        if valor is not None and valor != st.session_state.ultimo_click_v:
            st.session_state.ultimo_click_v = valor
            st.session_state.puntos_v.append((valor["x"], valor["y"]))
            st.rerun()

        total_v = len(st.session_state.puntos_v)

        if total_v == 0:
            st.info("Toca cada hoyo de tubo en la foto para comenzar el conteo.")
        elif total_v > 104:
            st.warning(f"Total marcados: **{total_v}** — por encima del máximo (104). Verifica.")
        else:
            st.success(f"Total marcados: **{total_v}**")

        if total_v > 0:
            st.markdown("---")
            st.write(f"**Patente:** {patente}")
            st.write(f"**Tipo:** Verticales")
            st.write(f"**Total:** {total_v} piezas")

            if st.button("💾 Confirmar y Guardar Auditoría", key="guardar_v"):
                try:
                    client = connect_to_sheets()
                    sheet = client.open_by_key(SHEET_ID).sheet1
                    drive_service = build_drive_service()
                    timestamp = datetime.datetime.now()
                    filename = f"auditoria_{patente}_Verticales_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                    photo_link = upload_image_to_drive(
                        file_bytes, filename, DRIVE_FOLDER_ID, drive_service,
                        uploaded_file.type or "image/jpeg"
                    )
                    sheet.append_row([
                        timestamp.strftime("%Y-%m-%d"),
                        timestamp.strftime("%H:%M:%S"),
                        patente, "Verticales", total_v, photo_link
                    ])
                    st.success("Auditoría guardada en Google Sheets.")
                    if photo_link:
                        st.markdown(f"[Ver foto en Drive]({photo_link})")
                    st.session_state.puntos_v = []
                    st.session_state.ultimo_click_v = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    # ── HORIZONTALES ────────────────────────────────────────────────────────
    elif tipo == "Horizontales":
        st.markdown("### Toca cada cabezal en la foto")
        st.caption("Cada toque agrega un número rojo. Limpiar para empezar de nuevo.")

        img_display = dibujar_puntos(file_bytes, st.session_state.puntos_h, tipo="horizontal")
        valor = streamlit_image_coordinates(img_display, key="coord_h")

        if valor is not None and valor != st.session_state.ultimo_click_h:
            st.session_state.ultimo_click_h = valor
            st.session_state.puntos_h.append((valor["x"], valor["y"]))
            st.rerun()

        total_h = len(st.session_state.puntos_h)

        if total_h == 0:
            st.info("Toca los cabezales en la foto para comenzar el conteo.")
        elif total_h > 212:
            st.warning(f"Total marcados: **{total_h}** — por encima del máximo (212). Verifica.")
        else:
            st.success(f"Total marcados: **{total_h}**")

        if total_h > 0:
            st.markdown("---")
            st.write(f"**Patente:** {patente}")
            st.write(f"**Tipo:** Horizontales")
            st.write(f"**Total:** {total_h} piezas")

            if st.button("💾 Confirmar y Guardar Auditoría", key="guardar_h"):
                try:
                    client = connect_to_sheets()
                    sheet = client.open_by_key(SHEET_ID).sheet1
                    drive_service = build_drive_service()
                    timestamp = datetime.datetime.now()
                    filename = f"auditoria_{patente}_Horizontales_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                    photo_link = upload_image_to_drive(
                        file_bytes, filename, DRIVE_FOLDER_ID, drive_service,
                        uploaded_file.type or "image/jpeg"
                    )
                    sheet.append_row([
                        timestamp.strftime("%Y-%m-%d"),
                        timestamp.strftime("%H:%M:%S"),
                        patente, "Horizontales", total_h, photo_link
                    ])
                    st.success("Auditoría guardada en Google Sheets.")
                    if photo_link:
                        st.markdown(f"[Ver foto en Drive]({photo_link})")
                    st.session_state.puntos_h = []
                    st.session_state.ultimo_click_h = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

st.markdown("---")
st.caption("AI-Count — Auditoría de Andamios")
