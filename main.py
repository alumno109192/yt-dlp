# main.py (usando FastAPI y yt-dlp)
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
from bs4 import BeautifulSoup
import requests
import json
import re
import os
from mutagen.mp4 import MP4
import logging
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configura CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir cualquier origen
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos los métodos
    allow_headers=["*"],  # Permitir todos los headers
)

app = FastAPI()

from fastapi import FastAPI, HTTPException, Form
import yt_dlp

app = FastAPI()

@app.post("/login")
def login_youtube(
    username: str = Form(...),
    password: str = Form(...),
    cookie_file: str = Form("cookies.txt")
):
    ydl_opts = {
        'username': username,
        'password': password,
        'cookiefile': cookie_file,
        'quiet': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info("https://www.youtube.com", download=False)
        return {"message": f"Cookies exportadas a {cookie_file}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al iniciar sesión: {e}")
    

# Añadir este endpoint a tu servidor FastAPI
@app.get("/search")
def search_videos(query: str):
    try:
        search_url = f"https://www.youtube.com/results?search_query={query}&sp=EgIQAQ%253D%253D"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Intentar extraer datos del HTML
        results = []
        # Esto puede necesitar ajustes según la estructura actual de YouTube
        scripts = soup.find_all('script')
        for script in scripts:
            if 'var ytInitialData = ' in script.text:
                # Extrae solo el objeto JSON usando regex
                match = re.search(r'var ytInitialData = (\{.*\});', script.text, re.DOTALL)
                if match:
                    data_str = match.group(1)
                    data = json.loads(data_str)
                else:
                    continue
                
                # Navegar por la estructura de datos para encontrar videos
                contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {})
                items = contents.get('sectionListRenderer', {}).get('contents', [{}])[0].get('itemSectionRenderer', {}).get('contents', [])
                
                for item in items:
                    video_renderer = item.get('videoRenderer', {})
                    if video_renderer:
                        video_id = video_renderer.get('videoId', '')
                        title = video_renderer.get('title', {}).get('runs', [{}])[0].get('text', 'Sin título')
                        channel = video_renderer.get('ownerText', {}).get('runs', [{}])[0].get('text', 'Canal desconocido')
                        
                        if video_id:
                            results.append({
                                'id': video_id,
                                'title': title,
                                'channel': channel
                            })
        
        return results[:10]  # Limitar a 10 resultados
    except Exception as e:
        return {"error": str(e)}

@app.get("/audioinfo")
def get_audio_info(url: str):
    output_path = "/tmp/audioinfo.m4a"
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'noplaylist': True,
        'no_warnings': True,
        'cookies': 'cookies.txt',  # <--- Añade esta línea
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": info["title"],
            "url": info["url"],
            "thumbnail": info["thumbnail"],
        }

@app.get("/api/search")
def api_search_videos(query: str):
    """Busca videos usando scraping web de YouTube"""
    try:
        # Codificar la query correctamente
        encoded_query = requests.utils.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgIQAQ%253D%253D"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extraer datos del HTML
        results = []
        scripts = soup.find_all('script')
        for script in scripts:
            if 'var ytInitialData = ' in script.text:
                # Extrae solo el objeto JSON usando regex
                match = re.search(r'var ytInitialData = (\{.*\});', script.text, re.DOTALL)
                if match:
                    data_str = match.group(1)
                    data = json.loads(data_str)
                else:
                    continue
                
                # Navegar por la estructura de datos para encontrar videos
                contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {})
                items = contents.get('sectionListRenderer', {}).get('contents', [{}])[0].get('itemSectionRenderer', {}).get('contents', [])
                
                for item in items:
                    try:
                        video_renderer = item.get('videoRenderer', {})
                        if video_renderer:
                            video_id = video_renderer.get('videoId', '')
                            title = video_renderer.get('title', {}).get('runs', [{}])[0].get('text', 'Sin título')
                            channel = video_renderer.get('ownerText', {}).get('runs', [{}])[0].get('text', 'Canal desconocido')
                            
                            # Intentar obtener la miniatura
                            thumbnail = ''
                            thumbnails = video_renderer.get('thumbnail', {}).get('thumbnails', [])
                            if thumbnails and len(thumbnails) > 0:
                                thumbnail = thumbnails[-1].get('url', '')
                            
                            if video_id:
                                results.append({
                                    'id': video_id,
                                    'title': title,
                                    'channel': channel,
                                    'thumbnail': thumbnail
                                })
                    except Exception as e:
                        print(f"Error procesando video: {e}")
                        continue
        
        return results[:10]  # Limitar a 10 resultados
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/related")
def get_related_videos(video_id: str, title: str = None, artist: str = None):
    """Obtiene videos relacionados basados en género y artista"""
    try:
        # Extraer el género actual si está disponible
        current_genre = ''
        if title:
            genres = _extract_genres(title)
            if genres:
                current_genre = genres[0]
        
        # Construir la consulta de búsqueda
        if current_genre:
            search_query = f'{current_genre} música {current_genre}'
            if artist:
                search_query = f'{search_query} {artist}'
        else:
            search_query = _build_search_query(title, artist)
        
        # Usar el endpoint de búsqueda API
        return api_search_videos(search_query)
    except Exception as e:
        return {"error": str(e)}

# Endpoint para descargar la canción
import os
import tempfile

@app.get("/audio/{video_id}")
def get_audio(video_id: str):
    output_path = f"/tmp/{video_id}.m4a"

    # Obtener el contenido de la variable de entorno COOKIES
    cookies_content = os.getenv("COOKIES")
    temp_cookies_path = None

    if not cookies_content:
        logger.warning("[WARNING] La variable de entorno COOKIES no está configurada. Intentando usar cookies.txt.")
        # Verificar si existe el archivo cookies.txt
        if os.path.exists("cookies.txt"):
            temp_cookies_path = "cookies.txt"
            logger.info("[LOG] Usando cookies desde el archivo cookies.txt.")
        else:
            logger.error("[ERROR] No se encontró la variable de entorno COOKIES ni el archivo cookies.txt.")
            raise HTTPException(status_code=500, detail="No se encontraron cookies en la variable de entorno ni en el archivo cookies.txt.")
    else:
        # Escribir las cookies en un archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as temp_cookies_file:
            temp_cookies_file.write(cookies_content)
            temp_cookies_path = temp_cookies_file.name
        logger.info(f"[LOG] Cookies guardadas temporalmente en: {temp_cookies_path}")

    # Log para verificar que el archivo de cookies se está utilizando
    try:
        with open(temp_cookies_path, "r") as f:
            file_content = f.read()
            logger.info(f"[LOG] Contenido del archivo de cookies:\n{file_content}")
    except Exception as e:
        logger.error(f"[ERROR] No se pudo leer el archivo de cookies: {e}")
        raise HTTPException(status_code=500, detail="Error al leer el archivo de cookies.")

    # Ejecutar yt-dlp usando subprocess
    try:
        logger.info(f"[LOG] Ejecutando yt-dlp para descargar el audio del video: {video_id}")
        command = [
            "yt-dlp",
            f"https://www.youtube.com/watch?v={video_id}",
            "--cookies", temp_cookies_path,
            "-f", "bestaudio[ext=m4a]/bestaudio/best",
            "-o", output_path,
            "--add-header", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]

        # Log del comando que se ejecutará
        logger.info(f"[LOG] Comando ejecutado: {' '.join(command)}")

        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Log de la salida del comando
        logger.info(f"[LOG] Salida de yt-dlp:\n{result.stdout}")
        if result.returncode != 0:
            logger.error(f"[ERROR] yt-dlp falló con el siguiente error:\n{result.stderr}")
            raise HTTPException(status_code=500, detail=f"Error al descargar audio: {result.stderr}")

        # Verificar si el archivo se descargó correctamente
        if os.path.exists(output_path):
            logger.info("[LOG] Archivo descargado correctamente. Sirviendo archivo.")
            return FileResponse(output_path, media_type="audio/mp4")
        else:
            logger.error("[ERROR] El archivo no se encontró después de la descarga.")
            raise HTTPException(status_code=500, detail="El archivo no se encontró después de la descarga.")
    except Exception as e:
        logger.error(f"[ERROR] Error al ejecutar yt-dlp: {e}")
        raise HTTPException(status_code=500, detail=f"Error al ejecutar yt-dlp: {e}")
    finally:
        # Eliminar el archivo temporal de cookies si se creó
        if temp_cookies_path and temp_cookies_path != "cookies.txt" and os.path.exists(temp_cookies_path):
            os.remove(temp_cookies_path)

@app.get("/download/{video_id}")
def download_audio_with_details(video_id: str):
    output_path = f"/tmp/{video_id}.m4a"

    # Obtener el contenido de la variable de entorno COOKIES
    cookies_content = os.getenv("COOKIES")
    temp_cookies_path = None

    if not cookies_content:
        logger.warning("[WARNING] La variable de entorno COOKIES no está configurada. Intentando usar cookies.txt.")
        if os.path.exists("cookies.txt"):
            temp_cookies_path = "cookies.txt"
            logger.info("[LOG] Usando cookies desde el archivo cookies.txt.")
        else:
            logger.error("[ERROR] No se encontró la variable de entorno COOKIES ni el archivo cookies.txt.")
            raise HTTPException(status_code=500, detail="No se encontraron cookies en la variable de entorno ni en el archivo cookies.txt.")
    else:
        # Escribir las cookies en un archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as temp_cookies_file:
            temp_cookies_file.write(cookies_content)
            temp_cookies_path = temp_cookies_file.name
        logger.info(f"[LOG] Cookies guardadas temporalmente en: {temp_cookies_path}")

    # Ejecutar yt-dlp para descargar el audio y obtener información
    try:
        logger.info(f"[LOG] Ejecutando yt-dlp para descargar el audio del video: {video_id}")
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': output_path,
            'quiet': True,
            'noplaylist': True,
            'no_warnings': True,
            'cookiefile': temp_cookies_path,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)

        # Verificar si el archivo se descargó correctamente
        if not os.path.exists(output_path):
            logger.error("[ERROR] El archivo no se encontró después de la descarga.")
            raise HTTPException(status_code=500, detail="El archivo no se encontró después de la descarga.")

        # Obtener información adicional del archivo descargado
        try:
            audio = MP4(output_path)
            duration = int(audio.info.length)  # Duración en segundos
        except Exception as e:
            logger.warning(f"[WARNING] No se pudo obtener la duración del audio: {e}")
            duration = None

        # Devolver los detalles del audio
        return {
            "title": info.get("title", "Sin título"),
            "duration": duration,
            "thumbnail": info.get("thumbnail", ""),
            "file_path": output_path
        }
    except Exception as e:
        logger.error(f"[ERROR] Error al ejecutar yt-dlp: {e}")
        raise HTTPException(status_code=500, detail=f"Error al ejecutar yt-dlp: {e}")
    finally:
        # Eliminar el archivo temporal de cookies si se creó
        if temp_cookies_path and temp_cookies_path != "cookies.txt" and os.path.exists(temp_cookies_path):
            os.remove(temp_cookies_path)

# Endpoint para servir el archivo de audio
@app.get("/stream/{video_id}")
def stream_audio(video_id: str):
    audio_path = f"/tmp/{video_id}.m4a"
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    # Obtener duración usando mutagen
    try:
        audio = MP4(audio_path)
        duration = int(audio.info.length)
    except Exception as e:
        duration = None
    headers = {}
    if duration:
        headers["X-Audio-Duration"] = str(duration)
    return FileResponse(audio_path, media_type="audio/mp4", headers=headers)

# Funciones de utilidad para la extracción de información
def _extract_genres(title: str):
    """Extrae posibles géneros musicales del título"""
    genre_keywords = {
        'bachata': ['bachata', 'bachatero', 'bachatera'],
        'salsa': ['salsa', 'salsero', 'salsera'],
        'reggaeton': ['reggaeton', 'reggaetón', 'regeton', 'regueton'],
        'merengue': ['merengue'],
        'dembow': ['dembow', 'dembo'],
        'latin': ['latin', 'latino', 'latina'],
        'pop': ['pop'],
        'rock': ['rock'],
        'hip hop': ['hip hop', 'rap', 'trap'],
        'electronic': ['electronic', 'edm', 'house', 'techno', 'trance', 'dubstep'],
        'r&b': ['r&b', 'rnb', 'rhythm and blues'],
        'jazz': ['jazz'],
        'classical': ['classical', 'orchestra', 'piano solo'],
        'country': ['country'],
        'flamenco': ['flamenco', 'rumba'],
        'mariachi': ['mariachi', 'ranchera'],
        'cumbia': ['cumbia'],
        'vallenato': ['vallenato'],
    }
    
    title_lower = title.lower()
    found_genres = []
    
    for genre, keywords in genre_keywords.items():
        for keyword in keywords:
            if keyword in title_lower:
                found_genres.append(genre)
                break
    
    return found_genres

def _extract_artist(title: str):
    """Extrae el posible nombre del artista del título"""
    import re
    
    # Patrón "Artista - Título"
    dash_pattern = re.compile(r'^(.*?)\s*-\s*.*$')
    dash_match = dash_pattern.match(title)
    if dash_match and dash_match.group(1):
        return dash_match.group(1).strip()
    
    # Patrón "Título by Artista"
    by_pattern = re.compile(r'.*\sby\s+(.*?)(\s|\(|$)')
    by_match = by_pattern.match(title)
    if by_match and by_match.group(1):
        return by_match.group(1).strip()
    
    return ''

def _build_search_query(title, artist):
    """Construye una consulta de búsqueda basada en título y artista"""
    if not title and not artist:
        return 'música popular'
    
    query_parts = []
    
    if title:
        genres = _extract_genres(title)
        if genres:
            query_parts.append(genres[0])
            query_parts.append(f'{genres[0]} música')
    
    if artist:
        query_parts.append(artist)
    elif title:
        extracted_artist = _extract_artist(title)
        if extracted_artist:
            query_parts.append(extracted_artist)
    
    if not query_parts and title:
        words = title.split()[:3]
        query_parts.extend(words)
    
    if not query_parts:
        return 'música popular'
    
    return ' '.join(query_parts).strip()

def search_youtube_music(query):
    # Simula una búsqueda en YouTube Music
    search_url = f"https://www.youtube.com/results?search_query={query}&sp=EgIQAQ%253D%253D"
    
    response = requests.get(search_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    results = []
    # Busca los contenedores de videos en el HTML
    for video in soup.select('ytd-video-renderer'):
        title = video.select_one('#video-title').text.strip()
        video_id = video.select_one('#video-title')['href'].split('v=')[1]
        results.append({'title': title, 'id': video_id})
    
    return results[:5]  # Primeros 5 resultados

# Asegúrate de tener esto al final de tu archivo main.py
if __name__ == "__main__":
    import uvicorn
    # "0.0.0.0" significa "escuchar en todas las interfaces"
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)