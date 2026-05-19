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

    radio_min = int(min(alto, ancho) * 0.025)
    radio_max = int(min(alto, ancho) * 0.10)

    circulos = cv2.HoughCircles(
        gris,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=radio_min * 2,
        param1=100,
        param2=38,
        minRadius=radio_min,
        maxRadius=radio_max,
    )

    resultado = img.copy()
    draw = ImageDraw.Draw(resultado)
    detecciones = []

    if circulos is not None:
        circulos = np.round(circulos[0, :]).astype("int")
        # Filtrar solo hoyos oscuros (interior oscuro = hoyo de tubo)
        for (x, y, r) in circulos:
            region = gris[max(0, y-r//2):y+r//2, max(0, x-r//2):x+r//2]
            if region.size > 0 and np.mean(region) < 130:
                detecciones.append((x, y, r))

    total = len(detecciones)

    for idx, (x, y, r) in enumerate(detecciones):
        numero = idx + 1
        tam_cruz = int(r * 0.75)
        tam_num = max(int(r * 0.45), 14)

        # Cruz negra dentro del hoyo
        draw.line([(x - tam_cruz, y), (x + tam_cruz, y)], fill=(0, 0, 0), width=max(3, r//8))
        draw.line([(x, y - tam_cruz), (x, y + tam_cruz)], fill=(0, 0, 0), width=max(3, r//8))

        # Número rojo centrado en la cruz
        bbox = draw.textbbox((0, 0), str(numero))
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((x - tw//2, y - th//2), str(numero), fill=(255, 0, 0))

    return resultado, total

def canvas_horizontal(image_bytes, count):
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    html = f"""
    <div style="width:100%; font-family:Arial, sans-serif;">
        <canvas id="cv" style="width:100%; touch-action:none; border:2px solid #ddd; border-radius:8px;"></canvas>
        <div style="margin-top:12px; display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
            <div style="font-size:24px; font-weight:bold; color:#cc0000;">
                Marcados: <span id="cnt">{count}</span>
            </div>
            <button onclick="deshacer()" style="padding:12px 20px; font-size:16px; background:#cc0000; color:white; border:none; border-radius:8px; cursor:pointer;">
                ↩ Deshacer
            </button>
            <button onclick="limpiar()" style="padding:12px 20px; font-size:16px; background:#555; color:white; border:none; border-radius:8px; cursor:pointer;">
                🗑 Limpiar
            </button>
        </div>
    </div>
    <script>
        const cv = document.getElementById('cv');
        const ctx = cv.getContext('2d');
        const img = new Image();
        let pts = [];

        img.onload = function() {{
            cv.width = img.naturalWidth;
            cv.height = img.naturalHeight;
            dibujar();
        }};
        img.src = 'data:image/jpeg;base64,{b64}';

        function dibujar() {{
            ctx.clearRect(0, 0, cv.width, cv.height);
            ctx.drawImage(img, 0, 0);
            pts.forEach(function(p, i) {{
                const r = Math.max(cv.width, cv.height) * 0.022;
                ctx.beginPath();
                ctx.arc(p[0], p[1], r, 0, 2 * Math.PI);
                ctx.fillStyle = 'rgba(220,0,0,0.82)';
                ctx.fill();
                ctx.strokeStyle = 'white';
                ctx.lineWidth = r * 0.18;
                ctx.stroke();
                ctx.fillStyle = 'white';
                ctx.font = 'bold ' + Math.round(r * 1.1) + 'px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(i + 1, p[0], p[1]);
            }});
            document.getElementById('cnt').innerText = pts.length;
            notificar();
        }}

        function getPos(e) {{
            const rect = cv.getBoundingClientRect();
            const sx = cv.width / rect.width;
            const sy = cv.height / rect.height;
            if (e.changedTouches) {{
                return [(e.changedTouches[0].clientX - rect.left) * sx,
                        (e.changedTouches[0].clientY - rect.top) * sy];
            }}
            return [(e.clientX - rect.left) * sx, (e.clientY - rect.top) * sy];
        }}

        cv.addEventListener('touchend', function(e) {{
            e.preventDefault();
            pts.push(getPos(e));
            dibujar();
        }}, {{passive: false}});

        cv.addEventListener('click', function(e) {{
            pts.push(getPos(e));
            dibujar();
        }});

        function deshacer() {{
            if (pts.length > 0) {{ pts.pop(); dibujar(); }}
        }}

        function limpiar() {{
            pts = []; dibujar();
        }}

        function notificar() {{
            window.parent.postMessage({{
                isStreamlitMessage: true,
                type: 'streamlit:setComponentValue',
                value: pts.length
            }}, '*');
        }}

        setTimeout(notificar, 500);
    </script>
    """
    return st.components.v1.html(html, height=720, scrolling=False)

# ── ESTADO ──────────────────────────────────────────────────────────────────
if "total_horizontal" not in st.session_state:
    st.session_state.total_horizontal = 0
if "analysis" not in st.session_state:
    st.session_state.analysis = {}

# ── UI ──────────────────────────────────────────────────────────────────────
st.title("🏗️ AI-Count: Auditoría de Andamios")
st.markdown("Sistema de auditoría logística para contar piezas de andamiaje desde el celular.")

patente = st.selectbox("Patente del Camión:", PATENTE_LIST)
tipo = st.radio("Tipo de material:", ["Verticales", "Horizontales"], horizontal=True)
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
                st.warning(f"Se detectaron {an['total']} tubos — por encima del máximo (104). Verifica.")
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
            st.session_state.analysis["total"] = correccion

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
                    st.success("Auditoría guardada correctamente en Google Sheets.")
                    if photo_link:
                        st.markdown(f"[Ver foto en Drive]({photo_link})")
                    st.session_state.analysis = {}
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    # ── HORIZONTALES ────────────────────────────────────────────────────────
    elif tipo == "Horizontales":
        st.markdown("### Toca cada cabezal en la foto")
        st.caption("Círculo rojo + número en cada toque. Usa Deshacer si te equivocas.")

        canvas_horizontal(file_bytes, st.session_state.total_horizontal)

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("➕ Sumar 1"):
                st.session_state.total_horizontal += 1
                st.rerun()
        with col2:
            if st.button("➖ Restar 1") and st.session_state.total_horizontal > 0:
                st.session_state.total_horizontal -= 1
                st.rerun()
        with col3:
            if st.button("🔄 Reiniciar"):
                st.session_state.total_horizontal = 0
                st.rerun()

        total_h = st.session_state.total_horizontal
        if total_h == 0:
            st.info("Toca los cabezales en la foto para comenzar el conteo.")
        elif total_h < 40:
            st.warning(f"Total: **{total_h}** — por debajo del mínimo esperado (40).")
        elif total_h > 212:
            st.warning(f"Total: **{total_h}** — por encima del máximo (212). Verifica.")
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
                    st.success("Auditoría guardada correctamente en Google Sheets.")
                    if photo_link:
                        st.markdown(f"[Ver foto en Drive]({photo_link})")
                    st.session_state.total_horizontal = 0
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

st.markdown("---")
st.caption("AI-Count — Auditoría de Andamios")
