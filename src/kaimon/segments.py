MIN_CHARS = 40


def iter_lines(text: str) -> list[tuple[int, int, bool]]:
    lines = []
    start = 0
    n = len(text)
    while start < n:
        nl = text.find("\n", start)
        if nl < 0:
            end = n
            lines.append((start, end, text[start:end].strip() == ""))
            break
        lines.append((start, nl + 1, text[start:nl].strip() == ""))
        start = nl + 1
    return lines


def _content_end(text: str, end: int) -> int:
    if end > 0 and text[end - 1 : end] == "\n":
        return end - 1
    return end


def paragraph_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    buf: list[tuple[int, int, bool]] = []

    def flush() -> None:
        if not buf:
            return
        start = buf[0][0]
        end = _content_end(text, buf[-1][1])
        if end > start:
            spans.append((start, end))
        buf.clear()

    for line in iter_lines(text):
        if line[2]:
            flush()
        else:
            buf.append(line)
    flush()
    return spans


def _regions(lines: list[tuple[int, int, bool]]) -> list[list[tuple[int, int, bool]]]:
    regions = []
    i = 0
    while i < len(lines):
        if lines[i][2]:
            i += 1
            continue
        j = i
        while j < len(lines) and not lines[j][2]:
            j += 1
        regions.append(lines[i:j])
        i = j
    return regions


def window_spans(text: str, sizes: tuple[tuple[int, int], ...] = ((4, 2), (8, 4), (16, 8))) -> list[tuple[int, int]]:
    spans = []
    for region in _regions(iter_lines(text)):
        for size, stride in sizes:
            if len(region) <= size:
                continue
            for k in range(0, len(region) - size + 1, stride):
                start = region[k][0]
                end = _content_end(text, region[k + size - 1][1])
                if end > start:
                    spans.append((start, end))
    return spans


def _substantial(text: str, span: tuple[int, int]) -> bool:
    chunk = text[span[0] : span[1]]
    count = 0
    for ch in chunk:
        if not ch.isspace():
            count += 1
            if count >= MIN_CHARS:
                return True
    return False


def _dedupe(spans: list[tuple[int, int]], text: str) -> list[tuple[int, int]]:
    seen = set()
    kept = []
    for span in spans:
        if span in seen or not _substantial(text, span):
            continue
        seen.add(span)
        kept.append(span)
    return kept


def candidate_spans(text: str) -> list[tuple[int, int]]:
    base = _dedupe(paragraph_spans(text) + window_spans(text, ((8, 4), (16, 8))), text)
    short = _dedupe(window_spans(text, ((4, 2),)), text)
    # shortcut: drop 4-line windows above 4500 candidates, raise the cap if short duplicates in huge files are missed
    if len(base) + len(short) > 4500:
        return base
    return _dedupe(base + short, text)
