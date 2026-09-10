import {
  CONTEXTS,
  makeTask,
  taskId,
  canonicalJSON,
  verifyTriple,
  validateTask,
} from "./engine.mjs";
import { createLiveVisuals } from "./live-viz.mjs";
const BASE = new URL("./", import.meta.url),
  REPO = "https://github.com/Kuberwastaken/math-gambling";
const $ = (id) => document.getElementById(id),
  text = (id, v) => {
    if ($(id)) $(id).textContent = v;
  };
const nf = new Intl.NumberFormat("en-US"),
  compact = new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  });
const fmt = (v) => {
  try {
    return nf.format(BigInt(v ?? 0));
  } catch {
    return "—";
  }
};
const small = (v) => {
  try {
    return compact.format(BigInt(v ?? 0));
  } catch {
    return "—";
  }
};
const date = (v) => {
  const d = new Date(v);
  return Number.isFinite(d.getTime())
    ? d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : "No timestamp";
};
const fetchJSON = async (file) => {
  const response = await fetch(new URL(file, BASE), { cache: "no-cache" });
  if (!response.ok) throw new Error(`Report unavailable (${response.status})`);
  return response.json();
};
let liveVisuals;
try {
  liveVisuals = createLiveVisuals(CONTEXTS);
} catch {
  /* Visuals never decide coverage. */
}
function showRun(method, value) {
  try {
    liveVisuals?.[method](value);
  } catch {
    liveVisuals = null;
    text(
      "viz-state",
      "Charts paused. Exact computation and saving remain active.",
    );
  }
}
function processorDuty() {
  const value = Number($("run-duty")?.value);
  return Math.min(90, Math.max(5, Number.isFinite(value) ? value : 25)) / 100;
}
function updateProcessor() {
  const percent = Math.round(processorDuty() * 100);
  text(
    "duty-readout",
    `${percent}% · ${percent === 90 ? "All in" : percent >= 60 ? "Feeling lucky" : percent >= 40 ? "A little more" : "Taking it easy"}`,
  );
  $("run-duty")?.setAttribute(
    "aria-valuetext",
    `${percent} percent of one worker${percent === 90 ? ", All in" : ""}`,
  );
}
$("run-duty")?.addEventListener("input", updateProcessor);
updateProcessor();
let profile = { name: "", github: "" };
try {
  profile = JSON.parse(localStorage.getItem("mg-profile") || "null") || profile;
} catch {}
profile = {
  name: typeof profile?.name === "string" ? profile.name.slice(0, 60) : "",
  github:
    typeof profile?.github === "string" ? profile.github.slice(0, 39) : "",
};
function profilePreview() {
  const name =
    typeof profile.name === "string" ? profile.name.slice(0, 60) : "";
  text("teaser-name", name || "________________________");
  text(
    "paper-contributor",
    name
      ? `Local contribution preview: ${name}${profile.github ? ` (@${profile.github})` : ""}`
      : "Contributor credit: ________________________",
  );
  if (name)
    text(
      "paper-preview-note",
      `This copy previews a contribution credit for ${name}. The finder and result remain blank. This is not a claim of authorship or discovery.`,
    );
}
profilePreview();
$("clear-profile")?.addEventListener("click", () => {
  localStorage.removeItem("mg-profile");
  profile = { name: "", github: "" };
  text(
    "clear-profile-status",
    "Profile removed. Computation receipts are retained.",
  );
  profilePreview();
});
$("print-paper")?.addEventListener("click", () => window.print());
function download(name, body, type = "application/json") {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
$("download-tex")?.addEventListener("click", async (e) => {
  if (!profile.name) return;
  e.preventDefault();
  try {
    let t = await (
      await fetch(new URL("downloads/math-gambling-draft.tex", BASE))
    ).text();
    const esc = (s) =>
      s.replace(
        /[\\{}$&#_%~^]/g,
        (c) =>
          ({
            "\\": "\\textbackslash{}",
            "{": "\\{",
            "}": "\\}",
            $: "\\$",
            "&": "\\&",
            "#": "\\#",
            _: "\\_",
            "%": "\\%",
            "~": "\\textasciitilde{}",
            "^": "\\textasciicircum{}",
          })[c],
      );
    t = t.replace(
      "\\underline{\\hspace{45mm}}",
      esc(profile.name + (profile.github ? ` (@${profile.github})` : "")),
    );
    download("math-gambling-personal-preview.tex", t, "application/x-tex");
  } catch {
    text(
      "paper-preview-note",
      "Download failed. The source remains available in the repository.",
    );
  }
});
const filterText = [
  "First, check the exact norm and whether it belongs to the task’s allowed shell.",
  "Require an invertible root extractor and independently check r³ ≡ 114 (mod D). Noninvertible inputs are unresolved, not globally impossible.",
  "Apply necessary congruence, parity and quadratic-residue conditions. A failed condition rules out that candidate. No model is involved.",
  "Use exact integer division and an integer square root. A floating-point near miss does not count.",
  "Reconstruct integer x and y, then add x³ + y³ + z³ exactly. A discovery must equal 114. GitHub’s verifier checks again independently.",
];
$("filter-stage")?.addEventListener("input", (e) =>
  text("filter-explanation", filterText[Number(e.target.value)]),
);

function lineChart(el, points, { label, format = small, height = 170 } = {}) {
  if (!el) return;
  const clean = points.filter(
    (p) => Number.isFinite(p.x) && Number.isFinite(p.y),
  );
  if (clean.length < 2) {
    el.replaceChildren(
      Object.assign(document.createElement("p"), {
        textContent: "Not enough recorded observations to draw a trend.",
      }),
    );
    return;
  }
  const W = 1000,
    H = height,
    pl = 75,
    pr = 12,
    pt = 15,
    pb = 30,
    minx = Math.min(...clean.map((p) => p.x)),
    maxx = Math.max(...clean.map((p) => p.x));
  let miny = Math.min(...clean.map((p) => p.y)),
    maxy = Math.max(...clean.map((p) => p.y));
  if (maxy === miny) {
    miny = Math.max(0, miny - 1);
    maxy += 1;
  }
  const X = (x) => pl + ((x - minx) / (maxx - minx || 1)) * (W - pl - pr),
    Y = (y) => pt + (1 - (y - miny) / (maxy - miny)) * (H - pt - pb);
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", label || "Recorded measurements");
  function node(tag, attrs, content) {
    const n = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (content != null) n.textContent = content;
    svg.append(n);
    return n;
  }
  const title = document.createElementNS(ns, "title");
  title.textContent = label || "Recorded measurements";
  svg.append(title);
  for (let i = 0; i < 3; i++) {
    const val = miny + ((maxy - miny) * i) / 2,
      y = Y(val);
    node("line", { x1: pl, y1: y, x2: W - pr, y2: y, class: "chart-grid" });
    node(
      "text",
      { x: pl - 10, y: y + 4, "text-anchor": "end", class: "chart-label" },
      format(Math.round(val)),
    );
  }
  node("path", {
    d: clean
      .map(
        (p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(2)},${Y(p.y).toFixed(2)}`,
      )
      .join(" "),
    class: "chart-line",
  });
  node(
    "text",
    { x: pl, y: H - 5, class: "chart-label" },
    clean[0].label || "Start",
  );
  node(
    "text",
    { x: W - pr, y: H - 5, "text-anchor": "end", class: "chart-label" },
    clean.at(-1).label || "Latest",
  );
  el.replaceChildren(svg);
}
function calibrationScatter(mac) {
  const el = $("mac-calibration");
  if (!el) return;
  const h = mac.learning?.holdout || {},
    rows = (h.rows || []).filter((r) => r.predicted > 0 && r.observed > 0);
  text(
    "mac-calibration-note",
    `Rank correlation: ${Number.isFinite(h.spearman) ? h.spearman.toFixed(3) : "unavailable"}. Top-quarter observed throughput / baseline: ${Number.isFinite(h.top_quarter_over_baseline) ? h.top_quarter_over_baseline.toFixed(2) + "×" : "unavailable"}. ${rows.length} held-out contexts.`,
  );
  if (!rows.length) {
    el.textContent = "No per-context calibration observations are available.";
    return;
  }
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 1000 340");
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    "Frozen Mac model: predicted versus observed conditional throughput, logarithmic axes",
  );
  const values = rows.flatMap((r) => [
      Math.log10(r.predicted),
      Math.log10(r.observed),
    ]),
    lo = Math.floor(Math.min(...values)),
    hi = Math.ceil(Math.max(...values)),
    X = (v) => 80 + ((v - lo) / (hi - lo)) * 860,
    Y = (v) => 290 - ((v - lo) / (hi - lo)) * 260;
  function node(tag, attrs, value) {
    const e = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (value != null) e.textContent = value;
    svg.append(e);
    return e;
  }
  for (let i = lo; i <= hi; i++) {
    node("line", { x1: 80, y1: Y(i), x2: 940, y2: Y(i), class: "chart-grid" });
    node(
      "text",
      { x: 70, y: Y(i) + 4, "text-anchor": "end", class: "chart-label" },
      small(10 ** i),
    );
    node(
      "text",
      { x: X(i), y: 315, "text-anchor": "middle", class: "chart-label" },
      small(10 ** i),
    );
  }
  node("line", {
    x1: 80,
    y1: 290,
    x2: 940,
    y2: 30,
    stroke: "#b5c5b8",
    "stroke-dasharray": "4 5",
  });
  for (const r of rows) {
    const circle = node("circle", {
      cx: X(Math.log10(r.predicted)),
      cy: Y(Math.log10(r.observed)),
      r: 4,
      fill: "#dfbd72",
      "fill-opacity": ".7",
    });
    const t = document.createElementNS(ns, "title");
    t.textContent = `${r.context}: predicted ${r.predicted.toFixed(2)}, observed ${r.observed.toFixed(2)}`;
    circle.append(t);
  }
  node(
    "text",
    { x: 510, y: 338, "text-anchor": "middle", class: "chart-label" },
    "Predicted throughput score",
  );
  node(
    "text",
    { x: 80, y: 15, class: "chart-label" },
    "Observed throughput score",
  );
  el.replaceChildren(svg);
}

let macData = null,
  clusterData = null,
  strategy = null;
async function loadMac() {
  if (!$("mac-curves")) return;
  try {
    const [mac, history] = await Promise.all([
      fetchJSON("data/mac.json"),
      fetchJSON("data/mac-history.json"),
    ]);
    macData = mac;
    calibrationScatter(mac);
    text("mac-curves", small(mac.totals?.curve_checks));
    text("mac-exact", small(mac.totals?.exact_tests));
    text("mac-hits", fmt((mac.solutions || []).length));
    const age = Date.now() - Date.parse(mac.updated_utc),
      stale = age > 2 * 3600000;
    text(
      "mac-state",
      stale
        ? "Snapshot overdue"
        : mac.state === "running"
          ? "Running at report time"
          : mac.state || "Snapshot",
    );
    text(
      "mac-updated",
      `${date(mac.updated_utc)}${stale ? " · more than 2 hours old" : ""}`,
    );
    if (history.snapshot_id === mac.snapshot_id || !history.snapshot_id) {
      const points = (history.samples || [])
        .filter((s) => s.totals?.curve_checks != null)
        .map((s) => ({
          x: Date.parse(s.updated_utc),
          y: Number(s.totals.curve_checks),
          label: new Date(s.updated_utc).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        }));
      lineChart($("mac-history-chart"), points, {
        label:
          "Recorded cumulative curve-interval checks in the native Mac campaign. The vertical axis is cropped to the observed range.",
      });
    } else
      text(
        "mac-history-chart",
        "The history snapshot is updating. Please refresh shortly.",
      );
    const audit = mac.audit || {},
      pass =
        audit.database_integrity === "ok" &&
        audit.source_identity_matches === true &&
        audit.reserved_tiles_disjoint_and_gapless === true;
    text(
      "mac-audit",
      `Audit: ${pass ? "integrity, source identity and reservation checks passed" : "see the source report for available checks"}. Observed ${date(audit.observed_utc)}. The throughput model is not a probability model.`,
    );
  } catch (e) {
    text("mac-state", "Report unavailable");
    text("mac-updated", e.message);
    text(
      "mac-history-chart",
      "No current report available. We do not extrapolate missing data.",
    );
  }
}
function renderAllocation() {
  if (!$("allocation-chart") || !strategy) return;
  const items = strategy.contexts || [],
    max = Math.max(...items.map((c) => Number(c.weight) || 0), 1 / 81),
    grid = $("allocation-chart");
  grid.replaceChildren();
  for (const context of CONTEXTS) {
    const entry = items.find((c) => c.id === context.id) || { weight: 1 / 81 };
    const b = document.createElement("button");
    b.className = "context-cell";
    b.textContent = context.id;
    b.setAttribute("aria-pressed", "false");
    b.setAttribute(
      "aria-label",
      `${context.id}, allocation ${(100 * entry.weight).toFixed(2)} percent`,
    );
    const intensity = Math.max(
      0.12,
      Math.min(0.7, ((Number(entry.weight) || 0) / max) * 0.7),
    );
    b.style.backgroundColor = `rgb(223 189 114 / ${intensity})`;
    b.addEventListener("click", () => {
      for (const c of grid.children) c.setAttribute("aria-pressed", "false");
      b.setAttribute("aria-pressed", "true");
      text(
        "context-detail",
        `${context.id}: ℓ=${context.ell}, shape ${context.shape + 1}, shell ${context.shell + 1}, |z|/D ∈ (${context.low}, ${context.high}]. Allocation ${(100 * entry.weight).toFixed(2)}%. ${entry.sample_size || 0} replay observations; ${entry.robust_cpu_ms == null ? "no stable cost estimate" : Number(entry.robust_cpu_ms).toFixed(2) + " ms robust replay cost"}.`,
      );
    });
    grid.append(b);
  }
  text("strategy-epoch", `Epoch ${strategy.epoch ?? 0}`);
  text(
    "strategy-reason",
    strategy.reason ||
      "Uniform allocation until enough verified observations exist.",
  );
}
async function loadStrategy() {
  try {
    const s = await fetchJSON("data/strategy.json");
    const entries = s.contexts;
    if (
      !Array.isArray(entries) ||
      entries.length !== 81 ||
      new Set(entries.map((c) => c.id)).size !== 81 ||
      entries.some(
        (c) =>
          !CONTEXTS.some((x) => x.id === c.id) ||
          !Number.isFinite(c.weight) ||
          c.weight < 0.4 / 81 - 1e-10,
      ) ||
      Math.abs(entries.reduce((a, c) => a + c.weight, 0) - 1) > 0.001
    )
      throw Error("Invalid policy");
    strategy = s;
    showRun("policy", strategy);
    renderAllocation();
  } catch {
    strategy = null;
    showRun("policy", null);
    text(
      "strategy-reason",
      "Strategy unavailable or invalid. Browser work uses uniform exploration.",
    );
  }
}
async function loadCluster() {
  try {
    clusterData = await fetchJSON("data/cluster.json");
    const t = clusterData.totals || {};
    text("cluster-reported", fmt(t.reported_tasks));
    text("cluster-inputs", fmt(t.verified_computations));
    text("cluster-verified", fmt(t.verified_unique_tasks));
    text("cluster-duplicates", fmt(t.duplicate_tasks));
    text("cluster-hits", fmt(t.verified_hits));
    text(
      "cluster-updated",
      clusterData.updated_at
        ? `Snapshot generated ${date(clusterData.updated_at)}`
        : "No published verification run yet",
    );
    text(
      "cluster-note",
      Number(t.verified_unique_tasks)
        ? "Ranked by independently verified inputs. Duplicate tasks earn no extra credit."
        : "The volunteer ledger starts at zero. Be the first to bank a verified computation.",
    );
    const body = $("contributors");
    if (body) {
      body.replaceChildren();
      const people = [...(clusterData.contributors || [])].sort((a, b) => {
        const x = BigInt(a.verified_computations || 0),
          y = BigInt(b.verified_computations || 0);
        return y > x ? 1 : y < x ? -1 : 0;
      });
      if (!people.length) {
        const row = body.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 3;
        cell.textContent =
          "No independently verified volunteer contributions yet.";
      } else
        for (const [rank, p] of people.entries()) {
          const row = body.insertRow();
          const alias = row.insertCell();
          const place = document.createElement("span");
          place.className = "rank-number";
          place.textContent = String(rank + 1).padStart(2, "0");
          const name = document.createElement("span");
          name.textContent = p.name || p.submitter || "Contributor";
          alias.append(place, name);
          const user = String(p.submitter || "");
          const cell = row.insertCell();
          if (/^[A-Za-z0-9-]{1,39}$/.test(user)) {
            const a = document.createElement("a");
            a.href = `https://github.com/${user}`;
            a.textContent = `@${user}`;
            cell.append(a);
          } else cell.textContent = "Unattributed";
          row.insertCell().textContent = `${fmt(p.verified_computations)} inputs · ${fmt(p.verified_tasks)} tasks`;
        }
    }
    const hist = clusterData.calibration_history || [];
    if (hist.length > 1)
      lineChart(
        $("calibration-chart"),
        hist.map((h) => ({
          x: Number(h.epoch),
          y: Number(h.through_verified_tasks ?? h.verified_unique_tasks ?? 0),
          label: `Epoch ${h.epoch}`,
        })),
        { label: "Verified unique tasks at recorded policy epochs" },
      );
    if ($("cluster-discoveries")) $("cluster-discoveries").replaceChildren();
    if ($("cluster-discoveries"))
      for (const d of clusterData.discoveries || []) {
        const xyz = d.xyz || d.hit?.xyz;
        if (verifyTriple(xyz)) {
          const p = document.createElement("p");
          p.className = "discovery";
          p.textContent = `Verified identity: ${xyz.map((x) => `(${x})³`).join(" + ")} = 114. See the repository evidence for attribution.`;
          $("cluster-discoveries").append(p);
        }
      }
    if ($("join-form")) await reconcileBanks();
  } catch (e) {
    text(
      "cluster-note",
      "Published ledger unavailable. Local computation remains available.",
    );
    text("cluster-updated", "Could not load report");
  }
}

// Finished tasks and prepared banks persist separately. Preparing/copying is not submitting.
let dbPromise;
function db() {
  return (dbPromise ??= new Promise((resolve, reject) => {
    const request = indexedDB.open("math-gambling-v1", 1);
    request.onupgradeneeded = () => {
      const d = request.result;
      d.createObjectStore("tasks", { keyPath: "id" });
      d.createObjectStore("banks", { keyPath: "digest" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  }));
}
async function readAll(store) {
  const d = await db();
  return new Promise((resolve, reject) => {
    const tx = d.transaction(store),
      req = tx.objectStore(store).getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function save(store, record) {
  const d = await db();
  return new Promise((resolve, reject) => {
    const tx = d.transaction(store, "readwrite");
    tx.objectStore(store).put(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || Error("Storage aborted"));
  });
}
async function hash(obj) {
  const b = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(
      canonicalJSON(obj).replace(
        /[\u007f-\uffff]/g,
        (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"),
      ),
    ),
  );
  return Array.from(new Uint8Array(b), (x) =>
    x.toString(16).padStart(2, "0"),
  ).join("");
}
let tasks = [],
  banks = [],
  activeBank = null;
function validStoredTask(t) {
  try {
    return (
      t &&
      t.id === taskId(t.result.task) &&
      t.result.id === t.id &&
      validProfile(t.contributor) &&
      typeof t.result.digest === "string" &&
      /^[0-9a-f]{64}$/.test(t.result.digest)
    );
  } catch {
    return false;
  }
}
async function refreshSaved() {
  const records = await readAll("tasks");
  tasks = records
    .filter(validStoredTask)
    .sort((a, b) => String(a.created).localeCompare(String(b.created)));
  banks = (await readAll("banks")).filter(
    (b) =>
      b &&
      typeof b.digest === "string" &&
      Array.isArray(b.ids) &&
      b.ids.every((id) => typeof id === "string") &&
      b.payload?.schema === "math-gambling-bank-v1",
  );
  if (tasks.length !== records.length)
    text(
      "session-message",
      "Some stored records have an unsupported format. They are retained in local storage; save your receipts before clearing browser data.",
    );
  updateBankUI();
}
function coveredIds() {
  return new Set(
    banks
      .filter((b) => b.status !== "rejected" && (b.observed || b.posted))
      .flatMap((b) => b.ids),
  );
}
function updateBankUI() {
  if (!$("bank-button")) return;
  const covered = coveredIds(),
    pending = tasks.filter((t) => !covered.has(t.id));
  text(
    "sync-state",
    `${fmt(tasks.length)} saved locally · ${fmt(pending.length)} ready to bank`,
  );
  $("bank-button").disabled = pending.length === 0;
  $("download-receipts").disabled = tasks.length === 0;
  const list = $("bank-history");
  if (list) {
    list.replaceChildren();
    for (const b of [...banks].reverse().slice(0, 8)) {
      const p = document.createElement("p");
      p.className = "form-note";
      p.textContent = b.observed
        ? `Bank ${b.digest.slice(0, 8)}: ${b.status}. ${b.accepted || 0} accepted, ${b.duplicates || 0} duplicates, ${b.rejected || 0} rejected; ${b.processed || 0}/${b.ids.length} processed.`
        : `Bank ${b.digest.slice(0, 8)}: ${b.posted ? "marked posted locally; not yet in published ledger" : "prepared locally; not submitted"}. ${b.ids.length} tasks.`;
      if (b.issue) {
        const a = document.createElement("a");
        a.href = `${REPO}/issues/${Number(b.issue)}`;
        a.textContent = " View submission ↗";
        p.append(a);
      }
      list.append(p);
    }
  }
}
async function reconcileBanks() {
  if (!clusterData) return;
  try {
    banks = await readAll("banks");
    let changed = false;
    for (const bank of banks) {
      const entry = (clusterData.banks || []).find(
        (b) => b.bank_digest === bank.digest,
      );
      if (entry) {
        bank.observed = true;
        bank.status = entry.status;
        bank.issue = entry.issue;
        bank.accepted = entry.accepted_tasks;
        bank.duplicates = entry.duplicate_tasks;
        bank.rejected = entry.rejected_tasks;
        bank.processed = entry.processed_tasks;
        await save("banks", bank);
        changed = true;
      }
    }
    if (changed) await refreshSaved();
  } catch {}
}
function validProfile(p) {
  return (
    typeof p.name === "string" &&
    p.name.trim().length > 0 &&
    p.name.length <= 60 &&
    typeof p.github === "string" &&
    (!p.github ||
      /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/.test(p.github))
  );
}
async function prepareBank(priorityId = null) {
  await refreshSaved();
  const observed = coveredIds();
  const pending = priorityId
    ? tasks.filter((t) => t.id === priorityId)
    : tasks.filter((t) => !observed.has(t.id));
  if (!pending.length) return;
  // A pending prepared bank stays stable until it appears in GitHub's published ledger.
  const previous = priorityId
    ? null
    : banks.find((b) => !b.observed && !b.posted);
  let bank = previous;
  if (!bank) {
    const owner = pending[0].contributor;
    const claims = [];
    for (const r of pending
      .filter(
        (t) =>
          t.contributor.name === owner.name &&
          t.contributor.github === owner.github,
      )
      .slice(0, 256)) {
      const claim = { task: r.result.task, digest: r.result.digest };
      if (r.result.hits?.length) claim.hits = r.result.hits;
      const candidate = {
        schema: "math-gambling-bank-v1",
        contributor: owner,
        tasks: [...claims, claim],
      };
      if (new TextEncoder().encode(JSON.stringify(candidate)).length > 58000)
        break;
      claims.push(claim);
    }
    const payload = {
      schema: "math-gambling-bank-v1",
      contributor: owner,
      tasks: claims,
    };
    const digest = await hash(payload);
    bank = {
      digest,
      payload,
      ids: claims.map((c) => taskId(c.task)),
      observed: false,
      created: new Date().toISOString(),
    };
    await save("banks", bank);
    banks.push(bank);
  }
  activeBank = bank;
  $("bank-panel").hidden = false;
  $("bank-body").value = JSON.stringify(bank.payload);
  text(
    "bank-count",
    `${bank.ids.length} completed tasks in this bank. Your receipt is kept locally until it appears in the published ledger.`,
  );
  $("bank-open").href =
    `${REPO}/issues/new?template=compute.yml&title=${encodeURIComponent("[compute] Bank " + bank.ids.length + " tasks")}`;
  updateBankUI();
  $("bank-panel").scrollIntoView({
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "instant"
      : "smooth",
    block: "nearest",
  });
}
$("bank-button")?.addEventListener("click", () =>
  prepareBank().catch((e) =>
    text(
      "session-message",
      `Could not prepare bank: ${e.message}. Save your receipts instead.`,
    ),
  ),
);
$("copy-bank")?.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("bank-body").value);
    text(
      "copy-status",
      "Copied. Open GitHub, paste into the receipt field, and submit the issue.",
    );
  } catch {
    $("bank-body").focus();
    $("bank-body").select();
    text(
      "copy-status",
      "Clipboard unavailable. The receipt is selected; copy it, then paste on GitHub.",
    );
  }
});
$("posted-bank")?.addEventListener("click", async () => {
  if (!activeBank) return;
  activeBank.posted = true;
  await save("banks", activeBank);
  await refreshSaved();
  $("bank-panel").hidden = true;
  text(
    "session-message",
    "Marked posted on this device. This is not verification; the published ledger will confirm processing.",
  );
});
$("download-bank")?.addEventListener("click", () => {
  if (activeBank)
    download(
      `math-gambling-bank-${activeBank.digest.slice(0, 12)}.json`,
      JSON.stringify(activeBank.payload, null, 2) + "\n",
    );
});
$("download-receipts")?.addEventListener("click", async () => {
  const raw = await readAll("tasks");
  download(
    "math-gambling-local-results.jsonl",
    raw.map((t) => JSON.stringify(t)).join("\n") + "\n",
    "application/x-ndjson",
  );
});

let worker = null,
  running = false,
  starting = false,
  busy = false,
  stopReason = "",
  sessionGeneration = 0,
  activeTask = null,
  startAt = 0,
  nextTimer = null,
  runTimer = null,
  counts = { generators: 0, curves: 0, exact_tests: 0, tasks: 0 },
  seen = new Set(),
  completedSinceRefresh = 0;
function randBelow(limit) {
  const n = BigInt(limit);
  if (n <= 0n) throw Error("Invalid random bound");
  const max = 1n << 64n,
    cap = max - (max % n);
  for (;;) {
    const bytes = crypto.getRandomValues(new Uint32Array(2));
    const r = (BigInt(bytes[0]) << 32n) | BigInt(bytes[1]);
    if (r < cap) return r % n;
  }
}
function nextTask() {
  const weights =
    strategy?.contexts || CONTEXTS.map((c) => ({ id: c.id, weight: 1 / 81 }));
  for (let attempt = 0; attempt < 100; attempt++) {
    let draw = Number(randBelow(1n << 53n)) / 2 ** 53;
    let id = weights.at(-1).id;
    for (const c of weights) {
      draw -= c.weight;
      if (draw <= 0) {
        id = c.id;
        break;
      }
    }
    const c = CONTEXTS.find((c) => c.id === id);
    const task = makeTask(
      id,
      randBelow(c.rowTasks) * BigInt(c.rowStride),
      Number(randBelow(c.blocks)),
    );
    if (!seen.has(taskId(task))) {
      seen.add(taskId(task));
      return task;
    }
  }
  throw Error("Could not allocate a fresh local task");
}
function renderCounts() {
  text("local-inputs", fmt(counts.generators));
  text("local-curves", fmt(counts.curves));
  text("local-exact", fmt(counts.exact_tests));
  text("local-tasks", fmt(counts.tasks));
}
function finishStop() {
  if (busy) return;
  worker?.terminate();
  worker = null;
  $("stop-button").disabled = true;
  $("start-button").disabled = false;
  text("session-state", "Stopped");
  showRun("state", "stopped");
  text(
    "session-message",
    stopReason || "Stopped. Finished tasks remain saved.",
  );
  $("join-form")
    ?.querySelectorAll("input,select")
    .forEach((e) => (e.disabled = false));
}
function stop(
  reason = "Stopped. Finished tasks remain saved and ready to bank.",
) {
  running = false;
  clearTimeout(nextTimer);
  clearInterval(runTimer);
  stopReason = reason;
  $("stop-button").disabled = true;
  if (busy) {
    text("session-state", "Finishing current task");
    text(
      "session-message",
      "Stopping after the current bounded task is safely saved.",
    );
  } else finishStop();
}
function failStop(reason) {
  busy = false;
  stop(reason);
}
function dispatch() {
  if (!running || busy) return;
  if (document.hidden) {
    text("session-state", "Paused · tab hidden");
    showRun("state", "paused");
    return;
  }
  if (tasks.filter((t) => !coveredIds().has(t.id)).length >= 4096) {
    stop(
      "Local receipt limit reached. Bank and save your work before starting another session.",
    );
    return;
  }
  try {
    const task = nextTask();
    busy = true;
    activeTask = task;
    text("session-state", "Computing");
    text(
      "task-detail",
      `${task.context} · rows ${task.row}–${BigInt(task.row) + 127n} · block ${task.block}`,
    );
    showRun("dispatch", task);
    worker.postMessage({ type: "start", task });
  } catch (e) {
    failStop(e.message);
  }
}
async function start(e) {
  e.preventDefault();
  if (running || starting || worker) return;
  starting = true;
  const username = $("player-github").value.trim().replace(/^@/, "");
  profile = {
    name: $("player-name").value.trim() || username || "Anonymous",
    github: username,
  };
  if (!validProfile(profile)) {
    text(
      "session-message",
      "Please enter a name or alias and a valid optional GitHub username.",
    );
    starting = false;
    return;
  }
  try {
    localStorage.setItem("mg-profile", JSON.stringify(profile));
    await refreshSaved();
  } catch (e) {
    text(
      "session-message",
      "Persistent storage is unavailable. Please enable local storage or use the downloadable runner; starting would risk losing your work.",
    );
    starting = false;
    return;
  }
  starting = false;
  const owner = { ...profile },
    generation = ++sessionGeneration;
  stopReason = "";
  profilePreview();
  seen = new Set(tasks.map((t) => t.id));
  counts = { generators: 0, curves: 0, exact_tests: 0, tasks: 0 };
  renderCounts();
  startAt = Date.now();
  showRun("reset");
  running = true;
  busy = false;
  $("start-button").disabled = true;
  $("stop-button").disabled = false;
  for (const id of ["player-name", "player-github"]) $(id).disabled = true;
  // The processor slider remains adjustable during a run.
  text(
    "session-message",
    "Your hand is in play. Every finished batch gets saved.",
  );
  try {
    worker = new Worker(new URL("search-worker.mjs", BASE), { type: "module" });
  } catch (e) {
    failStop(`Could not start a browser worker: ${e.message}`);
    return;
  }
  worker.onerror = (e) =>
    failStop(
      `Worker stopped after an error: ${e.message}. Completed receipts are preserved.`,
    );
  worker.onmessage = ({ data }) => {
    (async () => {
      if (generation !== sessionGeneration) return;
      if (data.type === "ready") {
        if (running) dispatch();
        else finishStop();
        return;
      }
      if (data.type === "error") {
        failStop(`Worker error: ${data.message}`);
        return;
      }
      if (data.type !== "result") return;
      const r = data.result;
      // An exact identity is valuable even if the surrounding task envelope is damaged.
      const exactHits = Array.isArray(r?.hits)
        ? r.hits.slice(0, 64).filter((h) => verifyTriple(h?.xyz))
        : [];
      if (exactHits.length) {
        const evidence = {
          schema: "math-gambling-independent-browser-identity-v1",
          xyz: exactHits.map((h) => h.xyz),
          contributor: owner,
          observed: new Date().toISOString(),
        };
        try {
          localStorage.setItem("mg-discovery-v1", JSON.stringify(evidence));
        } catch {
          download(
            "math-gambling-emergency-discovery.json",
            JSON.stringify(evidence, null, 2),
          );
        }
        $("discovery").hidden = false;
        $("discovery").textContent =
          "An exact 114 identity was detected and preserved before checking task metadata. Keep this browser data and save the evidence.";
        download(
          "math-gambling-identity-evidence.json",
          JSON.stringify(evidence, null, 2),
        );
      }

      if (
        !r ||
        !activeTask ||
        taskId(validateTask(r.task)) !== taskId(activeTask) ||
        r.id !== taskId(activeTask) ||
        !r.counters ||
        Object.values(r.counters).some(
          (v) => !Number.isSafeInteger(v) || v < 0,
        ) ||
        !["generators", "curves", "exact_tests"].every((k) =>
          Number.isSafeInteger(r.counters[k]),
        ) ||
        !Array.isArray(r.hits)
      )
        throw Error(
          "Worker result did not match its assigned task or counter schema",
        );
      const { digest, ...core } = r;
      if (digest !== (await hash(core)))
        throw Error("Worker result digest mismatch");
      for (const hit of r.hits || []) {
        if (!verifyTriple(hit.xyz)) {
          failStop(
            "A returned candidate failed the independent page identity check. It has not been credited.",
          );
          return;
        }
      }
      const record = {
        id: r.id,
        result: r,
        contributor: owner,
        created: new Date().toISOString(),
      };
      try {
        await save("tasks", record);
        tasks.push(record);
      } catch {
        download(
          "math-gambling-emergency-result.json",
          JSON.stringify(record, null, 2),
        );
        failStop(
          "Could not save to local storage. An emergency receipt download was started; preserve it before closing this page.",
        );
        return;
      }
      counts.generators += Number(r.counters.generators);
      counts.curves += Number(r.counters.curves);
      counts.exact_tests += Number(r.counters.exact_tests);
      counts.tasks++;
      renderCounts();
      updateBankUI();
      showRun("result", { result: r, elapsedMs: data.elapsedMs });
      if (r.hits?.length) {
        const hit = r.hits[0];
        $("discovery").hidden = false;
        $("discovery").textContent =
          `Exact identity found: ${hit.xyz.map((x) => `(${x})³`).join(" + ")} = 114. Saved locally. Download this evidence and bank it for independent verification.`;
        download(
          "math-gambling-discovery.json",
          JSON.stringify(record, null, 2),
        );
        busy = false;
        stop(
          "Candidate identity verified locally. Computation stopped to preserve the evidence.",
        );
        await prepareBank(r.id);
        return;
      }
      if (running && ++completedSinceRefresh >= 64) {
        completedSinceRefresh = 0;
        await loadStrategy();
        await loadCluster();
      }
      busy = false;
      if (running) {
        const duty = processorDuty();
        nextTimer = setTimeout(
          dispatch,
          Math.max(0, (data.elapsedMs * (1 - duty)) / duty),
        );
      } else finishStop();
    })().catch((e) =>
      failStop(
        `Result handling failed: ${e.message}. Previously completed receipts are preserved.`,
      ),
    );
  };
  runTimer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startAt) / 1000);
    text(
      "elapsed",
      `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`,
    );
  }, 500);
}
$("join-form")?.addEventListener("submit", start);
$("stop-button")?.addEventListener("click", () => stop());
window.addEventListener("beforeunload", (e) => {
  if (busy) {
    e.preventDefault();
    e.returnValue = "";
  }
});
document.addEventListener("visibilitychange", () => {
  if (running) {
    text(
      "session-state",
      document.hidden ? "Paused · tab hidden" : "Computing",
    );
    showRun("state", document.hidden ? "paused" : "running");
    if (!document.hidden) dispatch();
  }
});
if ($("join-form")) {
  if (typeof profile.name === "string") $("player-name").value = profile.name;
  if (typeof profile.github === "string")
    $("player-github").value = profile.github;
  refreshSaved()
    .then(() => {
      text(
        "session-message",
        tasks.length
          ? `${fmt(tasks.length)} hands saved on this device. Ready for another?`
          : "Waiting for you to make a questionable computational decision.",
      );
    })
    .catch(() => {
      text(
        "session-message",
        "Local storage is unavailable; use the downloadable runner.",
      );
      $("start-button").disabled = true;
    });
}
await Promise.allSettled([loadMac(), loadStrategy(), loadCluster()]);
setInterval(() => {
  if (!document.hidden) {
    loadMac();
    loadCluster();
  }
}, 60000);
