import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import test from 'node:test';
import {CONTEXTS, canonicalJSON, makeTask, norm, offsetBase, runTask, shellInterval} from '../web/engine.mjs';

test('pruned JS results retain the frozen unpruned corpus digest and logical empty tasks', async () => {
  const results = [];
  for (const c of CONTEXTS) {
    for (const [row, block] of [[0n, 0],
      [(BigInt(c.totalRows) - 1n) / 128n * 128n, c.blocks - 1],
      [BigInt(c.totalRows) / 7n / 128n * 128n, Math.floor(c.blocks / 2)]]) {
      results.push(await runTask(makeTask(c.id, row, block)));
    }
  }
  assert.equal(createHash('sha256').update(canonicalJSON(results)).digest('hex'),
    'b8db130a82bd3cfd37f3d99e4de84c112b6ffb9176f51d12618b3a9a7f9bb780');
  const empty = results.filter(r => r.counters.generators === r.counters.outside_shell);
  assert.equal(empty.length, 162);
  assert(empty.every(r => r.counters.generators > 0));
});

test('integer interval bounds retain all actual shell members, including huge coefficients', () => {
  let state = 114;
  const random = n => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state % n; };
  for (let iteration = 0; iteration < 3000; iteration++) {
    const ell = [1n, 5n, 25n][random(3)], scale = [1n, 10n ** 6n, 10n ** 20n][random(3)];
    const b = BigInt(random(61) - 30) * scale, c = BigInt(random(61) - 30) * scale;
    const base = offsetBase(ell, b, c), tlo = random(8224) - 32, thi = tlo + random(16);
    const constant = 114n * b ** 3n + 12996n * c ** 3n, linear = 342n * b * c;
    const values = Array.from({length: thi - tlo + 1}, (_, i) => norm(base + ell * BigInt(tlo + i), b, c));
    const n0 = values[random(values.length)], n1 = values[random(values.length)];
    const lower = (n0 < n1 ? n0 : n1) + BigInt(random(3) - 1);
    let upper = (n0 > n1 ? n0 : n1) + BigInt(random(3) - 1);
    if (upper <= lower) upper = lower + 1n;
    const [first, last] = shellInterval(base, ell, tlo, thi, lower, upper, constant, linear);
    assert(first >= tlo && first <= thi && last >= tlo - 1 && last <= thi);
    values.forEach((n, i) => {
      const t = tlo + i, a = base + ell * BigInt(t);
      assert.equal(a * a * a - linear * a + constant, n);
      if (lower < n && n <= upper) assert(t >= first && t <= last);
    });
  }
});

test('strict/inclusive shell edges and nonmonotone fallback remain exact', () => {
  assert.deepEqual(shellInterval(0n, 1n, -8, 7, -27n, 8n, 0n, 0n), [-2, 2]);
  assert.deepEqual(shellInterval(0n, 1n, 0, 15, 3375n, 4000n, 0n, 0n), [0, -1]);
  assert.deepEqual(shellInterval(0n, 1n, 0, 15, -2n, -1n, 0n, 0n), [0, -1]);
  assert.deepEqual(shellInterval(0n, 1n, 0, 15, 10500n, 11000n, 13110n, 342n), [0, 15]);
  assert.throws(() => shellInterval(0n, 5n, 0, 15, 10n ** 30n, 2n * 10n ** 30n, 1n, 0n), /divisibility/);
});
