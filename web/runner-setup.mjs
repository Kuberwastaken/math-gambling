// A download opens the actual setup instructions. No computation or submission
// is started by this module, and the ZIP link remains usable without JavaScript.
const COMMANDS = {
  unix: {
    shell: "Terminal (macOS or Linux)",
    setup: "cd ~/Downloads\nunzip math-gambling-runner.zip\ncd math-gambling",
    run: 'python3 --version\npython3 tools/runner.py --minutes 60 --workers 1 --name "Your name" --github username',
    automatic: 'python3 --version\npython3 tools/runner.py --login --submit --bank-every 256 --minutes 60 --workers 1 --name "Your name"',
    check: 'python3 tools/runner.py --name "Your name" --github username --mark-banked bank-FILENAME.json',
  },
  windows: {
    shell: "PowerShell (Windows)",
    setup: 'cd "$HOME\\Downloads"\nExpand-Archive .\\math-gambling-runner.zip -DestinationPath .\\math-gambling-runner\ncd .\\math-gambling-runner\\math-gambling',
    run: 'py -3 --version\npy -3 tools\\runner.py --minutes 60 --workers 1 --name "Your name" --github username',
    automatic: 'py -3 --version\npy -3 tools\\runner.py --login --submit --bank-every 256 --minutes 60 --workers 1 --name "Your name"',
    check: 'py -3 tools\\runner.py --name "Your name" --github username --mark-banked bank-FILENAME.json',
  },
};

export function setupRunnerDownload(doc = document) {
  const triggers = [...doc.querySelectorAll("[data-runner-download]")];
  if (!triggers.length || doc.getElementById("runner-dialog")) return;
  const dialog = doc.createElement("dialog");
  if (typeof dialog.showModal !== "function") return;
  dialog.id = "runner-dialog";
  dialog.className = "runner-dialog";
  dialog.setAttribute("aria-labelledby", "runner-dialog-title");
  dialog.innerHTML = `
    <div class="runner-dialog-header">
      <h2 id="runner-dialog-title">Run Math Gambling on your computer</h2>
      <button type="button" data-runner-close autofocus>Close</button>
    </div>
    <p><span data-runner-version>Portable runner</span> uses Python 3.11 or newer on macOS, Windows or Linux. No extra Python packages are needed.</p>
    <div class="runner-dialog-actions">
      <a data-runner-zip download>Download ZIP ↓</a>
      <a href="https://www.python.org/downloads/" target="_blank" rel="noopener noreferrer">Install Python ↗</a>
      <a href="https://github.com/Kuberwastaken/math-gambling/blob/main/docs/RUNNER_SETUP.md" target="_blank" rel="noopener noreferrer">Full setup guide ↗</a>
      <a data-runner-release href="https://github.com/Kuberwastaken/math-gambling/releases" target="_blank" rel="noopener noreferrer">GitHub releases & checksums ↗</a>
    </div>
    <label class="runner-platforms" for="runner-platform">Your system
      <select id="runner-platform"><option value="unix">macOS / Linux</option><option value="windows">Windows</option></select>
    </label>
    <label class="runner-platforms" for="runner-banking">Banking
      <select id="runner-banking"><option value="automatic">Automatic banking on GitHub</option><option value="manual">Manual banking</option></select>
    </label>
    <h3>1. Download and extract</h3>
    <p>Save the ZIP in Downloads, then open <span data-runner-shell></span> and run:</p>
    <pre><code data-runner-setup></code></pre>
    <button type="button" data-runner-copy="setup">Copy setup commands</button>
    <p>If you already unzipped it, open a terminal in the extracted <code>math-gambling</code> folder containing <code>tools</code> and <code>data</code>. If Downloads is elsewhere on your computer, use that location.</p>
    <p>For faster computation, choose your platform’s ZIP from <a href="https://github.com/Kuberwastaken/math-gambling/releases/tag/v0.5.1" target="_blank" rel="noopener noreferrer">the Rust runner release assets</a>, extract it, and add <code>--kernel rust</code> to the run command below. Python still handles login and checkpoints. The standard ZIP uses the Python fallback; <a href="https://github.com/Kuberwastaken/math-gambling/blob/main/docs/NATIVE_KERNEL.md" target="_blank" rel="noopener noreferrer">source build instructions</a> cover other architectures.</p>
    <h3>2. Set your budget and let it ride</h3>
    <p data-runner-identity>Replace <code>Your name</code> before running. The first line must report Python 3.11 or newer.</p>
    <p data-runner-automatic>First install the <a href="https://cli.github.com/" target="_blank" rel="noopener noreferrer">GitHub CLI</a>. <code>--login</code> opens GitHub’s browser sign-in and reads your username. <code>--submit</code> authorizes the runner to create bank issues for completed work.</p>
    <pre><code data-runner-command></code></pre>
    <button type="button" data-runner-copy="command">Copy run commands</button>
    <p><code>--minutes 60</code> allows one hour; <code>--workers 1</code> uses one process. Increase workers up to your available CPU count, at most 32. One worker is a sensible first run. Add <code>--url "https://your-site.example"</code> to link your alias.</p>
    <p>Press Ctrl+C once to stop. Current tasks finish and completed work is saved in <code>math-gambling-run</code>. Run the same command, from the same folder and with the same attribution, to continue. The local runner keeps working when its terminal is in the background.</p>
    <h3>3. Bank your work on GitHub</h3>
    <div data-runner-auto-bank>
      <p>The runner prepares a bank every 256 completed tasks and normally posts one issue every ten seconds, slowing down if GitHub rate-limits it. Change <code>--bank-every</code> from 1 to 256 to choose the batch size. The terminal shows pending banks and submitted issue links.</p>
      <p>GitHub Actions checks every submitted identity and samples eligible negative banks. Passed sampled banks earn provisional contribution credit for unique tasks. Exact replays are shown separately; unchecked claims certify no coverage and train no model. When computation stops, automatic mode uses the remaining time budget to submit queued banks. Anything left stays on disk and resumes with your next <code>--submit</code> run.</p>
    </div>
    <div data-runner-manual-bank hidden>
    <p>Open a <code>bank-*.json</code> file from <code>math-gambling-run/banks</code> in a text editor. Copy the entire file into a <a href="https://github.com/Kuberwastaken/math-gambling/issues/new?title=%5Bbank%5D%20Local%20computation%20bank" target="_blank" rel="noopener noreferrer">new bank issue</a> and submit. Use one issue per file. GitHub Actions samples eligible negative banks; passed sampled banks earn provisional contribution credit, with exact verification shown separately.</p>
    <p>After posting, record the actual bank filename locally so the runner can make room for more work:</p>
    <pre><code data-runner-check></code></pre>
    <button type="button" data-runner-copy="check">Copy bank command</button>
    <p>Keep the same name, GitHub username and optional URL when resuming or marking a bank. This records your submission; it does not mark results verified.</p>
    </div>
    <p data-runner-copy-status role="status"></p>
    <details><summary>Seeds, coverage and reproducibility</summary>
      <p>Each run prints a 256-bit seed and records policy snapshots, epochs, assigned task IDs and exact results in <code>math-gambling-run/runs</code>. Supply <code>--seed</code> with 64 hexadecimal digits to choose one. The Python and browser clients use separate PRNGs. A seed alone cannot replay changes to a live policy; the saved task log records what actually ran.</p>
      <p>Before dispatch, the runner checks an exact index of published verified tasks. Shards must pass SHA-256 checks before use. The index refreshes every 64 completed tasks or 60 seconds. Failed coverage checks pause new work; <code>--offline</code> explicitly uses the bundled snapshot. Concurrent and not-yet-published work can still overlap.</p>
    </details>
    <details><summary>Python or setup trouble?</summary>
      <p>Windows: if <code>py</code> is unavailable, try <code>python</code>. If Windows opens the Microsoft Store, finish installing Python from the link above and reopen PowerShell. macOS/Linux: if <code>python3</code> is unavailable, install Python first. If <code>unzip</code> is unavailable, extract the archive with your file manager and open a terminal in the folder containing <code>tools</code>.</p>
      <p>A missing <code>tools/runner.py</code> means the terminal is in the wrong folder. Missing SQLite support requires a standard Python installation with SQLite. Shared-strategy download failures fall back to the bundled policy. Coverage failures pause new work. Use manual mode with <code>--offline</code> to use the bundled snapshot without networking.</p>
      <p>The output folder stops accepting new work after 4,096 unsubmitted tasks. Bank its files and mark them submitted before continuing. No results upload automatically unless you explicitly add <code>--submit</code> with an authenticated <a href="https://cli.github.com/" target="_blank" rel="noopener noreferrer">GitHub CLI</a>.</p>
    </details>`;
  doc.body.append(dialog);
  const platform = dialog.querySelector("#runner-platform");
  const banking = dialog.querySelector("#runner-banking");
  let release = null;
  let archiveName = "math-gambling-runner.zip";
  const render = () => {
    const selected = COMMANDS[platform.value] || COMMANDS.unix;
    const automatic = banking.value === "automatic";
    dialog.querySelector("[data-runner-shell]").textContent = selected.shell;
    dialog.querySelector("[data-runner-setup]").textContent = selected.setup.replaceAll("math-gambling-runner.zip", archiveName);
    dialog.querySelector("[data-runner-command]").textContent = automatic ? selected.automatic : selected.run;
    dialog.querySelector("[data-runner-check]").textContent = selected.check;
    dialog.querySelector("[data-runner-automatic]").hidden = !automatic;
    dialog.querySelector("[data-runner-auto-bank]").hidden = !automatic;
    dialog.querySelector("[data-runner-manual-bank]").hidden = automatic;
    dialog.querySelector("[data-runner-identity]").textContent = automatic
      ? 'Replace "Your name" before running. The first line must report Python 3.11 or newer.'
      : 'Replace "Your name" and "username" before running. The first line must report Python 3.11 or newer.';
  };
  if (/Win/i.test(globalThis.navigator?.platform || "")) platform.value = "windows";
  platform.addEventListener("change", render);
  banking.addEventListener("change", render);
  render();
  dialog.querySelector("[data-runner-close]").addEventListener("click", () => dialog.close());
  for (const copy of dialog.querySelectorAll("[data-runner-copy]")) {
    copy.addEventListener("click", async () => {
      const status = dialog.querySelector("[data-runner-copy-status]");
      const code = dialog.querySelector(`[data-runner-${copy.dataset.runnerCopy}]`);
      try {
        if (!globalThis.navigator?.clipboard?.writeText) throw new Error("clipboard unavailable");
        await globalThis.navigator.clipboard.writeText(code.textContent);
        status.textContent = "Commands copied.";
      } catch {
        status.textContent = "Clipboard access is unavailable. Select and copy the command above.";
      }
    });
  }
  for (const trigger of triggers) {
    trigger.addEventListener("click", (event) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      dialog.querySelector("[data-runner-zip]").href = release?.download_url || trigger.href;
      const triggerFile = new URL(trigger.href, doc.baseURI).pathname.split("/").pop();
      archiveName = release ? `math-gambling-runner-v${release.version}.zip`
        : /^math-gambling-runner(?:-v\d+\.\d+\.\d+)?\.zip$/.test(triggerFile) ? triggerFile : "math-gambling-runner.zip";
      render();
      dialog.querySelector("[data-runner-copy-status]").textContent = "";
      dialog.showModal();
      dialog.scrollTop = 0;
    });
  }
  fetch(new URL("./data/runner-release.json", import.meta.url), { cache: "no-cache" })
    .then((response) => response.ok ? response.json() : null)
    .then((value) => {
      if (!value || value.schema !== "math-gambling-runner-release-v1" || !/^\d+\.\d+\.\d+$/.test(value.version)) return;
      const base = "https://github.com/Kuberwastaken/math-gambling/releases/";
      if (value.release_url !== `${base}tag/v${value.version}` || value.download_url !== `${base}download/v${value.version}/math-gambling-runner-v${value.version}.zip`) return;
      release = value;
      dialog.querySelector("[data-runner-version]").textContent = `Runner v${value.version}`;
      dialog.querySelector("[data-runner-release]").href = value.release_url;
      if (dialog.open) {
        archiveName = `math-gambling-runner-v${value.version}.zip`;
        dialog.querySelector("[data-runner-zip]").href = value.download_url;
        render();
      }
    }).catch(() => {});
}
