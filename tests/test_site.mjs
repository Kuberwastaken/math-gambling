/* Controlled UI lifecycle test, without a browser or network.
 * This executes the actual app source with a minimal DOM/IndexedDB/Worker host.
 * It is not a visual, browser-compatibility, or real-storage durability test.
 */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import vm from "node:vm";
import * as engine from "../web/engine.mjs";

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
} = {}) {
  const elements = new Map();
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, new Element(id));
    return elements.get(id);
  };
  get("run-duty").value = "50";
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
  const local = new Map();
  if (cachedProfile !== null)
    local.set("mg-profile", JSON.stringify(cachedProfile));
  const stores = new Map(),
    workers = [],
    pendingWrites = [],
    timeouts = new Map(),
    intervals = new Map();
  let holdWrites = false,
    timerId = 0;
  const connection = {
    createObjectStore(name, { keyPath }) {
      stores.set(name, { keyPath, rows: new Map() });
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
    open() {
      const req = {};
      queueMicrotask(() => {
        req.result = connection;
        req.onupgradeneeded?.();
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
    __engine: engine,
    console,
    document,
    indexedDB,
    Worker: FakeWorker,
    localStorage: {
      getItem: (key) => local.get(key) ?? null,
      setItem: (key, value) => local.set(key, String(value)),
      removeItem: (key) => local.delete(key),
    },
    crypto: globalThis.crypto,
    TextEncoder,
    TextDecoder,
    URL,
    Blob,
    Intl,
    Date,
    navigator: { clipboard: { writeText: async () => {} } },
    window: { print() {}, addEventListener() {} },
    matchMedia: () => ({ matches: true }),
    fetch: async () => {
      throw new Error("fixture offline; no network requests");
    },
    setTimeout(fn) {
      const id = ++timerId;
      timeouts.set(id, fn);
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
    `(async()=>{${source}\n globalThis.__app={start,stop,dispatch,processorDuty,updateProcessor,
    state:()=>({running,starting,busy,worker,tasks,counts}),
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
  assert.equal(worker.posts.length, 1);
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
  assert.equal(stored.contributor.name, "Lifecycle test");
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
  h.get("run-duty").value = "90";
  h.app.updateProcessor();
  assert.equal(h.app.processorDuty(), 0.9);
  assert.match(h.get("duty-readout").textContent, /All in/);
  h.get("run-duty").value = "5";
  assert.equal(h.app.processorDuty(), 0.05);
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
