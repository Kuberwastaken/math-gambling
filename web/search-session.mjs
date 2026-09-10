import { CONTEXTS, ENGINE, makeTask, taskId } from './engine.mjs';

const INDEX_CAP = 128 * 1024, SHARD_CAP = 8 * 1024 * 1024;
const hex = bytes => [...bytes].map(x => x.toString(16).padStart(2, '0')).join('');
export const SEED_ALGORITHM = 'sha256-counter-be64-v1';
export function newSeed() { return hex(crypto.getRandomValues(new Uint8Array(32))); }
export function seededRandom(seed) {
  if (!/^[0-9a-f]{64}$/.test(seed)) throw Error('Seed must contain 64 lowercase hexadecimal characters');
  const source = Uint8Array.from(seed.match(/../g), x => parseInt(x, 16));
  let counter = 0n, words = [];
  return {
    async below(limit) {
      const n = BigInt(limit), max = 1n << 64n;
      if (n < 1n || n > max) throw Error('Unsupported random bound');
      const cap = max - max % n;
      for (;;) {
        if (!words.length) {
          if (counter >= max) throw Error('Seed stream exhausted');
          const input = new Uint8Array(40);
          input.set(source);
          new DataView(input.buffer).setBigUint64(32, counter++, false);
          const digest = await crypto.subtle.digest('SHA-256', input);
          const view = new DataView(digest);
          words = [0, 8, 16, 24].map(i => view.getBigUint64(i, false));
        }
        const value = words.shift();
        if (value < cap) return value % n;
      }
    },
  };
}

async function boundedBytes(response, cap) {
  if (!response.ok) throw Error(`Coverage report unavailable (${response.status})`);
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
const decode = bytes => JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(bytes));
export function validateManifest(index) {
  if (index?.schema !== 'math-gambling-coverage-v1' || index.engine !== ENGINE ||
      !Number.isSafeInteger(index.revision) || index.revision < 0 ||
      index.verified_task_count !== index.revision || !index.shards ||
      Object.keys(index.shards).sort().join() !== CONTEXTS.map(c => c.id).sort().join())
    throw Error('Invalid shared coverage index');
  let total = 0;
  for (const c of CONTEXTS) {
    const s = index.shards[c.id];
    if (!s || !/^[0-9a-f]{64}$/.test(s.sha256) ||
        s.file !== `${c.id}-${s.sha256}.json` || !Number.isSafeInteger(s.count) ||
        s.count < 0 || s.count > 100000) throw Error('Invalid shared coverage shard descriptor');
    total += s.count;
  }
  if (total !== index.revision) throw Error('Shared coverage counts disagree');
  return index;
}
export function createCoverageClient(base, {fetcher = fetch, now = Date.now} = {}) {
  let index = null, checked = 0, refreshPromise = null;
  const cache = new Map();
  async function read(file, cap, mode) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try { return await boundedBytes(await fetcher(new URL(file, base), {cache:mode, signal:controller.signal}), cap); }
    finally { clearTimeout(timeout); }
  }
  return {
    get revision() { return index?.revision ?? null; },
    async refresh(force = false) {
      if (!force && index && now() - checked < 60000) return index;
      if (refreshPromise) return refreshPromise;
      refreshPromise = (async () => {
        const fresh = validateManifest(decode(await read('data/coverage/index.json', INDEX_CAP, 'no-cache')));
        if (index && fresh.revision < index.revision) throw Error('Shared coverage index moved backwards');
        if (index && fresh.revision === index.revision &&
            JSON.stringify(fresh.shards) !== JSON.stringify(index.shards)) throw Error('Shared coverage changed without a new revision');
        index = fresh; checked = now(); return index;
      })();
      try { return await refreshPromise; } finally { refreshPromise = null; }
    },
    async has(task) {
      if (!index || now() - checked >= 60000) await this.refresh();
      const descriptor = index.shards[task.context];
      let shard = cache.get(task.context);
      if (!shard || shard.sha256 !== descriptor.sha256) {
        const bytes = await read(`data/coverage/${descriptor.file}`, SHARD_CAP, 'force-cache');
        const digest = hex(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)));
        if (digest !== descriptor.sha256) throw Error('Shared coverage checksum failed');
        const data = decode(bytes);
        if (data.schema !== 'math-gambling-coverage-shard-v1' || data.engine !== ENGINE ||
            data.context !== task.context || !Array.isArray(data.tasks) || data.tasks.length !== descriptor.count)
          throw Error('Invalid shared coverage shard');
        const completed = new Set();
        let previous = '';
        for (const id of data.tasks) {
          if (typeof id !== 'string') throw Error('Invalid completed task identity');
          const parts = id.split(':');
          if (parts.length !== 4 || parts[0] !== ENGINE || parts[1] !== task.context ||
              !/^(0|[1-9][0-9]*)$/.test(parts[3]) ||
              taskId(makeTask(parts[1], parts[2], Number(parts[3]))) !== id || id <= previous)
            throw Error('Invalid or duplicate completed task identity');
          completed.add(id); previous = id;
        }
        if (shard && [...shard.completed].some(id => !completed.has(id)))
          throw Error('Shared coverage removed completed work');
        shard = {sha256:descriptor.sha256, completed};
      }
      // Keep exact cached membership bounded on phones as the public ledger grows.
      cache.delete(task.context); cache.set(task.context, shard);
      let cachedIds = [...cache.values()].reduce((sum, item) => sum + item.completed.size, 0);
      while (cachedIds > 200000) {
        const oldest = cache.keys().next().value;
        cachedIds -= cache.get(oldest).completed.size; cache.delete(oldest);
      }
      return shard.completed.has(taskId(task));
    },
  };
}
