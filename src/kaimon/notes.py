from pathlib import Path

from kaimon.errors import AppError


def list_txt(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    if not folder.is_dir():
        raise AppError("K010", "The notes folder cannot be read.", status=500)
    try:
        entries = list(folder.iterdir())
    except OSError:
        raise AppError("K010", "The notes folder cannot be read.", status=500) from None
    names = [
        path.name
        for path in entries
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() == ".txt"
    ]
    names.sort(key=str.casefold)
    return names


def read_txt(folder: Path, name: str) -> bytes:
    if not isinstance(name, str) or name != Path(name).name or name.startswith(".") or not name.lower().endswith(".txt"):
        raise AppError("K008", "Only a .txt file can be opened.")
    try:
        root = folder.resolve()
        path = (folder / name).resolve()
    except OSError:
        raise AppError("K010", "The notes folder cannot be read.", status=500) from None
    if path != root and root not in path.parents:
        raise AppError("K008", "Only a .txt file can be opened.")
    if not path.is_file():
        raise AppError("K009", "The file is not in the notes folder.", status=404)
    try:
        return path.read_bytes()
    except OSError:
        raise AppError("K010", "The notes folder cannot be read.", status=500) from None
