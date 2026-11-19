# Map

- `src/kaimon/server.py` — upload, health, the page, and language files.
- `src/kaimon/textio.py` — size limit and decoding of the uploaded `.txt`.
- `src/kaimon/segments.py` — search-only spans. Paragraphs where blank lines exist, and line windows where they do not.
- `src/kaimon/pairs.py` — similarity, which pairs are kept, and how a highlight moves after an edit.
- `src/kaimon/analyze.py` — connects spans to the local embedding model.
- `src/kaimon/errors.py` — error codes.
- `src/kaimon/static/` — the two panels. `pairs.mjs` is the browser copy of span movement.
- `languages/` — `English.ini` and `Russian.ini`.
- `tests/` — decoding, spans, pairing, catalogs, and HTTP errors.
- `Dockerfile`, `docker-compose.yml`, `.env` — container on the external `homelab` network. Compose pulls the `dev` image.
- `.github/workflows/checks.yml` — tests, then the dev image and the dev draft. It does not publish `:latest`.
