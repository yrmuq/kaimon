import numpy as np

from kaimon.analyze import find_pairs


def test_progress_names_the_slow_step():
    steps = []

    def embed(texts, progress=None):
        progress(1, len(texts))
        progress(len(texts), len(texts))
        vectors = np.ones((len(texts), 4), dtype=np.float32)
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    text = "встреча с подрядчиком перенесена на четверг и нужна смета.\n\n" * 2
    find_pairs(text, embed=embed, progress=lambda step, percent, **extra: steps.append((step, percent)))
    names = [step for step, _percent in steps]
    assert names[0] == "model"
    assert "split" in names
    assert names[-1] == "select"
    embed_percents = [percent for step, percent in steps if step == "embed"]
    assert embed_percents == sorted(embed_percents)
    assert embed_percents[-1] > embed_percents[0]
