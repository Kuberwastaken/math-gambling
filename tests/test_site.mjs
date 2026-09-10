/* Controlled UI lifecycle test, without a browser or network.
 * This executes the actual app source with a minimal DOM/IndexedDB/Worker host.
 * It is not a visual, browser-compatibility, or real-storage durability test.
 */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import vm from "node:vm";
import * as engine from "../web/engine.mjs";
import * as sessionTools from "../web/search-session.mjs";

const appURL = new URL("../web/app.mjs", import.meta.url);
const appSource = await fs.readFile(appURL, "utf8");

class Element {
  constructor(id = "") {
    this.id = id;
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.textContent = "";
    this.children = [];
    this.listeners = new Map();
    this.style = {};
  }
  addEventListener(type, fn) {
    const list = this.listeners.get(type) || [];
    list.push(fn);
    this.listeners.set(type, list);
  }
  replaceChildren(...items) {
    this.children = [...items];
  }
  append(...items) {
    this.children.push(...items);
  }
  setAttribute(name, value) {
    this[name] = String(value);
  }
  getAttribute(name) {
    return this[name];
  }
  scrollIntoView() {}
  focus() {}
  select() {}
  click() {}
  insertRow() {
    const row = new Element();
    this.append(row);
    return row;
  }
  insertCell() {
    const cell = new Element();
    this.append(cell);
    return cell;
  }
}

async function harness({
  workerCreationFails = false,
  cachedProfile = null,
  coverageFails = false,
  coverageProbe = null,
  coverageRefreshProbe = null,
  randomFactory = null,
  fixtureTarget = 114,
  brokenCelebration = false,
  fetchProbe = null,
  localStorageFails = false,
  downloadFails = false,
  identityStorageFails = false,
  cachedIdentities = [],
} = {}) {
  const elements = new Map();
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, new Element(id));
    return elements.get(id);
  };
  get("run-duty").value = "1";
  get("join-form").querySelectorAll = () =>
    ["player-name", "player-github", "run-duty"].map(get);
  const listeners = new Map();
  const document = {
    hidden: false,
    getElementById: get,
    createElement: () => new Element(),
    createElementNS: () => new Element(),
    addEventListener(type, fn) {
      const list = listeners.get(type) || [];
      list.push(fn);
      listeners.set(type, list);
    },
  };
  const local = new Map(), celebrations = [];
  if (cachedProfile !== null)
    local.set("mg-profile", JSON.stringify(cachedProfile));
  const stores = new Map(), databases = new Set(),
    workers = [],
    pendingWrites = [],
    timeouts = new Map(),
    intervals = new Map();
  let holdWrites = false,
    timerId = 0;
  const connection = {
    createObjectStore(name, { keyPath }) {
      const rows = new Map();
      if (name === "identities") for (const record of cachedIdentities)
        rows.set(record[keyPath], structuredClone(record));
      stores.set(name, { keyPath, rows });
    },
    transaction(name, mode) {
      const tx = {};
      tx.objectStore = () => ({
        getAll() {
          const req = {};
          queueMicrotask(() => {
            req.result = [...stores.get(name).rows.values()].map((value) =>
              structuredClone(value),
            );
            req.onsuccess?.();
          });
          return req;
        },
        put(record) {
          const commit = () => {
            if (name === "identities" && identityStorageFails) {
              tx.error = Error("fixture identity backup unavailable");
              tx.onabort?.();
              return;
            }
            const store = stores.get(name);
            store.rows.set(record[store.keyPath], structuredClone(record));
            tx.oncomplete?.();
          };
          if (holdWrites) pendingWrites.push(commit);
          else queueMicrotask(commit);
        },
      });
      return tx;
    },
  };
  const indexedDB = {
    open(name) {
      const req = {};
      queueMicrotask(() => {
        req.result = connection;
        if (!databases.has(name)) { req.onupgradeneeded?.(); databases.add(name); }
        req.onsuccess?.();
      });
      return req;
    },
  };
  class FakeWorker {
    constructor() {
      if (workerCreationFails)
        throw new Error("fixture Worker construction failure");
      this.posts = [];
      this.terminated = false;
      workers.push(this);
    }
    postMessage(data) {
      assert(!this.terminated);
      this.posts.push(structuredClone(data));
    }
    terminate() {
      this.terminated = true;
    }
    emit(data) {
      return this.onmessage?.({ data });
    }
  }
  const context = vm.createContext({
    __engine: { ...engine, verifyTriple: (xyz) => engine.verifyTriple(xyz, fixtureTarget) },
    __jackpot: () => ({ show(value) {
      if (brokenCelebration) throw Error("fixture broken animation");
      celebrations.push(value);
      return true;
    } }),
    __sessionTools: {...sessionTools, seededRandom: randomFactory || sessionTools.seededRandom, createCoverageClient: () => ({
      revision: 128,
      async refresh(force) {
        if (coverageFails) throw Error("fixture coverage offline");
        if (coverageRefreshProbe) return coverageRefreshProbe(force);
      },
      async has(task) { return coverageProbe ? coverageProbe(task) : false; },
    })},
    console,
    document,
    indexedDB,
    Worker: FakeWorker,
    localStorage: {
      getItem: (key) => local.get(key) ?? null,
      setItem: (key, value) => {
        if (localStorageFails) throw Error("fixture localStorage unavailable");
        local.set(key, String(value));
      },
      removeItem: (key) => local.delete(key),
    },
    crypto: globalThis.crypto,
    TextEncoder,
    TextDecoder,
    URL: downloadFails ? class extends URL {
      static createObjectURL() { throw Error("fixture download unavailable"); }
    } : URL,
    Blob,
    AbortController,
    Intl,
    Date,
    navigator: { clipboard: { writeText: async () => {} } },
    window: { print() {}, addEventListener() {} },
    matchMedia: () => ({ matches: true }),
    fetch: async (...args) => {
      if (fetchProbe) return fetchProbe(...args);
      throw new Error("fixture offline; no network requests");
    },
    setTimeout(fn, delay) {
      const id = ++timerId;
      timeouts.set(id, {fn, delay});
      return id;
    },
    clearTimeout(id) {
      timeouts.delete(id);
    },
    setInterval(fn) {
      const id = ++timerId;
      intervals.set(id, fn);
      return id;
    },
    clearInterval(id) {
      intervals.delete(id);
    },
  });
  const source = appSource
    .replace(/import \{ createJackpot \} from "\.\/jackpot\.mjs";/,
      "const createJackpot=__jackpot;")
    .replace(/import \{ createCoverageClient, newSeed, seededRandom, SEED_ALGORITHM \} from "\.\/search-session\.mjs";/,
      "const { createCoverageClient, newSeed, seededRandom, SEED_ALGORITHM } = __sessionTools;")
    .replace(/import \{ setupRunnerDownload \} from "\.\/runner-setup\.mjs";/,
      "const setupRunnerDownload=()=>{};")
    .replace(
      /import \{ renderModelEvolution \} from "\.\/model-viz\.mjs";/,
      "const renderModelEvolution=()=>{};",
    )
    .replace(
      /^import\s*\{([^}]+)\}\s*from\s*['"]\.\/engine\.mjs['"];?/,
      "const {$1} = __engine;",
    )
    .replace(
      /import \{ createLiveVisuals \} from \".\/live-viz.mjs\";/,
      "const createLiveVisuals = () => null;",
    )
    .replaceAll("import.meta.url", JSON.stringify(appURL.href));
  await vm.runInContext(
    `(async()=>{${source}\n globalThis.__app={start,stop,dispatch,processorDuty,updateProcessor,openBank,submitBankProfile,prepareBank,safeProfileURL,counter,
    state:()=>({running,starting,busy,worker,tasks,counts,pendingIdentitySaves}),
    fetchJSON, setRefreshCounter:n=>{completedSinceRefresh=n;},
    setHistory:(t,b)=>{tasks=t;banks=b;},
    ageRun:()=>{startAt=Date.now()-86400000;}};})()`,
    context,
    { filename: "app-under-lifecycle-test.mjs" },
  );
  // Let the initial saved-state refresh finish too.
  await new Promise(setImmediate);
  get("player-name").value = "Lifecycle test";
  get("player-github").value = "test-user";
  return {
    app: context.__app,
    get,
    workers,
    stores,
    local,
    celebrations,
    holdWrites(value = true) {
      holdWrites = value;
    },
    flushWrites() {
      holdWrites = false;
      for (const commit of pendingWrites.splice(0)) commit();
    },
    pendingWriteCount: () => pendingWrites.length,
    visibility(hidden) {
      document.hidden = hidden;
      for (const fn of listeners.get("visibilitychange") || []) fn();
    },
    tickIntervals() {
      for (const fn of [...intervals.values()]) fn();
    },
    tickTimeouts(delay) {
      for (const [id, timer] of [...timeouts]) {
        if (timer.delay === delay) { timeouts.delete(id); timer.fn(); }
      }
    },
  };
}

const event = () => ({ preventDefault() {} });
async function waitFor(predicate, message) {
  const deadline = Date.now() + 2000;
  while (Date.now() < deadline) {
    if (predicate()) return;
    await new Promise(setImmediate);
  }
  assert.fail(message);
}
async function ready(h) {
  await h.app.start(event());
  const worker = h.workers.at(-1);
  await worker.emit({ type: "ready" });
  await waitFor(() => worker.posts.length === 1, "shared coverage dispatch did not finish");
  return worker;
}
async function deliver(worker) {
  const task = worker.posts.at(-1).task;
  const result = await engine.runTask(task);
  return worker.emit({ type: "result", result, elapsedMs: 5 });
}

// Stop while a task is inflight must drain its completed receipt before
// terminating the worker or enabling a replacement session.
{
  const h = await harness(),
    worker = await ready(h);
  h.app.stop("test stop");
  assert.equal(worker.terminated, false);
  assert.equal(h.get("start-button").disabled, true);
  await h.app.start(event());
  assert.equal(h.workers.length, 1);
  await deliver(worker);
  await waitFor(() => worker.terminated, "stopped result did not drain");
  assert.equal(h.stores.get("tasks").rows.size, 1);
  assert.equal(h.app.state().running, false);
  assert.equal(h.app.state().busy, false);
  assert.equal(worker.terminated, true);
  assert.equal(h.get("start-button").disabled, false);
}

// Visibility changes cannot dispatch another task while the first result's
// IndexedDB transaction is incomplete. Start events also cannot create two
// workers while the initial saved-state read is pending.
{
  const h = await harness();
  const first = h.app.start(event()),
    second = h.app.start(event());
  await Promise.all([first, second]);
  assert.equal(h.workers.length, 1);
  const worker = h.workers[0];
  await worker.emit({ type: "ready" });
  await waitFor(() => worker.posts.length === 1, "initial dispatch did not finish");
  const result = await engine.runTask(worker.posts[0].task);
  h.holdWrites();
  const saving = worker.emit({ type: "result", result, elapsedMs: 5 });
  await waitFor(
    () => h.pendingWriteCount() > 0,
    "result never reached pending persistence",
  );
  h.visibility(true);
  h.visibility(false);
  h.app.dispatch();
  assert.equal(
    worker.posts.length,
    1,
    "second task dispatched before durable save",
  );
  assert.equal(h.app.state().busy, true);
  h.app.stop("stop while saving");
  assert.equal(worker.terminated, false);
  h.flushWrites();
  await saving;
  await waitFor(
    () => worker.terminated,
    "save barrier did not finish before stop",
  );
  assert.equal(h.stores.get("tasks").rows.size, 1);
  assert.equal(worker.terminated, true);
  const stored = [...h.stores.get("tasks").rows.values()][0];
  assert.equal(stored.contributor.name, "Anonymous");
}

// Worker construction failure returns to usable controls without an orphan
// running state. Corrupted cached profile values cannot abort module startup.
{
  const h = await harness({
    workerCreationFails: true,
    cachedProfile: { name: "Old name", github: { toString: null } },
  });
  await h.app.start(event());
  assert.equal(h.workers.length, 0);
  assert.equal(h.app.state().running, false);
  assert.equal(h.app.state().busy, false);
  assert.equal(h.get("start-button").disabled, false);
  assert.match(h.get("session-message").textContent, /Could not start/i);
}

// Browser runs have no clock deadline, allow an anonymous start, and read the
// processor slider live. Changing display controls must not replace a worker.
{
  const h = await harness();
  h.get("player-name").value = "";
  h.get("player-github").value = "";
  const worker = await ready(h);
  h.app.ageRun();
  h.tickIntervals();
  assert.equal(h.app.state().running, true);
  assert.equal(worker.terminated, false);
  assert.equal(h.get("run-duty").disabled, false);
  h.get("run-duty").value = "2";
  h.app.updateProcessor();
  assert.equal(h.app.processorDuty(), 0.9);
  assert.match(h.get("duty-readout").textContent, /All in/);
  h.get("run-duty").value = "0";
  assert.equal(h.app.processorDuty(), 0.25);
  h.app.stop();
  await deliver(worker);
  await waitFor(() => worker.terminated, "unlimited run did not stop safely");
  assert.equal(
    [...h.stores.get("tasks").rows.values()][0].contributor.name,
    "Anonymous",
  );
}
console.log(
  "UI lifecycle checks passed: stop/drain, persistence, double start, failure recovery, anonymous unlimited runs and live processor slider. No external posts.",
);

// Starting never reads identity fields. Bank attribution is chosen later and
// changes neither the saved exact result nor an earlier prepared bank.
{
  const h = await harness({
    cachedProfile: { name: "Old alias", github: "old-user" },
  });
  h.get("player-github").value = "invalid handle";
  const worker = await ready(h);
  h.app.stop();
  await deliver(worker);
  await waitFor(() => worker.terminated, "anonymous result did not drain");
  const original = [...h.stores.get("tasks").rows.values()][0],
    before = JSON.stringify(original);
  assert.equal(original.contributor.name, "Anonymous");
  h.app.openBank();
  assert.equal(h.get("bank-panel").hidden, false);
  assert.equal(h.get("bank-receipt").hidden, true);
  h.get("player-name").value = "Later alias";
  h.get("player-github").value = "bad handle";
  await h.app.submitBankProfile(event());
  assert.equal(h.stores.get("banks").rows.size, 0);
  assert.match(h.get("bank-identity-status").textContent, /valid/);
  h.get("player-github").value = "@later-user";
  for (const url of ["javascript:alert(1)", "https://user:pass@example.com", "//example.com", "https://example.com:99999", "https://example.com/with space"]) {
    h.get("player-url").value = url;
    await h.app.submitBankProfile(event());
    assert.equal(h.stores.get("banks").rows.size, 0);
  }
  h.get("player-url").value = "https://example.com/about";
  await h.app.submitBankProfile(event());
  const first = [...h.stores.get("banks").rows.values()][0];
  assert.equal(first.payload.contributor.name, "Later alias");
  assert.equal(first.payload.contributor.github, "later-user");
  assert.equal(first.payload.contributor.url, "https://example.com/about");
  assert.equal(first.payload.tasks[0].digest, original.result.digest);
  assert.equal(
    JSON.stringify(h.stores.get("tasks").rows.get(original.id)),
    before,
  );
  await h.app.submitBankProfile(event());
  assert.equal(
    h.stores.get("banks").rows.size,
    1,
    "same bank identity must retain its prepared digest",
  );
  h.get("player-name").value = "Revised alias";
  await h.app.submitBankProfile(event());
  assert.equal(h.stores.get("banks").rows.size, 2);
  assert.equal(
    h.stores.get("banks").rows.get(first.digest).payload.contributor.name,
    "Later alias",
  );
  assert.equal(
    JSON.stringify(h.stores.get("tasks").rows.get(original.id)),
    before,
  );
  // A priority result retains its exact task when identity is supplied later.
  await h.app.prepareBank(original.id);
  h.get("player-name").value = "Priority alias";
  await h.app.submitBankProfile(event());
  const priority = JSON.parse(h.get("bank-body").value);
  assert.equal(priority.tasks.length, 1);
  assert.equal(engine.taskId(priority.tasks[0].task), original.id);
  assert.equal(priority.contributor.name, "Priority alias");
  console.log(
    "Deferred attribution checks passed: anonymous start, validation, unchanged exact receipts, stable banks and priority result retention.",
  );
}

// Display scaling never loses the exact integer value exposed to assistive tools.
{
  const h = await harness();
  for (const value of [0n, 123456789n, 999999999999999999999999999999999n]) {
    h.app.counter("local-inputs", value);
    const el = h.get("local-inputs");
    assert.ok(el.textContent.length <= 9);
    assert.equal(el.title, new Intl.NumberFormat("en-US").format(value));
    assert.equal(el.getAttribute("aria-label"), el.title);
  }
}

{
  const h = await harness({coverageFails: true});
  await h.app.start(event());
  assert.equal(h.workers.length, 0);
  assert.match(h.get("session-message").textContent, /coverage is unavailable/);
  assert.equal(h.app.state().starting, false);
}


// A tab hidden during a coverage lookup must not reserve a task that was never
// sent to a worker. A fixed test stream will choose that same task on resume.
{
  let releaseCoverage, lookups = 0;
  const h = await harness({
    randomFactory: () => ({ async below() { return 0n; } }),
    coverageProbe: () => ++lookups === 1
      ? new Promise(resolve => { releaseCoverage = resolve; }) : false,
  });
  await h.app.start(event());
  const worker = h.workers[0];
  worker.emit({ type: "ready" });
  await waitFor(() => lookups === 1, "coverage lookup was not held");
  h.visibility(true);
  releaseCoverage(false);
  await new Promise(setImmediate);
  assert.equal(worker.posts.length, 0, "hidden tab dispatched the pending selection");
  h.visibility(false);
  await waitFor(() => worker.posts.length === 1, "unissued selection was incorrectly excluded after resume");
  assert.equal(engine.taskId(worker.posts[0].task), engine.taskId(engine.makeTask("c00", "0", 0)));
  h.app.stop();
  await deliver(worker);
  await waitFor(() => worker.terminated, "resumed selection did not drain");
}

// An old receipt transaction can finish after a worker error and a replacement
// session. Keep that exact result and its original seed, without clearing the
// new worker's busy flag, changing its counters, or relabelling its provenance.
{
  let streams = 0;
  const h = await harness({ randomFactory: () => {
    const value = BigInt(streams++);
    return { async below(limit) { return value % BigInt(limit); } };
  } });
  const oldWorker = await ready(h), oldSeed = h.get("run-seed").textContent;
  const oldResult = await engine.runTask(oldWorker.posts[0].task);
  h.holdWrites();
  oldWorker.emit({ type: "result", result: oldResult, elapsedMs: 5 });
  await waitFor(() => h.pendingWriteCount() === 1, "old result did not reach durable-write barrier");
  oldWorker.onerror({ message: "fixture error while saving old result" });
  assert.equal(oldWorker.terminated, true);
  const newWorker = await ready(h), newSeed = h.get("run-seed").textContent;
  assert.notEqual(newSeed, oldSeed);
  assert.notEqual(engine.taskId(newWorker.posts[0].task), oldResult.id);
  oldWorker.onerror({ message: "late error event from terminated worker" });
  assert.equal(h.app.state().worker, newWorker);
  h.flushWrites();
  await waitFor(() => h.stores.get("tasks").rows.has(oldResult.id), "old completed receipt was lost");
  await new Promise(setImmediate);
  const oldStored = h.stores.get("tasks").rows.get(oldResult.id);
  assert.equal(oldStored.search_session.seed, oldSeed);
  assert.equal(oldStored.result.digest, oldResult.digest);
  assert.equal(h.app.state().running, true);
  assert.equal(h.app.state().busy, true);
  assert.equal(h.app.state().worker, newWorker);
  assert.equal(h.app.state().counts.tasks, 0);
  assert.equal(newWorker.terminated, false);
  h.app.stop();
  await deliver(newWorker);
  await waitFor(() => newWorker.terminated, "replacement session did not drain safely");
  assert.equal(h.stores.get("tasks").rows.size, 2);
}
console.log("Async coverage lifecycle checks passed: hidden selection retry and stale receipt/error isolation.");

// Known k=39 is substituted only inside this isolated host. No 114 solution is
// manufactured or submitted. Test the actual app's emergency and priority paths.
for (const brokenCelebration of [false, true]) {
  const h = await harness({ fixtureTarget: 39, brokenCelebration }), worker = await ready(h);
  const result = await engine.runTask(worker.posts[0].task);
  const xyz = ["-159380", "134476", "117367"];
  result.hits = [{xyz}];
  result.counters.hits = 1;
  const {digest, ...core} = result;
  result.digest = Buffer.from(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(engine.canonicalJSON(core)))).toString("hex");
  worker.emit({type: "result", result, elapsedMs: 5});
  await waitFor(() => h.stores.get("banks").rows.size === 1, "positive evidence never reached the priority bank");
  assert.equal(worker.terminated, true);
  assert.deepEqual(JSON.parse(h.local.get("mg-discovery-v1")).hits, [{xyz}]);
  const bank = JSON.parse(h.get("bank-body").value);
  assert.deepEqual(bank.tasks[0].hits, [{xyz}]);
  assert.equal(bank.tasks.length, 1);
  assert.equal(h.app.state().running, false);
}
{
  const h = await harness({fixtureTarget: 39}), worker = await ready(h);
  const xyz = ["-159380", "134476", "117367"];
  worker.emit({type: "result", result: {hits: [{xyz}], task: "broken envelope"}});
  await waitFor(() => worker.terminated, "malformed envelope did not stop after preserving its identity");
  assert.deepEqual(JSON.parse(h.local.get("mg-discovery-v1")).hits, [{xyz}]);
  assert.equal(h.stores.get("tasks").rows.size, 0, "bad envelope must not grant negative coverage");
  assert.equal(h.celebrations.length, 1);
}
{
  const h = await harness(), worker = await ready(h);
  worker.emit({type: "result", result: {hits: [{xyz: ["1", "2", "3"]}]}});
  await waitFor(() => worker.terminated, "invalid result did not stop");
  assert.equal(h.local.has("mg-discovery-v1"), false);
  assert.equal(h.celebrations.length, 0, "unverified candidates must never celebrate");
}
console.log("Positive lifecycle checks passed with isolated k=39: emergency preservation, priority banking, stop, animation-failure isolation and false-hit rejection.");

// A positive crosses the worker boundary before receipt hashing. Its independent
// backup survives a later worker error even when localStorage and downloads fail.
{
  const h = await harness({fixtureTarget: 39, localStorageFails: true, downloadFails: true});
  const worker = await ready(h), seed = h.get("run-seed").textContent;
  const xyz = ["-159380", "134476", "117367"];
  worker.emit({type: "identity", hit: {xyz}, task: worker.posts[0].task});
  worker.emit({type: "error", message: "fixture failure after the independently verified hit"});
  await waitFor(() => h.stores.get("identities").rows.size === 1, "early identity lost when the task later failed");
  const backup = [...h.stores.get("identities").rows.values()][0].evidence;
  assert.deepEqual(backup.hits, [{xyz}]);
  assert.equal(backup.search_session.seed, seed);
  assert.equal(h.local.has("mg-discovery-v1"), false);
  assert.equal(h.stores.get("tasks").rows.size, 0, "identity event must not grant task credit");
  assert.equal(h.app.state().counts.tasks, 0);
  assert.equal(worker.terminated, true);
  assert.equal(h.celebrations.length, 1);
  const restored = await harness({fixtureTarget: 39, localStorageFails: true,
    cachedIdentities: [...h.stores.get("identities").rows.values()]});
  await waitFor(() => restored.celebrations.length === 1, "durable identity backup was not recovered after reload");
  assert.deepEqual([...restored.celebrations[0].xyz], xyz);
  assert.equal(restored.celebrations[0].receipt.search_session.seed, seed);
  assert.equal(restored.celebrations[0].animate, false);
}
{
  const h = await harness({fixtureTarget: 39, identityStorageFails: true});
  const worker = await ready(h), xyz = ["-159380", "134476", "117367"];
  worker.emit({type: "identity", hit: {xyz}});
  await waitFor(() => h.local.has("mg-discovery-v1"), "local identity rescue was not synchronous");
  worker.emit({type: "error", message: "fixture receipt store failed"});
  await waitFor(() => !h.app.state().pendingIdentitySaves, "failed backup did not release its unload guard");
  assert.deepEqual(JSON.parse(h.local.get("mg-discovery-v1")).hits, [{xyz}]);
  assert.equal(h.stores.get("tasks").rows.size, 0);
}
{
  const h = await harness(), worker = await ready(h);
  worker.emit({type: "identity", hit: {xyz: ["1", "2", "3"]}});
  await new Promise(setImmediate);
  assert.equal(h.app.state().running, true, "an invalid early identity stopped the search");
  assert.equal(h.stores.get("identities").rows.size, 0);
  h.app.stop(); await deliver(worker);
  await waitFor(() => worker.terminated, "invalid identity fixture did not drain");
}

// Old-session evidence carries the old assignment, regardless of the currently
// running worker. Both early events and legacy result envelopes use this path.
for (const type of ["identity", "result"]) {
  const h = await harness({fixtureTarget: 39});
  const oldWorker = await ready(h), oldSeed = h.get("run-seed").textContent;
  oldWorker.onerror({message: "fixture restart"});
  const newWorker = await ready(h), newSeed = h.get("run-seed").textContent;
  const hit = {xyz: ["-159380", "134476", "117367"]};
  oldWorker.emit(type === "identity" ? {type, hit} : {type, result: {hits: [hit]}});
  await waitFor(() => h.local.has("mg-discovery-v1"), "late identity was not preserved");
  const evidence = JSON.parse(h.local.get("mg-discovery-v1"));
  assert.equal(evidence.search_session.seed, oldSeed);
  assert.notEqual(evidence.search_session.seed, newSeed);
  assert.equal(h.app.state().running, false);
  await deliver(newWorker);
  await waitFor(() => newWorker.terminated, "replacement worker did not drain after late identity");
}

// Optional refreshes cannot trap Stop after the receipt is already saved.
// Even a fetcher that never settles is bounded, and overlapping requests share
// one fetch. Real browser fetch also receives an AbortSignal.
{
  let stall = false, stalledRequests = 0, aborted = false;
  const h = await harness({fetchProbe: async (url, options) => {
    if (stall && String(url).endsWith("strategy.json")) {
      stalledRequests++;
      options.signal.addEventListener("abort", () => { aborted = true; });
      return new Promise(() => {});
    }
    throw Error("fixture offline");
  }});
  const worker = await ready(h);
  h.app.setRefreshCounter(63); stall = true;
  await deliver(worker);
  await waitFor(() => stalledRequests === 1, "64th completion did not request reports");
  assert.equal(h.app.state().busy, false, "report fetch held the durable-save barrier");
  assert.equal(h.stores.get("tasks").rows.size, 1);
  h.app.stop();
  assert.equal(worker.terminated, true);
  assert.equal(h.get("start-button").disabled, false);
  const waiting = h.app.fetchJSON("data/strategy.json");
  assert.equal(stalledRequests, 1, "overlapping report requests were not coalesced");
  h.tickTimeouts(12000);
  await assert.rejects(waiting, /timed out/);
  assert.equal(aborted, true);
}
{
  let report = null, aborted = false;
  const h = await harness({fetchProbe: async (_url, options) => {
    if (!report) throw Error("fixture offline");
    options.signal.addEventListener("abort", () => { aborted = true; });
    return report;
  }});
  report = new Response("{}", {headers: {"content-length": String(16 * 1024 * 1024 + 1)}});
  await assert.rejects(h.app.fetchJSON("data/oversized.json"), /size limit/);
  assert.equal(aborted, true);
  aborted = false;
  report = new Response(new ReadableStream({start(controller) {
    controller.enqueue(new Uint8Array(8 * 1024 * 1024));
    controller.enqueue(new Uint8Array(8 * 1024 * 1024 + 1));
    controller.close();
  }}));
  await assert.rejects(h.app.fetchJSON("data/oversized-stream.json"), /size limit/);
  assert.equal(aborted, true, "streaming reports also need a byte limit");
}

// Count a getter, not wall time: bank membership must be read once per dispatch,
// even after many successful banks. This fails deterministically on O(n²) scans.
{
  const h = await harness();
  await h.app.start(event());
  const history = Array.from({length: 10000}, (_, i) => ({id: `history-${i}`}));
  const ids = history.map(task => task.id);
  let reads = 0;
  h.app.setHistory(history, [{posted: true, get ids() { reads++; return ids; }}]);
  await h.app.dispatch();
  assert.equal(reads, 1, "dispatch rebuilt all posted IDs for each saved task");
  const worker = h.workers[0];
  assert.equal(worker.posts.length, 1);
  h.app.stop(); await deliver(worker);
  await waitFor(() => worker.terminated, "history regression did not drain");
}
console.log("Audit regressions passed: early identity rescue, independent storage failure, immutable worker provenance, bounded report refresh and linear history checks.");

{
  let refreshes = 0;
  const h = await harness({coverageRefreshProbe: () => {
    if (++refreshes > 1) throw Error("fixture new coverage unavailable");
  }});
  const worker = await ready(h);
  h.app.setRefreshCounter(63);
  await deliver(worker);
  await waitFor(() => h.app.state().counts.tasks === 1 && !h.app.state().busy, "64th result was not saved");
  await h.app.dispatch();
  assert.equal(refreshes, 2);
  assert.equal(worker.posts.length, 1, "failed mandatory coverage refresh allowed new work");
  assert.equal(worker.terminated, true);
  assert.equal(h.stores.get("tasks").rows.size, 1);
}
