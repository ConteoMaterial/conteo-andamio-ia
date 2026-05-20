import streamlit as st
from PIL import Image, ImageOps
import numpy as np
import cv2
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from streamlit_image_coordinates import streamlit_image_coordinates
import datetime
import io

SHEET_ID        = "1tVGss0qpGZwzmTpWd_jdBqIczpQyUkibwa209Gq2t7Y"
DRIVE_FOLDER_ID = "1njn6Hp3qoaw3kYqkErseReHhA7mrvPjA"

PATENTES    = ["HSFC-61","HSFC-62","LPXW-25","LPXW-87","TKXD-17","LPXW-12","THXX-18"]
CHOFERES    = ["Juan Perez","Daniel Ramirez","Hugo Diaz","Cristian Olmos",
               "Victoria Garcia","Luis Ayala","Miguel Herrera"]
TURNOS      = ["Mañana","Tarde","Noche"]
MOVIMIENTOS = ["Salida","Devolución"]

COL_NEGRO    = "#0A0A0F"
COL_AZUL     = "#2D6BE4"
COL_CIAN     = "#00D4FF"
COL_PIZARRA  = "#2E3A4E"
COL_CARBONO  = "#1E2A3A"
COL_VERDE    = "#00E5A0"
COL_ROJO     = "#FF3D5A"
COL_AMARILLO = "#FFB020"

st.set_page_config(page_title="ARMATEC · Auditoría Andamios", layout="wide", page_icon="🏗️")

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
    border-radius: 12px; padding: 18px 22px; text-align: center;
  }}
  .metric-label {{ font-size:0.72rem; color:#8899BB; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px; }}
  .metric-value {{ font-size:2rem; font-weight:700; color:{COL_CIAN}; }}
  .metric-sub   {{ font-size:0.78rem; color:#8899BB; margin-top:4px; }}
  .badge-conforme {{ background:{COL_VERDE}22; color:{COL_VERDE}; border:1px solid {COL_VERDE}66; border-radius:20px; padding:2px 12px; font-size:0.78rem; font-weight:600; }}
  .badge-alerta   {{ background:{COL_ROJO}22;  color:{COL_ROJO};  border:1px solid {COL_ROJO}66;  border-radius:20px; padding:2px 12px; font-size:0.78rem; font-weight:600; }}
  .badge-revision {{ background:{COL_AMARILLO}22; color:{COL_AMARILLO}; border:1px solid {COL_AMARILLO}66; border-radius:20px; padding:2px 12px; font-size:0.78rem; font-weight:600; }}
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
    display: flex; align-items: center; gap: 12px; font-size: 0.82rem;
  }}
  .audit-row-label {{ color: #8899BB; min-width: 90px; }}
  .audit-row-val   {{ color: {COL_PIZARRA}; font-weight: 600; }}
</style>
""", unsafe_allow_html=True)

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
    drive  = build("drive",  "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)
    return gc, drive, sheets

def formato_sheets(ws, sheets_service):
    sid = ws._properties["sheetId"]
    requests = [
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor":     {"red": 0.176, "green": 0.420, "blue": 0.894},
                "textFormat":          {"bold": True, "foregroundColor": {"red":1,"green":1,"blue":1}, "fontSize": 10},
                "horizontalAlignment": "CENTER",
                "verticalAlignment":   "MIDDLE",
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)"
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 32}, "fields": "pixelSize"
        }},
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"
        }},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 11, "endColumnIndex": 12}],
            "booleanRule": {
                "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Conforme"}]},
                "format": {"backgroundColor": {"red": 0.0, "green": 0.898, "blue": 0.627}}
            }
        }, "index": 0}},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 11, "endColumnIndex": 12}],
            "booleanRule": {
                "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "No Conforme"}]},
                "format": {"backgroundColor": {"red": 1.0, "green": 0.239, "blue": 0.353}}
            }
        }, "index": 1}},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 11, "endColumnIndex": 12}],
            "booleanRule": {
                "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Revision"}]},
                "format": {"backgroundColor": {"red": 1.0, "green": 0.690, "blue": 0.125}}
            }
        }, "index": 2}},
    ]
    anchos = [110,100,80,80,90,130,120,110,120,120,90,110,160,130,220]
    for i, w in enumerate(anchos):
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i+1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"
        }})
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID, body={"requests": requests}
    ).execute()

def get_sheet(gc, sheets_service=None):
    wb = gc.open_by_key(SHEET_ID)
    try:
        ws = wb.worksheet("Auditorias")
    except gspread.exceptions.WorksheetNotFound:
        ws = wb.add_worksheet("Auditorias", rows=1000, cols=20)
        ws.append_row([
            "N° Auditoria","Fecha","Hora","Turno","Patente","Chofer",
            "Tipo Movimiento","Material","Cantidad Declarada","Cantidad Contada",
            "Diferencia","Estado","Observaciones","Auditado Por","Link Foto"
        ])
        if sheets_service:
            try:
                formato_sheets(ws, sheets_service)
            except Exception:
                pass
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

def subir_a_drive(drive, img_bytes, nombre):
    media = MediaIoBaseUpload(io.BytesIO(img_bytes), mimetype="image/jpeg")
    meta  = {"name": nombre, "parents": [DRIVE_FOLDER_ID]}
    f = drive.files().create(
        body=meta, media_body=media,
        fields="id, webViewLink",
        supportsAllDrives=True
    ).execute()
    return f.get("webViewLink", "")

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
    img = np.array(img_pil)
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
            cv2.line(img, (x-radio,y), (x+radio,y), (0,0,0), max(2,radio//5))
            cv2.line(img, (x,y-radio), (x,y+radio), (0,0,0), max(2,radio//5))
            cv2.putText(img, txt, (tx-1,ty+1), fuente, escala, (255,255,255), grosor+2, cv2.LINE_AA)
            cv2.putText(img, txt, (tx,ty),     fuente, escala, (0,0,255),     grosor,   cv2.LINE_AA)
        else:
            cv2.circle(img, (x,y), radio, (0,0,220), max(2,radio//5))
            cv2.putText(img, txt, (tx-1,ty+1), fuente, escala, (0,0,0),      grosor+2, cv2.LINE_AA)
            cv2.putText(img, txt, (tx,ty),     fuente, escala, (255,255,255), grosor,   cv2.LINE_AA)
    return Image.fromarray(img)

for k, v in {"puntos_v":[],"puntos_h":[],"img_orig":None,"guardado":False,"link_drive":""}.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown("""
<div class="armatec-header">
  <div class="armatec-title">🏗️ ARMATEC · Auditoría de Andamios</div>
  <div class="armatec-sub">Sistema de control y registro de material · Auditado por: <b>Richard Romero</b></div>
</div>
""", unsafe_allow_html=True)

tab_auditoria, tab_dashboard = st.tabs(["📋  Auditoría", "📊  Dashboard"])

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
    st.markdown(
        "<span style='color:" + COL_CIAN + ";font-weight:700;'>📷 Cargar imagen del camión</span>",
        unsafe_allow_html=True
    )

    img_nueva = None
    archivo = st.file_uploader(
        "Selecciona una foto o toma una desde la cámara",
        type=["jpg","jpeg","png","webp"],
        label_visibility="collapsed"
    )
    st.caption("En el celular, al tocar el botón aparecen las opciones: Cámara o Galería.")
    if archivo:
        try:
            img_nueva = cargar_imagen(archivo)
        except Exception as e:
            st.error("No se pudo abrir la imagen: " + str(e))

    if img_nueva is not None and st.session_state["img_orig"] is None:
        st.session_state.update({
            "img_orig":   img_nueva,
            "puntos_v":   [],
            "puntos_h":   [],
            "guardado":   False,
            "link_drive": ""
        })

    if st.session_state["img_orig"]:

        tab_v, tab_h = st.tabs(["🔵  Verticales", "🔴  Horizontales / Cabezales"])

        with tab_v:
            st.markdown(
                "<p style='color:#8899BB;font-size:0.82rem;'>Toca cada tubo vertical → cruz negra + número rojo.</p>",
                unsafe_allow_html=True
            )
            ci, cc = st.columns([3, 1])
            with ci:
                coord_v = streamlit_image_coordinates(
                    dibujar_puntos(st.session_state["img_orig"],
                                   st.session_state["puntos_v"], "vertical"),
                    key="mapa_v"
                )
            with cc:
                tv = len(st.session_state["puntos_v"])
                st.markdown(
                    "<div class='metric-card' style='margin-top:20px;'>"
                    "<div class='metric-label'>Verticales</div>"
                    "<div class='metric-value'>" + str(tv) + "</div>"
                    "<div class='metric-sub'>tubos marcados</div></div>",
                    unsafe_allow_html=True
                )
                if st.button("↩ Deshacer (V)", key="undo_v"):
                    if st.session_state["puntos_v"]: st.session_state["puntos_v"].pop()
                    st.rerun()
                if st.button("🗑 Limpiar (V)", key="clear_v"):
                    st.session_state["puntos_v"] = []
                    st.rerun()
                decl_v = st.number_input("Cantidad declarada (V)", min_value=0, value=0, key="decl_v")
                if tv > 0 and decl_v > 0:
                    d = tv - decl_v
                    if d == 0:
                        st.markdown("<span class='badge-conforme'>✓ Conforme</span>", unsafe_allow_html=True)
                    elif abs(d) <= 2:
                        st.markdown("<span class='badge-revision'>⚠ Dif: " + f"{d:+d}" + "</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span class='badge-alerta'>✗ Dif: " + f"{d:+d}" + "</span>", unsafe_allow_html=True)
            if coord_v:
                x, y = int(coord_v["x"]), int(coord_v["y"])
                if not st.session_state["puntos_v"] or st.session_state["puntos_v"][-1] != (x, y):
                    st.session_state["puntos_v"].append((x, y))
                    st.rerun()

        with tab_h:
            st.markdown(
                "<p style='color:#8899BB;font-size:0.82rem;'>Toca cada horizontal/cabezal → círculo rojo + número blanco.</p>",
                unsafe_allow_html=True
            )
            ci, cc = st.columns([3, 1])
            with ci:
                coord_h = streamlit_image_coordinates(
                    dibujar_puntos(st.session_state["img_orig"],
                                   st.session_state["puntos_h"], "horizontal"),
                    key="mapa_h"
                )
            with cc:
                th_ = len(st.session_state["puntos_h"])
                st.markdown(
                    "<div class='metric-card' style='margin-top:20px;'>"
                    "<div class='metric-label'>Horizontales</div>"
                    "<div class='metric-value'>" + str(th_) + "</div>"
                    "<div class='metric-sub'>piezas marcadas</div></div>",
                    unsafe_allow_html=True
                )
                if st.button("↩ Deshacer (H)", key="undo_h"):
                    if st.session_state["puntos_h"]: st.session_state["puntos_h"].pop()
                    st.rerun()
                if st.button("🗑 Limpiar (H)", key="clear_h"):
                    st.session_state["puntos_h"] = []
                    st.rerun()
                decl_h = st.number_input("Cantidad declarada (H)", min_value=0, value=0, key="decl_h")
                if th_ > 0 and decl_h > 0:
                    d = th_ - decl_h
                    if d == 0:
                        st.markdown("<span class='badge-conforme'>✓ Conforme</span>", unsafe_allow_html=True)
                    elif abs(d) <= 2:
                        st.markdown("<span class='badge-revision'>⚠ Dif: " + f"{d:+d}" + "</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span class='badge-alerta'>✗ Dif: " + f"{d:+d}" + "</span>", unsafe_allow_html=True)
            if coord_h:
                x, y = int(coord_h["x"]), int(coord_h["y"])
                if not st.session_state["puntos_h"] or st.session_state["puntos_h"][-1] != (x, y):
                    st.session_state["puntos_h"].append((x, y))
                    st.rerun()

        st.markdown("---")
        total_contado   = len(st.session_state["puntos_v"]) + len(st.session_state["puntos_h"])
        cant_decl_total = st.session_state.get("decl_v", 0) + st.session_state.get("decl_h", 0)
        material_label  = "V:" + str(len(st.session_state["puntos_v"])) + " · H:" + str(len(st.session_state["puntos_h"]))

        c1, c2 = st.columns([2, 1])
        c1.info(
            "**Contado:** " + str(total_contado) +
            "  |  **Declarado:** " + str(cant_decl_total) +
            "  |  **Diferencia:** " + f"{total_contado - cant_decl_total:+d}" +
            "  |  " + material_label
        )
        guardar = c2.button("✅ Guardar en Sheets + Drive", type="primary",
                            disabled=st.session_state["guardado"])

        if guardar and not st.session_state["guardado"]:
            with st.spinner("Guardando..."):
                try:
                    gc, drive, sheets = get_clients()
                    diff_total = total_contado - cant_decl_total
                    if cant_decl_total == 0:    estado = "Sin declarar"
                    elif diff_total == 0:        estado = "Conforme"
                    elif abs(diff_total) <= 2:   estado = "Revision"
                    else:                        estado = "No Conforme"
                    ws    = get_sheet(gc, sheets)
                    n_aud = get_next_audit_number(ws)
                    ahora = datetime.datetime.now()
                    img_final = dibujar_puntos(st.session_state["img_orig"], st.session_state["puntos_v"], "vertical")
                    img_final = dibujar_puntos(img_final, st.session_state["puntos_h"], "horizontal")
                    buf = io.BytesIO()
                    img_final.save(buf, format="JPEG", quality=88)
                    nombre_archivo = n_aud + "_" + patente + "_" + ahora.strftime("%Y%m%d_%H%M%S") + ".jpg"
                    link = subir_a_drive(drive, buf.getvalue(), nombre_archivo)
                    guardar_en_sheets(gc, {
                        "n_auditoria": n_aud, "fecha": ahora.strftime("%Y-%m-%d"),
                        "hora": ahora.strftime("%H:%M:%S"), "turno": turno,
                        "patente": patente, "chofer": chofer,
                        "tipo_movimiento": tipo_mov, "material": material_label,
                        "cantidad_declarada": cant_decl_total, "cantidad_contada": total_contado,
                        "diferencia": diff_total, "estado": estado,
                        "observaciones": observaciones, "auditado_por": "Richard Romero",
                        "link_foto": link,
                    })
                    st.session_state.update({"guardado": True, "link_drive": link})
                    st.success("✅ Auditoría **" + n_aud + "** guardada · Estado: **" + estado + "**")
                    if link:
                        st.markdown("[📷 Ver imagen en Drive](" + link + ")")
                except Exception as e:
                    st.error("Error al guardar: " + str(e))

        if st.session_state["guardado"]:
            if st.button("🔄 Nueva auditoría"):
                st.session_state.update({
                    "puntos_v": [], "puntos_h": [], "img_orig": None,
                    "guardado": False, "link_drive": ""
                })
                st.rerun()

with tab_dashboard:
    st.markdown(
        "<span style='color:" + COL_CIAN + ";font-weight:700;font-size:1rem;'>📊 Resumen de auditorías</span>",
        unsafe_allow_html=True
    )

    col_fmt1, col_fmt2 = st.columns([3, 1])
    col_fmt1.markdown(
        "<small style='color:#8899BB;'>Si la hoja no tiene colores, presiona el botón para aplicar el formato profesional.</small>",
        unsafe_allow_html=True
    )
    if col_fmt2.button("🎨 Aplicar formato a Sheets"):
        with st.spinner("Aplicando formato profesional..."):
            try:
                gc, _, sheets = get_clients()
                wb = gc.open_by_key(SHEET_ID)
                ws = wb.worksheet("Auditorias")
                formato_sheets(ws, sheets)
                st.success("✅ Formato aplicado. Abre Google Sheets para verlo.")
            except Exception as e:
                st.error("Error: " + str(e))

    st.markdown("---")

    try:
        gc, _, _sheets = get_clients()
        historial = cargar_historial(gc)
    except Exception as e:
        st.error("No se pudo cargar el historial: " + str(e))
        historial = []

    if not historial:
        st.info("Aún no hay registros. Guarda una auditoría para verla aquí.")
    else:
        import pandas as pd
        df = pd.DataFrame(historial)
        for col in ["Cantidad Declarada", "Cantidad Contada", "Diferencia"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        total_aud  = len(df)
        conformes  = len(df[df["Estado"] == "Conforme"])
        no_conf    = len(df[df["Estado"] == "No Conforme"])
        revisiones = len(df[df["Estado"] == "Revision"])
        pct        = round(conformes / total_aud * 100) if total_aud else 0

        k1, k2, k3, k4, k5 = st.columns(5)
        for col, label, value, sub in [
            (k1, "Total auditorías", total_aud,  "registros"),
            (k2, "Conformes",        conformes,  str(pct) + "%"),
            (k3, "No Conformes",     no_conf,    "con diferencia"),
            (k4, "En Revisión",      revisiones, "±1-2 unid."),
            (k5, "Tasa conformidad", str(pct)+"%","del total"),
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
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;'>Auditorías por patente</div>", unsafe_allow_html=True)
            if "Patente" in df.columns:
                d = df["Patente"].value_counts().reset_index()
                d.columns = ["Patente","N"]
                st.bar_chart(d.set_index("Patente"), color=COL_AZUL)
        with g2:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;'>Salidas vs Devoluciones</div>", unsafe_allow_html=True)
            if "Tipo Movimiento" in df.columns:
                d = df["Tipo Movimiento"].value_counts().reset_index()
                d.columns = ["Tipo","N"]
                st.bar_chart(d.set_index("Tipo"), color=COL_CIAN)

        g3, g4 = st.columns(2)
        with g3:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;'>Auditorías por chofer</div>", unsafe_allow_html=True)
            if "Chofer" in df.columns:
                d = df["Chofer"].value_counts().reset_index()
                d.columns = ["Chofer","N"]
                st.bar_chart(d.set_index("Chofer"), color=COL_AZUL)
        with g4:
            st.markdown("<div style='color:" + COL_CIAN + ";font-weight:600;'>Estado de auditorías</div>", unsafe_allow_html=True)
            if "Estado" in df.columns:
                d = df["Estado"].value_counts().reset_index()
                d.columns = ["Estado","N"]
                st.bar_chart(d.set_index("Estado"))

        st.markdown("---")
        st.markdown("<div style='color:" + COL_AMARILLO + ";font-weight:700;'>⚠ Últimas diferencias detectadas</div>", unsafe_allow_html=True)
        if "Estado" in df.columns:
            alertas = df[df["Estado"].isin(["No Conforme","Revision"])].tail(10)
            if alertas.empty:
                st.success("Sin alertas recientes.")
            else:
                for _, row in alertas.iterrows():
                    dv       = int(row.get("Diferencia", 0))
                    estado_r = str(row.get("Estado", ""))
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
