import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {CONTEXTS, ROWS_PER_TASK, makeTask, runTask, scanCurve, verifyTriple, isqrt, canonicalJSON} from '../web/engine.mjs';

for (const n of [0n, 1n, 2n, 3n, 10n ** 18n, 2n ** 127n, 10n ** 60n]) {
  for (const delta of [-1n, 0n, 1n]) {
    const square = n * n + delta;
    if (square < 0n) continue;
    const r = isqrt(square); assert(r * r <= square); assert((r + 1n) ** 2n > square);
  }
}
for (const [k, triple] of [[39, [-159380n, 134476n, 117367n]], [84, [41639611n, -41531726n, -8241191n]], [30, [2220422932n, -2218888517n, -283059965n]], [75, [-435203231n, 435203083n, 4381159n]]]) {
  const abs = n => n < 0n ? -n : n;
  const xyz = triple.slice().sort((a, b) => abs(a) < abs(b) ? -1 : 1);
  const [z, x, y] = xyz, d = abs(x + y), r = ((z % d) + d) % d, q = (z - r) / d;
  const found = scanCurve(k, d, r, q, q);
  assert.equal(found.hits.length, 1); assert(verifyTriple(found.hits[0].xyz, k));
}
assert(!verifyTriple(['1', '2', '3']));
assert(!verifyTriple(['-0', '1', '1'], 2));
assert.throws(() => makeTask('c00', '01'));
assert.throws(() => makeTask('c00', 0, -1));
assert.throws(() => makeTask('c00', Number.MAX_SAFE_INTEGER + 1));

const tasks = CONTEXTS.flatMap(c => [makeTask(c.id, 0, 0),
  makeTask(c.id, (BigInt(c.totalRows) - 1n) / BigInt(ROWS_PER_TASK) * BigInt(ROWS_PER_TASK), c.blocks - 1),
  makeTask(c.id, BigInt(c.totalRows) / 7n / BigInt(ROWS_PER_TASK) * BigInt(ROWS_PER_TASK), Math.floor(c.blocks / 2))]);
const python = spawnSync(process.env.PYTHON || 'python3', ['-c',
  "import json,sys;sys.path.insert(0,'tools');import search_core as e;print(json.dumps([e.run_task(t) for t in json.load(sys.stdin)]))"],
  {cwd: fileURLToPath(new URL('..', import.meta.url)), input: JSON.stringify(tasks), encoding: 'utf8', maxBuffer: 8 * 1024 * 1024});
assert.equal(python.status, 0, python.stderr);
const expected = JSON.parse(python.stdout);
let curves = 0, points = 0, exact = 0;
for (let i = 0; i < tasks.length; i++) {
  const actual = await runTask(tasks[i]);
  assert.equal(canonicalJSON(actual), canonicalJSON(expected[i]), `JS/Python mismatch ${actual.id}`);
  curves += actual.counters.curves; points += actual.counters.quotient_points; exact += actual.counters.exact_tests;
}
console.log(JSON.stringify({ok: true, crossLanguageTasks: tasks.length, curves, quotientPoints: points, exactTests: exact}));
