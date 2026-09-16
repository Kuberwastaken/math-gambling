/* The browser must treat one position as covered whichever engine version
 * verified it: v1 coverage stays at data/coverage/, v2 coverage is published
 * separately at data/coverage/v2/ and is optional while it is being rolled out.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import {createHash, webcrypto} from 'node:crypto';
import {CONTEXTS, ENGINE, ENGINE_V2, containerTask, makeTask, overlappingIds, subtasks, taskId} from '../web/engine.mjs';
import {createDualCoverageClient, createV2CoverageClient, validateManifestV2} from '../web/coverage-v2.mjs';
if (!globalThis.crypto) globalThis.crypto = webcrypto;
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

/* Flat shard-v1 layout, as the published v1 index still uses for old clients. */
function flatFixture(ids = {}, engine = ENGINE) {
  const files = new Map(), shards = {};
  let count = 0;
  for (const c of CONTEXTS) {
    const tasks = [...(ids[c.id] || [])].sort();
    const bytes = JSON.stringify({schema: 'math-gambling-coverage-shard-v1', engine, context: c.id, tasks}, null, 2) + '\n';
    const sha256 = digest(bytes);
    files.set(`${c.id}-${sha256}.json`, bytes);
    shards[c.id] = {file: `${c.id}-${sha256}.json`, sha256, count: tasks.length};
    count += tasks.length;
  }
  const index = {schema: 'math-gambling-coverage-v1', engine, revision: count,
    verified_task_count: count, updated_at: '2026-09-17T00:00:00Z', shards};
  files.set('index.json', JSON.stringify(index));
  return {files, index};
}

/* Chunked context-v2 layout, as the live publisher emits. */
function chunkedFixture(ids = {}, engine = ENGINE_V2) {
  const files = new Map(), shards = {};
  const write = (prefix, payload, count) => {
    const bytes = JSON.stringify(payload, null, 2) + '\n', sha256 = digest(bytes);
    files.set(`${prefix}-${sha256}.json`, bytes);
    return {file: `${prefix}-${sha256}.json`, sha256, count};
  };
  let total = 0;
  for (const c of CONTEXTS) {
    const own = [...(ids[c.id] || [])], buckets = {};
    for (const id of own) (buckets[digest(id).slice(0, 2)] ||= []).push(id);
    for (const [bucket, list] of Object.entries(buckets))
      buckets[bucket] = [write(`${c.id}-b${bucket}`, {schema: 'math-gambling-coverage-chunk-v2',
        engine, context: c.id, bucket, tasks: list.sort()}, list.length)];
    shards[c.id] = write(c.id, {schema: 'math-gambling-coverage-context-v2', engine, context: c.id, buckets}, own.length);
    total += own.length;
  }
  const index = {schema: 'math-gambling-coverage-v2', engine, revision: total,
    verified_task_count: total, updated_at: '2026-09-17T00:00:00Z', shards};
  files.set('index.json', JSON.stringify(index));
  return {files, index};
}

function host({v1 = flatFixture(), v2 = null} = {}) {
  let clock = 1;
  const requested = [];
  const client = createDualCoverageClient(new URL('https://example.test/math-gambling/'), {
    now: () => clock,
    fetcher: async url => {
      const path = url.pathname.replace('/math-gambling/data/coverage/', '');
      requested.push(path);
      const [source, name] = path.startsWith('v2/') ? [v2, path.slice(3)] : [v1, path];
      const body = source?.files.get(name);
      return new Response(body ?? 'missing', {status: body == null ? 404 : 200});
    },
  });
  return {client, requested, advance(ms = 61000) { clock += ms; }};
}

const v2Task = makeTask('c00', 1024, 0, 2);
const [firstSub, , thirdSub] = subtasks(v2Task);

test('a v2 proposal is excluded by v2 coverage and by any overlapping v1 coverage', async () => {
  const fresh = host({v2: chunkedFixture()});
  await fresh.client.refresh(true);
  assert.equal(await fresh.client.has(v2Task), false);

  const ownId = host({v2: chunkedFixture({c00: [taskId(v2Task)]})});
  assert.equal(await ownId.client.has(v2Task), true);
  assert.equal(ownId.client.revisionV2, 1);

  // One verified v1 sub-task already covers those 128 of the 1024 rows.
  const overlap = host({v1: flatFixture({c00: [taskId(thirdSub)]}), v2: chunkedFixture()});
  assert.equal(await overlap.client.has(v2Task), true);
  assert.equal(await overlap.client.has(makeTask('c00', 1024 * 2, 0, 2)), false);
});

test('a v1 task is excluded by the v2 task containing it', async () => {
  const h = host({v1: flatFixture(), v2: chunkedFixture({c00: [taskId(v2Task)]})});
  assert.equal(await h.client.has(firstSub), true);
  assert.equal(await h.client.has(makeTask('c00', 0)), false, 'a different container must not be excluded');
  assert.deepEqual(overlappingIds(firstSub), [taskId(containerTask(firstSub))]);
});

test('an absent v2 index is empty, while the v1 index stays required', async () => {
  const h = host({v1: flatFixture({c00: [taskId(firstSub)]}), v2: null});
  await h.client.refresh(true);
  assert.equal(h.client.revision, 1);
  assert.equal(h.client.revisionV2, 0);
  assert.equal(await h.client.has(v2Task), true, 'v1 coverage still excludes the container');
  assert.equal(await h.client.has(makeTask('c00', 1024 * 5, 0, 2)), false);
  assert.ok(h.requested.includes('v2/index.json'));

  const offline = host({v1: null, v2: null});
  await assert.rejects(offline.client.refresh(true), /unavailable/);
});

test('served but invalid v2 coverage fails closed', async () => {
  const corrupt = chunkedFixture({c00: [taskId(v2Task)]});
  corrupt.files.set(corrupt.index.shards.c00.file, '{}');
  await assert.rejects(host({v2: corrupt}).client.has(v2Task), /checksum/);

  const wrongEngine = chunkedFixture({c00: [taskId(v2Task)]}, ENGINE);
  await assert.rejects(host({v2: wrongEngine}).client.refresh(true), /Invalid shared v2 coverage index/);

  const mislabelled = chunkedFixture();
  mislabelled.index.revision += 1;
  mislabelled.index.verified_task_count = mislabelled.index.revision;
  assert.throws(() => validateManifestV2(mislabelled.index), /counts disagree/);
  assert.throws(() => validateManifestV2({...mislabelled.index, shards: {}}), /Invalid shared v2 coverage index/);
});

test('the v2 reader also accepts the flat shard layout and rejects v1 tasks', async () => {
  const flat = flatFixture({c00: [taskId(v2Task)]}, ENGINE_V2);
  const client = createV2CoverageClient(new URL('https://example.test/math-gambling/'), {
    fetcher: async url => {
      const name = url.pathname.split('/').at(-1), body = flat.files.get(name);
      return new Response(body ?? 'missing', {status: body == null ? 404 : 200});
    },
  });
  assert.equal(await client.has(v2Task), true);
  assert.equal(await client.has(makeTask('c00', 0, 0, 2)), false);
  await assert.rejects(client.has(makeTask('c00', 0)), /only holds engine v2 tasks/);
});
