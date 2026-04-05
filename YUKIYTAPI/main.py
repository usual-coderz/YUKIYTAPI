import os
import time
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from YUKIYTAPI.database.stats import init_db, add_download, get_stats

app = FastAPI(title="YUKI YT API")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "YUKIYTAPI", "saved")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt") # <-- 
os.makedirs(CACHE_DIR, exist_ok=True)

init_db()

TOKENS = {}
START_TIME = time.time()

@app.get("/")
async def home(request: Request):
    uptime = round(time.time() - START_TIME, 2)
    return JSONResponse({
        "status": "Running...",
        "owner": "YUKIMUSIC",
        "uptime": f"{uptime}s",
        "message": "Welcome to YUKI API"
    })

@app.get("/stats")
async def api_stats(request: Request):
    total_dl, cache_mb = get_stats()
    return JSONResponse({
        "status": "success",
        "total_song_downloads": total_dl,
        "total_cache_size_mb": cache_mb,
        "active_tokens": len(TOKENS)
    })

@app.get("/download")
async def generate_token(request: Request, url: str, type: str = "audio"):
    video_id = url.split('v=')[-1].split('&')[0] if 'v=' in url else url
    
    random_str = str(uuid.uuid4().hex)[:16]
    yuki_token = f"YUKIMusic{random_str}YukiBots"
    
    TOKENS[yuki_token] = {
        "video_id": video_id,
        "type": type,
        "expires": time.time() + 60
    }
    
    return JSONResponse({
        "status": "success",
        "video_id": video_id,
        "download_token": yuki_token,
        "usage": "Use token parameter in /stream endpoint"
    })

@app.get("/stream/{video_id}")
async def stream_music(request: Request, video_id: str, type: str = "audio", token: str = None):
    if not token or token not in TOKENS:
        raise HTTPException(status_code=401, detail="Invalid Token Access Denied")
        
    token_data = TOKENS[token]
    if time.time() > token_data["expires"] or token_data["video_id"] != video_id:
        raise HTTPException(status_code=401, detail="Token Expired")
        
    del TOKENS[token]

    ext = "mp3" if type == "audio" else "mp4"
    file_path = os.path.join(CACHE_DIR, f"{video_id}.{ext}")

    if not os.path.exists(file_path):
        outtmpl = os.path.join(CACHE_DIR, f"{video_id}.%(ext)s")
        
        
        if type == "audio":
            cmd = [
                "yt-dlp",
                "--cookies", COOKIES_FILE,
                "--js-runtimes", "node",
                "--remote-components", "ejs:github",
                "-f", "bestaudio/best",
                "-x", "--audio-format", "mp3", "--audio-quality", "192",
                "-o", outtmpl,
                "--quiet",
                video_id
            ]
        else:
            cmd = [
                "yt-dlp",
                "--cookies", COOKIES_FILE,
                "--js-runtimes", "node",
                "--remote-components", "ejs:github",
                "-f", "(bestvideo[ext=mp4]+bestaudio[ext=m4a])/best[ext=mp4]/best",
                "-o", outtmpl,
                "--quiet",
                video_id
            ]

        try:
            #
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise HTTPException(status_code=500, detail=f"CLI Error: {stderr.decode()}")
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    add_download()
    
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/mpeg" if type == "audio" else "video/mp4")
    else:
        raise HTTPException(status_code=500, detail="FFmpeg failed to create MP3")
        
