from kaimon.errors import AppError

# shortcut: reject NUL files instead of guessing UTF-16 without a BOM, upgrade if real notes arrive as BOM-less UTF-16
MAX_BYTES = 8 * 1024 * 1024


def read_limited(chunks) -> bytes:
    total = 0
    parts = []
    for block in chunks:
        total += len(block)
        if total > MAX_BYTES:
            raise AppError("K003", "The file is larger than 8 MB.")
        parts.append(block)
    return b"".join(parts)


def decode_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    elif b"\x00" in data:
        raise AppError("K002", "The file contains NUL bytes and is not a text file.")
    else:
        raw = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1251")
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.strip() == "":
        raise AppError("K001", "The file is empty.")
    return text
