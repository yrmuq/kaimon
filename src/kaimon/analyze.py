import threading

import numpy as np

from kaimon.errors import ModelError
from kaimon.pairs import select_pairs
from kaimon.segments import candidate_spans

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


def embed_texts(texts: list[str]) -> np.ndarray:
    clipped = [text[:4000] for text in texts]
    model = get_model()
    with _lock:
        try:
            raw = list(model.embed(clipped))
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError(str(exc)) from exc
    vectors = np.vstack([np.asarray(vec, dtype=np.float32) for vec in raw])
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def find_pairs(text: str, embed=embed_texts) -> list[dict]:
    spans = candidate_spans(text)
    if len(spans) < 2:
        return []
    snippets = [text[start:end] for start, end in spans]
    vectors = embed(snippets)
    return select_pairs(text, spans, vectors)
