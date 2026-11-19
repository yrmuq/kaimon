## Required Behavior

- Both panels edit one shared document. Search spans are not records and must never be written back as a cut-up file.
- Next only scrolls and highlights a pair. It must not select text or delete anything.
- A pair is skipped when a highlight collapsed, the two sides overlap, or one side lost most of its original length. Do not drop a pair only because a paraphrase has low word overlap.
- Uploads are normalized to UTF-8 and `\n` before editing. UTF-8 is tried first, then Windows-1251; UTF-16 is accepted only with a BOM. The download is that normalized text, not the original bytes.

## External Compatibility Constraints

- Semantic comparison uses the local model `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` baked into the image. Notes are Russian and may be paraphrased, and the container must not call an external API.
- Compose attaches only to the external Docker network `homelab`. Do not add a default network or a database service.
