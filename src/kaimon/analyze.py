import threading

import numpy as np

from kaimon.errors import ModelError
from kaimon.pairs import select_pairs
from kaimon.segments import candidate_spans
from kaimon.store import STORE_MIN

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
_model = None
_lock = threading.Lock()


def get_model():
    global _model
    with _lock:
        if _model is None:
            try:
                from fastembed import TextEmbedding

                _model = TextEmbedding(MODEL_NAME)
            except Exception as exc:
                raise ModelError(str(exc)) from exc
        return _model


def embed_texts(texts: list[str], progress=None) -> np.ndarray:
    clipped = [text[:4000] for text in texts]
    model = get_model()
    total = len(clipped)
    rows = []
    with _lock:
        try:
            for start in range(0, total, 32):
                chunk = clipped[start : start + 32]
                rows.extend(model.embed(chunk))
                if progress:
                    progress(min(start + len(chunk), total), total)
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError(str(exc)) from exc
    if not rows:
        return np.zeros((0, 1), dtype=np.float32)
    vectors = np.vstack([np.asarray(vec, dtype=np.float32) for vec in rows])
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def find_pairs(text: str, embed=embed_texts, progress=None) -> list[dict]:
    def report(step: str, percent: int, **extra) -> None:
        if progress:
            progress(step, percent, **extra)

    report("model", 5)
    if embed is embed_texts:
        get_model()
    spans = candidate_spans(text)
    report("split", 12, count=len(spans))
    if len(spans) < 2:
        return []
    snippets = [text[start:end] for start, end in spans]

    def on_embed(done: int, total: int) -> None:
        percent = 15 + round(73 * done / total) if total else 88
        report("embed", min(88, percent), done=done, total=total)

    vectors = embed(snippets, progress=on_embed)
    report("select", 94)
    return select_pairs(text, spans, vectors, semantic_min=STORE_MIN, lexical_min=STORE_MIN)

