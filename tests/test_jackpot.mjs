import assert from "node:assert/strict";
import { createJackpot } from "../web/jackpot.mjs";

class Element {
  constructor() { this.children = []; this.hidden = true; this.events = {}; this.style = {setProperty() {}}; }
  append(item) { this.children.push(item); }
  setAttribute() {}
  addEventListener(event, callback) { this.events[event] = callback; }
  remove() { this.removed = true; }
  focus() { this.focused = true; }
  scrollIntoView() {}
}
const nodes = new Map(), events = {};
const root = { hidden: false, body: new Element(), createElement: () => new Element(),
  getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); },
  addEventListener(event, callback) { events[event] = callback; },
};
let reduced = false, saved;
globalThis.matchMedia = () => ({matches: reduced});
const xyz = ["-159380", "134476", "117367"]; // Known k=39 fixture, never a fabricated 114 solution.
const production = createJackpot({root});
assert.equal(production.show({xyz}), false, "a different target cannot trigger the 114 jackpot");
assert.equal(root.getElementById("jackpot-panel").hidden, true);
assert.equal(root.body.children.length, 0);
const display = createJackpot({root, target: 39, onSave: (value) => { saved = value; }});
const receipt = {contributor: {name: "Fixture", github: "fixture"}, hits: [{xyz}]};
assert.equal(display.show({xyz: ["-159380", "134476", "117368"], receipt}), false);
assert.equal(display.show({xyz, receipt}), true);
assert.equal(root.getElementById("jackpot-panel").hidden, false);
assert.match(root.getElementById("jackpot-equation").textContent, /= 39$/);
assert.equal(root.body.children.length, 1);
assert.equal(root.body.children[0].children.length, 144);
assert.equal(root.body.children[0].children.filter((e) => e.className === "jackpot-sparkle").length, 36);
const bank = JSON.parse(new URL(root.getElementById("jackpot-bank").href).searchParams.get("body"));
assert.equal(bank.schema, "math-gambling-identity-v1");
assert.deepEqual(bank.hits, [{xyz}]);
assert.equal(Object.hasOwn(bank, "tasks"), false);
root.getElementById("jackpot-save").events.click();
assert.equal(saved, receipt);
display.show({xyz: [...xyz].reverse(), receipt});
assert.equal(root.body.children.length, 1, "duplicate/permuted identities cannot repeat the effects");
root.hidden = true;
events.visibilitychange();
assert.equal(root.body.children[0].removed, true);
display.show({xyz, receipt: {}, source: "cluster"});
root.getElementById("jackpot-save").events.click();
assert.equal(saved, receipt, "a global refresh cannot replace local discovery evidence");
root.hidden = false;
reduced = true;
const quietDisplay = createJackpot({root, target: 39});
quietDisplay.show({xyz, receipt, source: "cluster"});
assert.equal(root.body.children.length, 1, "reduced motion displays no particles");
assert.match(root.getElementById("jackpot-status").textContent, /cluster found/);
assert.match(root.getElementById("jackpot-bank").href, /data\/receipts\/hits$/);
quietDisplay.quiet();
delete globalThis.matchMedia;
console.log("Jackpot gate verified: exact arithmetic, malformed/other-target rejection, particle cleanup, reduced motion, deduplication, evidence save and identity banking.");
