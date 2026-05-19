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
DRIVE_FOLDER_ID = "1K1Q3d4KV_b4RzhQsFVxN_cf9u8F0Wuae"
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
            media_body=media, fields="id,webViewLink"
        ).execute()
        if created.get("id"):
            try:
                drive_service.permissions().create(
                    fileId=created["id"],
                    body={"type": "anyone", "role": "reader"},
                    fields="id"
                ).execute()
            except Exception:
                pass
            return created.get("webViewLink") or f"https://drive.google.com/file/d/{created['id']}/view"
    except Exception as e:
        st.error(f"Error subiendo foto: {e}")
    return ""

def detectar_verticales(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_np = np.array(img)
    alto, ancho = img_np.shape[:2]

    gris = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    gris = cv2.GaussianBlur(gris, (9, 9), 2)

    radio_min = int(min(alto, ancho) * 0.04)
    radio_max = int(min(alto, ancho) * 0.12)

    circulos = cv2.HoughCircles(
        gris, cv2.HOUGH_GRADIENT,
        dp=1.2, minDist=radio_min * 2,
        param1=100, param2=38,
        minRadius=radio_min, maxRadius=radio_max,
    )

    resultado_np = img_np.copy()
    detecciones = []

    if circulos is not None:
        circulos = np.round(circulos[0, :]).astype("int")
        for (x, y, r) in circulos:
            y1, y2 = max(0, y - r//2), min(alto, y + r//2)
            x1, x2 = max(0, x - r//2), min(ancho, x + r//2)
            centro = gris[y1:y2, x1:x2]
            if centro.size == 0:
                continue
            brillo_centro = np.mean(centro)
            # Comparar centro vs borde para filtrar rosetas
            yr1, yr2 = max(0, y - r), min(alto, y + r)
            xr1, xr2 = max(0, x - r), min(ancho, x + r)
            borde = gris[yr1:yr2, xr1:xr2]
            brillo_borde = np.mean(borde) if borde.size > 0 else brillo_centro
            if brillo_centro < 155 and brillo_centro < brillo_borde * 0.88:
                detecciones.append((x, y, r))

    for idx, (x, y, r) in enumerate(detecciones):
        numero = idx + 1
        tam_cruz = int(r * 0.8)
        grosor = max(3, r // 8)
        cv2.line(resultado_np, (x - tam_cruz, y), (x + tam_cruz, y), (0, 0, 0), grosor)
        cv2.line(resultado_np, (x, y - tam_cruz), (x, y + tam_cruz), (0, 0, 0), grosor)
        font_scale = max(0.6, r / 25)
        font_thickness = max(2, r // 12)
        text = str(numero)
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
        tx, ty = x - tw // 2, y + th // 2
        cv2.putText(resultado_np, text, (tx-1, ty-1), cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale, (255, 255, 255), font_thickness + 2, cv2.LINE_AA)
        cv2.putText(resultado_np, text, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale, (255, 0, 0), font_thickness, cv2.LINE_AA)

    return Image.fromarray(resultado_np), len(detecciones)

def dibujar_puntos(image_bytes, puntos, max_width=380):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
    img_np = np.array(img)
    radio = max(14, min(img_np.shape[1], img_np.shape[0]) // 22)
    for idx, (px, py) in enumerate(puntos):
        cv2.circle(img_np, (px, py), radio, (220, 0, 0), -1)
        cv2.circle(img_np, (px, py), radio, (255, 255, 255), 2)
        text = str(idx + 1)
        font_scale = max(0.4, radio / 18)
        thickness = max(1, radio // 10)
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        cv2.putText(img_np, text, (px - tw//2, py + th//2),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return Image.fromarray(img_np)

def redimensionar(image_bytes, max_width=380):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
    return img

# ── ESTADO ──────────────────────────────────────────────────────────────────
if "analysis" not in st.session_state:
    st.session_state.analysis = {}
if "puntos_h" not in st.session_state:
    st.session_state.puntos_h = []
if "ultimo_click" not in st.session_state:
    st.session_state.ultimo_click = None

# ── UI ──────────────────────────────────────────────────────────────────────
st.title("🏗️ AI-Count: Auditoría de Andamios")
st.markdown("Sistema de auditoría logística para contar piezas de andamiaje desde el celular.")

patente = st.selectbox("Patente del Camión:", PATENTE_LIST)
tipo = st.radio("Tipo de material:", ["Verticales", "Horizontales"], horizontal=True)

if tipo == "Horizontales":
    if st.button("🔄 Limpiar marcas"):
        st.session_state.puntos_h = []
        st.session_state.ultimo_click = None
        st.rerun()

uploaded_file = st.file_uploader("Suba una foto del material:", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()

    # ── VERTICALES ──────────────────────────────────────────────────────────
    if tipo == "Verticales":
        if st.button("Contar Verticales automáticamente"):
            with st.spinner("Analizando imagen..."):
                resultado_img, total = detectar_verticales(file_bytes)
                st.session_state.analysis = {
                    "tipo_material": "Verticales",
                    "annotated_img": resultado_img,
                    "total": total,
                    "file_bytes": file_bytes,
                }

        if st.session_state.analysis.get("tipo_material") == "Verticales":
            an = st.session_state.analysis
            if an["total"] < 20:
                st.warning(f"Se detectaron {an['total']} tubos — verifica que la foto sea de frente.")
            elif an["total"] > 104:
                st.warning(f"Se detectaron {an['total']} tubos — por encima del máximo (104).")
            else:
                st.success(f"Se detectaron {an['total']} tubos verticales.")

            st.image(an["annotated_img"],
                     caption=f"Detectados: {an['total']} tubos",
                     use_column_width=True)

            correccion = st.number_input(
                "Corregir conteo si es necesario:",
                min_value=0,
                value=an["total"],
                step=1
            )

            st.markdown("---")
            st.write(f"**Patente:** {patente}")
            st.write(f"**Tipo:** Verticales")
            st.write(f"**Total:** {correccion} piezas")

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
                        patente, "Verticales", correccion, photo_link
                    ])
                    st.success("Auditoría guardada en Google Sheets.")
                    if photo_link:
                        st.markdown(f"[Ver foto en Drive]({photo_link})")
                    st.session_state.analysis = {}
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    # ── HORIZONTALES ────────────────────────────────────────────────────────
    elif tipo == "Horizontales":
        st.markdown("### Toca cada cabezal en la foto")
        st.caption("Cada toque agrega un número rojo. Toca Limpiar para empezar de nuevo.")

        img_display = dibujar_puntos(file_bytes, st.session_state.puntos_h)

        valor = streamlit_image_coordinates(img_display, key="coord_h")

        if valor is not None and valor != st.session_state.ultimo_click:
            st.session_state.ultimo_click = valor
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
                    st.session_state.ultimo_click = None
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

st.markdown("---")
st.caption("AI-Count — Auditoría de Andamios")
