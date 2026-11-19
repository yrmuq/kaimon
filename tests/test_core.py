import hashlib
import json
import re
from pathlib import Path

import numpy as np

from kaimon.pairs import map_span, select_pairs
from kaimon.segments import candidate_spans, paragraph_spans
from kaimon.textio import decode_text, read_limited

ROOT = Path(__file__).resolve().parents[1]
NOTE = "Встреча с подрядчиком перенесена на четверг, нужно согласовать смету и список материалов."
OTHER = "Совсем другая запись про поездку на море, билеты и гостиницу у вокзала."


def test_paragraphs_keep_separate_notes():
    text = "a\n\n\nb\n\nc\n"
    assert [text[s:e] for s, e in paragraph_spans(text)] == ["a", "b", "c"]


def test_unseparated_text_stays_one_paragraph():
    text = "a\nb\nc\n"
    assert paragraph_spans(text) == [(0, 5)]


def test_map_span_cases():
    cases = json.loads((ROOT / "tests" / "map_cases.json").read_text(encoding="utf-8"))
    for case in cases:
        got = map_span(tuple(case["span"]), case["cut"], case["endOld"], case["insertLen"])
        assert (None if got is None else list(got)) == case["expect"], case["name"]


def _fake_embed(texts):
    dim = 128
    matrix = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        for token in re.findall(r"\w+", text.casefold(), re.U):
            digest = hashlib.md5(token.encode()).digest()
            matrix[i, digest[0] % dim] += 1.0
            matrix[i, digest[1] % dim] += 0.5
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def test_duplicate_paragraphs_pair_without_cutting_the_file():
    text = f"{NOTE}\n\n{OTHER}\n\n{NOTE}\n"
    original = text
    pairs = select_pairs(text, candidate_spans(text), _fake_embed([text[s:e] for s, e in candidate_spans(text)]))
    assert text == original
    assert pairs
    left = text[pairs[0]["left"][0] : pairs[0]["left"][1]]
    right = text[pairs[0]["right"][0] : pairs[0]["right"][1]]
    assert left == right == NOTE
    assert OTHER in text


def test_repeated_block_without_blank_lines():
    line = "альфа {} нужно сохранить эту длинную строку заметки целиком"
    block = "\n".join(line.format(n) for n in range(1, 5))
    other = "\n".join(f"море {n} отдельная длинная строка про поездку и билеты" for n in range(1, 5))
    text = f"{block}\n{block}\n{other}\n"
    spans = candidate_spans(text)
    pairs = select_pairs(text, spans, _fake_embed([text[s:e] for s, e in spans]))
    matched = [text[p["left"][0] : p["left"][1]] for p in pairs if text[p["left"][0] : p["left"][1]] == text[p["right"][0] : p["right"][1]]]
    assert any(block.split("\n", 1)[0] in item for item in matched)
    assert len(text) == len(f"{block}\n{block}\n{other}\n")


def test_same_note_is_not_queued_without_limit():
    text = "\n\n".join([NOTE] * 7) + "\n"
    spans = candidate_spans(text)
    pairs = select_pairs(text, spans, _fake_embed([text[s:e] for s, e in spans]))
    assert pairs
    assert len(pairs) < 21
    uses = {}
    for pair in pairs:
        for side in ("left", "right"):
            key = tuple(pair[side])
            uses[key] = uses.get(key, 0) + 1
            assert text[key[0] : key[1]] == NOTE
    assert max(uses.values()) <= 5


def test_decode_utf8_crlf_and_cp1251_and_utf16():
    assert decode_text("а\r\nб\r\n".encode()) == "а\nб\n"
    assert decode_text("Привет из старой записи.\n".encode("cp1251")) == "Привет из старой записи.\n"
    assert decode_text("Привет из старой записи.\n".encode("utf-16")) == "Привет из старой записи.\n"
    try:
        decode_text(b"\x00\x01")
    except Exception as exc:
        assert exc.code == "K002"
    else:
        raise AssertionError("expected K002")


def test_read_limited(monkeypatch):
    import kaimon.textio as textio

    monkeypatch.setattr(textio, "MAX_BYTES", 4)
    try:
        textio.read_limited([b"12345"])
    except Exception as exc:
        assert exc.code == "K003"
    else:
        raise AssertionError("expected K003")
