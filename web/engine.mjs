/* Exact bounded kernel. Numbers select finite indices; arithmetic is BigInt.
 * A receipt is replayable evidence, not a cryptographic proof of donated CPU.
 */
export const ENGINE = 'mg114-offset-v1';
/* Engine v2 covers the identical mathematical positions in 8x larger tasks
 * (1024 rows instead of 128) to cut per-task dispatch, persistence and banking
 * overhead. Counters and hits of a v2 task equal the sum/concatenation of its
 * eight aligned v1 sub-tasks; v1 receipts and digests are unchanged. */
export const ENGINE_V2 = 'mg114-offset-v2';
export const ENGINES = Object.freeze({1: ENGINE, 2: ENGINE_V2});
export const ROWS_BY_VERSION = Object.freeze({1: 128, 2: 1024});
export const MAX_TASKS_PER_RECEIPT = 8;
export const BLOCK_SIZE = 16;
export const ROWS_PER_TASK = 128;
const SCALE = 10n ** 18n;
const ALPHA = 4848807585839879338n;
const ALPHA2 = 23510935004498358840n;
export const D0 = 10n ** 19n / 54n;
export const PRIMES = Object.freeze([5, 7, 11, 13, 17, 19, 23, 31, 37, 41, 43, 47, 53, 59, 61]);
const SHAPES = [[6000000, 8, 31], [1500000, 128, 511], [375000, 2048, 8191]];
const BANDS = [[0, 64], [64, 256], [256, 4096]];
const contexts = [];
for (const ell of [1, 5, 25]) for (let shape = 0; shape < SHAPES.length; shape++) {
  const [radius, tlo, thi] = SHAPES[shape];
  for (let shell = 0; shell < 3; shell++) for (let band = 0; band < BANDS.length; band++) {
    const [low, high] = BANDS[band];
    contexts.push(Object.freeze({id: `c${String(contexts.length).padStart(2, '0')}`, ell,
      shape, shell, band, radius, tlo, thi, dlo: String(D0 * 2n ** BigInt(shell)),
      dhi: String(D0 * 2n ** BigInt(shell + 1)), low, high,
      totalRows: String(BigInt(2 * radius + 1) ** 2n),
      rowStride: ROWS_PER_TASK,
      rowTasks: String((BigInt(2 * radius + 1) ** 2n + BigInt(ROWS_PER_TASK) - 1n) / BigInt(ROWS_PER_TASK)),
      rowStrideV2: ROWS_BY_VERSION[2],
      rowTasksV2: String((BigInt(2 * radius + 1) ** 2n + BigInt(ROWS_BY_VERSION[2]) - 1n) / BigInt(ROWS_BY_VERSION[2])),
      blocks: Math.floor((thi - tlo + BLOCK_SIZE) / BLOCK_SIZE)}));
  }
}
export const CONTEXTS = Object.freeze(contexts);
const byId = new Map(CONTEXTS.map(c => [c.id, c]));
const counterKeys = ['generators', 'outside_shell', 'invalid_d', 'signed_excluded', 'noninvertible',
  'curves', 'quotient_points', 'rejected_mod243', 'rejected_parity', 'rejected_prime', 'exact_tests', 'hits'];
const emptyCounters = () => Object.fromEntries(counterKeys.map(k => [k, 0]));
const mod = (a, b) => { const r = a % b; return r < 0n ? r + b : r; };
const modNumber = (a, b) => ((a % b) + b) % b;
const floorDiv = (a, b) => a / b - (a % b < 0n ? 1n : 0n);
const abs = a => a < 0n ? -a : a;
const gcd = (a, b) => { a = abs(a); while (b) [a, b] = [b, a % b]; return a; };
function inverse(a, m) {
  let [t, nt, r, nr] = [0n, 1n, m, mod(a, m)];
  while (nr) { const q = r / nr; [t, nt] = [nt, t - q * nt]; [r, nr] = [nr, r - q * nr]; }
  if (r !== 1n) throw new RangeError('noninvertible value');
  return mod(t, m);
}

export function canonicalJSON(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJSON).join(',')}]`;
  if (value !== null && typeof value === 'object') return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonicalJSON(value[k])}`).join(',')}}`;
  return JSON.stringify(value);
}

export function validateTask(task) {
  if (!task || typeof task !== 'object' || Array.isArray(task) ||
      Object.keys(task).sort().join(',') !== 'block,context,engine,row,version') throw new TypeError('unexpected or missing task fields');
  const engine = ENGINES[task.version];
  if (!Number.isInteger(task.version) || !engine || task.engine !== engine) throw new RangeError('unsupported engine/version');
  const c = byId.get(task.context);
  if (!c) throw new RangeError('unknown fixed context');
  const stride = BigInt(ROWS_BY_VERSION[task.version]);
  if (typeof task.row !== 'string' || !/^(0|[1-9][0-9]{0,14})$/.test(task.row) || BigInt(task.row) >= BigInt(c.totalRows) || BigInt(task.row) % stride) throw new RangeError('row outside context or not aligned to rowStride');
  if (!Number.isInteger(task.block) || task.block < 0 || task.block >= c.blocks) throw new RangeError('block outside context');
  return {version: task.version, engine, context: task.context, row: task.row, block: task.block};
}
export function makeTask(context, row, block = 0, version = 1) {
  if (typeof row === 'number' && !Number.isSafeInteger(row)) throw new TypeError('row number must be a safe integer');
  return validateTask({version, engine: ENGINES[version], context, row: String(row), block});
}
export function taskId(task) { const t = validateTask(task); return `${t.engine}:${t.context}:${t.row}:${t.block}`; }

/* Number of coefficient rows a task spans (before the context's row limit). */
export function taskRows(task) { return ROWS_BY_VERSION[validateTask(task).version]; }

/* The aligned v1 tasks whose positions a task covers (itself, for v1). */
export function subtasks(task) {
  const t = validateTask(task);
  if (t.version === 1) return [t];
  const total = BigInt(byId.get(t.context).totalRows), start = BigInt(t.row);
  const end = start + BigInt(ROWS_BY_VERSION[2]) < total ? start + BigInt(ROWS_BY_VERSION[2]) : total;
  const out = [];
  for (let row = start; row < end; row += BigInt(ROWS_BY_VERSION[1])) out.push(makeTask(t.context, row, t.block, 1));
  return out;
}

/* The v2 task containing a v1 task's positions (itself, for v2). */
export function containerTask(task) {
  const t = validateTask(task);
  if (t.version === 2) return t;
  const stride = BigInt(ROWS_BY_VERSION[2]);
  return makeTask(t.context, BigInt(t.row) / stride * stride, t.block, 2);
}

/* Task IDs of the *other* engine version whose positions overlap this task.
 * A v1 task is already covered if its containing v2 task is verified; a v2 task
 * is a duplicate if any of its v1 sub-tasks is verified. Coverage and credit
 * logic must consult these, since the two versions share one search domain. */
export function overlappingIds(task) {
  const t = validateTask(task);
  return t.version === 1 ? [taskId(containerTask(t))] : subtasks(t).map(taskId);
}

export function isqrt(n) {
  if (typeof n !== 'bigint' || n < 0n) throw new RangeError('isqrt needs a nonnegative BigInt');
  if (n < 2n) return n;
  let x = 1n << BigInt(Math.ceil(n.toString(2).length / 2));
  for (;;) { const y = (x + n / x) / 2n; if (y >= x) return x; x = y; }
}
export function verifyTriple(xyz, k = 114) {
  if (!Array.isArray(xyz) || xyz.length !== 3 || !Number.isSafeInteger(k) ||
      xyz.some(v => typeof v !== 'string' || !/^-?(0|[1-9][0-9]{0,127})$/.test(v) || v === '-0')) return false;
  return xyz.reduce((s, v) => s + BigInt(v) ** 3n, 0n) === BigInt(k);
}
export function offsetBase(ell, b, c) {
  ell = BigInt(ell); b = BigInt(b); c = BigInt(c);
  const residue = mod(-4n * b - 16n * c, ell);
  const numerator = -ALPHA * b - ALPHA2 * c - residue * SCALE;
  const denominator = ell * SCALE;
  return residue + ell * floorDiv(2n * numerator + denominator, 2n * denominator);
}
export function norm(a, b, c, k = 114n) { k = BigInt(k); return a ** 3n + k * b ** 3n + k * k * c ** 3n - 3n * k * a * b * c; }

const filterCache = new Map();
function filters(k) {
  if (filterCache.has(k)) return filterCache.get(k);
  const cubes = Array.from({length: 243}, (_, v) => v ** 3 % 243);
  const pairs = Array.from({length: 243}, () => new Uint8Array(243));
  for (let x = 0; x < 243; x++) for (let y = 0; y < 243; y++) pairs[(x + y) % 243][(cubes[x] + cubes[y]) % 243] = 1;
  const allowed = Array.from({length: 243}, (_, s) => cubes.flatMap((cube, z) => pairs[s][modNumber(k - cube, 243)] ? [z] : []));
  const masks = PRIMES.map(p => {
    const qr = new Set(Array.from({length: p}, (_, v) => v * v % p));
    return Array.from({length: p}, (_, s) => Uint8Array.from({length: p}, (_, z) => qr.has(modNumber(3 * s * (4 * k - 4 * z ** 3 - s ** 3), p)) ? 1 : 0));
  });
  const result = {allowed, masks};
  if (filterCache.size >= 32) filterCache.delete(filterCache.keys().next().value);
  filterCache.set(k, result); return result;
}

export function checkCandidate(k, s, z, {minimal = true} = {}) {
  k = BigInt(k); s = BigInt(s); z = BigInt(z);
  if (!s) return null;
  const numerator = 4n * (k - z ** 3n) - s ** 3n, denominator = 3n * s;
  if (numerator % denominator) return null;
  const square = numerator / denominator;
  if (square < 0n) return null;
  const v = isqrt(square);
  if (v * v !== square || (s + v) % 2n) return null;
  const x = (s + v) / 2n, y = (s - v) / 2n;
  if (minimal && (abs(z) > abs(x) || abs(z) > abs(y))) return null;
  const xyz = [String(x), String(y), String(z)];
  if (!verifyTriple(xyz, Number(k))) throw new Error('final exact cube identity failed');
  return xyz;
}

export function scanCurve(k, d, r, qlo, qhi, {sieve = true, minimal = true, onHit} = {}) {
  if (!Number.isSafeInteger(k) || k < 3 || k > 1000 || ![3, 6].includes(modNumber(k, 9))) throw new RangeError('unsupported regression k');
  d = BigInt(d); r = BigInt(r); qlo = BigInt(qlo); qhi = BigInt(qhi);
  if (d < 2n || d % 3n === 0n || r < 0n || r >= d || r ** 3n % d !== mod(BigInt(k), d)) throw new RangeError('invalid modular root');
  if (qhi < qlo || qhi - qlo > 8192n) throw new RangeError('bounded regression interval required');
  const s = d % 3n === BigInt((2 * (Math.floor(k / 3) % 3)) % 3) ? d : -d;
  const counters = emptyCounters(); counters.curves = 1; counters.quotient_points = Number(qhi - qlo + 1n);
  const hits = [], {allowed, masks} = filters(k);
  let qs = [];
  if (sieve) {
    const inv = inverse(d, 243n);
    for (const zmod of allowed[Number(mod(s, 243n))]) {
      const residue = mod((BigInt(zmod) - r) * inv, 243n);
      const first = qlo + mod(residue - qlo, 243n);
      for (let q = first; q <= qhi; q += 243n) qs.push(q);
    }
    qs.sort((a, b) => a < b ? -1 : a > b ? 1 : 0);
    counters.rejected_mod243 = counters.quotient_points - qs.length;
  } else { for (let q = qlo; q <= qhi; q++) qs.push(q); }
  const smallS = PRIMES.map(p => Number(mod(s, BigInt(p))));
  for (const q of qs) {
    const z = r + d * q;
    if (sieve && mod(BigInt(k) - s - z, 2n)) { counters.rejected_parity++; continue; }
    if (sieve && PRIMES.some((p, j) => !masks[j][smallS[j]][Number(mod(z, BigInt(p)))])) { counters.rejected_prime++; continue; }
    counters.exact_tests++;
    const xyz = checkCandidate(k, s, z, {minimal});
    if (xyz) {
      const hit = {xyz, D: String(d), r: String(r), q: String(q)};
      hits.push(hit);
      // Publish an exact positive before another candidate or receipt hashing
      // can fail. Observers cannot mutate, or abort, the mathematical result.
      try { onHit?.({...hit, xyz: [...xyz]}); } catch {}
    }
  }
  counters.hits = hits.length;
  return {counters, hits};
}

export function shellInterval(base, ell, tlo, thi, lower, upper, constant, linear) {
  // N(a)=a^3-linear*a+constant; N'(a)=3*a^2-linear. Endpoint integer
  // bounds prove monotonicity. If they cannot, retain the complete interval.
  const a0 = base + ell * BigInt(tlo), a1 = base + ell * BigInt(thi);
  const n0 = a0 * a0 * a0 - linear * a0 + constant;
  // N(a+ell) == N(a) (mod ell), including all generators omitted below.
  if (n0 % ell) throw new Error('norm lattice divisibility failed');
  const minimumAbsA = a0 >= 0n ? a0 : a1 <= 0n ? -a1 : 0n;
  if (3n * minimumAbsA * minimumAbsA < linear) return [tlo, thi];
  const n1 = a1 * a1 * a1 - linear * a1 + constant;
  if (n1 <= lower || n0 > upper) return [tlo, tlo - 1];
  let first = tlo, last = thi;
  if (n0 <= lower) {
    let left = tlo + 1, right = thi;
    while (left < right) {
      const middle = Math.floor((left + right) / 2), a = base + ell * BigInt(middle);
      if (a * a * a - linear * a + constant <= lower) left = middle + 1;
      else right = middle;
    }
    first = left;
  }
  if (n1 > upper) {
    let left = first, right = thi;
    while (left < right) {
      const middle = Math.floor((left + right) / 2), a = base + ell * BigInt(middle);
      if (a * a * a - linear * a + constant <= upper) left = middle + 1;
      else right = middle;
    }
    last = left - 1;
  }
  return [first, last];
}

function runRow(task, c, row, onHit) {
  const ell = BigInt(c.ell), radius = BigInt(c.radius), width = 2n * radius + 1n;
  const b = row % width - radius, cc = row / width - radius, base = offsetBase(ell, b, cc);
  const tlo = c.tlo + BLOCK_SIZE * task.block, thi = Math.min(tlo + BLOCK_SIZE - 1, c.thi);
  const counters = emptyCounters(), hits = [];
  const constant = 114n * b * b * b + 12996n * cc * cc * cc, linear = 342n * b * cc;
  const dlo = BigInt(c.dlo), dhi = BigInt(c.dhi);
  const [first, last] = shellInterval(base, ell, tlo, thi, ell * dlo, ell * dhi, constant, linear);
  counters.generators = thi - tlo + 1;
  counters.outside_shell = counters.generators - Math.max(0, last - first + 1);
  for (let t = first; t <= last; t++) {
    const a = base + ell * BigInt(t), n = a * a * a - linear * a + constant;
    if (n % ell) throw new Error('norm lattice divisibility failed');
    const d = n / ell;
    if (d <= dlo || d > dhi) { counters.outside_shell++; continue; }
    if (d < 2n || d % 3n === 0n) { counters.invalid_d++; continue; }
    const s = d % 3n === 1n ? d : -d;
    if ([0, 4, 6].includes(Number(mod(s, 8n))) || [0, 19, 76, 95, 114, 133, 171, 209, 304, 323].includes(Number(mod(s, 361n)))) { counters.signed_excluded++; continue; }
    const B = 114n * cc * cc - a * b, C = b * b - a * cc;
    if (gcd(C, d) !== 1n) { counters.noninvertible++; continue; }
    const r = mod(B * inverse(C, d), d);
    if (r ** 3n % d !== 114n % d) throw new Error('norm modular root identity failed');
    const zmin = BigInt(c.low) * d > 10n ** 17n ? BigInt(c.low) * d : 10n ** 17n;
    const zmax = BigInt(c.high) * d;
    const [qlo, qhi] = s < 0n ? [floorDiv(zmin - r, d) + 1n, floorDiv(zmax - r, d)] : [-((zmax + r) / d), -((zmin + r) / d) - 1n];
    const found = scanCurve(114, d, r, qlo, qhi, {onHit: onHit && (hit =>
      onHit({...hit, abc: [String(a), String(b), String(cc)], t, row: String(row)}))});
    for (const key of counterKeys) counters[key] += found.counters[key];
    for (const hit of found.hits) hits.push({...hit, abc: [String(a), String(b), String(cc)], t, row: String(row)});
  }
  if (counters.generators !== ['outside_shell', 'invalid_d', 'signed_excluded', 'noninvertible', 'curves'].reduce((s, k) => s + counters[k], 0)) throw new Error('generator accounting failed');
  if (counters.quotient_points !== ['rejected_mod243', 'rejected_parity', 'rejected_prime', 'exact_tests'].reduce((s, k) => s + counters[k], 0)) throw new Error('quotient accounting failed');
  return {counters, hits};
}

export function runTaskCore(input, {onHit} = {}) {
  const task = validateTask(input), c = byId.get(task.context);
  const rows = BigInt(ROWS_BY_VERSION[task.version]);
  const start = BigInt(task.row), end = start + rows < BigInt(c.totalRows) ? start + rows : BigInt(c.totalRows);
  const counters = emptyCounters(), hits = [];
  for (let row = start; row < end; row++) {
    const found = runRow(task, c, row, onHit);
    for (const key of counterKeys) counters[key] += found.counters[key];
    hits.push(...found.hits);
  }
  return {task, id: taskId(task), counters, hits};
}

export async function runTask(input, options) {
  const result = runTaskCore(input, options);
  const hash = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonicalJSON(result)));
  return {...result, digest: Array.from(new Uint8Array(hash), x => x.toString(16).padStart(2, '0')).join('')};
}
