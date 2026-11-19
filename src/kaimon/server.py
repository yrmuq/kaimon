import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from kaimon.analyze import find_pairs
from kaimon.errors import AppError, ModelError
from kaimon.textio import decode_text, read_limited

logger = logging.getLogger("kaimon")
PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
LANG_DIR = ROOT / "languages"
LANG_FILES = {"English.ini", "Russian.ini"}

app = FastAPI(docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")


@app.exception_handler(AppError)
async def app_error(_request: Request, exc: AppError):
    logger.error("%s %s", exc.code, exc.message)
    return JSONResponse(status_code=exc.status, content={"error": exc.code, "message": exc.message})


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(PACKAGE / "static" / "index.html")


@app.get("/languages/{name}")
def language(name: str):
    if name not in LANG_FILES:
        raise AppError("K007", "The language catalog is missing.", status=404)
    path = LANG_DIR / name
    if not path.is_file():
        raise AppError("K007", "The language catalog is missing.", status=500)
    return FileResponse(path, media_type="text/plain; charset=utf-8")


@app.post("/api/analyze")
async def analyze(request: Request):
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise AppError("K006", "No file was uploaded.")
    name = Path(getattr(upload, "filename", "") or "").name
    if not name.lower().endswith(".txt"):
        raise AppError("K008", "Only a .txt file can be opened.")
    blocks = []
    while True:
        block = await upload.read(1024 * 1024)
        if not block:
            break
        blocks.append(block)
    data = read_limited(blocks)
    text = decode_text(data)
    try:
        pairs = await asyncio.to_thread(find_pairs, text)
    except ModelError:
        raise AppError("K004", "The similarity model failed to load.", status=500) from None
    except AppError:
        raise
    except Exception:
        logger.exception("K005 The comparison failed.")
        raise AppError("K005", "The comparison failed.", status=500) from None
    logger.info("compared %s pairs", len(pairs))
    return {"name": name, "text": text, "pairs": pairs}
