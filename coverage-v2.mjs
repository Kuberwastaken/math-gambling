/* Shared coverage across both engine versions.
 *
 * The published v1 index (data/coverage/index.json) stays v1-only so existing
 * clients keep working. Engine v2 coverage is published separately under
 * data/coverage/v2/ with the same index/shard/chunk formats and v2 task IDs.
 * A task is already covered when its own ID is in its version's index, or when
 * any overlapping ID (engine.mjs overlappingIds) is in the other version's
 * index: the two versions search exactly the same positions.
 *
 * The v2 index is optional. A 404 means "nothing verified under v2 yet" and is
 * treated as an empty index; anything that is served but does not validate
 * fails closed, exactly as the v1 index does.
 */
import {CONTEXTS, ENGINE_V2, containerTask, makeTask, subtasks, taskId, validateTask} from './engine.mjs?v=3ba4fb1151c9';
import {createCoverageClient} from './search-session.mjs?v=3ba4fb1151c9';

const INDEX_CAP = 128 * 1024, SHARD_CAP = 8 * 1024 * 1024, CHUNK_CAP = 32768;
export const V2_COVERAGE_PATH = 'data/coverage/v2/';
const hex = bytes => [...bytes].map(x => x.toString(16).padStart(2, '0')).join('');
const sha256 = async value => hex(new Uint8Array(await crypto.subtle.digest('SHA-256',
  typeof value === 'string' ? new TextEncoder().encode(value) : value)));

async function boundedBytes(response, cap) {
  if (Number(response.headers.get('content-length')) > cap) throw Error('Coverage file exceeds its size limit');
  const reader = response.body.getReader(), chunks = [];
  let total = 0;
  try {
    for (;;) {
      const {done, value} = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > cap) throw Error('Coverage file exceeds its size limit');
      chunks.push(value);
    }
  } catch (error) { await reader.cancel(); throw error; }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return bytes;
}
const decode = bytes => JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes));

export function validateManifestV2(index) {
  if (!['math-gambling-coverage-v1', 'math-gambling-coverage-v2'].includes(index?.schema) || index.engine !== ENGINE_V2 ||
      !Number.isSafeInteger(index.revision) || index.revision < 0 ||
      index.verified_task_count !== index.revision || !index.shards ||
      Object.keys(index.shards).sort().join() !== CONTEXTS.map(c => c.id).sort().join())
    throw Error('Invalid shared v2 coverage index');
  let total = 0;
  for (const c of CONTEXTS) {
    const s = index.shards[c.id];
    if (!s || !/^[0-9a-f]{64}$/.test(s.sha256) || s.file !== `${c.id}-${s.sha256}.json` ||
        !Number.isSafeInteger(s.count) || s.count < 0 ||
        s.count > (index.schema.endsWith('-v1') ? 100000 : Number.MAX_SAFE_INTEGER))
      throw Error('Invalid shared v2 coverage shard descriptor');
    total += s.count;
  }
  if (total !== index.revision) throw Error('Shared v2 coverage counts disagree');
  return index;
}

/* Membership in the published engine-v2 coverage index. Accepts both the flat
 * shard-v1 layout and the chunked context-v2 layout, like the v1 reader. */
export function createV2CoverageClient(base, {fetcher = fetch, now = Date.now, path = V2_COVERAGE_PATH} = {}) {
  let index = null, checked = 0, absent = false, refreshPromise = null;
  const shards = new Map(), nodes = new Map(), chunks = new Map();
  async function read(file, cap, mode) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetcher(new URL(`${path}${file}`, base), {cache: mode, signal: controller.signal});
      if (response.status === 404) return null; // Not published yet: no v2 coverage exists.
      if (!response.ok) throw Error(`Coverage report unavailable (${response.status})`);
      return await boundedBytes(response, cap);
    } finally { clearTimeout(timeout); }
  }
  async function checkedFile(entry, cap) {
    const bytes = await read(entry.file, cap, 'force-cache');
    if (!bytes) throw Error(`Coverage report unavailable (404): ${entry.file}`);
    if (await sha256(bytes) !== entry.sha256) throw Error('Shared v2 coverage checksum failed');
    return decode(bytes);
  }
  function checkedIds(list, context, expected) {
    const ids = new Set();
    let previous = '';
    for (const id of list) {
      if (typeof id !== 'string' || id <= previous) throw Error('Unsorted or duplicate v2 coverage identity');
      const parts = id.split(':');
      if (parts.length !== 4 || parts[0] !== ENGINE_V2 || parts[1] !== context ||
          !/^(0|[1-9][0-9]*)$/.test(parts[3]) || taskId(makeTask(context, parts[2], Number(parts[3]), 2)) !== id)
        throw Error('Invalid v2 coverage identity');
      ids.add(id); previous = id;
    }
    if (ids.size !== expected) throw Error('Invalid v2 coverage count');
    return ids;
  }
  async function chunkIds(context, bucket, entry) {
    let ids = chunks.get(entry.file);
    if (!ids) {
      const value = await checkedFile(entry, CHUNK_CAP);
      if (value.schema !== 'math-gambling-coverage-chunk-v2' || value.engine !== ENGINE_V2 ||
          value.context !== context || value.bucket !== bucket || !Array.isArray(value.tasks))
        throw Error('Invalid shared v2 coverage chunk');
      ids = checkedIds(value.tasks, context, entry.count);
      for (const id of ids) if ((await sha256(id)).slice(0, 2) !== bucket) throw Error('Misrouted v2 coverage identity');
    }
    chunks.delete(entry.file); chunks.set(entry.file, ids);
    while (chunks.size > 64) chunks.delete(chunks.keys().next().value);
    return ids;
  }
  async function chunkedHas(task, descriptor) {
    let node = nodes.get(task.context);
    if (!node || node.sha256 !== descriptor.sha256) {
      const value = await checkedFile(descriptor, SHARD_CAP);
      if (value.schema !== 'math-gambling-coverage-context-v2' || value.engine !== ENGINE_V2 ||
          value.context !== task.context || !value.buckets || Array.isArray(value.buckets))
        throw Error('Invalid v2 coverage context');
      let total = 0;
      for (const [bucket, entries] of Object.entries(value.buckets)) {
        if (!/^[0-9a-f]{2}$/.test(bucket) || !Array.isArray(entries) || !entries.length) throw Error('Invalid v2 coverage bucket');
        const files = new Set();
        for (const entry of entries) {
          if (!entry || !/^[0-9a-f]{64}$/.test(entry.sha256) || entry.file !== `${task.context}-b${bucket}-${entry.sha256}.json` ||
              !Number.isSafeInteger(entry.count) || entry.count < 1 || entry.count > 256 || files.has(entry.file))
            throw Error('Invalid v2 coverage chunk descriptor');
          files.add(entry.file); total += entry.count;
        }
      }
      if (total !== descriptor.count) throw Error('v2 coverage chunk counts disagree');
      node = {sha256: descriptor.sha256, buckets: value.buckets};
      nodes.delete(task.context); nodes.set(task.context, node);
      while (nodes.size > 8) nodes.delete(nodes.keys().next().value);
    }
    const id = taskId(task), bucket = (await sha256(id)).slice(0, 2);
    for (const entry of node.buckets[bucket] || []) if ((await chunkIds(task.context, bucket, entry)).has(id)) return true;
    return false;
  }
  async function flatHas(task, descriptor) {
    let shard = shards.get(task.context);
    if (!shard || shard.sha256 !== descriptor.sha256) {
      const value = await checkedFile(descriptor, SHARD_CAP);
      if (value.schema !== 'math-gambling-coverage-shard-v1' || value.engine !== ENGINE_V2 ||
          value.context !== task.context || !Array.isArray(value.tasks))
        throw Error('Invalid shared v2 coverage shard');
      shard = {sha256: descriptor.sha256, completed: checkedIds(value.tasks, task.context, descriptor.count)};
    }
    shards.delete(task.context); shards.set(task.context, shard);
    let cached = [...shards.values()].reduce((sum, item) => sum + item.completed.size, 0);
    while (cached > 200000) {
      const oldest = shards.keys().next().value;
      cached -= shards.get(oldest).completed.size; shards.delete(oldest);
    }
    return shard.completed.has(taskId(task));
  }
  return {
    get revision() { return index?.revision ?? (absent ? 0 : null); },
    get published() { return index != null; },
    async refresh(force = false) {
      if (!force && (index || absent) && now() - checked < 60000) return index;
      if (refreshPromise) return refreshPromise;
      refreshPromise = (async () => {
        const bytes = await read('index.json', INDEX_CAP, 'no-cache');
        checked = now();
        if (!bytes) { absent = true; index = null; return null; }
        const fresh = validateManifestV2(decode(bytes));
        if (index && fresh.revision < index.revision) throw Error('Shared v2 coverage index moved backwards');
        absent = false; index = fresh; return index;
      })();
      try { return await refreshPromise; } finally { refreshPromise = null; }
    },
    async has(task) {
      const t = validateTask(task);
      if (t.version !== 2) throw Error('The v2 coverage index only holds engine v2 tasks');
      if ((!index && !absent) || now() - checked >= 60000) await this.refresh();
      if (!index) return false;
      const descriptor = index.shards[t.context];
      return index.schema === 'math-gambling-coverage-v2' ? chunkedHas(t, descriptor) : flatHas(t, descriptor);
    },
  };
}

/* One membership question answered against both published indexes. */
export function createDualCoverageClient(base, options = {}) {
  const v1 = createCoverageClient(base, options);
  const v2 = createV2CoverageClient(base, options);
  return {
    get revision() { return v1.revision; },
    get revisionV2() { return v2.revision; },
    get versions() { return {1: v1, 2: v2}; },
    async refresh(force = false) {
      const index = await v1.refresh(force);
      await v2.refresh(force);
      return index;
    },
    async has(task) {
      const t = validateTask(task);
      const own = t.version === 2 ? v2 : v1;
      if (await own.has(t)) return true;
      // Same positions, other engine version: one v2 container, or up to eight
      // v1 sub-tasks. Their IDs are exactly overlappingIds(t).
      const other = t.version === 2 ? v1 : v2;
      for (const overlap of t.version === 2 ? subtasks(t) : [containerTask(t)])
        if (await other.has(overlap)) return true;
      return false;
    },
  };
}
