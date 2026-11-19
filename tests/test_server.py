import json

from fastapi.testclient import TestClient

from kaimon.errors import ModelError
from kaimon.server import app

client = TestClient(app)


def _events(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_health_and_page():
    assert client.get("/api/health").json() == {"ok": True}
    page = client.get("/")
    assert page.status_code == 200
    assert "id=\"next\"" in page.text
    assert client.get("/languages/Russian.ini").status_code == 200
    missing = client.get("/languages/French.ini")
    assert missing.status_code == 404
    assert missing.json()["error"] == "K007"


def test_analyze_errors(monkeypatch):
    import kaimon.textio as textio

    monkeypatch.setattr(textio, "MAX_BYTES", 8)
    assert client.post("/api/analyze", data={"x": "1"}).json()["error"] == "K006"
    assert client.post("/api/analyze", files={"file": ("a.md", b"hello", "text/plain")}).json()["error"] == "K008"
    assert client.post("/api/analyze", files={"file": ("a.txt", b"   \n", "text/plain")}).json()["error"] == "K001"
    assert client.post("/api/analyze", files={"file": ("a.txt", b"a\0b", "text/plain")}).json()["error"] == "K002"
    assert client.post("/api/analyze", files={"file": ("a.txt", b"123456789", "text/plain")}).json()["error"] == "K003"


def test_analyze_returns_full_text(monkeypatch):
    seen = {}

    def fake(text, progress=None):
        seen["text"] = text
        if progress:
            progress("embed", 40, done=1, total=2)
        return [{"left": [0, 4], "right": [5, 9], "score": 0.9, "semantic": 0.9, "lexical": 0.9, "leftLen": 4, "rightLen": 4}]

    monkeypatch.setattr("kaimon.server.find_pairs", fake)
    body = "Привет\r\nэто длинная запись.\r\n".encode("cp1251")
    response = client.post("/api/analyze", files={"file": ("notes.txt", body, "text/plain")})
    assert response.status_code == 200
    events = _events(response)
    assert events[0]["step"] == "read"
    assert any(item["step"] == "embed" for item in events)
    payload = events[-1]
    assert payload["event"] == "result"
    assert payload["name"] == "notes.txt"
    assert payload["text"] == "Привет\nэто длинная запись.\n"
    assert seen["text"] == payload["text"]
    assert "\r" not in payload["text"]


def test_model_and_compare_errors(monkeypatch):
    def broken(text, progress=None):
        raise ModelError("missing")

    monkeypatch.setattr("kaimon.server.find_pairs", broken)
    response = client.post("/api/analyze", files={"file": ("a.txt", "привет мир, этой строки хватает для текста.\n".encode(), "text/plain")})
    assert response.status_code == 200
    assert _events(response)[-1]["error"] == "K004"

    def crash(text, progress=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("kaimon.server.find_pairs", crash)
    response = client.post("/api/analyze", files={"file": ("a.txt", "привет мир, этой строки хватает для текста.\n".encode(), "text/plain")})
    assert response.status_code == 200
    assert _events(response)[-1]["error"] == "K005"


def test_notes_folder(tmp_path, monkeypatch):
    monkeypatch.setattr("kaimon.server.FILES", tmp_path)
    monkeypatch.setattr("kaimon.server.DATA", tmp_path / "program")
    (tmp_path / "beta.txt").write_text("beta", encoding="utf-8")
    (tmp_path / "Alpha.TXT").write_text("alpha", encoding="utf-8")
    (tmp_path / "skip.md").write_text("no", encoding="utf-8")
    (tmp_path / ".hidden.txt").write_text("no", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "inside.txt").write_text("no", encoding="utf-8")
    assert client.get("/api/files").json()["files"] == ["Alpha.TXT", "beta.txt"]
    missing = client.post("/api/open", json={"name": "../secret.txt"})
    assert missing.status_code == 400
    assert missing.json()["error"] == "K008"
    absent = client.post("/api/open", json={"name": "gone.txt"})
    assert absent.status_code == 404
    assert absent.json()["error"] == "K009"

    def fake(text, progress=None):
        return []

    monkeypatch.setattr("kaimon.server.find_pairs", fake)
    opened = client.post("/api/open", json={"name": "beta.txt"})
    assert _events(opened)[-1]["text"] == "beta"
    blocked = tmp_path / "not-a-folder"
    blocked.write_text("x", encoding="utf-8")
    monkeypatch.setattr("kaimon.server.FILES", blocked)
    unreadable = client.get("/api/files")
    assert unreadable.status_code == 500
    assert unreadable.json()["error"] == "K010"


def test_draft_save_and_scan_cache(tmp_path, monkeypatch):
    files = tmp_path / "files"
    data = tmp_path / "data"
    files.mkdir()
    monkeypatch.setattr("kaimon.server.FILES", files)
    monkeypatch.setattr("kaimon.server.DATA", data)
    (files / "notes.txt").write_text("original\n", encoding="utf-8")
    calls = {"n": 0}

    def fake(text, progress=None):
        calls["n"] += 1
        return [{"left": [0, 4], "right": [5, 9], "score": 0.91, "semantic": 0.8, "lexical": 0.91, "leftLen": 4, "rightLen": 4}]

    monkeypatch.setattr("kaimon.server.find_pairs", fake)
    body = "заметка достаточно длинная для правки и повторного открытия.\n"
    pair = {"left": [0, 4], "right": [5, 9], "score": 0.5, "semantic": 0.5, "lexical": 0.8, "leftLen": 4, "rightLen": 4}
    stored = client.put("/api/draft", json={"name": "notes.txt", "text": body, "pairs": [pair]})
    assert stored.status_code == 200
    draft = client.get("/api/draft", params={"name": "notes.txt"})
    assert draft.json()["text"] == body
    saved = client.post("/api/save", json={"name": "notes.txt", "text": body, "pairs": [pair]})
    assert saved.status_code == 200
    assert (files / "notes.txt").read_text(encoding="utf-8") == body
    assert client.get("/api/draft", params={"name": "notes.txt"}).status_code == 404
    opened = client.post("/api/open", json={"name": "notes.txt"})
    assert _events(opened)[-1]["pairs"][0]["semantic"] == 0.5
    assert calls["n"] == 0
    (files / "other.txt").write_text("other text that is not cached yet.\n", encoding="utf-8")
    first = client.post("/api/open", json={"name": "other.txt"})
    assert _events(first)[-1]["pairs"][0]["score"] == 0.91
    second = client.post("/api/open", json={"name": "other.txt"})
    assert _events(second)[-1]["pairs"][0]["score"] == 0.91
    assert calls["n"] == 1
