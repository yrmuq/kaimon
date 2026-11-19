# Map

- `src/kaimon/server.py` — upload, notes folder, drafts, health, the page, and language files.
- `src/kaimon/notes.py` — which `.txt` files the side list may open.
- `src/kaimon/store.py` — saved scans and unsaved edits on disk.
- `src/kaimon/textio.py` — size limit and decoding of the uploaded `.txt`.
- `src/kaimon/segments.py` — search-only spans. Paragraphs where blank lines exist, and line windows where they do not.
- `src/kaimon/pairs.py` — similarity, which pairs are kept, and how a highlight moves after an edit.
- `src/kaimon/analyze.py` — connects spans to the local embedding model.
- `src/kaimon/errors.py` — error codes.
- `src/kaimon/static/` — the notes list and the two panels. `pairs.mjs` is the browser copy of span movement.
- `languages/` — `English.ini` and `Russian.ini`.
- `tests/` — decoding, spans, pairing, catalogs, and HTTP errors.
- `Dockerfile`, `docker-compose.yml`, `.env` — container that pulls the `dev` image. Notes and program data are mounted separately.
- `.github/workflows/checks.yml` — tests, then the dev image and the dev draft. It does not publish `:latest`.
