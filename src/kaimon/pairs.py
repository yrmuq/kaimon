import re
from collections import defaultdict

import numpy as np
from rapidfuzz.fuzz import ratio

SEMANTIC_MIN = 0.72
LEXICAL_MIN = 0.76
TOP_K = 6
MAX_PAIRS = 300
SIDE_CAP = 5
WORD = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+")


def map_span(span, cut: int, end_old: int, insert_len: int):
    if not span:
        return None
    start, end = span
    if start >= end:
        return None
    delta = insert_len - (end_old - cut)
    if end <= cut:
        return (start, end)
    if start >= end_old:
        return (start + delta, end + delta)
    new_start = start if start <= cut else cut + insert_len
    new_end = end + delta if end >= end_old else cut
    if new_start >= new_end:
        return None
    return (new_start, new_end)


def _words(text: str) -> list[str]:
    return [w.casefold() for w in WORD.findall(text)]


def _shingles(tokens: list[str], n: int = 4) -> set[str]:
    if not tokens:
        return set()
    if len(tokens) < n:
        return {" ".join(tokens)}
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _overlap_frac(a, b) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    shorter = min(a[1] - a[0], b[1] - b[0])
    if shorter <= 0:
        return 0.0
    return inter / shorter


def _spans_overlap(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _same_hit(left_a, right_a, left_b, right_b) -> bool:
    direct = _overlap_frac(left_a, left_b) >= 0.6 and _overlap_frac(right_a, right_b) >= 0.6
    swapped = _overlap_frac(left_a, right_b) >= 0.6 and _overlap_frac(right_a, left_b) >= 0.6
    return direct or swapped


def lexical_candidates(snippets: list[str]) -> set[tuple[int, int]]:
    sets = [_shingles(_words(text)) for text in snippets]
    postings = defaultdict(list)
    df = defaultdict(int)
    for i, shingles in enumerate(sets):
        for sh in shingles:
            postings[sh].append(i)
            df[sh] += 1
    shared = defaultdict(int)
    for i, shingles in enumerate(sets):
        for sh in shingles:
            if df[sh] > 40:
                continue
            for j in postings[sh]:
                if j <= i:
                    continue
                shared[(i, j)] += 1
    chosen = set()
    for (i, j), inter in shared.items():
        union = len(sets[i]) + len(sets[j]) - inter
        if union and inter / union >= 0.55:
            chosen.add((i, j))
    grouped = defaultdict(list)
    for i, text in enumerate(snippets):
        key = " ".join(_words(text))
        if key:
            grouped[key].append(i)
    for indexes in grouped.values():
        if len(indexes) < 2:
            continue
        ordered = sorted(indexes)
        for a, i in enumerate(ordered):
            for j in ordered[a + 1 : a + 1 + SIDE_CAP]:
                chosen.add((i, j) if i < j else (j, i))
    return chosen


def select_pairs(text: str, spans: list[tuple[int, int]], vectors: np.ndarray) -> list[dict]:
    n = len(spans)
    if n < 2:
        return []
    snippets = [text[s:e] for s, e in spans]
    sims = vectors @ vectors.T
    chosen = lexical_candidates(snippets)
    for i in range(n):
        row = sims[i]
        if n == 1:
            continue
        k = min(TOP_K, n - 1)
        idx = np.argpartition(row, -k)[-k:]
        order = idx[np.argsort(row[idx])[::-1]]
        for j in order:
            j = int(j)
            if i == j or float(row[j]) < SEMANTIC_MIN:
                continue
            chosen.add((i, j) if i < j else (j, i))

    raw = []
    for i, j in chosen:
        if _spans_overlap(spans[i], spans[j]):
            continue
        semantic = float(sims[i, j])
        lexical = ratio(snippets[i], snippets[j]) / 100.0
        if semantic < SEMANTIC_MIN and lexical < LEXICAL_MIN:
            continue
        left, right = (i, j) if spans[i][0] <= spans[j][0] else (j, i)
        raw.append(
            {
                "left": spans[left],
                "right": spans[right],
                "score": max(semantic, lexical),
                "semantic": semantic,
                "lexical": lexical,
            }
        )
    raw.sort(key=lambda item: (item["score"], (item["left"][1] - item["left"][0]) + (item["right"][1] - item["right"][0])), reverse=True)

    kept = []
    uses = defaultdict(int)
    for item in raw:
        if any(_same_hit(item["left"], item["right"], prev["left"], prev["right"]) for prev in kept):
            continue
        if uses[item["left"]] >= SIDE_CAP or uses[item["right"]] >= SIDE_CAP:
            continue
        kept.append(item)
        uses[item["left"]] += 1
        uses[item["right"]] += 1
        # shortcut: keep at most 300 pairs, raise it if a file has more real duplicates than the queue shows
        if len(kept) >= MAX_PAIRS:
            break

    result = []
    for item in kept:
        left = item["left"]
        right = item["right"]
        result.append(
            {
                "left": [left[0], left[1]],
                "right": [right[0], right[1]],
                "score": round(item["score"], 4),
                "semantic": round(item["semantic"], 4),
                "lexical": round(item["lexical"], 4),
                "leftLen": left[1] - left[0],
                "rightLen": right[1] - right[0],
            }
        )
    return result
