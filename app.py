import streamlit as st
from PIL import Image, ImageOps
import numpy as np
import cv2
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from streamlit_image_coordinates import streamlit_image_coordinates
import datetime
from zoneinfo import ZoneInfo
import io

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
SHEET_ID    = "1tVGss0qpGZwzmTpWd_jdBqIczpQyUkibwa209Gq2t7Y"
PATENTES    = ["HSFC-61","HSFC-62","LPXW-25","LPXW-87","TKXD-17","LPXW-12","THXX-18"]
CHOFERES    = ["Juan Perez","Daniel Ramirez","Hugo Diaz","Cristian Olmos",
               "Victoria Garcia","Luis Ayala","Miguel Herrera"]
TURNOS      = ["Mañana","Tarde","Noche"]
MOVIMIENTOS = ["Salida","Devolución"]
HEADERS     = ["N° Auditoria","Fecha","Hora","Turno","Patente","Chofer",
               "Tipo Movimiento","Material","Cantidad Declarada","Cantidad Contada",
               "Diferencia","Estado","Observaciones","Auditado Por"]

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

    reqs.append({"mergeCells": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                  "startColumnIndex": 0, "endColumnIndex": n_cols},
        "mergeType": "MERGE_ALL"
    }})
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
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 44}, "fields": "pixelSize"
    }})
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
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 32}, "fields": "pixelSize"
    }})
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 2}},
        "fields": "gridProperties.frozenRowCount"
    }})
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": sid, "startRowIndex": 2,
                    "startColumnIndex": 11, "endColumnIndex": 12}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Conforme"}]},
            "format": {"backgroundColor": {"red": 0.0, "green": 0.898, "blue": 0.627}}
        }
    }, "index": 0}})
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": sid, "startRowIndex": 2,
                    "startColumnIndex": 11, "endColumnIndex": 12}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "No Conforme"}]},
            "format": {"backgroundColor": {"red": 1.0, "green": 0.239, "blue": 0.353}}
        }
    }, "index": 1}})
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": sid, "startRowIndex": 2,
                    "startColumnIndex": 11, "endColumnIndex": 12}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Revision"}]},
            "format": {"backgroundColor": {"red": 1.0, "green": 0.690, "blue": 0.125}}
        }
    }, "index": 2}})
    reqs.append({"addBanding": {"bandedRange": {
        "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 1000,
                  "startColumnIndex": 0, "endColumnIndex": n_cols},
        "rowProperties": {
            "headerColor":     {"red": 0.176, "green": 0.420, "blue": 0.894},
            "firstBandColor":  {"red": 0.94, "green": 0.96, "blue": 1.0},
            "secondBandColor": {"red": 1.0,  "green": 1.0,  "blue": 1.0},
        }
    }}})
    anchos = [110,100,75,80,90,130,120,110,120,120,85,110,160,130]
    for i, w in enumerate(anchos):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i+1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"
        }})

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
        ws.update("A1", [["🏗️ ARMATEC · AUDITORÍA DE ANDAMIOS"]])
        ws.append_row(HEADERS)
        if sheets_service:
            try:
                formato_sheets(ws, sheets_service)
            except Exception:
                pass
    return ws

def get_next_audit_number(ws):
    data = ws.get_all_values()
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
    ])

def cargar_historial(gc):
    ws     = get_sheet(gc)
    values = ws.get_all_values()
    if len(values) <= 2:
        return []
    headers = values[1]
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

def dibujar_puntos(img_pil, puntos, tipo="vertical"):
    img    = np.array(img_pil)
    ih, iw = img.shape[:2]
    radio  = max(10, min(iw, ih) // 28)
    fuente = cv2.FONT_HERSHEY_SIMPLEX
    escala = max(0.4, radio / 22)
    grosor = max(1, radio // 9)
    for i, (x, y) in enumerate(puntos, 1):
        txt = str(i)
        tw, th = cv2.getTextSize(txt, fuente, escala, grosor)[0]
        tx, ty = x - tw // 2, y + th // 2
        if tipo == "vertical":
            cv2.line(img, (x-radio,y), (x+radio,y), (0,0,0),    max(2,radio//5))
            cv2.line(img, (x,y-radio), (x,y+radio), (0,0,0),    max(2,radio//5))
            cv2.putText(img, txt, (tx-1,ty+1), fuente, escala, (255,255,255), grosor+2, cv2.LINE_AA)
            cv2.putText(img, txt, (tx,ty),     fuente, escala, (0,0,255),     grosor,   cv2.LINE_AA)
        else:
            cv2.circle(img, (x,y), radio, (0,0,220), max(2,radio//5))
            cv2.putText(img, txt, (tx-1,ty+1), fuente, escala, (0,0,0),      grosor+2, cv2.LINE_AA)
            cv2.putText(img, txt, (tx,ty),     fuente, escala, (255,255,255), grosor,   cv2.LINE_AA)
    return Image.fromarray(img)

# ─── FRAGMENT: CONTEO ─────────────────────────────────────────────────────────
@st.fragment
def contar_material(tipo):
    key_p  = "puntos_v"  if tipo == "vertical" else "puntos_h"
    key_m  = "mapa_v"    if tipo == "vertical" else "mapa_h"
    key_d  = "decl_v"    if tipo == "vertical" else "decl_h"
    label  = "Verticales" if tipo == "vertical" else "Horizontales"
    desc   = "tubo vertical → cruz negra + número rojo" if tipo == "vertical" \
             else "horizontal/cabezal → círculo rojo + número blanco"

    # ── Contador arriba ──────────────────────────────────────────────────────
    total = len(st.session_state[key_p])
    st.markdown(
        "<div class='metric-card'>"
        "<div class='metric-label'>" + label + " marcados</div>"
        "<div class='metric-value'>" + str(total) + "</div>"
        "</div>",
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)
    if c1.button("↩ Deshacer", key="undo_" + tipo[0]):
        if st.session_state[key_p]:
            st.session_state[key_p].pop()
    if c2.button("🗑 Limpiar todo", key="clear_" + tipo[0]):
        st.session_state[key_p] = []

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

    st.markdown(
        "<p style='color:#8899BB;font-size:0.82rem;margin:10px 0 4px 0;'>"
        "Toca cada " + desc + ".</p>",
        unsafe_allow_html=True
    )

    # ── Imagen abajo (sin salto de pantalla al tocar) ─────────────────────────
    img_anotada = dibujar_puntos(
        st.session_state["img_orig"], st.session_state[key_p], tipo
    )
    coord = streamlit_image_coordinates(img_anotada, key=key_m + "_" + str(len(st.session_state[key_p])))

    # Registrar tap
    if coord:
        x, y = int(coord["x"]), int(coord["y"])
        if not st.session_state[key_p] or st.session_state[key_p][-1] != (x, y):
            st.session_state[key_p].append((x, y))
            st.rerun()

# ─── SESSION STATE ────────────────────────────────────────────────────────────
for k, v in {
    "puntos_v": [], "puntos_h": [], "img_orig": None, "guardado": False,
    "s_patente": PATENTES[0], "s_chofer": CHOFERES[0], "s_turno": TURNOS[0],
    "s_tipo_mov": MOVIMIENTOS[0], "s_observaciones": "", "upload_counter": 0,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── HEADER ───────────────────────────────────────────────────────────────────
st.markdown("""
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
                                help="Salida: lleva material · Devolución: retorna material")
        observaciones = c5.text_input("Observaciones", placeholder="Daños, faltantes, notas...")

    st.session_state["s_patente"]       = patente
    st.session_state["s_chofer"]        = chofer
    st.session_state["s_turno"]         = turno
    st.session_state["s_tipo_mov"]      = tipo_mov
    st.session_state["s_observaciones"] = observaciones

    st.markdown("---")
    st.markdown(
        "<span style='color:" + COL_CIAN + ";font-weight:700;'>📷 Cargar imagen del camión</span>",
        unsafe_allow_html=True
    )

    archivo = st.file_uploader(
        "📁 Selecciona la foto del camión desde tu galería",
        type=["jpg","jpeg","png","webp"],
        key="uploader_" + str(st.session_state.get("upload_counter", 0))
    )

    if st.session_state["img_orig"] is None:
        fuente = archivo if archivo else None
        if fuente:
            try:
                img_nueva = cargar_imagen(fuente)
                st.session_state.update({
                    "img_orig":  img_nueva,
                    "puntos_v":  [],
                    "puntos_h":  [],
                    "guardado":  False,
                })
            except Exception as e:
                st.error("No se pudo cargar la imagen: " + str(e))

    if st.session_state["img_orig"]:

        tab_v, tab_h = st.tabs(["🔵  Verticales", "🔴  Horizontales / Cabezales"])

        with tab_v:
            contar_material("vertical")

        with tab_h:
            contar_material("horizontal")

        st.markdown("---")
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
        btn_guardar = c2.button(
            "✅ Guardar en Sheets",
            type="primary",
            disabled=st.session_state["guardado"]
        )

        if btn_guardar and not st.session_state["guardado"]:
            with st.spinner("Guardando en Google Sheets..."):
                try:
                    gc, sheets = get_clients()
                    diff = total_contado - cant_decl_total
                    if cant_decl_total == 0:  estado = "Sin declarar"
                    elif diff == 0:            estado = "Conforme"
                    elif abs(diff) <= 2:       estado = "Revision"
                    else:                      estado = "No Conforme"

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
                        "auditado_por":   "Richard Romero",
                    })

                    st.session_state["guardado"] = True
                    st.success(
                        "✅ Auditoría **" + n_aud + "** guardada · Estado: **" + estado + "**"
                    )
                except Exception as e:
                    st.error("Error al guardar: " + str(e))

        if st.session_state["guardado"]:
            if st.button("🔄 Nueva auditoría"):
                st.session_state.update({
                    "puntos_v": [], "puntos_h": [],
                    "img_orig": None, "guardado": False,
                    "upload_counter": st.session_state.get("upload_counter", 0) + 1,
                })
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:

    st.markdown(
        "<span style='color:" + COL_CIAN + ";font-weight:700;font-size:1rem;'>"
        "📊 Resumen de auditorías</span>",
        unsafe_allow_html=True
    )

    try:
        gc, _ = get_clients()
        historial = cargar_historial(gc)
    except Exception as e:
        st.error("No se pudo cargar el historial: " + str(e))
        historial = []

    if not historial:
        st.info("Aún no hay registros. Guarda una auditoría para verla aquí.")
    else:
        import pandas as pd
        df = pd.DataFrame(historial)
        for col in ["Cantidad Declarada","Cantidad Contada","Diferencia"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        if "Estado" not in df.columns:
            df["Estado"] = ""

        total_aud  = len(df)
        conformes  = len(df[df["Estado"] == "Conforme"])
        no_conf    = len(df[df["Estado"] == "No Conforme"])
        revisiones = len(df[df["Estado"] == "Revision"])
        pct        = round(conformes / total_aud * 100) if total_aud else 0

        k1,k2,k3,k4,k5 = st.columns(5)
        for col, label, value, sub in [
            (k1,"Total auditorías", total_aud,  "registros"),
            (k2,"Conformes",        conformes,  str(pct)+"%"),
            (k3,"No Conformes",     no_conf,    "con diferencia"),
            (k4,"En Revisión",      revisiones, "±1-2 unid."),
            (k5,"Tasa conformidad", str(pct)+"%","del total"),
        ]:
            col.markdown(
                "<div class='metric-card'>"
                "<div class='metric-label'>" + label + "</div>"
                "<div class='metric-value'>" + str(value) + "</div>"
                "<div class='metric-sub'>" + sub + "</div></div>",
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        g1, g2 = st.columns(2)
        with g1:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;margin-bottom:6px;'>Auditorías por patente</div>", unsafe_allow_html=True)
            if "Patente" in df.columns:
                d = df["Patente"].value_counts().reset_index()
                d.columns = ["Patente","N"]
                st.bar_chart(d.set_index("Patente"), color=COL_AZUL)
        with g2:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;margin-bottom:6px;'>Salidas vs Devoluciones</div>", unsafe_allow_html=True)
            if "Tipo Movimiento" in df.columns:
                d = df["Tipo Movimiento"].value_counts().reset_index()
                d.columns = ["Tipo","N"]
                st.bar_chart(d.set_index("Tipo"), color=COL_CIAN)

        g3, g4 = st.columns(2)
        with g3:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;margin-bottom:6px;'>Auditorías por chofer</div>", unsafe_allow_html=True)
            if "Chofer" in df.columns:
                d = df["Chofer"].value_counts().reset_index()
                d.columns = ["Chofer","N"]
                st.bar_chart(d.set_index("Chofer"), color=COL_AZUL)
        with g4:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;margin-bottom:6px;'>Estado de auditorías</div>", unsafe_allow_html=True)
            if "Estado" in df.columns:
                d = df["Estado"].value_counts().reset_index()
                d.columns = ["Estado","N"]
                st.bar_chart(d.set_index("Estado"))

        st.markdown("---")
        st.markdown(
            "<div style='color:" + COL_AMARILLO + ";font-weight:700;margin-bottom:8px;'>"
            "⚠ Últimas diferencias detectadas</div>",
            unsafe_allow_html=True
        )
        if "Estado" in df.columns:
            alertas = df[df["Estado"].isin(["No Conforme","Revision"])].tail(10)
            if alertas.empty:
                st.success("Sin alertas recientes.")
            else:
                for _, row in alertas.iterrows():
                    dv       = int(row.get("Diferencia", 0))
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

        st.markdown("---")
        with st.expander("📋 Historial completo"):
            cols_show = [c for c in [
                "N° Auditoria","Fecha","Turno","Patente","Chofer",
                "Tipo Movimiento","Cantidad Declarada","Cantidad Contada",
                "Diferencia","Estado","Observaciones"
            ] if c in df.columns]
            st.dataframe(df[cols_show], use_container_width=True, hide_index=True)
