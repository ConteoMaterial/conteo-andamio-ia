import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
import datetime
from zoneinfo import ZoneInfo
import io
import os
import base64

# ─── COMPONENTE CANVAS (conteo instantáneo en la tablet, sin lag) ─────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
_canvas = components.declare_component(
    "canvas_counter", path=os.path.join(_DIR, "canvas_component")
)

def canvas_counter(img_b64, puntos, tipo, key):
    return _canvas(img=img_b64, puntos=puntos, tipo=tipo, key=key, default=puntos)

def img_a_b64(img_pil):
    buf = io.BytesIO()
    img_pil.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
SHEET_ID    = "1tVGss0qpGZwzmTpWd_jdBqIczpQyUkibwa209Gq2t7Y"
PATENTES    = ["HSFC-61","HSFC-62","LPXW-25","LPXW-87","TKXD-17","LPXW-12","THXX-18"]
CHOFERES    = ["Juan Perez","Daniel Ramirez","Hugo Diaz","Cristian Olmos",
               "Victoria Garcia","Luis Ayala","Miguel Herrera"]
TURNOS      = ["Mañana","Tarde","Noche"]
MOVIMIENTOS = ["Salida","Devolución"]
HEADERS     = ["N° Auditoria","Fecha","Hora","Turno","Patente","Chofer",
               "Tipo Movimiento","Material","Cantidad Declarada","Cantidad Contada",
               "Diferencia","Estado","Observaciones","Auditado Por",
               "Diagonales","Amarras 3.0m","Amarras 1.5m","Plataformas",
               "Tablones","Bases/Niveladores","Abrazaderas"]

# (label visible, clave corta para session_state)
MATERIALES_SEC = [
    ("Diagonales",        "diag"),
    ("Amarras 3.0m",      "am30"),
    ("Amarras 1.5m",      "am15"),
    ("Plataformas",       "plat"),
    ("Tablones",          "tabl"),
    ("Bases/Niveladores", "base"),
    ("Abrazaderas",       "abra"),
]

# ─── COLORES ──────────────────────────────────────────────────────────────────
COL_NEGRO    = "#0A0A0F"
COL_AZUL     = "#2D6BE4"
COL_CIAN     = "#00D4FF"
COL_PIZARRA  = "#2E3A4E"
COL_CARBONO  = "#1E2A3A"
COL_VERDE    = "#00E5A0"
COL_ROJO     = "#FF3D5A"
COL_AMARILLO = "#FFB020"

# ─── CONFIG PÁGINA ────────────────────────────────────────────────────────────
st.set_page_config(page_title="ARMATEC · Auditoría Andamios",
                   layout="wide", page_icon="🏗️")

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
    background-color: {COL_NEGRO};
    color: {COL_PIZARRA};
  }}
  .stTabs [data-baseweb="tab-list"] {{
    background-color: {COL_CARBONO};
    border-radius: 8px; gap: 4px; padding: 4px;
  }}
  .stTabs [data-baseweb="tab"] {{
    background-color: transparent; color: #8899BB;
    border-radius: 6px; font-weight: 600; font-size: 0.85rem;
    padding: 8px 20px; border: none;
  }}
  .stTabs [aria-selected="true"] {{ background-color: {COL_AZUL}; color: white; }}
  .metric-card {{
    background: {COL_CARBONO}; border: 1px solid {COL_AZUL}44;
    border-radius: 12px; padding: 14px 18px; text-align: center; margin: 6px 0;
  }}
  .metric-label {{ font-size:0.72rem; color:#8899BB; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:4px; }}
  .metric-value {{ font-size:2.2rem; font-weight:700; color:{COL_CIAN}; }}
  .metric-sub   {{ font-size:0.75rem; color:#8899BB; margin-top:2px; }}
  .badge-conforme {{ background:{COL_VERDE}22; color:{COL_VERDE}; border:1px solid {COL_VERDE}66; border-radius:20px; padding:3px 14px; font-size:0.82rem; font-weight:600; }}
  .badge-alerta   {{ background:{COL_ROJO}22;  color:{COL_ROJO};  border:1px solid {COL_ROJO}66;  border-radius:20px; padding:3px 14px; font-size:0.82rem; font-weight:600; }}
  .badge-revision {{ background:{COL_AMARILLO}22; color:{COL_AMARILLO}; border:1px solid {COL_AMARILLO}66; border-radius:20px; padding:3px 14px; font-size:0.82rem; font-weight:600; }}
  .armatec-header {{
    background: linear-gradient(135deg, {COL_CARBONO}, {COL_NEGRO});
    border: 1px solid {COL_AZUL}55; border-radius: 12px;
    padding: 16px 24px; margin-bottom: 20px;
  }}
  .armatec-title {{ font-size:1.4rem; font-weight:700; color:{COL_CIAN}; letter-spacing:0.04em; }}
  .armatec-sub   {{ font-size:0.78rem; color:#8899BB; }}
  div.stButton > button {{
    background: linear-gradient(135deg, {COL_AZUL}, #1a4fc7);
    color: white; border: none; border-radius: 8px; font-weight: 600; padding: 10px 20px;
  }}
  hr {{ border-color: {COL_AZUL}22; }}
  .audit-row {{
    background: {COL_CARBONO}; border: 1px solid {COL_AZUL}22;
    border-radius: 8px; padding: 10px 16px; margin-bottom: 6px;
    display: flex; align-items: center; gap: 12px; font-size: 0.82rem; flex-wrap: wrap;
  }}
  .audit-row-label {{ color: #8899BB; min-width: 90px; }}
  .audit-row-val   {{ color: {COL_PIZARRA}; font-weight: 600; }}
</style>
""", unsafe_allow_html=True)

# ─── GOOGLE AUTH ──────────────────────────────────────────────────────────────
@st.cache_resource
def get_clients():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds  = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    gc     = gspread.authorize(creds)
    sheets = build("sheets", "v4", credentials=creds)
    return gc, sheets

# ─── FORMATO PROFESIONAL SHEETS ───────────────────────────────────────────────
def formato_sheets(ws, sheets_service):
    sid    = ws._properties["sheetId"]
    n_cols = len(HEADERS)
    reqs   = []

    # Fila 1: fusionar celdas para título
    reqs.append({"mergeCells": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                  "startColumnIndex": 0, "endColumnIndex": n_cols},
        "mergeType": "MERGE_ALL"
    }})
    # Fila 1: formato título (negro + cian)
    reqs.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
        "cell": {"userEnteredFormat": {
            "backgroundColor": {"red": 0.039, "green": 0.039, "blue": 0.059},
            "textFormat": {"bold": True, "fontSize": 14,
                           "foregroundColor": {"red": 0.0, "green": 0.831, "blue": 1.0}},
            "horizontalAlignment": "CENTER",
            "verticalAlignment":   "MIDDLE",
        }},
        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)"
    }})
    # Fila 1: altura 44px
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 44}, "fields": "pixelSize"
    }})
    # Fila 2: encabezados (azul + blanco)
    reqs.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2},
        "cell": {"userEnteredFormat": {
            "backgroundColor": {"red": 0.176, "green": 0.420, "blue": 0.894},
            "textFormat": {"bold": True, "fontSize": 10,
                           "foregroundColor": {"red":1,"green":1,"blue":1}},
            "horizontalAlignment": "CENTER",
            "verticalAlignment":   "MIDDLE",
        }},
        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)"
    }})
    # Fila 2: altura 32px
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 32}, "fields": "pixelSize"
    }})
    # Congelar filas 1 y 2
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 2}},
        "fields": "gridProperties.frozenRowCount"
    }})
    # Formato condicional Estado: Conforme → verde
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": sid, "startRowIndex": 2,
                    "startColumnIndex": 11, "endColumnIndex": 12}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Conforme"}]},
            "format": {"backgroundColor": {"red": 0.0, "green": 0.898, "blue": 0.627}}
        }
    }, "index": 0}})
    # Estado: No Conforme → rojo
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": sid, "startRowIndex": 2,
                    "startColumnIndex": 11, "endColumnIndex": 12}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "No Conforme"}]},
            "format": {"backgroundColor": {"red": 1.0, "green": 0.239, "blue": 0.353}}
        }
    }, "index": 1}})
    # Estado: Revision → amarillo
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": sid, "startRowIndex": 2,
                    "startColumnIndex": 11, "endColumnIndex": 12}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Revision"}]},
            "format": {"backgroundColor": {"red": 1.0, "green": 0.690, "blue": 0.125}}
        }
    }, "index": 2}})
    # Filas alternadas (banding) desde fila 3
    reqs.append({"addBanding": {"bandedRange": {
        "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 1000,
                  "startColumnIndex": 0, "endColumnIndex": n_cols},
        "rowProperties": {
            "headerColor":     {"red": 0.176, "green": 0.420, "blue": 0.894},
            "firstBandColor":  {"red": 0.94, "green": 0.96, "blue": 1.0},
            "secondBandColor": {"red": 1.0,  "green": 1.0,  "blue": 1.0},
        }
    }}})
    # Anchos de columna
    anchos = [110,100,75,80,90,130,120,110,120,120,85,110,160,130]
    for i, w in enumerate(anchos):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i+1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"
        }})

    # Ejecutar request a request para tolerar errores individuales
    for req in reqs:
        try:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID, body={"requests": [req]}
            ).execute()
        except Exception:
            pass

# ─── SHEETS CRUD ──────────────────────────────────────────────────────────────
def get_sheet(gc, sheets_service=None):
    wb = gc.open_by_key(SHEET_ID)
    try:
        ws = wb.worksheet("Auditorias")
    except gspread.exceptions.WorksheetNotFound:
        ws = wb.add_worksheet("Auditorias", rows=1000, cols=20)
        # Fila 1: título
        ws.update("A1", [["🏗️ ARMATEC · AUDITORÍA DE ANDAMIOS"]])
        # Fila 2: encabezados
        ws.append_row(HEADERS)
        if sheets_service:
            try:
                formato_sheets(ws, sheets_service)
            except Exception:
                pass
    return ws

def get_next_audit_number(ws):
    data = ws.get_all_values()
    # Fila 1 = título, Fila 2 = encabezados, Fila 3+ = datos
    if len(data) <= 2:
        return "AUD-0001"
    return "AUD-" + str(len(data) - 1).zfill(4)

def guardar_en_sheets(gc, registro):
    ws = get_sheet(gc)
    ws.append_row([
        registro["n_auditoria"],    registro["fecha"],
        registro["hora"],           registro["turno"],
        registro["patente"],        registro["chofer"],
        registro["tipo_movimiento"],registro["material"],
        registro["cant_declarada"], registro["cant_contada"],
        registro["diferencia"],     registro["estado"],
        registro["observaciones"],  registro["auditado_por"],
        registro.get("diag", 0),    registro.get("am30", 0),
        registro.get("am15", 0),    registro.get("plat", 0),
        registro.get("tabl", 0),    registro.get("base", 0),
        registro.get("abra", 0),
    ])

def cargar_historial(gc):
    ws     = get_sheet(gc)
    values = ws.get_all_values()
    if len(values) <= 2:
        return []
    headers = values[1]   # Fila 2 son los encabezados
    records = []
    for row in values[2:]:
        row_p = row + [""] * (len(headers) - len(row))
        records.append(dict(zip(headers, row_p)))
    return records

# ─── IMAGEN ───────────────────────────────────────────────────────────────────
def cargar_imagen(fuente):
    img = Image.open(fuente)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > 500:
        scale = 500 / max(w, h)
        img   = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img

# ─── FRAGMENT: CONTEO (foto propia por tab, canvas sin lag, fix mobile) ────────
@st.fragment
def contar_material(tipo):
    key_p   = "puntos_v"   if tipo == "vertical" else "puntos_h"
    key_m   = "mapa_v"     if tipo == "vertical" else "mapa_h"
    key_d   = "decl_v"     if tipo == "vertical" else "decl_h"
    key_img = "img_orig_v" if tipo == "vertical" else "img_orig_h"
    key_b64 = "img_b64_v"  if tipo == "vertical" else "img_b64_h"
    key_uc  = "uc_v"       if tipo == "vertical" else "uc_h"
    label   = "Verticales" if tipo == "vertical" else "Horizontales"

    # ── Foto propia para este tab (dentro del fragment → no recarga la página) ──
    st.markdown(
        "<span style='color:#8899BB;font-size:0.82rem;'>📷 Foto de " + label + "</span>",
        unsafe_allow_html=True
    )
    archivo = st.file_uploader(
        "Foto de " + label,
        type=["jpg","jpeg","png","webp"],
        key="upl_" + tipo[0] + "_" + str(st.session_state.get(key_uc, 0)),
        label_visibility="collapsed"
    )
    if archivo and st.session_state[key_img] is None:
        try:
            img_nueva = cargar_imagen(archivo)
            st.session_state[key_img] = img_nueva
            st.session_state[key_b64] = img_a_b64(img_nueva)
            st.session_state[key_p]   = []
        except Exception as e:
            st.error("No se pudo cargar la imagen: " + str(e))

    if st.session_state[key_img] is None:
        st.info("Sube la foto de " + label.lower() + " para iniciar el conteo.")
        return

    # ── Canvas (instantáneo en la tablet) ────────────────────────────────────
    ret = canvas_counter(
        st.session_state[key_b64],
        st.session_state[key_p],
        tipo,
        key=key_m,
    )
    if ret is not None:
        nuevos = [[int(p[0]), int(p[1])] for p in ret]
        if nuevos != st.session_state[key_p]:
            st.session_state[key_p] = nuevos

    total = len(st.session_state[key_p])

    # ── Cantidad declarada + badge ────────────────────────────────────────────
    decl = st.number_input(
        "Cantidad declarada (" + label + ")",
        min_value=0, value=0, key=key_d
    )
    if total > 0 and decl > 0:
        d = total - decl
        if d == 0:
            st.markdown("<span class='badge-conforme'>✓ Conforme</span>", unsafe_allow_html=True)
        elif abs(d) <= 2:
            st.markdown("<span class='badge-revision'>⚠ Diferencia: " + f"{d:+d}" + "</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='badge-alerta'>✗ Diferencia: " + f"{d:+d}" + "</span>", unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
_ss_defaults = {
    "puntos_v": [], "puntos_h": [],
    "img_orig_v": None, "img_b64_v": None,
    "img_orig_h": None, "img_b64_h": None,
    "guardado": False,
    "last_audit_id": "", "last_audit_estado": "",
    "s_patente": PATENTES[0], "s_chofer": CHOFERES[0], "s_turno": TURNOS[0],
    "s_tipo_mov": MOVIMIENTOS[0], "s_observaciones": "",
    "upload_counter": 0, "uc_v": 0, "uc_h": 0,
}
for _lbl, _key in MATERIALES_SEC:
    _ss_defaults["sec_" + _key] = 0
for k, v in _ss_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── HEADER ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="armatec-header">
  <div class="armatec-title">🏗️ ARMATEC · Auditoría de Andamios</div>
  <div class="armatec-sub">Sistema de control y registro de material · Auditado por: <b>Richard Gonzalez</b></div>
</div>
""", unsafe_allow_html=True)

tab_auditoria, tab_dashboard = st.tabs(["📋  Auditoría", "📊  Dashboard"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — AUDITORÍA
# ══════════════════════════════════════════════════════════════════════════════
with tab_auditoria:

    # ── Formulario ───────────────────────────────────────────────────────────
    with st.expander("📝  Datos del turno", expanded=True):
        c1, c2, c3 = st.columns(3)
        patente  = c1.selectbox("Patente / Camión", PATENTES)
        chofer   = c2.selectbox("Chofer", CHOFERES)
        turno    = c3.selectbox("Turno", TURNOS)
        c4, c5   = st.columns(2)
        tipo_mov = c4.selectbox("Tipo de movimiento", MOVIMIENTOS,
                                help="Salida: lleva material · Devolución: retorna material")
        observaciones = c5.text_input("Observaciones", placeholder="Daños, faltantes, notas...")

    # Guardar form en session_state para acceder desde el guardado
    st.session_state["s_patente"]      = patente
    st.session_state["s_chofer"]       = chofer
    st.session_state["s_turno"]        = turno
    st.session_state["s_tipo_mov"]     = tipo_mov
    st.session_state["s_observaciones"]= observaciones

    col_r, _ = st.columns([1, 5])
    if col_r.button("🔄 Refrescar"):
        st.rerun()

    # ── Pantalla post-guardado ────────────────────────────────────────────────
    if st.session_state["guardado"]:
        n_id  = st.session_state.get("last_audit_id", "")
        n_est = st.session_state.get("last_audit_estado", "")
        st.markdown("<br>", unsafe_allow_html=True)
        st.success("✅ Auditoría **" + n_id + "** guardada · Estado: **" + n_est + "**")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Nueva auditoría", type="primary", use_container_width=True):
            _reset = {
                "puntos_v": [], "puntos_h": [],
                "img_orig_v": None, "img_b64_v": None,
                "img_orig_h": None, "img_b64_h": None,
                "guardado": False,
                "last_audit_id": "", "last_audit_estado": "",
                "upload_counter": st.session_state.get("upload_counter", 0) + 1,
                "uc_v": st.session_state.get("uc_v", 0) + 1,
                "uc_h": st.session_state.get("uc_h", 0) + 1,
            }
            for _, _k in MATERIALES_SEC:
                _reset["sec_" + _k] = 0
            st.session_state.update(_reset)
            st.rerun()

    else:
        st.markdown("---")

        # ── Tabs — cada uno carga su propia foto ─────────────────────────────
        tab_v, tab_h, tab_sec = st.tabs([
            "🔵  Verticales",
            "🔴  Horizontales / Cabezales",
            "🔩  Accesorios"
        ])

        with tab_v:
            contar_material("vertical")

        with tab_h:
            contar_material("horizontal")

        with tab_sec:
            st.markdown(
                "<div style='color:#00D4FF;font-weight:700;margin-bottom:12px;'>"
                "🔩 Registro de Materiales Secundarios y Accesorios</div>",
                unsafe_allow_html=True
            )
            st.markdown(
                "<p style='color:#8899BB;font-size:0.82rem;margin-bottom:14px;'>"
                "Ingresa la cantidad contada de cada accesorio. "
                "La foto es opcional como respaldo visual.</p>",
                unsafe_allow_html=True
            )
            for lbl, key in MATERIALES_SEC:
                st.markdown(
                    "<div style='color:#fff;font-weight:600;margin:10px 0 4px 0;'>"
                    + lbl + "</div>",
                    unsafe_allow_html=True
                )
                c1, c2 = st.columns([1, 2])
                cant_sec = c1.number_input(
                    "Cantidad",
                    min_value=0,
                    value=st.session_state.get("sec_" + key, 0),
                    key="sec_input_" + key,
                    label_visibility="collapsed"
                )
                st.session_state["sec_" + key] = cant_sec
                foto_sec = c2.file_uploader(
                    "Foto",
                    type=["jpg","jpeg","png","webp"],
                    key="sec_foto_" + key + "_" + str(st.session_state.get("upload_counter", 0)),
                    label_visibility="collapsed"
                )
                if foto_sec:
                    st.image(foto_sec, width=180)
                st.markdown("<hr style='border-color:#2D6BE422;margin:8px 0;'>", unsafe_allow_html=True)

        # ── Guardar ──────────────────────────────────────────────────────────
        st.markdown("---")
        st.caption("Un solo Guardar registra todo: Verticales + Horizontales + Accesorios.")
        total_v         = len(st.session_state["puntos_v"])
        total_h         = len(st.session_state["puntos_h"])
        total_contado   = total_v + total_h
        cant_decl_total = st.session_state.get("decl_v", 0) + st.session_state.get("decl_h", 0)
        material_label  = "V:" + str(total_v) + " · H:" + str(total_h)

        c1, c2 = st.columns([2, 1])
        c1.info(
            "**Contado:** " + str(total_contado) +
            "  |  **Declarado:** " + str(cant_decl_total) +
            "  |  **Diferencia:** " + f"{total_contado - cant_decl_total:+d}" +
            "  |  " + material_label
        )
        btn_guardar = c2.button("✅ Guardar todo", type="primary")

        if btn_guardar:
            with st.spinner("Guardando en Google Sheets..."):
                try:
                    gc, sheets = get_clients()
                    diff = total_contado - cant_decl_total
                    if cant_decl_total == 0:  estado = "Sin declarar"
                    elif diff == 0:           estado = "Conforme"
                    elif abs(diff) <= 2:      estado = "Revision"
                    else:                     estado = "No Conforme"

                    ws    = get_sheet(gc, sheets)
                    n_aud = get_next_audit_number(ws)
                    ahora = datetime.datetime.now(ZoneInfo("America/Santiago"))

                    guardar_en_sheets(gc, {
                        "n_auditoria":    n_aud,
                        "fecha":          ahora.strftime("%Y-%m-%d"),
                        "hora":           ahora.strftime("%H:%M:%S"),
                        "turno":          st.session_state["s_turno"],
                        "patente":        st.session_state["s_patente"],
                        "chofer":         st.session_state["s_chofer"],
                        "tipo_movimiento":st.session_state["s_tipo_mov"],
                        "material":       material_label,
                        "cant_declarada": cant_decl_total,
                        "cant_contada":   total_contado,
                        "diferencia":     diff,
                        "estado":         estado,
                        "observaciones":  st.session_state["s_observaciones"],
                        "auditado_por":   "Richard Gonzalez",
                        **{k: st.session_state.get("sec_" + k, 0) for _, k in MATERIALES_SEC},
                    })

                    st.session_state["guardado"]          = True
                    st.session_state["last_audit_id"]     = n_aud
                    st.session_state["last_audit_estado"] = estado
                    st.rerun()
                except Exception as e:
                    st.error("Error al guardar: " + str(e))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    import pandas as pd

    col_act, _ = st.columns([1, 3])
    if col_act.button("🔄 Actualizar datos"):
        st.cache_resource.clear()
        st.rerun()

    # ── Cargar historial ─────────────────────────────────────────────────────
    try:
        gc, _ = get_clients()
        historial = cargar_historial(gc)
    except Exception as e:
        st.error("No se pudo cargar el historial: " + str(e))
        historial = []

    if not historial:
        st.info("Aún no hay registros. Guarda una auditoría para verla aquí.")
    else:
        df = pd.DataFrame(historial)

        # Limpiar nombres de columna (quitar espacios ocultos)
        df.columns = [c.strip() for c in df.columns]

        for col in ["Cantidad Declarada","Cantidad Contada","Diferencia"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        # Limpiar Estado (strip + capitalizar para tolerar variaciones)
        if "Estado" not in df.columns:
            df["Estado"] = "Sin declarar"
        else:
            df["Estado"] = df["Estado"].astype(str).str.strip()

        total_aud  = len(df)
        conformes  = len(df[df["Estado"] == "Conforme"])
        no_conf    = len(df[df["Estado"] == "No Conforme"])
        revisiones = len(df[df["Estado"] == "Revision"])
        sin_decl   = len(df[df["Estado"] == "Sin declarar"])
        pct        = round(conformes / total_aud * 100) if total_aud else 0

        # ── KPIs ─────────────────────────────────────────────────────────────
        k1,k2,k3,k4,k5 = st.columns(5)
        for col, label, value, sub in [
            (k1, "Total",        total_aud,       "auditorías"),
            (k2, "Conformes",    conformes,        str(pct)+"%"),
            (k3, "No Conformes", no_conf,          "diferencia"),
            (k4, "En Revisión",  revisiones,       "±1-2 unid."),
            (k5, "Sin declarar", sin_decl,         "sin cantidad"),
        ]:
            col.markdown(
                "<div class='metric-card'>"
                "<div class='metric-label'>" + label + "</div>"
                "<div class='metric-value'>" + str(value) + "</div>"
                "<div class='metric-sub'>" + sub + "</div></div>",
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Historial completo (todas las columnas de Sheets, sin filtro) ───────
        st.markdown(
            "<div style='color:" + COL_CIAN + ";font-weight:700;margin-bottom:8px;'>"
            "📋 Registros de auditorías</div>",
            unsafe_allow_html=True
        )
        # Excluir solo columnas vacías o internas
        cols_excluir = {"auditado por", "auditado_por"}
        cols_mostrar = [c for c in df.columns if c.strip().lower() not in cols_excluir and c.strip() != ""]
        col_fecha = next((c for c in df.columns if "fecha" in c.lower()), None)
        df_show = df[cols_mostrar].sort_values(col_fecha, ascending=False) if col_fecha else df[cols_mostrar]
        st.dataframe(df_show, use_container_width=True, hide_index=True)

        # ── Gráficos ─────────────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        g1, g2 = st.columns(2)
        col_pat  = next((c for c in df.columns if "patente" in c.lower()), None)
        col_chof = next((c for c in df.columns if "chofer" in c.lower()), None)
        col_mov  = next((c for c in df.columns if "movimiento" in c.lower()), None)

        with g1:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;margin-bottom:6px;'>Por patente</div>", unsafe_allow_html=True)
            if col_pat:
                d = df[col_pat].value_counts().reset_index()
                d.columns = ["Patente","N"]
                st.bar_chart(d.set_index("Patente"), color=COL_AZUL)
            else:
                st.caption("Sin datos de patente")
        with g2:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;margin-bottom:6px;'>Por chofer</div>", unsafe_allow_html=True)
            if col_chof:
                d = df[col_chof].value_counts().reset_index()
                d.columns = ["Chofer","N"]
                st.bar_chart(d.set_index("Chofer"), color=COL_AZUL)
            else:
                st.caption("Sin datos de chofer")

        g3, g4 = st.columns(2)
        with g3:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;margin-bottom:6px;'>Salidas vs Devoluciones</div>", unsafe_allow_html=True)
            if col_mov:
                d = df[col_mov].value_counts().reset_index()
                d.columns = ["Tipo","N"]
                st.bar_chart(d.set_index("Tipo"), color=COL_CIAN)
            else:
                st.caption("Sin datos de movimiento")
        with g4:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;margin-bottom:6px;'>Estado</div>", unsafe_allow_html=True)
            d = df["Estado"].value_counts().reset_index()
            d.columns = ["Estado","N"]
            st.bar_chart(d.set_index("Estado"))

        # ── Alertas ───────────────────────────────────────────────────────────
        alertas = df[df["Estado"].isin(["No Conforme","Revision"])].tail(10)
        if not alertas.empty:
            st.markdown("---")
            st.markdown(
                "<div style='color:" + COL_AMARILLO + ";font-weight:700;margin-bottom:8px;'>"
                "⚠ Últimas diferencias detectadas</div>",
                unsafe_allow_html=True
            )
            for _, row in alertas.iterrows():
                try:
                    dv = int(float(row.get("Diferencia", 0)))
                except Exception:
                    dv = 0
                estado_r = str(row.get("Estado",""))
                badge    = "badge-alerta" if estado_r == "No Conforme" else "badge-revision"
                st.markdown(
                    "<div class='audit-row'>"
                    "<span class='audit-row-label'>" + str(row.get("N° Auditoria","")) + "</span>"
                    "<span class='audit-row-val'>" + str(row.get("Patente","")) + " · " + str(row.get("Chofer","")) + "</span>"
                    "<span style='color:#8899BB;'>" + str(row.get("Fecha","")) + " " + str(row.get("Hora","")) + "</span>"
                    "<span style='color:" + COL_AMARILLO + ";font-weight:700;'>Dif: " + f"{dv:+d}" + "</span>"
                    "<span class='" + badge + "'>" + estado_r + "</span>"
                    "</div>",
                    unsafe_allow_html=True
                )
