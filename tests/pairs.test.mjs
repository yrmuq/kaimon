import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { diffChange, mapSpan, pairUsable } from "../src/kaimon/static/pairs.mjs";

const cases = JSON.parse(readFileSync(new URL("./map_cases.json", import.meta.url), "utf8"));

test("mapSpan matches the shared cases", () => {
  for (const item of cases) {
    assert.deepEqual(mapSpan(item.span, item.cut, item.endOld, item.insertLen), item.expect, item.name);
  }
});

test("diffChange sees one replacement", () => {
  assert.deepEqual(diffChange("abcdef", "abdef"), { cut: 2, endOld: 3, insertLen: 0 });
  assert.deepEqual(diffChange("abcdef", "abXcdef"), { cut: 2, endOld: 2, insertLen: 1 });
});

test("pairUsable keeps a paraphrase and drops a deleted side", () => {
  const pair = { left: [0, 100], right: [200, 300], leftLen: 100, rightLen: 100, score: 0.9 };
  assert.equal(pairUsable(pair, 400), true);
  assert.equal(pairUsable({ ...pair, left: [0, 30] }, 400), false);
  assert.equal(pairUsable({ ...pair, right: [80, 180] }, 400), false);
});
