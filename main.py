from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
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

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de OAuth 2.0
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
CLIENT_SECRETS_FILE = 'client_secrets.json'  # Sube este archivo a Render.com
TOKEN_FILE = 'token.json'  # Se generará tras la autenticación

CLIENT_SECRETS_JSON = os.getenv('CLIENT_SECRETS_JSON')
if CLIENT_SECRETS_JSON:
    client_secrets = json.loads(CLIENT_SECRETS_JSON)
    flow = Flow.from_client_config(client_secrets, scopes=SCOPES)
else:
    raise FileNotFoundError("El archivo client_secrets.json no se encontró y no se configuró la variable de entorno.")

# Endpoint para iniciar la autenticación OAuth
@app.get("/login")
def login():
    """Inicia el flujo de autenticación OAuth 2.0 redirigiendo al usuario a Google."""
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return RedirectResponse(authorization_url)

# Endpoint para manejar el callback de OAuth
@app.get("/oauth2callback")
def oauth2callback(request: Request):
    """Maneja la respuesta de Google y guarda las credenciales."""
    flow.fetch_token(authorization_response=str(request.url))
    credentials = flow.credentials
    with open(TOKEN_FILE, 'w') as token_file:
        token_file.write(credentials.to_json())
    return {"message": "Autenticación completada"}

# Función para obtener el servicio de YouTube autenticado
def get_youtube_service():
    """Devuelve un cliente autenticado de la API de YouTube."""
    if not os.path.exists(TOKEN_FILE):
        raise HTTPException(status_code=401, detail="No autenticado. Usa /login primero.")
    with open(TOKEN_FILE, 'r') as token_file:
        credentials = Credentials.from_authorized_user_info(json.load(token_file), SCOPES)
    return build('youtube', 'v3', credentials=credentials)

# Endpoint de búsqueda usando la API de YouTube
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
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": info["title"],
            "url": info["url"],
            "thumbnail": info["thumbnail"],
        }

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