# 🏗️ AI-Count: Sistema de Auditoría Logística de Andamios

Sistema automatizado de auditoría para el conteo de piezas de andamiaje en camiones usando **YOLOv8**, **Streamlit** y **Google Cloud APIs**. Los trabajadores pueden usar la app directamente desde su teléfono o tablet para registrar conteos sin costo de servidor.

---

## 📋 Características

✅ **Detección por IA**: YOLOv8n para identificar piezas automáticamente  
✅ **Interfaz móvil**: Optimizada para teléfonos y tablets con Streamlit  
✅ **Respaldo en Drive**: Cada foto se guarda automáticamente en Google Drive  
✅ **Registro en Sheets**: Auditoría completa con fecha, hora, patente, conteo y enlace a foto  
✅ **Dropdown de patentes**: Lista oficial sin entrada manual  
✅ **Botones independientes**: Conteo separado para Horizontales y Verticales  
✅ **Seguridad en la nube**: Credenciales gestionadas mediante Streamlit Secrets  

---

## 🔐 Configuración inicial (IMPORTANTE)

### 1. Obtener credentials.json de Google Cloud

1. Ve a [Google Cloud Console](https://console.cloud.google.com)
2. Crea un proyecto y activa **Google Sheets API** y **Google Drive API**
3. Ve a **IAM y administración** → **Cuentas de servicio**
4. Crea una cuenta de servicio
5. En **Crear claves**, descarga un JSON y guárdalo como **credentials.json**
6. Comparte tu Google Sheet y carpeta Drive con el email de la cuenta de servicio

### 2. Actualizar IDs en app.py

Reemplaza en app.py:
- SHEET_ID = "1ew4P9dsQWrINTCfEc5bg-qlcUmvSfZDPXUEq6hFxlOg" con tu Sheet ID
- DRIVE_FOLDER_ID = "1K1Q3d4KV_b4RzhQsFVxN_cf9u8F0Wuae" con tu Folder ID

---

## 🚀 Comandos para GitHub

`ash
# Inicializar Git
git init

# Agregar todos los archivos
git add .

# Crear el primer commit
git commit -m \"Initial commit: AI-Count Streamlit app for scaffolding material auditing\"

# Conectar con el repositorio remoto
git remote add origin https://github.com/ConteoMaterial/conteo-andamios-ia.git

# Renombrar rama a 'main'
git branch -M main

# Subir el proyecto a GitHub
git push -u origin main
`

### Para actualizaciones futuras:

`ash
git add .
git commit -m \"Update: [descripción de cambios]\"
git push origin main
`

---

## ☁️ Desplegar en Streamlit Cloud

1. Ve a [share.streamlit.io](https://share.streamlit.io)
2. Haz clic en **New app**
3. Selecciona tu repositorio en GitHub, rama **main** y archivo **app.py**
4. **IMPORTANTE**: Ve a **Settings** → **Secrets** y agrega:
   - **Nombre**: GOOGLE_CREDENTIALS
   - **Valor**: Copia TODO el contenido de credentials.json (el JSON completo)
5. Guarda y la app se desplegará

---

## 📁 Estructura del proyecto

`
conteo-andamios-ia/
├── app.py
├── requirements.txt
├── credentials.json (NO subir a GitHub, protegido por .gitignore)
├── .gitignore
└── README.md
`

---

## 🧪 Pruebas locales

`ash
pip install -r requirements.txt
streamlit run app.py
`

---

## 📧 Contacto y Soporte

Para problemas, revisa:
- Logs en Streamlit Cloud (Settings → Logs)
- Que credentials.json esté en Secrets
- Que Google Sheet y Drive estén compartidos con la cuenta de servicio

---

**¡Éxito! Tu app estará online en https://tu-app.streamlit.app 🎉**
