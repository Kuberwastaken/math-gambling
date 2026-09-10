// A download opens the actual setup instructions. No computation or submission
// is started by this module, and the ZIP link remains usable without JavaScript.
const COMMANDS = {
  unix: {
    shell: "Terminal (macOS or Linux)",
    setup: "cd ~/Downloads\nunzip math-gambling-runner.zip\ncd math-gambling",
    run: 'python3 --version\npython3 tools/runner.py --minutes 60 --workers 1 --name "Your name" --github username',
    check: 'python3 tools/runner.py --name "Your name" --github username --mark-banked bank-FILENAME.json',
  },
  windows: {
    shell: "PowerShell (Windows)",
    setup: 'cd "$HOME\\Downloads"\nExpand-Archive .\\math-gambling-runner.zip -DestinationPath .\\math-gambling-runner\ncd .\\math-gambling-runner\\math-gambling',
    run: 'py -3 --version\npy -3 tools\\runner.py --minutes 60 --workers 1 --name "Your name" --github username',
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
    <p>The portable runner uses Python 3.11 or newer on macOS, Windows or Linux. No extra Python packages are needed.</p>
    <div class="runner-dialog-actions">
      <a data-runner-zip download>Download ZIP ↓</a>
      <a href="https://www.python.org/downloads/" target="_blank" rel="noopener noreferrer">Install Python ↗</a>
      <a href="https://github.com/Kuberwastaken/math-gambling/blob/main/docs/RUNNER_SETUP.md" target="_blank" rel="noopener noreferrer">Full setup guide ↗</a>
    </div>
    <label class="runner-platforms" for="runner-platform">Your system
      <select id="runner-platform"><option value="unix">macOS / Linux</option><option value="windows">Windows</option></select>
    </label>
    <h3>1. Download and extract</h3>
    <p>Save the ZIP in Downloads, then open <span data-runner-shell></span> and run:</p>
    <pre><code data-runner-setup></code></pre>
    <button type="button" data-runner-copy="setup">Copy setup commands</button>
    <p>If you already unzipped it, open a terminal in the extracted <code>math-gambling</code> folder containing <code>tools</code> and <code>data</code>. If Downloads is elsewhere on your computer, use that location.</p>
    <h3>2. Set your budget and let it ride</h3>
    <p>Replace <code>Your name</code> and <code>username</code> before running. The first line must report Python 3.11 or newer.</p>
    <pre><code data-runner-command></code></pre>
    <button type="button" data-runner-copy="command">Copy run commands</button>
    <p><code>--minutes 60</code> allows one hour; <code>--workers 1</code> uses one process. Increase workers up to your available CPU count, at most 32. One worker is a sensible first run. Add <code>--url "https://your-site.example"</code> to link your alias.</p>
    <p>Press Ctrl+C once to stop. Current tasks finish and completed work is saved in <code>math-gambling-run</code>. Run the same command, from the same folder and with the same attribution, to continue. The local runner keeps working when its terminal is in the background.</p>
    <h3>3. Bank your work on GitHub</h3>
    <p>Open a <code>bank-*.json</code> file from <code>math-gambling-run/banks</code> in a text editor. Copy the entire file into a <a href="https://github.com/Kuberwastaken/math-gambling/issues/new?title=%5Bbank%5D%20Local%20computation%20bank" target="_blank" rel="noopener noreferrer">new bank issue</a> and submit. Use one issue per file. GitHub Actions replays the tasks, deduplicates them and updates the leaderboard after verification.</p>
    <p>After posting, record the actual bank filename locally so the runner can make room for more work:</p>
    <pre><code data-runner-check></code></pre>
    <button type="button" data-runner-copy="check">Copy bank command</button>
    <p data-runner-copy-status role="status"></p>
    <p>Keep the same name, GitHub username and optional URL when resuming or marking a bank. This records your submission; it does not mark results verified.</p>
    <details><summary>Python or setup trouble?</summary>
      <p>Windows: if <code>py</code> is unavailable, try <code>python</code>. If Windows opens the Microsoft Store, finish installing Python from the link above and reopen PowerShell. macOS/Linux: if <code>python3</code> is unavailable, install Python first. If <code>unzip</code> is unavailable, extract the archive with your file manager and open a terminal in the folder containing <code>tools</code>.</p>
      <p>A missing <code>tools/runner.py</code> means the terminal is in the wrong folder. Missing SQLite support requires a standard Python installation with SQLite. Shared-strategy download failures fall back to the bundled policy. Use <code>--offline</code> to disable those downloads.</p>
      <p>The output folder stops accepting new work after 4,096 unsubmitted tasks. Bank its files and mark them submitted before continuing. No results upload automatically unless you explicitly add <code>--submit</code> with an authenticated <a href="https://cli.github.com/" target="_blank" rel="noopener noreferrer">GitHub CLI</a>.</p>
    </details>`;
  doc.body.append(dialog);
  const platform = dialog.querySelector("#runner-platform");
  const render = () => {
    const selected = COMMANDS[platform.value] || COMMANDS.unix;
    dialog.querySelector("[data-runner-shell]").textContent = selected.shell;
    dialog.querySelector("[data-runner-setup]").textContent = selected.setup;
    dialog.querySelector("[data-runner-command]").textContent = selected.run;
    dialog.querySelector("[data-runner-check]").textContent = selected.check;
  };
  if (/Win/i.test(globalThis.navigator?.platform || "")) platform.value = "windows";
  platform.addEventListener("change", render);
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
      dialog.querySelector("[data-runner-zip]").href = trigger.href;
      dialog.querySelector("[data-runner-copy-status]").textContent = "";
      dialog.showModal();
      dialog.scrollTop = 0;
    });
  }
}
