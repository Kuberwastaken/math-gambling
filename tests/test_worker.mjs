/* Fault injection uses a known k=39 identity only. Production remains fixed at
 * 114. Exercise the real scan callback, task accumulator, hash and worker host. */
import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs/promises";
import vm from "node:vm";
import {scanCurve, verifyTriple} from "../web/engine.mjs";

const xyz = ["-159380", "134476", "117367"];
const d = 24904n, z = 117367n, r = z % d, q = (z - r) / d;

test("scan publishes a checked identity synchronously and isolates observers", () => {
  let received = 0;
  const result = scanCurve(39, d, r, q, q, {onHit(hit) {
    assert.equal(verifyTriple(hit.xyz, 39), true);
    received++;
    hit.xyz[0] = "0";
    throw Error("a failed observer must not alter the result");
  }});
  assert.equal(received, 1);
  assert.equal(result.hits.length, 1);
  assert.equal(verifyTriple(result.hits[0].xyz, 39), true);
});

const engineSource = await fs.readFile(new URL("../web/engine.mjs", import.meta.url), "utf8");
const workerSource = await fs.readFile(new URL("../web/search-worker.mjs", import.meta.url), "utf8");

for (const failure of ["hash", "later-row"]) {
  test(`worker emits a positive before ${failure} failure, without negative coverage`, async () => {
    const first = engineSource.indexOf("function runRow("),
      last = engineSource.indexOf("export function runTaskCore", first);
    assert.ok(first >= 0 && last > first);
    // Only replace the fixed 114 row producer with one known-positive row.
    // The real scan callback and every later stage run without substitution.
    const fixture = engineSource.slice(0, first) + `
      function runRow(task, c, row, onHit) {
        if (row === 0n) return scanCurve(39, ${d}n, ${r}n, ${q}n, ${q}n, {onHit});
        if (__laterFailure) throw Error("injected later row failure");
        return {counters: emptyCounters(), hits: []};
      }
    ` + engineSource.slice(last);
    const context = vm.createContext({
      TextEncoder,
      __laterFailure: failure === "later-row",
      crypto: {subtle: {digest: async () => { throw Error("injected digest failure"); }}},
    });
    vm.runInContext(fixture.replace(/^[ \t]*export /gm, "") + `
      globalThis.__engine = {runTask, makeTask, ENGINE,
        verifyTriple: xyz => verifyTriple(xyz, 39)};
    `, context);
    const messages = [], self = {postMessage(value) { messages.push(structuredClone(value)); }};
    vm.runInNewContext(workerSource.replace(
      /import \{[^}]+\} from '\.\/engine\.mjs';/,
      "const {runTask, verifyTriple, ENGINE} = __engine;",
    ), {__engine: context.__engine, self, performance});
    await self.onmessage({data: {type: "start", task: context.__engine.makeTask("c00", 0)}});
    assert.deepEqual(messages.map(message => message.type), ["ready", "identity", "error"]);
    assert.equal(verifyTriple(messages[1].hit.xyz, 39), true);
    assert.equal(messages.some(message => message.type === "result"), false);
    assert.match(messages[2].message, failure === "hash" ? /digest failure/ : /later row failure/);
  });
}
