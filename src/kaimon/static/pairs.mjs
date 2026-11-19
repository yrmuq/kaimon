export function mapSpan(span, cut, endOld, insertLen) {
  if (!span) return null;
  const start = span[0];
  const end = span[1];
  if (start >= end) return null;
  const delta = insertLen - (endOld - cut);
  if (end <= cut) return [start, end];
  if (start >= endOld) return [start + delta, end + delta];
  const newStart = start <= cut ? start : cut + insertLen;
  const newEnd = end >= endOld ? end + delta : cut;
  if (newStart >= newEnd) return null;
  return [newStart, newEnd];
}

export function overlaps(a, b) {
  return a[0] < b[1] && b[0] < a[1];
}

export function mapPoint(pos, cut, endOld, insertLen) {
  const delta = insertLen - (endOld - cut);
  if (pos <= cut) return pos;
  if (pos >= endOld) return pos + delta;
  return cut;
}

export function diffChange(oldText, newText) {
  let cut = 0;
  const oldLen = oldText.length;
  const newLen = newText.length;
  while (cut < oldLen && cut < newLen && oldText[cut] === newText[cut]) cut += 1;
  let endOld = oldLen;
  let endNew = newLen;
  while (endOld > cut && endNew > cut && oldText[endOld - 1] === newText[endNew - 1]) {
    endOld -= 1;
    endNew -= 1;
  }
  return { cut, endOld, insertLen: endNew - cut };
}

export function remapPair(pair, cut, endOld, insertLen) {
  return {
    ...pair,
    left: mapSpan(pair.left, cut, endOld, insertLen),
    right: mapSpan(pair.right, cut, endOld, insertLen),
  };
}

export function pairUsable(pair, textLength) {
  if (!pair?.left || !pair?.right) return false;
  const llen = pair.left[1] - pair.left[0];
  const rlen = pair.right[1] - pair.right[0];
  if (llen < 20 || rlen < 20) return false;
  if (llen < pair.leftLen * 0.4 || rlen < pair.rightLen * 0.4) return false;
  if (overlaps(pair.left, pair.right)) return false;
  if (pair.left[0] < 0 || pair.right[0] < 0) return false;
  if (pair.left[1] > textLength || pair.right[1] > textLength) return false;
  return true;
}
