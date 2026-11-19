import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r"\{[a-zA-Z0-9_]+\}")


def _load(name):
    code = ""
    entries = {}
    for line in (ROOT / "languages" / name).read_text(encoding="utf-8").splitlines():
        if line.startswith(";"):
            if "code" in line:
                code = line.split("=", 1)[1].strip()
            continue
        if not line.strip():
            continue
        ident, english, translation = line.split(" = ", 2)
        entries[ident] = (english, translation)
    return code, entries


def test_catalogs_match():
    en_code, english = _load("English.ini")
    ru_code, russian = _load("Russian.ini")
    assert en_code == "en"
    assert ru_code == "ru"
    assert set(english) == set(russian)
    for ident, (en_text, en_translation) in english.items():
        ru_text, ru_translation = russian[ident]
        assert en_text == ru_text
        assert PLACEHOLDER.findall(en_text) == PLACEHOLDER.findall(en_translation)
        assert PLACEHOLDER.findall(en_text) == PLACEHOLDER.findall(ru_translation)
        assert ru_translation.strip()
