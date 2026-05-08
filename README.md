# 🏗️ AI-Count: Sistema de Auditoría Logística de Andamios

Sistema automatizado de auditoría para el conteo de piezas de andamiaje en camiones usando **YOLOv8**, **Streamlit** y **Google Cloud APIs**. Los trabajadores pueden usar la app directamente desde su teléfono o tablet para registrar conteos sin servidor propio.

---

## 📋 Características

- Detección automática con IA usando YOLOv8n
- Interfaz móvil con Streamlit
- Fotos subidas a Google Drive
- Auditorías guardadas en Google Sheets
- Dropdown de patentes para selección rápida
- Botones independientes: Contar Horizontales / Contar Verticales
- Credenciales seguras usando Streamlit Secrets

---

## 🔐 Configuración de Google Cloud

1. Ve a [Google Cloud Console](https://console.cloud.google.com)
2. Activa Google Sheets API y Google Drive API
3. Crea una cuenta de servicio en IAM
4. Descarga la clave JSON y guárdala como `credentials.json`
5. Comparte tu Google Sheet con el email de la cuenta de servicio
6. Comparte la carpeta de Drive con el mismo email

---

## 📦 Archivos del proyecto

- `app.py` - Aplicación principal de Streamlit
- `requirements.txt` - Dependencias de Python
- `credentials.json` - Clave de servicio de Google (NO subir a GitHub)
- `.gitignore` - Ignora archivos sensibles y temporales
- `README.md` - Documentación del proyecto

---

## 🚀 Despliegue en Streamlit Cloud

1. Ve a [share.streamlit.io](https://share.streamlit.io)
2. Inicia sesión con GitHub
3. Haz clic en **New app**
4. Selecciona:
   - `ConteoMaterial/conteo-andamio-ia`
   - Rama `main`
   - Archivo `app.py`
5. En **Settings > Secrets**, agrega `GOOGLE_CREDENTIALS` con el contenido completo de `credentials.json`

---

## 🧪 Pruebas locales

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 📌 Notas importantes

- No subas `credentials.json` a GitHub.
- Asegúrate de que la cuenta de servicio tenga permisos en Sheets y Drive.
- Si usas Streamlit Cloud, el secret `GOOGLE_CREDENTIALS` debe contener todo el JSON.

---

## 📣 Comandos de Git

```bash
git add README.md
git commit -m "Resolve merge conflict in README.md"
git push -u origin main
```
