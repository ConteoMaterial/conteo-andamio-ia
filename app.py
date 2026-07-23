import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps, ImageDraw, ImageFont
import gspread
import requests as _requests
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
               "Tablones","Bases/Niveladores","Abrazaderas",
               "Foto V","Foto H"]

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
    pk = creds_dict.get("private_key", "")
    pk = pk.replace("\\n", "\n")
    creds_dict = dict(creds_dict)
    creds_dict["private_key"] = pk
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    gc = gspread.service_account_from_dict(creds_dict, scopes=scope)
    return gc, None

# ─── SUPABASE STORAGE (fotos de auditoría) ────────────────────────────────────
SUPA_BUCKET = "AuditoriaFotos"

def foto_con_puntos(img_pil, puntos, tipo):
    """Devuelve una copia de la foto con los puntos del conteo dibujados."""
    img = img_pil.copy()
    draw = ImageDraw.Draw(img)
    color = "#2D6BE4" if tipo == "vertical" else "#FF3D5A"
    r = max(9, int(min(img.size) * 0.022))
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(r * 1.2))
    except Exception:
        font = ImageFont.load_default()
    for i, p in enumerate(puntos):
        x, y = int(p[0]), int(p[1])
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color, outline="white", width=2)
        num = str(i + 1)
        try:
            bb = draw.textbbox((0, 0), num, font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            draw.text((x - tw / 2, y - th / 2 - bb[1]), num, fill="white", font=font)
        except Exception:
            draw.text((x - 4, y - 6), num, fill="white")
    # Banda inferior con el total
    total = str(len(puntos))
    etiqueta = ("VERTICALES: " if tipo == "vertical" else "HORIZONTALES: ") + total
    band_h = max(26, int(img.size[1] * 0.055))
    nueva = Image.new("RGB", (img.size[0], img.size[1] + band_h), "#0A0A0F")
    nueva.paste(img, (0, 0))
    d2 = ImageDraw.Draw(nueva)
    try:
        f2 = ImageFont.truetype("DejaVuSans-Bold.ttf", int(band_h * 0.55))
    except Exception:
        f2 = ImageFont.load_default()
    d2.text((10, img.size[1] + int(band_h * 0.2)), etiqueta, fill="#00D4FF", font=f2)
    return nueva

def subir_foto_supabase(img_pil, nombre_archivo):
    """Sube la foto. Devuelve (url, error). Si error != "" la subida falló."""
    try:
        buf = io.BytesIO()
        img_pil.save(buf, format="JPEG", quality=85)
        supa_url = st.secrets["supabase"]["url"].rstrip("/")
        supa_key = st.secrets["supabase"]["key"].strip()
        if any(ord(ch) > 127 for ch in supa_key):
            return "", ("La clave de Supabase guardada en los secretos de Streamlit "
                        "está CORRUPTA (contiene caracteres inválidos como '•'). "
                        "Vuelve a pegar la clave anon completa en Settings → Secrets.")
        upload_url = supa_url + "/storage/v1/object/" + SUPA_BUCKET + "/" + nombre_archivo
        resp = _requests.post(
            upload_url,
            data=buf.getvalue(),
            headers={
                "Authorization": "Bearer " + supa_key,
                "Content-Type":  "image/jpeg",
                "x-upsert":      "true",
            },
            timeout=20,
        )
        if resp.status_code in (200, 201):
            return supa_url + "/storage/v1/object/public/" + SUPA_BUCKET + "/" + nombre_archivo, ""
        return "", "HTTP " + str(resp.status_code) + ": " + resp.text[:200]
    except KeyError as e:
        return "", "Falta el secreto de Supabase en Streamlit: " + str(e)
    except Exception as e:
        return "", repr(e)

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
    # Busca el número AUD más alto ya usado (no depende de la posición de filas)
    data = ws.get_all_values()
    max_n = 0
    for row in data:
        if row and row[0].strip().upper().startswith("AUD-"):
            try:
                n = int(row[0].strip().split("-")[1])
                max_n = max(max_n, n)
            except (ValueError, IndexError):
                pass
    return "AUD-" + str(max_n + 1).zfill(4)

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
        registro.get("foto_v", ""), registro.get("foto_h", ""),
    ])

def cargar_historial(gc):
    ws     = get_sheet(gc)
    values = ws.get_all_values()
    if not values:
        return []
    # Detectar automáticamente la fila de encabezados (busca "Patente" y "Chofer")
    hdr_idx = None
    for i, row in enumerate(values[:6]):
        joined = " ".join(row).lower()
        if "patente" in joined and "chofer" in joined:
            hdr_idx = i
            break
    if hdr_idx is None:
        # Fallback: si las filas de datos empiezan con AUD-, usar HEADERS fijos
        records = []
        for row in values:
            if row and row[0].strip().upper().startswith("AUD-"):
                row_p = row + [""] * (len(HEADERS) - len(row))
                records.append(dict(zip(HEADERS, row_p)))
        return records
    headers = [h.strip() for h in values[hdr_idx]]
    records = []
    for row in values[hdr_idx + 1:]:
        if not any(cell.strip() for cell in row):
            continue
        row_p = row + [""] * (len(headers) - len(row))
        records.append(dict(zip(headers, row_p)))
    return records

@st.cache_data(ttl=120, show_spinner=False)
def cargar_historial_cache():
    """Lee el historial máximo una vez cada 2 min para no agotar la cuota de Google."""
    gc, _ = get_clients()
    return cargar_historial(gc)

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
    "guardado": False, "foto_warn": "",
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
    if col_r.button("🔃 Recargar"):
        components.html(
            "<script>window.parent.location.reload();</script>",
            height=0
        )

    # ── Pantalla post-guardado ────────────────────────────────────────────────
    if st.session_state["guardado"]:
        n_id  = st.session_state.get("last_audit_id", "")
        n_est = st.session_state.get("last_audit_estado", "")
        st.markdown("<br>", unsafe_allow_html=True)
        st.success("✅ Auditoría **" + n_id + "** guardada · Estado: **" + n_est + "**")
        _fw = st.session_state.get("foto_warn", "")
        if _fw:
            st.warning("⚠️ El registro se guardó, pero las fotos NO se subieron:\n\n" + _fw)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Nueva auditoría", type="primary", use_container_width=True):
            _reset = {
                "puntos_v": [], "puntos_h": [],
                "img_orig_v": None, "img_b64_v": None,
                "img_orig_h": None, "img_b64_h": None,
                "guardado": False, "foto_warn": "",
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
            _ok = False
            _err = ""
            with st.spinner("Guardando registro y subiendo fotos..."):
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
                    ts    = ahora.strftime("%Y%m%d_%H%M%S")

                    foto_v_url = ""
                    foto_h_url = ""
                    foto_errs  = []
                    if st.session_state.get("img_orig_v") is not None:
                        img_v = foto_con_puntos(
                            st.session_state["img_orig_v"],
                            st.session_state.get("puntos_v", []),
                            "vertical"
                        )
                        foto_v_url, err_v = subir_foto_supabase(
                            img_v, n_aud + "_V_" + ts + ".jpg"
                        )
                        if err_v:
                            foto_errs.append("Foto V: " + err_v)
                    if st.session_state.get("img_orig_h") is not None:
                        img_h = foto_con_puntos(
                            st.session_state["img_orig_h"],
                            st.session_state.get("puntos_h", []),
                            "horizontal"
                        )
                        foto_h_url, err_h = subir_foto_supabase(
                            img_h, n_aud + "_H_" + ts + ".jpg"
                        )
                        if err_h:
                            foto_errs.append("Foto H: " + err_h)
                    st.session_state["foto_warn"] = " | ".join(foto_errs)

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
                        "foto_v":         foto_v_url,
                        "foto_h":         foto_h_url,
                        **{k: st.session_state.get("sec_" + k, 0) for _, k in MATERIALES_SEC},
                    })

                    st.session_state["guardado"]          = True
                    st.session_state["last_audit_id"]     = n_aud
                    st.session_state["last_audit_estado"] = estado
                    cargar_historial_cache.clear()
                    _ok = True
                except Exception as e:
                    _err = repr(e)

            if _ok:
                st.rerun()
            elif _err:
                st.error("Error al guardar: " + _err)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    import pandas as pd
    import re as _re

    col_act, _ = st.columns([1, 5])
    if col_act.button("🔄 Actualizar datos", use_container_width=True):
        cargar_historial_cache.clear()
        st.rerun()

    # ── Cargar historial (con caché para no agotar cuota de Google) ──────────
    try:
        historial = cargar_historial_cache()
    except Exception as e:
        st.error("No se pudo cargar el historial: " + str(e))
        historial = []

    if not historial:
        st.info("Aún no hay registros. Guarda una auditoría para verla aquí.")
    else:
        df = pd.DataFrame(historial)
        df.columns = [c.strip() for c in df.columns]

        def _fc(df, *names):
            low = {c.strip().lower(): c for c in df.columns}
            for name in names:
                n = name.strip().lower()
                if n in low:
                    return low[n]
            for name in names:
                n = name.strip().lower()
                for k, v in low.items():
                    if n in k:
                        return v
            return None

        def _v(row, col):
            if not col or col not in row.index:
                return "—"
            v = str(row[col])
            return v if v not in ("nan", "None", "") else "—"

        def _int(row, col):
            try:
                return int(float(_v(row, col).replace("—", "0")))
            except Exception:
                return 0

        col_n    = _fc(df, "N° Auditoria", "auditoria", "n auditoria")
        col_f    = _fc(df, "Fecha")
        col_h    = _fc(df, "Hora")
        col_t    = _fc(df, "Turno")
        col_pat  = _fc(df, "Patente")
        col_chof = _fc(df, "Chofer")
        col_mov  = _fc(df, "Tipo Movimiento", "Movimiento")
        col_mat  = _fc(df, "Material")
        col_cd   = _fc(df, "Cantidad Declarada", "Declarada")
        col_cc   = _fc(df, "Cantidad Contada", "Contada")
        col_dif  = _fc(df, "Diferencia")
        col_est  = _fc(df, "Estado")
        col_obs  = _fc(df, "Observaciones")
        col_aud  = _fc(df, "Auditado Por", "Auditado")
        col_diag = _fc(df, "Diagonales")
        col_am30 = _fc(df, "Amarras 3.0m", "Amarras 3")
        col_am15 = _fc(df, "Amarras 1.5m", "Amarras 1")
        col_plat = _fc(df, "Plataformas")
        col_tabl = _fc(df, "Tablones")
        col_base = _fc(df, "Bases", "Niveladores")
        col_abra = _fc(df, "Abrazaderas")
        col_fotov = _fc(df, "Foto V", "Foto Verticales")
        col_fotoh = _fc(df, "Foto H", "Foto Horizontales")

        for c in [col_cd, col_cc, col_dif, col_diag, col_am30, col_am15,
                  col_plat, col_tabl, col_base, col_abra]:
            if c:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

        df["_est"] = df[col_est].astype(str).str.strip() if col_est else "Sin declarar"

        # ── Filtros ───────────────────────────────────────────────────────────
        with st.expander("🔍 Filtros", expanded=False):
            fc1, fc2, fc3 = st.columns(3)
            opts_pat = ["Todas"] + sorted(df[col_pat].dropna().unique().tolist()) if col_pat else ["Todas"]
            opts_mov = ["Todos"] + sorted(df[col_mov].dropna().unique().tolist()) if col_mov else ["Todos"]
            f_pat = fc1.selectbox("Patente", opts_pat)
            f_est = fc2.selectbox("Estado", ["Todos", "Conforme", "No Conforme", "Revision", "Sin declarar"])
            f_mov = fc3.selectbox("Movimiento", opts_mov)

        df_f = df.copy()
        if f_pat != "Todas" and col_pat:
            df_f = df_f[df_f[col_pat] == f_pat]
        if f_est != "Todos":
            df_f = df_f[df_f["_est"] == f_est]
        if f_mov != "Todos" and col_mov:
            df_f = df_f[df_f[col_mov] == f_mov]

        df_sorted = df_f.sort_values([col_f, col_h], ascending=False) if col_f and col_h else df_f

        # ── KPIs ─────────────────────────────────────────────────────────────
        total_aud  = len(df_f)
        conformes  = len(df_f[df_f["_est"] == "Conforme"])
        no_conf    = len(df_f[df_f["_est"] == "No Conforme"])
        revisiones = len(df_f[df_f["_est"] == "Revision"])
        sin_decl   = len(df_f[df_f["_est"] == "Sin declarar"])
        pct        = round(conformes / total_aud * 100) if total_aud else 0

        k1, k2, k3, k4, k5 = st.columns(5)
        for _col, label, value, sub in [
            (k1, "Total",        total_aud,  "auditorías"),
            (k2, "Conformes",    conformes,  str(pct) + "%"),
            (k3, "No Conformes", no_conf,    "diferencia"),
            (k4, "En Revisión",  revisiones, "±1-2 unid."),
            (k5, "Sin declarar", sin_decl,   "sin cantidad"),
        ]:
            _col.markdown(
                f"<div class='metric-card'><div class='metric-label'>{label}</div>"
                f"<div class='metric-value'>{value}</div>"
                f"<div class='metric-sub'>{sub}</div></div>",
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Selector de auditoría ─────────────────────────────────────────────
        st.markdown(
            f"<div style='color:{COL_CIAN};font-weight:700;font-size:1rem;margin-bottom:8px;'>"
            "🔍 Selecciona una auditoría para ver el detalle completo</div>",
            unsafe_allow_html=True
        )

        def _lbl(row):
            parts = [
                _v(row, col_n),
                _v(row, col_f),
                _v(row, col_h)[:5] if col_h else "—",
                _v(row, col_pat),
                _v(row, col_chof),
                "[" + _v(row, col_est) + "]",
            ]
            return "  ·  ".join(parts)

        PLACEHOLDER = "— Selecciona una auditoría de la lista —"
        opciones = [PLACEHOLDER] + [_lbl(row) for _, row in df_sorted.iterrows()]
        sel = st.selectbox("Auditoría:", opciones, label_visibility="collapsed")

        if sel and sel != PLACEHOLDER:
            i   = opciones.index(sel) - 1
            row = df_sorted.iloc[i]

            # Estado → color y CSS
            estado = _v(row, col_est)
            if estado == "Conforme":
                est_css = f"background:{COL_VERDE}22;color:{COL_VERDE};border:1px solid {COL_VERDE}66;"
            elif estado == "No Conforme":
                est_css = f"background:{COL_ROJO}22;color:{COL_ROJO};border:1px solid {COL_ROJO}66;"
            elif estado == "Revision":
                est_css = f"background:{COL_AMARILLO}22;color:{COL_AMARILLO};border:1px solid {COL_AMARILLO}66;"
            else:
                est_css = f"background:{COL_PIZARRA}22;color:#8899BB;border:1px solid {COL_PIZARRA}66;"

            # ── Cabecera del detalle ──────────────────────────────────────────
            _campos = [
                ("Fecha",       _v(row, col_f)),
                ("Hora",        _v(row, col_h)),
                ("Turno",       _v(row, col_t)),
                ("Patente",     _v(row, col_pat)),
                ("Chofer",      _v(row, col_chof)),
                ("Movimiento",  _v(row, col_mov)),
                ("Auditado por",_v(row, col_aud)),
            ]
            _campos_html = "".join(
                f"<div style='min-width:110px;'>"
                f"<div style='font-size:0.68rem;color:#5A6B85;text-transform:uppercase;letter-spacing:0.05em;'>{lbl_c}</div>"
                f"<div style='font-size:0.9rem;font-weight:600;color:#C8D4E8;'>{val_c}</div>"
                f"</div>"
                for lbl_c, val_c in _campos
            )
            st.markdown(
                f"<div style='background:{COL_CARBONO};border:1px solid {COL_AZUL}44;"
                f"border-radius:12px;padding:16px 20px;margin:10px 0 14px 0;'>"
                f"<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;'>"
                f"<div style='font-size:1.5rem;font-weight:800;color:{COL_CIAN};'>{_v(row, col_n)}</div>"
                f"<div style='font-size:0.85rem;font-weight:700;padding:5px 18px;border-radius:20px;{est_css}'>{estado}</div>"
                f"</div>"
                f"<div style='display:flex;gap:14px;flex-wrap:wrap;'>"
                f"{_campos_html}"
                f"</div></div>",
                unsafe_allow_html=True
            )

            # ── Conteo V / H / totales ────────────────────────────────────────
            mat_str = _v(row, col_mat)
            mv = _re.search(r'[Vv][:\s·]+(\d+)', mat_str)
            mh = _re.search(r'[Hh][:\s·]+(\d+)', mat_str)
            v_cnt = int(mv.group(1)) if mv else 0
            h_cnt = int(mh.group(1)) if mh else 0

            diff_val = _v(row, col_dif)
            try:
                diff_int = int(diff_val)
                diff_color = COL_VERDE if diff_int == 0 else (COL_AMARILLO if abs(diff_int) <= 2 else COL_ROJO)
            except Exception:
                diff_int  = 0
                diff_color = "#8899BB"

            dc1, dc2, dc3, dc4, dc5 = st.columns(5)
            dc1.markdown(
                f"<div class='metric-card'><div class='metric-label'>🔵 Verticales</div>"
                f"<div class='metric-value' style='color:{COL_AZUL};'>{v_cnt}</div>"
                f"<div class='metric-sub'>contados</div></div>",
                unsafe_allow_html=True
            )
            dc2.markdown(
                f"<div class='metric-card'><div class='metric-label'>🔴 Horizontales</div>"
                f"<div class='metric-value' style='color:{COL_ROJO};'>{h_cnt}</div>"
                f"<div class='metric-sub'>contados</div></div>",
                unsafe_allow_html=True
            )
            dc3.markdown(
                f"<div class='metric-card'><div class='metric-label'>📦 Total contado</div>"
                f"<div class='metric-value' style='color:{COL_CIAN};'>{_v(row, col_cc)}</div>"
                f"<div class='metric-sub'>V + H</div></div>",
                unsafe_allow_html=True
            )
            dc4.markdown(
                f"<div class='metric-card'><div class='metric-label'>📋 Declarado</div>"
                f"<div class='metric-value'>{_v(row, col_cd)}</div>"
                f"<div class='metric-sub'>por chofer</div></div>",
                unsafe_allow_html=True
            )
            dc5.markdown(
                f"<div class='metric-card'><div class='metric-label'>⚖ Diferencia</div>"
                f"<div class='metric-value' style='color:{diff_color};'>"
                f"{('+' if diff_int > 0 else '') + str(diff_int) if diff_val != '—' else '—'}</div>"
                f"<div class='metric-sub'>{'✓ exacto' if diff_int == 0 and diff_val != '—' else ''}</div></div>",
                unsafe_allow_html=True
            )

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Accesorios ────────────────────────────────────────────────────
            st.markdown(
                f"<div style='color:{COL_CIAN};font-weight:700;margin-bottom:10px;'>🔩 Accesorios registrados</div>",
                unsafe_allow_html=True
            )
            acc_def = [
                ("Diagonales",        col_diag, COL_AZUL),
                ("Amarras 3.0m",      col_am30, COL_ROJO),
                ("Amarras 1.5m",      col_am15, COL_AMARILLO),
                ("Plataformas",       col_plat, COL_VERDE),
                ("Tablones",          col_tabl, "#A78BFA"),
                ("Bases/Niveladores", col_base, COL_CIAN),
                ("Abrazaderas",       col_abra, "#F97316"),
            ]
            acc_cols = st.columns(7)
            hay_acc = False
            for idx_a, (lbl_a, col_a, color_a) in enumerate(acc_def):
                v_int = _int(row, col_a)
                if v_int > 0:
                    hay_acc = True
                acc_cols[idx_a].markdown(
                    f"<div class='metric-card'>"
                    f"<div class='metric-label' style='font-size:0.68rem;'>{lbl_a}</div>"
                    f"<div class='metric-value' style='color:{color_a if v_int > 0 else '#3D4E66'};font-size:1.7rem;'>{v_int}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            if not hay_acc:
                st.caption("Sin accesorios en esta auditoría — todos en cero.")

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Fotografías ───────────────────────────────────────────────────
            st.markdown(
                f"<div style='color:{COL_CIAN};font-weight:700;margin-bottom:10px;'>📷 Fotografías del registro</div>",
                unsafe_allow_html=True
            )
            url_v = _v(row, col_fotov)
            url_h = _v(row, col_fotoh)
            cf1, cf2 = st.columns(2)
            with cf1:
                if url_v not in ("—", "") and url_v.startswith("http"):
                    st.image(url_v, caption="📷 Verticales", use_container_width=True)
                else:
                    st.markdown(
                        f"<div style='background:{COL_CARBONO};border:2px dashed {COL_AZUL}33;"
                        f"border-radius:10px;height:180px;display:flex;align-items:center;"
                        f"justify-content:center;color:#475569;font-size:0.85rem;'>"
                        f"📷 Sin foto de Verticales</div>",
                        unsafe_allow_html=True
                    )
                st.caption("Foto Verticales")
            with cf2:
                if url_h not in ("—", "") and url_h.startswith("http"):
                    st.image(url_h, caption="📷 Horizontales", use_container_width=True)
                else:
                    st.markdown(
                        f"<div style='background:{COL_CARBONO};border:2px dashed {COL_AZUL}33;"
                        f"border-radius:10px;height:180px;display:flex;align-items:center;"
                        f"justify-content:center;color:#475569;font-size:0.85rem;'>"
                        f"📷 Sin foto de Horizontales</div>",
                        unsafe_allow_html=True
                    )
                st.caption("Foto Horizontales")

            # ── Observaciones ─────────────────────────────────────────────────
            obs = _v(row, col_obs)
            if obs not in ("—", ""):
                st.markdown("<br>", unsafe_allow_html=True)
                st.info("📝 **Observaciones:** " + obs)

        st.markdown("---")

        # ── Tabla completa ────────────────────────────────────────────────────
        st.markdown(
            f"<div style='color:{COL_CIAN};font-weight:700;margin-bottom:8px;'>📋 Todos los registros</div>",
            unsafe_allow_html=True
        )
        cols_ocultar = {c for c in [col_aud, col_diag, col_am30, col_am15,
                                     col_plat, col_tabl, col_base, col_abra,
                                     col_fotov, col_fotoh] if c}
        cols_mostrar = [c for c in df_f.columns if c not in cols_ocultar and not c.startswith("_")]
        st.dataframe(
            df_sorted[cols_mostrar],
            use_container_width=True, hide_index=True
        )

        # ── Gráficos ─────────────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        g1, g2 = st.columns(2)

        with g1:
            st.markdown(
                f"<div style='color:{COL_CIAN};font-weight:600;margin-bottom:6px;'>Estado de auditorías</div>",
                unsafe_allow_html=True
            )
            d = df_f["_est"].value_counts().reset_index()
            d.columns = ["Estado", "N"]
            st.bar_chart(d.set_index("Estado"))

        with g2:
            st.markdown(
                f"<div style='color:{COL_CIAN};font-weight:600;margin-bottom:6px;'>Salidas vs Devoluciones</div>",
                unsafe_allow_html=True
            )
            if col_mov:
                d = df_f[col_mov].value_counts().reset_index()
                d.columns = ["Tipo", "N"]
                st.bar_chart(d.set_index("Tipo"), color=COL_CIAN)
            else:
                st.caption("Sin datos de movimiento")

        g3, g4 = st.columns(2)
        with g3:
            st.markdown(
                f"<div style='color:{COL_CIAN};font-weight:600;margin-bottom:6px;'>Auditorías por patente</div>",
                unsafe_allow_html=True
            )
            if col_pat:
                d = df_f[col_pat].value_counts().reset_index()
                d.columns = ["Patente", "N"]
                st.bar_chart(d.set_index("Patente"), color=COL_AZUL)
            else:
                st.caption("Sin datos de patente")

        with g4:
            st.markdown(
                f"<div style='color:{COL_CIAN};font-weight:600;margin-bottom:6px;'>Auditorías por chofer</div>",
                unsafe_allow_html=True
            )
            if col_chof:
                d = df_f[col_chof].value_counts().reset_index()
                d.columns = ["Chofer", "N"]
                st.bar_chart(d.set_index("Chofer"), color=COL_AZUL)
            else:
                st.caption("Sin datos de chofer")

        # ── Alertas ───────────────────────────────────────────────────────────
        alertas = df_f[df_f["_est"].isin(["No Conforme", "Revision"])].tail(10)
        if not alertas.empty:
            st.markdown("---")
            st.markdown(
                f"<div style='color:{COL_AMARILLO};font-weight:700;margin-bottom:8px;'>⚠ Últimas diferencias detectadas</div>",
                unsafe_allow_html=True
            )
            for _, row in alertas.iterrows():
                dv = _int(row, col_dif)
                estado_r = _v(row, col_est)
                badge = "badge-alerta" if estado_r == "No Conforme" else "badge-revision"
                st.markdown(
                    f"<div class='audit-row'>"
                    f"<span class='audit-row-label'>{_v(row, col_n)}</span>"
                    f"<span class='audit-row-val'>{_v(row, col_pat)} · {_v(row, col_chof)}</span>"
                    f"<span style='color:#8899BB;'>{_v(row, col_f)} {_v(row, col_h)}</span>"
                    f"<span style='color:{COL_AMARILLO};font-weight:700;'>Dif: {dv:+d}</span>"
                    f"<span class='{badge}'>{estado_r}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
