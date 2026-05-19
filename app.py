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
import base64

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
    gris = cv2.GaussianBlur(gris, (9, 9), 2)
    alto, ancho = gris.shape
    radio_min = int(min(alto, ancho) * 0.025)
    radio_max = int(min(alto, ancho) * 0.09)
    circulos = cv2.HoughCircles(
        gris,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=radio_min * 3,
        param1=120,
        param2=55,
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

def imagen_a_base64(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")

def mostrar_canvas_tactil(image_bytes, puntos):
    b64 = imagen_a_base64(image_bytes)
    puntos_js = str([[p[0], p[1]] for p in puntos])
    html = f"""
    <div style="position:relative; display:inline-block; width:100%;">
        <canvas id="canvas" style="width:100%; touch-action:none; border:2px solid #ccc;"></canvas>
        <div style="margin-top:8px; font-size:18px; font-weight:bold; color:#e00;">
            Marcados: <span id="contador">{len(puntos)}</span>
        </div>
        <button onclick="deshacer()" style="margin-top:8px; padding:10px 20px; font-size:16px; background:#e00; color:white; border:none; border-radius:8px;">
            ↩ Deshacer último
        </button>
    </div>
    <script>
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const img = new Image();
        let puntos = {puntos_js};
        let escalaX = 1;
        let escalaY = 1;

        img.onload = function() {{
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            dibujar();
        }};
        img.src = 'data:image/jpeg;base64,{b64}';

        function dibujar() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);
            puntos.forEach(function(p) {{
                ctx.beginPath();
                ctx.arc(p[0], p[1], 18, 0, 2 * Math.PI);
                ctx.fillStyle = 'rgba(255,0,0,0.7)';
                ctx.fill();
                ctx.strokeStyle = 'white';
                ctx.lineWidth = 3;
                ctx.stroke();
            }});
            document.getElementById('contador').innerText = puntos.length;
        }}

        function getPos(e) {{
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            if (e.touches) {{
                return [
                    (e.touches[0].clientX - rect.left) * scaleX,
                    (e.touches[0].clientY - rect.top) * scaleY
                ];
            }}
            return [
                (e.clientX - rect.left) * scaleX,
                (e.clientY - rect.top) * scaleY
            ];
        }}

        canvas.addEventListener('touchend', function(e) {{
            e.preventDefault();
            const pos = getPos(e.changedTouches[0] ? {{touches: e.changedTouches}} : e);
            puntos.push(pos);
            dibujar();
            enviarPuntos();
        }}, {{passive: false}});

        canvas.addEventListener('click', function(e) {{
            const pos = getPos(e);
            puntos.push(pos);
            dibujar();
            enviarPuntos();
        }});

        function deshacer() {{
            if (puntos.length > 0) {{
                puntos.pop();
                dibujar();
                enviarPuntos();
            }}
        }}

        function enviarPuntos() {{
            const data = JSON.stringify(puntos);
            window.parent.postMessage({{type: 'puntos_canvas', puntos: data}}, '*');
        }}
    </script>
    """
    st.components.v1.html(html, height=700, scrolling=True)

st.title("🏗️ AI-Count: Auditoría de Andamios")
st.markdown("Sistema de auditoría logística para contar piezas de andamiaje desde el celular.")

if "conteo_asistido" not in st.session_state:
    st.session_state.conteo_asistido = 0
if "puntos_horizontal" not in st.session_state:
    st.session_state.puntos_horizontal = []
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
            correccion = st.number_input(
                "Corregir conteo si es necesario:",
                min_value=0,
                value=st.session_state.analysis["total"],
                step=1
            )
            st.session_state.analysis["total"] = correccion

    elif tipo == "Horizontales":
        st.markdown("### Toca cada horizontal en la foto para marcarlo")
        st.caption("Cada toque agrega un punto rojo. Usa el botón Deshacer si te equivocas.")

        if st.button("🔄 Limpiar todos los puntos"):
            st.session_state.puntos_horizontal = []

        mostrar_canvas_tactil(file_bytes, st.session_state.puntos_horizontal)

        total_horizontal = len(st.session_state.puntos_horizontal)
        st.markdown(f"## Total marcados: **{total_horizontal}**")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Sumar 1 manualmente"):
                st.session_state.conteo_asistido += 1
        with col2:
            if st.button("➖ Restar 1"):
                if st.session_state.conteo_asistido > 0:
                    st.session_state.conteo_asistido -= 1

        total_final = total_horizontal + st.session_state.conteo_asistido
        if total_final > 0:
            if st.button("Confirmar conteo de Horizontales"):
                st.session_state.analysis = {
                    "tipo_material": "Horizontales",
                    "annotated_img": Image.open(io.BytesIO(file_bytes)),
                    "total": total_final,
                    "file_bytes": file_bytes,
                }
                st.success(f"Conteo confirmado: {total_final} horizontales.")

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
            st.session_state.puntos_horizontal = []
            st.session_state.conteo_asistido = 0
        except Exception as exc:
            st.error(f"No se pudo guardar: {exc}")

st.markdown("---")
st.caption("AI-Count — Auditoría de Andamios")
