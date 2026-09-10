import assert from "node:assert/strict";
import { CONTEXTS } from "../web/engine.mjs";
import { createLiveVisuals } from "../web/live-viz.mjs";
import { renderModelEvolution } from "../web/model-viz.mjs";
class Element {
  constructor() {
    this.children = [];
    this.attributes = {};
    this.textContent = "";
    this.value = "0";
    this.max = "0";
    this.style = {
      setProperty(k, v) {
        this[k] = v;
      },
    };
    this.events = {};
  }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
  }
  append(...n) {
    this.children.push(...n);
  }
  replaceChildren(...n) {
    this.children = n;
  }
  addEventListener(k, v) {
    this.events[k] = v;
  }
}
const elements = new Map();
const get = (id) => {
  if (!elements.has(id)) elements.set(id, new Element());
  return elements.get(id);
};
globalThis.document = {
  getElementById: get,
  createElement: () => new Element(),
  createElementNS: () => new Element(),
};
const descendants = (e) => [e, ...e.children.flatMap(descendants)];
const text = (e) => [e.textContent, ...e.children.map(text)].join("");
let now = 1000;
const clock = Date.now;
Date.now = () => now;
try {
  const visual = createLiveVisuals(CONTEXTS);
  visual.reset();
  const task = { context: "c00", block: 0 };
  visual.dispatch(task);
  now += 300;
  visual.result({
    result: {
      task,
      counters: {
        quotient_points: 1000,
        rejected_mod243: 800,
        rejected_parity: 150,
        rejected_prime: 45,
        exact_tests: 5,
        curves: 10,
      },
    },
    elapsedMs: 20,
  });
  assert.equal(get("run-lanes").children.length, 81);
  assert.equal(get("lane-total").textContent, "1 / 81 lanes played");
  assert.match(
    text(get("run-sieve")),
    /Candidates1KAfter mod 243200After parity50After prime filters5Exact square tests5/,
  );
  assert.equal(get("filter-cut").textContent, "99.5000% filtered");
  visual.state("paused");
  assert.match(text(get("run-wheel")), /PAUSED/);
  assert.equal(get("run-rate").textContent, "Paused");
  now += 300;
  visual.state("running");
  visual.result({
    result: {
      task,
      counters: {
        quotient_points: 1000,
        rejected_mod243: 800,
        rejected_parity: 150,
        rejected_prime: 45,
        exact_tests: 5,
        curves: 10,
      },
    },
    elapsedMs: 20,
  });
  visual.state("stopped");
  assert.equal(get("run-pulse").children[0].attributes.role, "img");
  assert.match(text(get("run-wheel")), /AT REST/);
  visual.reset();
  assert.equal(get("lane-total").textContent, "0 / 81 lanes played");
  assert.match(text(get("run-wheel")), /UNCLAIMED/);
  assert.equal(get("run-stream").children.length, 0);
  const uniform = Object.fromEntries(CONTEXTS.map((c) => [c.id, 1 / 81]));
  const second = { ...uniform, c00: 2 / 81, c01: 0 };
  const report = {
    totals: { verified_unique_tasks: 130 },
    calibration_history: [
      { epoch: 1, through_verified_tasks: 64, weights: uniform },
      { epoch: 2, through_verified_tasks: 128, weights: second },
    ],
  };
  renderModelEvolution(report, {
    epoch: 2,
    contexts: [{ sample_size: 3 }, { sample_size: 2 }],
  });
  assert.equal(get("model-selected").textContent, "Epoch 2 · 128 batches");
  assert.equal(get("model-trained").textContent, "1");
  assert.equal(get("model-progress").value, 2);
  const bars = () =>
    descendants(get("model-history")).filter(
      (n) => n.attributes.class === "model-bar",
    );
  assert.equal(bars().length, 81);
  assert.equal(Number(bars()[1].attributes.height), 0);
  assert.ok(bars().every((n) => Number.isFinite(Number(n.attributes.height))));
  get("model-epoch").value = "0";
  get("model-epoch").oninput();
  assert.equal(get("model-selected").textContent, "Uniform prior · 0 batches");
  assert.equal(new Set(bars().map((b) => b.attributes.height)).size, 1);
  renderModelEvolution(report, { epoch: 2, contexts: [] });
  assert.equal(
    get("model-epoch").value,
    "0",
    "polling must preserve a selected historical epoch",
  );
  bars()[0].events.click();
  assert.match(get("model-detail").textContent, /epoch 0/);
  console.log(
    "Visual checks passed: real filter conservation, state/reset, finite plots, recorded epochs, uniform prior and history selection.",
  );
} finally {
  Date.now = clock;
  delete globalThis.document;
}
