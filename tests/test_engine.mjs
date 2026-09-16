import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {CONTEXTS, ROWS_PER_TASK, ROWS_BY_VERSION, ENGINE, ENGINE_V2, makeTask, runTask, runTaskCore,
  scanCurve, verifyTriple, isqrt, canonicalJSON, taskId, taskRows, subtasks, containerTask,
  overlappingIds, validateTask} from '../web/engine.mjs';

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

/* Engine v2 covers the same positions in 1024-row tasks. Its counters are the
 * sum, and its hits the concatenation, of its aligned v1 sub-tasks. */
assert.deepEqual(makeTask('c00', 128), {version: 1, engine: ENGINE, context: 'c00', row: '128', block: 0});
assert.equal(taskId(makeTask('c00', 128)), 'mg114-offset-v1:c00:128:0');
assert.equal(taskRows(makeTask('c00', 128)), 128);
assert.equal(ROWS_BY_VERSION[2], 1024);
assert.deepEqual(makeTask('c00', 1024, 0, 2), {version: 2, engine: ENGINE_V2, context: 'c00', row: '1024', block: 0});
assert.equal(taskId(makeTask('c00', 1024, 0, 2)), 'mg114-offset-v2:c00:1024:0');
assert.equal(taskRows(makeTask('c00', 1024, 0, 2)), 1024);
for (const bad of [{version: 2, engine: ENGINE, context: 'c00', row: '0', block: 0},
                   {version: 2, engine: ENGINE_V2, context: 'c00', row: '128', block: 0},
                   {version: 1, engine: ENGINE_V2, context: 'c00', row: '0', block: 0},
                   {version: 3, engine: ENGINE_V2, context: 'c00', row: '0', block: 0},
                   {version: '2', engine: ENGINE_V2, context: 'c00', row: '0', block: 0}])
  assert.throws(() => validateTask(bad), `accepted ${JSON.stringify(bad)}`);
assert.throws(() => makeTask('c00', 128, 0, 2));
assert.throws(() => makeTask('c00', 0, 0, 3));

{ // Overlap helpers mirror tools/search_core.py exactly.
  const v1 = makeTask('c05', 128 * 9, 1), container = containerTask(v1);
  assert.deepEqual([container.version, container.row, container.block], [2, '1024', 1]);
  assert.deepEqual(overlappingIds(v1), [taskId(container)]);
  const ids = overlappingIds(container);
  assert.equal(ids.length, 8);
  assert.ok(ids.includes(taskId(v1)));
  assert.deepEqual(containerTask(container), container);
  assert.deepEqual(subtasks(v1), [v1]);
  assert.deepEqual(subtasks(container).map(taskId), ids);
  for (const sub of subtasks(container)) assert.deepEqual(containerTask(sub), container);
}

{ // A sample of every context: whole v2 task == its concatenated sub-tasks.
  const counterKeys = Object.keys(runTaskCore(makeTask('c00', 0)).counters);
  for (const [index, c] of CONTEXTS.entries()) {
    const stride = BigInt(c.rowStrideV2);
    const row = (BigInt(c.totalRows) / BigInt(7 + index) / stride) * stride;
    const whole = runTaskCore(makeTask(c.id, row, index % c.blocks, 2));
    const parts = subtasks(whole.task).map(runTaskCore);
    assert.ok(parts.length >= 1 && parts.length <= 8);
    assert.ok(parts.every(p => p.task.version === 1));
    assert.equal(whole.id, `${ENGINE_V2}:${c.id}:${row}:${index % c.blocks}`);
    for (const key of counterKeys)
      assert.equal(whole.counters[key], parts.reduce((sum, p) => sum + p.counters[key], 0), `${whole.id} ${key}`);
    assert.equal(canonicalJSON(whole.hits), canonicalJSON(parts.flatMap(p => p.hits)));
  }
}

{ // The final v2 task of a context is truncated at its row limit.
  const c = CONTEXTS[0], stride = BigInt(c.rowStrideV2);
  const last = (BigInt(c.totalRows) - 1n) / stride * stride;
  const task = makeTask(c.id, last, 0, 2), parts = subtasks(task);
  assert.ok(parts.length <= 8);
  assert.equal(runTaskCore(task).counters.generators,
    parts.reduce((sum, p) => sum + runTaskCore(p).counters.generators, 0));
}

{ // Full v2 receipts, including digests, agree with the Python reference.
  const v2Tasks = [makeTask('c00', 0, 0, 2), makeTask('c40', 1024 * 3, 2, 2),
    makeTask('c80', (BigInt(CONTEXTS[80].totalRows) - 1n) / 1024n * 1024n, CONTEXTS[80].blocks - 1, 2)];
  const reference = spawnSync(process.env.PYTHON || 'python3', ['-c',
    "import json,sys;sys.path.insert(0,'tools');import search_core as e;print(json.dumps([e.run_task(t) for t in json.load(sys.stdin)]))"],
    {cwd: fileURLToPath(new URL('..', import.meta.url)), input: JSON.stringify(v2Tasks), encoding: 'utf8', maxBuffer: 8 * 1024 * 1024});
  assert.equal(reference.status, 0, reference.stderr);
  const expectedV2 = JSON.parse(reference.stdout);
  for (let i = 0; i < v2Tasks.length; i++)
    assert.equal(canonicalJSON(await runTask(v2Tasks[i])), canonicalJSON(expectedV2[i]), `JS/Python v2 mismatch ${expectedV2[i].id}`);
  console.log(JSON.stringify({ok: true, engineV2Contexts: CONTEXTS.length, crossLanguageV2Tasks: v2Tasks.length}));
}
