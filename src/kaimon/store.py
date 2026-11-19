import hashlib
import json
from pathlib import Path

from kaimon.errors import AppError
from kaimon.notes import safe_txt_name
from kaimon.textio import MAX_BYTES

STORE_MIN = 0.50


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_text(text) -> str:
    if not isinstance(text, str):
        raise AppError("K014", "The document is not valid.")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise AppError("K003", "The file is larger than 8 MB.")
    return text


def clean_pairs(raw, length: int) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > 300:
        raise AppError("K014", "The document is not valid.")
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            raise AppError("K014", "The document is not valid.")
        if item.get("left") is None or item.get("right") is None:
            continue
        try:
            left = [int(item["left"][0]), int(item["left"][1])]
            right = [int(item["right"][0]), int(item["right"][1])]
            semantic = float(item["semantic"])
            lexical = float(item["lexical"])
            score = float(item["score"])
            left_len = int(item["leftLen"])
            right_len = int(item["rightLen"])
        except (KeyError, TypeError, ValueError, IndexError):
            raise AppError("K014", "The document is not valid.") from None
        spans_ok = 0 <= left[0] < left[1] <= length and 0 <= right[0] < right[1] <= length
        scores_ok = 0 <= semantic <= 1 and 0 <= lexical <= 1 and 0 <= score <= 1
        if not spans_ok or not scores_ok:
            raise AppError("K014", "The document is not valid.")
        cleaned.append(
            {
                "left": left,
                "right": right,
                "score": round(score, 4),
                "semantic": round(semantic, 4),
                "lexical": round(lexical, 4),
                "leftLen": left_len,
                "rightLen": right_len,
            }
        )
    return cleaned


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        raise


def load_scan(folder: Path, text: str, model: str) -> list[dict] | None:
    path = folder / "scans" / f"{text_key(text)}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        pairs = clean_pairs(payload.get("pairs"), len(text))
    except (OSError, ValueError, AppError):
        return None
    if payload.get("model") != model:
        return None
    return pairs


def store_scan(folder: Path, text: str, model: str, pairs: list[dict]) -> None:
    path = folder / "scans" / f"{text_key(text)}.json"
    try:
        _write_json(path, {"model": model, "pairs": pairs})
    except OSError:
        return


def draft_path(folder: Path, name: str) -> Path:
    return folder / ".temp" / f"{safe_txt_name(name)}.json"


def read_draft(folder: Path, name: str) -> dict:
    path = draft_path(folder, name)
    if not path.is_file():
        raise AppError("K013", "There are no unsaved edits.", status=404)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        text = clean_text(payload.get("text"))
        pairs = clean_pairs(payload.get("pairs"), len(text))
    except (OSError, ValueError, AppError):
        raise AppError("K012", "The unsaved edits could not be stored.", status=500) from None
    return {"name": safe_txt_name(name), "text": text, "pairs": pairs}


def write_draft(folder: Path, name: str, text: str, pairs: list) -> dict:
    safe = safe_txt_name(name)
    text = clean_text(text)
    pairs = clean_pairs(pairs, len(text))
    try:
        _write_json(draft_path(folder, safe), {"name": safe, "text": text, "pairs": pairs})
    except OSError:
        raise AppError("K012", "The unsaved edits could not be stored.", status=500) from None
    return {"name": safe, "text": text, "pairs": pairs}


def delete_draft(folder: Path, name: str) -> None:
    path = draft_path(folder, name)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        raise AppError("K012", "The unsaved edits could not be stored.", status=500) from None


def write_note(folder: Path, name: str, text: str) -> str:
    safe = safe_txt_name(name)
    text = clean_text(text)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe
    tmp = path.with_suffix(".txt.tmp")
    try:
        tmp.write_bytes(text.encode("utf-8"))
        tmp.replace(path)
    except OSError:
        raise AppError("K011", "The notes file could not be saved.", status=500) from None
    return safe
