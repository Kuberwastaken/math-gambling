/* Exact bounded kernel. Numbers select finite indices; arithmetic is BigInt.
 * A receipt is replayable evidence, not a cryptographic proof of donated CPU.
 */
export const ENGINE = 'mg114-offset-v1';
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
  if (task.version !== 1 || task.engine !== ENGINE) throw new RangeError('unsupported engine/version');
  const c = byId.get(task.context);
  if (!c) throw new RangeError('unknown fixed context');
  if (typeof task.row !== 'string' || !/^(0|[1-9][0-9]{0,14})$/.test(task.row) || BigInt(task.row) >= BigInt(c.totalRows) || BigInt(task.row) % BigInt(ROWS_PER_TASK)) throw new RangeError('row outside context or not aligned to rowStride');
  if (!Number.isInteger(task.block) || task.block < 0 || task.block >= c.blocks) throw new RangeError('block outside context');
  return {version: 1, engine: ENGINE, context: task.context, row: task.row, block: task.block};
}
export function makeTask(context, row, block = 0) {
  if (typeof row === 'number' && !Number.isSafeInteger(row)) throw new TypeError('row number must be a safe integer');
  return validateTask({version: 1, engine: ENGINE, context, row: String(row), block});
}
export function taskId(task) { const t = validateTask(task); return `${ENGINE}:${t.context}:${t.row}:${t.block}`; }

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

export function scanCurve(k, d, r, qlo, qhi, {sieve = true, minimal = true} = {}) {
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
    if (xyz) hits.push({xyz, D: String(d), r: String(r), q: String(q)});
  }
  counters.hits = hits.length;
  return {counters, hits};
}

function runRow(task, c, row) {
  const ell = BigInt(c.ell), radius = BigInt(c.radius), width = 2n * radius + 1n;
  const b = row % width - radius, cc = row / width - radius, base = offsetBase(ell, b, cc);
  const tlo = c.tlo + BLOCK_SIZE * task.block, thi = Math.min(tlo + BLOCK_SIZE - 1, c.thi);
  const counters = emptyCounters(), hits = [];
  for (let t = tlo; t <= thi; t++) {
    counters.generators++;
    const a = base + ell * BigInt(t), n = norm(a, b, cc);
    if (n % ell) throw new Error('norm lattice divisibility failed');
    const d = n / ell;
    if (d <= BigInt(c.dlo) || d > BigInt(c.dhi)) { counters.outside_shell++; continue; }
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
    const found = scanCurve(114, d, r, qlo, qhi);
    for (const key of counterKeys) counters[key] += found.counters[key];
    for (const hit of found.hits) hits.push({...hit, abc: [String(a), String(b), String(cc)], t, row: String(row)});
  }
  if (counters.generators !== ['outside_shell', 'invalid_d', 'signed_excluded', 'noninvertible', 'curves'].reduce((s, k) => s + counters[k], 0)) throw new Error('generator accounting failed');
  if (counters.quotient_points !== ['rejected_mod243', 'rejected_parity', 'rejected_prime', 'exact_tests'].reduce((s, k) => s + counters[k], 0)) throw new Error('quotient accounting failed');
  return {counters, hits};
}

export function runTaskCore(input) {
  const task = validateTask(input), c = byId.get(task.context);
  const start = BigInt(task.row), end = start + BigInt(ROWS_PER_TASK) < BigInt(c.totalRows) ? start + BigInt(ROWS_PER_TASK) : BigInt(c.totalRows);
  const counters = emptyCounters(), hits = [];
  for (let row = start; row < end; row++) {
    const found = runRow(task, c, row);
    for (const key of counterKeys) counters[key] += found.counters[key];
    hits.push(...found.hits);
  }
  return {task, id: taskId(task), counters, hits};
}

export async function runTask(input) {
  const result = runTaskCore(input);
  const hash = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonicalJSON(result)));
  return {...result, digest: Array.from(new Uint8Array(hash), x => x.toString(16).padStart(2, '0')).join('')};
}
