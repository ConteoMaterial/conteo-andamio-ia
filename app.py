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
import json

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
SHEET_ID        = "1ew4P9dsQWrINTCfEc5bg-qlcUmvSfZDPXUEq6hFxlOg"
DRIVE_FOLDER_ID = "1njn6Hp3qoaw3kYqkErseReHhA7mrvPjA"

PATENTES   = ["HSFC-61","HSFC-62","LPXW-25","LPXW-87","TKXD-17","LPXW-12","THXX-18"]
CHOFERES   = ["Juan Perez","Daniel Ramirez","Hugo Diaz","Cristian Olmos",
              "Victoria Garcia","Luis Ayala","Miguel Herrera"]
TURNOS     = ["Mañana","Tarde","Noche"]
MOVIMIENTOS = ["Salida","Devolución"]

# ─── PALETA ───────────────────────────────────────────────────────────────────
C = {
    "negro":    "#0A0A0F",
    "azul":     "#2D6BE4",
    "cian":     "#00D4FF",
    "pizarra":  "#2E3A4E",
    "carbono":  "#1E2A3A",
    "verde":    "#00E5A0",
    "rojo":     "#FF3D5A",
    "amarillo": "#FFB020",
}

# ─── PÁGINA ───────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ARMATEC · Auditoría Andamios", layout="wide", page_icon="🏗️")

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
    background-color: {C['negro']};
    color: {C['pizarra']};
  }}
  section[data-testid="stSidebar"] {{
    background-color: {C['carbono']};
    border-right: 1px solid {C['azul']}33;
  }}
  .stTabs [data-baseweb="tab-list"] {{
    background-color: {C['carbono']};
    border-radius: 8px;
    gap: 4px;
    padding: 4px;
  }}
  .stTabs [data-baseweb="tab"] {{
    background-color: transparent;
    color: #8899BB;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 8px 20px;
    border: none;
  }}
  .stTabs [aria-selected="true"] {{
    background-color: {C['azul']};
    color: white;
  }}
  .metric-card {{
    background: {C['carbono']};
    border: 1px solid {C['azul']}44;
    border-radius: 12px;
    padding: 18px 22px;
    text-align: center;
  }}
  .metric-label {{
    font-size: 0.72rem;
    color: #8899BB;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
  }}
  .metric-value {{
    font-size: 2rem;
    font-weight: 700;
    color: {C['cian']};
  }}
  .metric-sub {{
    font-size: 0.78rem;
    color: #8899BB;
    margin-top: 4px;
  }}
  .badge-conforme {{ background:{C['verde']}22; color:{C['verde']}; border:1px solid {C['verde']}66; border-radius:20px; padding:2px 12px; font-size:0.78rem; font-weight:600; }}
  .badge-alerta   {{ background:{C['rojo']}22;  color:{C['rojo']};  border:1px solid {C['rojo']}66;  border-radius:20px; padding:2px 12px; font-size:0.78rem; font-weight:600; }}
  .badge-revision {{ background:{C['amarillo']}22; color:{C['amarillo']}; border:1px solid {C['amarillo']}66; border-radius:20px; padding:2px 12px; font-size:0.78rem; font-weight:600; }}
  .armatec-header {{
    background: linear-gradient(135deg, {C['carbono']}, {C['negro']});
    border: 1px solid {C['azul']}55;
    border-radius: 12px;
    padding: 16px 24px;
    margin-bottom: 20px;
  }}
  .armatec-title {{
    font-size: 1.4rem;
    font-weight: 700;
    color: {C['cian']};
    letter-spacing: 0.04em;
  }}
  .armatec-sub {{ font-size: 0.78rem; color: #8899BB; }}
  div.stButton > button {{
    background: linear-gradient(135deg, {C['azul']}, #1a4fc7);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 10px 20px;
  }}
  hr {{ border-color: {C['azul']}22; }}
  .audit-row {{
    background: {C['carbono']};
    border: 1px solid {C['azul']}22;
    border-radius: 8px;
    padding: 10px 16px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.82rem;
  }}
  .audit-row-label {{ color: #8899BB; min-width: 90px; }}
  .audit-row-val   {{ color: {C['pizarra']}; font-weight: 600; }}
</style>
""", unsafe_allow_html=True)

# ─── GOOGLE AUTH ──────────────────────────────────────────────────────────────
@st.cache_resource
def get_clients():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    gc    = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)
    return gc, drive

# ─── SHEETS ───────────────────────────────────────────────────────────────────
def get_sheet(gc):
    wb = gc.open_by_key(SHEET_ID)
    try:
        ws = wb.worksheet("Auditorias")
    except gspread.exceptions.WorksheetNotFound:
        ws = wb.add_worksheet("Auditorias", rows=1000, cols=20)
        ws.append_row([
            "N° Auditoría","Fecha","Hora","Turno","Patente","Chofer",
            "Tipo Movimiento","Material","Cantidad Declarada","Cantidad Contada",
            "Diferencia","Estado","Observaciones","Auditado Por","Link Foto"
        ])
    return ws

def get_next_audit_number(ws):
    data = ws.get_all_values()
    if len(data) <= 1:
        return "AUD-0001"
    return f"AUD-{len(data):04d}"

def guardar_en_sheets(gc, registro):
    ws = get_sheet(gc)
    ws.append_row([
        registro["n_auditoria"], registro["fecha"], registro["hora"],
        registro["turno"], registro["patente"], registro["chofer"],
        registro["tipo_movimiento"], registro["material"],
        registro["cantidad_declarada"], registro["cantidad_contada"],
        registro["diferencia"], registro["estado"],
        registro["observaciones"], registro["auditado_por"], registro["link_foto"],
    ])

def cargar_historial(gc):
    return get_sheet(gc).get_all_records()

# ─── DRIVE ────────────────────────────────────────────────────────────────────
def subir_a_drive(drive, img_bytes, nombre):
    media = MediaIoBaseUpload(io.BytesIO(img_bytes), mimetype="image/jpeg")
    meta  = {"name": nombre, "parents": [DRIVE_FOLDER_ID]}
    f = drive.files().create(
        body=meta, media_body=media,
        fields="id, webViewLink",
        supportsAllDrives=True
    ).execute()
    return f.get("webViewLink", "")

# ─── DIBUJO ───────────────────────────────────────────────────────────────────
def dibujar_puntos(img_pil, puntos, tipo="vertical"):
    img = np.array(img_pil)
    ih, iw = img.shape[:2]
    radio = max(10, min(iw, ih) // 28)
    fuente = cv2.FONT_HERSHEY_SIMPLEX
    escala = max(0.4, radio / 22)
    grosor = max(1, radio // 9)

    for i, (x, y) in enumerate(puntos, 1):
        txt = str(i)
        tw, th = cv2.getTextSize(txt, fuente, escala, grosor)[0]
        tx, ty = x - tw // 2, y + th // 2

        if tipo == "vertical":
            cv2.line(img, (x - radio, y), (x + radio, y), (0,0,0), max(2, radio//5))
            cv2.line(img, (x, y - radio), (x, y + radio), (0,0,0), max(2, radio//5))
            cv2.putText(img, txt, (tx-1, ty+1), fuente, escala, (255,255,255), grosor+2, cv2.LINE_AA)
            cv2.putText(img, txt, (tx, ty),     fuente, escala, (0,0,255),     grosor,   cv2.LINE_AA)
        else:
            cv2.circle(img, (x, y), radio, (0,0,220), max(2, radio//5))
            cv2.putText(img, txt, (tx-1, ty+1), fuente, escala, (0,0,0),     grosor+2, cv2.LINE_AA)
            cv2.putText(img, txt, (tx, ty),     fuente, escala, (255,255,255), grosor,  cv2.LINE_AA)

    return Image.fromarray(img)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
for k, v in {"puntos_v":[],"puntos_h":[],"img_orig":None,
             "guardado":False,"link_drive":""}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── HEADER ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="armatec-header">
  <div class="armatec-title">🏗️ ARMATEC · Auditoría de Andamios</div>
  <div class="armatec-sub">Sistema de control y registro de material · Auditado por: <b>Richard Romero</b></div>
</div>
""", unsafe_allow_html=True)

tab_auditoria, tab_dashboard = st.tabs(["📋  Auditoría", "📊  Dashboard"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — AUDITORÍA
# ══════════════════════════════════════════════════════════════════════════════
with tab_auditoria:

    with st.expander("📝  Datos del turno", expanded=True):
        c1, c2, c3 = st.columns(3)
        patente  = c1.selectbox("Patente / Camión", PATENTES)
        chofer   = c2.selectbox("Chofer", CHOFERES)
        turno    = c3.selectbox("Turno", TURNOS)
        c4, c5   = st.columns(2)
        tipo_mov = c4.selectbox("Tipo de movimiento", MOVIMIENTOS,
                                help="Salida: camión lleva material · Devolución: camión retorna material")
        observaciones = c5.text_input("Observaciones", placeholder="Daños, faltantes, notas...")

    st.markdown("---")
    st.markdown(f"<span style='color:{C['cian']};font-weight:700;'>📷 Imagen del camión</span>",
                unsafe_allow_html=True)

    archivo = st.file_uploader("Subir foto", type=["jpg","jpeg","png"],
                               label_visibility="collapsed")

    if archivo:
        img_orig = Image.open(archivo).convert("RGB")
        w, h = img_orig.size
        if max(w, h) > 900:
            scale    = 900 / max(w, h)
            img_orig = img_orig.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
        if st.session_state["img_orig"] is None:
            st.session_state["img_orig"]  = img_orig
            st.session_state["puntos_v"]  = []
            st.session_state["puntos_h"]  = []
            st.session_state["guardado"]  = False
            st.session_state["link_drive"]= ""

    if st.session_state["img_orig"]:

        tab_v, tab_h = st.tabs(["🔵  Verticales", "🔴  Horizontales / Cabezales"])

        # ── VERTICALES ──────────────────────────────────────────────────────
        with tab_v:
            st.markdown("<p style='color:#8899BB;font-size:0.82rem;'>Toca cada tubo vertical → cruz negra + número rojo.</p>",
                        unsafe_allow_html=True)
            ci, cc = st.columns([3,1])
            with ci:
                coord_v = streamlit_image_coordinates(
                    dibujar_puntos(st.session_state["img_orig"], st.session_state["puntos_v"], "vertical"),
                    key="mapa_v")
            with cc:
                total_v = len(st.session_state["puntos_v"])
                st.markdown(f"""<div class="metric-card" style="margin-top:20px;">
                  <div class="metric-label">Verticales</div>
                  <div class="metric-value">{total_v}</div>
                  <div class="metric-sub">tubos marcados</div>
                </div>""", unsafe_allow_html=True)
                if st.button("↩ Deshacer (V)", key="undo_v"):
                    if st.session_state["puntos_v"]: st.session_state["puntos_v"].pop()
                    st.rerun()
                if st.button("🗑 Limpiar (V)", key="clear_v"):
                    st.session_state["puntos_v"] = []
                    st.rerun()
                decl_v = st.number_input("Cantidad declarada (V)", min_value=0, value=0, key="decl_v")
                if total_v > 0 and decl_v > 0:
                    d = total_v - decl_v
                    if d == 0:   st.markdown("<span class='badge-conforme'>✓ Conforme</span>", unsafe_allow_html=True)
                    elif abs(d)<=2: st.markdown(f"<span class='badge-revision'>⚠ Dif: {d:+d}</span>", unsafe_allow_html=True)
                    else:        st.markdown(f"<span class='badge-alerta'>✗ Dif: {d:+d}</span>", unsafe_allow_html=True)

            if coord_v:
                x, y = int(coord_v["x"]), int(coord_v["y"])
                if not st.session_state["puntos_v"] or st.session_state["puntos_v"][-1] != (x,y):
                    st.session_state["puntos_v"].append((x,y))
                    st.rerun()

        # ── HORIZONTALES ────────────────────────────────────────────────────
        with tab_h:
            st.markdown("<p style='color:#8899BB;font-size:0.82rem;'>Toca cada horizontal/cabezal → círculo rojo + número blanco.</p>",
                        unsafe_allow_html=True)
            ci, cc = st.columns([3,1])
            with ci:
                coord_h = streamlit_image_coordinates(
                    dibujar_puntos(st.session_state["img_orig"], st.session_state["puntos_h"], "horizontal"),
                    key="mapa_h")
            with cc:
                total_h = len(st.session_state["puntos_h"])
                st.markdown(f"""<div class="metric-card" style="margin-top:20px;">
                  <div class="metric-label">Horizontales</div>
                  <div class="metric-value">{total_h}</div>
                  <div class="metric-sub">piezas marcadas</div>
                </div>""", unsafe_allow_html=True)
                if st.button("↩ Deshacer (H)", key="undo_h"):
                    if st.session_state["puntos_h"]: st.session_state["puntos_h"].pop()
                    st.rerun()
                if st.button("🗑 Limpiar (H)", key="clear_h"):
                    st.session_state["puntos_h"] = []
                    st.rerun()
                decl_h = st.number_input("Cantidad declarada (H)", min_value=0, value=0, key="decl_h")
                if total_h > 0 and decl_h > 0:
                    d = total_h - decl_h
                    if d == 0:   st.markdown("<span class='badge-conforme'>✓ Conforme</span>", unsafe_allow_html=True)
                    elif abs(d)<=2: st.markdown(f"<span class='badge-revision'>⚠ Dif: {d:+d}</span>", unsafe_allow_html=True)
                    else:        st.markdown(f"<span class='badge-alerta'>✗ Dif: {d:+d}</span>", unsafe_allow_html=True)

            if coord_h:
                x, y = int(coord_h["x"]), int(coord_h["y"])
                if not st.session_state["puntos_h"] or st.session_state["puntos_h"][-1] != (x,y):
                    st.session_state["puntos_h"].append((x,y))
                    st.rerun()

        # ── GUARDAR ─────────────────────────────────────────────────────────
        st.markdown("---")
        total_contado   = len(st.session_state["puntos_v"]) + len(st.session_state["puntos_h"])
        cant_decl_total = st.session_state.get("decl_v",0) + st.session_state.get("decl_h",0)
        material_label  = f"V:{len(st.session_state['puntos_v'])} · H:{len(st.session_state['puntos_h'])}"

        c1, c2 = st.columns([2,1])
        c1.info(f"**Contado:** {total_contado}  |  **Declarado:** {cant_decl_total}  |  "
                f"**Diferencia:** {total_contado - cant_decl_total:+d}  |  {material_label}")
        guardar = c2.button("✅ Guardar en Sheets + Drive", type="primary",
                            disabled=st.session_state["guardado"])

        if guardar and not st.session_state["guardado"]:
            with st.spinner("Guardando..."):
                try:
                    gc, drive = get_clients()
                    diff_total = total_contado - cant_decl_total
                    if cant_decl_total == 0:      estado = "Sin declarar"
                    elif diff_total == 0:          estado = "Conforme"
                    elif abs(diff_total) <= 2:     estado = "Revisión"
                    else:                          estado = "No Conforme"

                    ws    = get_sheet(gc)
                    n_aud = get_next_audit_number(ws)
                    ahora = 
