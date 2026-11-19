import asyncio
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from kaimon.analyze import MODEL_NAME, find_pairs
from kaimon.errors import AppError, ModelError
from kaimon.notes import list_txt, read_txt, safe_txt_name
from kaimon.store import (
    clean_pairs,
    clean_text,
    delete_draft,
    load_scan,
    read_draft,
    store_scan,
    text_key,
    write_draft,
    write_note,
)
from kaimon.textio import decode_text, read_limited

logger = logging.getLogger("kaimon")
PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
LANG_DIR = ROOT / "languages"
LANG_FILES = {"English.ini", "Russian.ini"}
FILES = Path(os.environ.get("KAIMON_FILES", "/data/files"))
DATA = Path(os.environ.get("KAIMON_DATA", "/data/data"))
_jobs_by_key = {}
_jobs_by_name = {}

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
    return {"files": list_txt(FILES)}


@app.get("/api/draft")
def draft_get(name: str):
    return read_draft(DATA, name)


@app.put("/api/draft")
async def draft_put(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        raise AppError("K014", "The document is not valid.")
    return write_draft(DATA, body.get("name"), body.get("text"), body.get("pairs"))


@app.delete("/api/draft")
def draft_delete(name: str):
    delete_draft(DATA, name)
    return {"ok": True}


@app.post("/api/save")
async def save(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        raise AppError("K014", "The document is not valid.")
    text = clean_text(body.get("text"))
    pairs = clean_pairs(body.get("pairs"), len(text))
    safe = write_note(FILES, body.get("name"), text)
    store_scan(DATA, text, MODEL_NAME, pairs)
    delete_draft(DATA, safe)
    return {"ok": True, "name": safe}


def _prepare_upload(name: str, data: bytes) -> tuple[str, str]:
    if not name.lower().endswith(".txt"):
        raise AppError("K008", "Only a .txt file can be opened.")
    return name, decode_text(read_limited([data]))


class _Job:
    def __init__(self, name: str, text: str, key: str):
        self.name = name
        self.text = text
        self.key = key
        self.events = []
        self.subscribers = []
        self.done = False
        self.failed = False


def _publish(job: _Job, payload) -> None:
    job.events.append(payload)
    for queue in list(job.subscribers):
        queue.put_nowait(True)


async def _async_publish(job: _Job, payload) -> None:
    _publish(job, payload)


async def _run_job(job: _Job) -> None:
    loop = asyncio.get_running_loop()

    def progress(step: str, percent: int, **extra) -> None:
        payload = {"event": "progress", "step": step, "percent": int(percent)}
        payload.update(extra)
        asyncio.run_coroutine_threadsafe(_async_publish(job, payload), loop).result()

    _publish(job, {"event": "progress", "step": "read", "percent": 2})
    try:
        cached = load_scan(DATA, job.text, MODEL_NAME)
        if cached is None:
            pairs = await asyncio.to_thread(find_pairs, job.text, progress=progress)
            store_scan(DATA, job.text, MODEL_NAME, pairs)
        else:
            pairs = cached
            _publish(job, {"event": "progress", "step": "select", "percent": 100})
        _publish(job, {"event": "result", "name": job.name, "text": job.text, "pairs": pairs})
    except ModelError:
        job.failed = True
        logger.error("K004 The similarity model failed to load.")
        _publish(job, {"event": "error", "error": "K004", "message": "The similarity model failed to load."})
    except AppError as exc:
        job.failed = True
        logger.error("%s %s", exc.code, exc.message)
        _publish(job, {"event": "error", "error": exc.code, "message": exc.message})
    except Exception:
        job.failed = True
        logger.exception("K005 The comparison failed.")
        _publish(job, {"event": "error", "error": "K005", "message": "The comparison failed."})
    finally:
        job.done = True
        if job.failed:
            if _jobs_by_key.get(job.key) is job:
                _jobs_by_key.pop(job.key, None)
            if _jobs_by_name.get(job.name) is job:
                _jobs_by_name.pop(job.name, None)
        _publish(job, None)


def _start_job(name: str, text: str) -> _Job:
    key = text_key(text)
    current = _jobs_by_key.get(key)
    if current is not None and not current.failed:
        _jobs_by_name[name] = current
        return current
    job = _Job(name, text, key)
    _jobs_by_key[key] = job
    _jobs_by_name[name] = job
    asyncio.create_task(_run_job(job))
    return job


async def _listen(job: _Job):
    queue: asyncio.Queue = asyncio.Queue()
    job.subscribers.append(queue)
    sent = 0
    try:
        while True:
            while sent < len(job.events):
                item = job.events[sent]
                sent += 1
                if item is None:
                    return
                yield json.dumps(item, ensure_ascii=False) + "\n"
            if job.done and sent >= len(job.events):
                return
            await queue.get()
    finally:
        if queue in job.subscribers:
            job.subscribers.remove(queue)


def _stream(name: str, text: str) -> StreamingResponse:
    return StreamingResponse(_listen(_start_job(name, text)), media_type="application/x-ndjson")


@app.get("/api/job")
def job_stream(name: str):
    safe = safe_txt_name(name)
    job = _jobs_by_name.get(safe)
    if job is None or job.failed:
        raise AppError("K015", "There is no comparison running.", status=404)
    return StreamingResponse(_listen(job), media_type="application/x-ndjson")


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
    data = read_txt(FILES, name)
    safe, text = _prepare_upload(Path(name).name, data)
    return _stream(safe, text)
