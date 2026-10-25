// Regression test: Split may only be offered when both player cards are the
// same rank. A "pair of tens" must deal two identical faces (Q,Q or K,K),
// never Q,10 — that hand once showed an enabled Split button.
//
// Run with: node --test
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { webcrypto } from "node:crypto";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const start = html.indexOf("<script>") + "<script>".length;
const end = html.indexOf("</script>", start);
const appScript = html.slice(start, end);

// Minimal DOM stand-ins: just enough for the script to load and deal hands.
function element() {
  return {
    hidden: false, disabled: false, innerHTML: "", textContent: "", value: "",
    dataset: {}, style: {}, classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {}, appendChild() {}, remove() {}, select() {},
    setAttribute() {}, getAttribute: () => null,
    querySelectorAll: () => [],
  };
}
function makeContext() {
  const els = {};
  const store = new Map();
  const sandbox = {
    document: {
      getElementById: (id) => (els[id] = els[id] || element()),
      querySelectorAll: () => [],
      createElement: element,
      addEventListener() {},
      body: element(),
    },
    window: { addEventListener() {} },
    navigator: { userAgent: "node-test" },
    localStorage: {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: (k) => store.delete(k),
    },
    crypto: webcrypto,
    fetch: () => Promise.reject(new Error("no server in tests")),
    setTimeout: () => 0, clearTimeout() {},
    console,
  };
  const ctx = vm.createContext(sandbox);
  vm.runInContext(appScript, ctx);
  return { ctx, els };
}

const get = (ctx, expr) => vm.runInContext(expr, ctx);

test("split is only offered when both cards are the same rank", () => {
  const { ctx, els } = makeContext();
  for (const mode of ["random", "pair", "hard", "soft"]) {
    get(ctx, `S.mode = ${JSON.stringify(mode)};`);
    for (let i = 0; i < 2000; i++) {
      get(ctx, "deal()");
      const { row, type, r1, r2 } = get(ctx,
        "({ row: current.row, type: rowType(current.row), r1: current.cards[0].r, r2: current.cards[1].r })");
      const hand = `${row} dealt ${r1},${r2} (mode ${mode})`;
      if (els.aSplit.disabled === false) {
        assert.equal(r1, r2, `Split offered on a non-pair: ${hand}`);
      }
      if (type === "pair") {
        assert.equal(r1, r2, `Pair row dealt mismatched ranks: ${hand}`);
        assert.equal(els.aSplit.disabled, false, `Split not offered on a real pair: ${hand}`);
      } else {
        assert.equal(els.aSplit.disabled, true, `Split offered on a ${type} hand: ${hand}`);
      }
    }
  }
});

test("a pair of tens always shows two identical faces", () => {
  const { ctx } = makeContext();
  get(ctx, 'S.mode = "pair";');
  let tenPairs = 0;
  for (let i = 0; i < 3000 && tenPairs < 50; i++) {
    get(ctx, "deal()");
    const { row, r1, r2 } = get(ctx,
      "({ row: current.row, r1: current.cards[0].r, r2: current.cards[1].r })");
    if (row !== "P9") continue;
    tenPairs++;
    assert.equal(r1, r2, `Ten-pair dealt ${r1},${r2} — must be the same face`);
  }
  assert.ok(tenPairs >= 50, `only saw ${tenPairs} ten-pair deals; expected at least 50`);
});
