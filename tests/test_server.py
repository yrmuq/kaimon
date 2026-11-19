from fastapi.testclient import TestClient

from kaimon.errors import ModelError
from kaimon.server import app

client = TestClient(app)


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

    def fake(text):
        seen["text"] = text
        return [{"left": [0, 4], "right": [5, 9], "score": 0.9, "semantic": 0.9, "lexical": 0.9, "leftLen": 4, "rightLen": 4}]

    monkeypatch.setattr("kaimon.server.find_pairs", fake)
    body = "Привет\r\nэто длинная запись.\r\n".encode("cp1251")
    response = client.post("/api/analyze", files={"file": ("notes.txt", body, "text/plain")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "notes.txt"
    assert payload["text"] == "Привет\nэто длинная запись.\n"
    assert seen["text"] == payload["text"]
    assert "\r" not in payload["text"]


def test_model_and_compare_errors(monkeypatch):
    def broken(text):
        raise ModelError("missing")

    monkeypatch.setattr("kaimon.server.find_pairs", broken)
    response = client.post("/api/analyze", files={"file": ("a.txt", "привет мир, этой строки хватает для текста.\n".encode(), "text/plain")})
    assert response.status_code == 500
    assert response.json()["error"] == "K004"

    def crash(text):
        raise RuntimeError("boom")

    monkeypatch.setattr("kaimon.server.find_pairs", crash)
    response = client.post("/api/analyze", files={"file": ("a.txt", "привет мир, этой строки хватает для текста.\n".encode(), "text/plain")})
    assert response.status_code == 500
    assert response.json()["error"] == "K005"
