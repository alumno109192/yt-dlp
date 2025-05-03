from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import yt_dlp
from mutagen.mp4 import MP4
import os
import json
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Lista de variables de entorno requeridas
REQUIRED_ENV_VARS = [
    "CLIENT_ID",
    "CLIENT_SECRET",
    "REDIRECT_URI",
    "AUTH_URI",
    "TOKEN_URI",
    "AUTH_PROVIDER_X509_CERT_URL"
]

# Validar variables de entorno
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
    raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")

# Configuración de OAuth 2.0 usando variables de entorno
client_config = {
    "web": {
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "redirect_uris": [os.getenv("REDIRECT_URI")],
        "auth_uri": os.getenv("AUTH_URI"),
        "token_uri": os.getenv("TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL")
    }
}

# Scopes para la API de YouTube
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']

# Crear el flujo OAuth 2.0 con redirect_uri configurado
try:
    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=os.getenv("REDIRECT_URI"))
except Exception as e:
    logger.error(f"Failed to create OAuth flow: {e}")
    raise

# Endpoint para iniciar la autenticación
@app.get("/login")
def login():
    """Inicia el flujo de autenticación OAuth 2.0 redirigiendo al usuario a Google."""
    try:
        logger.info("Iniciando el flujo de autenticación OAuth 2.0.")
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        logger.info(f"URL de autorización generada: {authorization_url}")
        return RedirectResponse(authorization_url)
    except Exception as e:
        logger.error(f"Error al iniciar el flujo de autenticación: {e}")
        raise HTTPException(status_code=500, detail=f"Error al iniciar el flujo de autenticación: {str(e)}")

# Endpoint para manejar el callback de OAuth
@app.get("/oauth2callback")
async def oauth2callback(request: Request):
    """Maneja la respuesta de Google y obtiene el token de acceso."""
    try:
        logger.info("Recibiendo el callback de OAuth 2.0.")
        flow.fetch_token(authorization_response=str(request.url))
        credentials = flow.credentials
        logger.info("Token de acceso obtenido correctamente.")
        
        with open('token.json', 'w') as token_file:
            token_file.write(credentials.to_json())
        
        return {"message": "Autenticación completada"}
    except Exception as e:
        logger.error(f"Error al manejar el callback de OAuth: {e}")
        raise HTTPException(status_code=500, detail=f"Error al manejar el callback de OAuth: {str(e)}")

# Función para obtener el servicio de YouTube autenticado
def get_youtube_service():
    """Devuelve un cliente autenticado de la API de YouTube."""
    if not os.path.exists('token.json'):
        raise HTTPException(status_code=401, detail="No autenticado. Usa /login primero.")
    with open('token.json', 'r') as token_file:
        credentials = Credentials.from_authorized_user_info(json.load(token_file), SCOPES)
    return build('youtube', 'v3', credentials=credentials)

# Endpoint para buscar videos usando la API de YouTube
@app.get("/search")
def search_videos(query: str):
    """Busca videos en YouTube usando la API oficial."""
    try:
        youtube = get_youtube_service()
        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=10
        )
        response = request.execute()
        results = []
        for item in response.get('items', []):
            results.append({
                'id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'channel': item['snippet']['channelTitle'],
                'thumbnail': item['snippet']['thumbnails']['default']['url']
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al buscar videos: {e}")

# Endpoint para obtener información del audio
@app.get("/audioinfo")
def get_audio_info(url: str):
    """Obtiene información del audio sin descargar."""
    output_path = "/tmp/audioinfo.m4a"
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'noplaylist': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt',  # Usar cookies para autenticación
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "title": info["title"],
            "url": info["url"],
            "thumbnail": info["thumbnail"],
        }
    except Exception as e:
        logger.error(f"Error al obtener información del audio: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener información del audio: {e}")

# Endpoint para descargar audio
@app.get("/audio/{video_id}")
def get_audio(video_id: str):
    """Descarga o sirve un archivo de audio desde YouTube."""
    output_path = f"/tmp/{video_id}.m4a"
    logger.info(f"Petición para descargar/reutilizar audio: {video_id}")
    if os.path.exists(output_path):
        logger.info("El archivo ya existe. Sirviendo archivo local.")
        return FileResponse(output_path, media_type="audio/mp4")
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'noplaylist': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt',  # Usar cookies para autenticación
    }
    try:
        logger.info("Iniciando descarga con yt-dlp...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        if os.path.exists(output_path):
            logger.info("Archivo descargado correctamente.")
            return FileResponse(output_path, media_type="audio/mp4")
        else:
            raise HTTPException(status_code=500, detail="El archivo no se encontró tras la descarga.")
    except Exception as e:
        logger.error(f"Error al descargar audio: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        raise HTTPException(status_code=500, detail=f"Error al descargar audio: {e}")

# Endpoint para streaming de audio
@app.get("/stream/{video_id}")
def stream_audio(video_id: str):
    """Sirve un archivo de audio existente con su duración."""
    audio_path = f"/tmp/{video_id}.m4a"
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    try:
        audio = MP4(audio_path)
        duration = int(audio.info.length)
    except Exception as e:
        duration = None
    headers = {"X-Audio-Duration": str(duration)} if duration else {}
    return FileResponse(audio_path, media_type="audio/mp4", headers=headers)

# Inicio del servidor
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)