import asyncio
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from kaimon.analyze import find_pairs
from kaimon.errors import AppError, ModelError
from kaimon.notes import list_txt, read_txt
from kaimon.textio import decode_text, read_limited

logger = logging.getLogger("kaimon")
PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
LANG_DIR = ROOT / "languages"
LANG_FILES = {"English.ini", "Russian.ini"}
NOTES = Path(os.environ.get("KAIMON_NOTES", "/data"))

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


@app.get("/api/files")
def files():
    return {"files": list_txt(NOTES)}


def _prepare_upload(name: str, data: bytes) -> tuple[str, str]:
    if not name.lower().endswith(".txt"):
        raise AppError("K008", "Only a .txt file can be opened.")
    return name, decode_text(read_limited([data]))


def _stream(name: str, text: str) -> StreamingResponse:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def progress(step: str, percent: int, **extra) -> None:
        payload = {"event": "progress", "step": step, "percent": int(percent)}
        payload.update(extra)
        asyncio.run_coroutine_threadsafe(queue.put(payload), loop).result()

    async def work() -> None:
        await queue.put({"event": "progress", "step": "read", "percent": 2})
        try:
            pairs = await asyncio.to_thread(find_pairs, text, progress=progress)
            await queue.put({"event": "result", "name": name, "text": text, "pairs": pairs})
        except ModelError:
            logger.error("K004 The similarity model failed to load.")
            await queue.put({"event": "error", "error": "K004", "message": "The similarity model failed to load."})
        except AppError as exc:
            logger.error("%s %s", exc.code, exc.message)
            await queue.put({"event": "error", "error": exc.code, "message": exc.message})
        except Exception:
            logger.exception("K005 The comparison failed.")
            await queue.put({"event": "error", "error": "K005", "message": "The comparison failed."})
        finally:
            await queue.put(None)

    async def generate():
        task = asyncio.create_task(work())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield json.dumps(item, ensure_ascii=False) + "\n"
        finally:
            task.cancel()

    return StreamingResponse(generate(), media_type="application/x-ndjson")


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
    safe, text = _prepare_upload(name, read_limited(blocks))
    return _stream(safe, text)


@app.post("/api/open")
async def open_note(request: Request):
    body = await request.json()
    name = body.get("name") if isinstance(body, dict) else None
    data = read_txt(NOTES, name)
    safe, text = _prepare_upload(Path(name).name, data)
    return _stream(safe, text)
