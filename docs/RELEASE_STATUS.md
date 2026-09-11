# Rust/WASM release, 11 September 2026

[Runner v0.5.0](https://github.com/Kuberwastaken/math-gambling/releases/tag/v0.5.0) passed [all three platform gates](https://github.com/Kuberwastaken/math-gambling/actions/runs/34618079823): Linux x86_64, Windows x86_64 and macOS arm64. Each platform archive was extracted and executed with the Rust backend before upload. All four ZIPs, including the portable fallback/source archive, have release SHA-256 checksums.

The local integration passed 158 Python tests (two opt-in HTTP/archive tests are exercised by the release gates), 22 JavaScript tests and the Rust unit tests. The [matched benchmark](../research/benchmarks/native-wasm-2026-09-11.json) measured 20.2× native/Python and 5.2× WASM/JavaScript kernel speedups. A real Chromium worker matched a 269-curve fixture both with WASM and with a deliberately blocked WASM download. Fixtures submitted nothing.

[Negative audits](NEGATIVE_AUDITS.md) reduce the expected replay task count for eligible new banks. Unreplayed claims receive no verified credit, exact coverage or learning weight. A subsequent verified copy credits the original matching retained claim. Sampling tests cover challenge persistence, quarantine, copied-claim attribution and exclusion from verified aggregates. These changes do not establish exhaustive mathematical coverage or a discovery predictor.

---

# Release status, 11 September 2026

[Runner v0.4.1](https://github.com/Kuberwastaken/math-gambling/releases/tag/v0.4.1) passed [Linux, Windows and macOS release gates](https://github.com/Kuberwastaken/math-gambling/actions/runs/34527341792). A separate download check verified SHA-256 `26c84c0045e16b743ea1f2a482a5d8c07844cca83d93ad7ba66773dd6195f92f` for the 6,975,229-byte archive and completed one offline task. It submitted nothing and earned no leaderboard credit. The v0.4.0 tag remains an unpublished failed gate; the Windows filesystem-test timeout was repaired without removing byte checks.

The core integration passed 20 JavaScript tests and 141 Python tests, with two opt-in tests exercised separately in the extracted-runner HTTP suite. The 243-task golden corpus retains every old result, counter and digest; 6,000 integer-interval cases exercise exact shell pruning. [Measured kernel performance and proof](SHELL_PRUNING.md) distinguish the mixed-corpus 10–13% improvement from faster empty tasks.

[The first isolated verifier](https://github.com/Kuberwastaken/math-gambling/actions/runs/34527714649) successfully ingested queued work, updated the geometry/cost policy, trained shadow models and published mathematical interval records. At pinned data commit `99fc8a8075fe1da25ad4a35aac43271c20e797f8`, the ledger contained 32,127 tasks, 23,838 with no admitted curves, policy epoch 501, 31 shadow models and 30 evaluations. The separate partial interval audit covered 32 tasks and 1,946 task-local merged intervals. No verified identity was present. These are a dated observation, not live totals or distinct global mathematical coverage.

`main` holds reviewed source. `cluster-data` holds evolving observations and the live README. `gh-pages` holds the built website. Deployment checks out the exact published `gh-pages` commit before uploading its files; routine builds run every 20 minutes. [Branch trust and migration details](BRANCHES.md).

The live browser check confirmed the new policy description, the versioned download link and no JavaScript page errors. The geometric prior remains uncalibrated for our selected norm families, and the spatial predictor remains in shadow. No score adjustments or native-campaign changes were made by this release.

---

# Original launch evidence, 10 September 2026

Source and verified launch data have been pushed to [Kuberwastaken/math-gambling](https://github.com/Kuberwastaken/math-gambling). The website is live at [kuber.studio/math-gambling](https://kuber.studio/math-gambling/) with HTTPS enforced.

## Release evidence

- The source and complete test suite passed on both the Mac and the designated personal VPS.
- [Private hosted build](https://github.com/Kuberwastaken/math-gambling/actions/runs/34465664060) passed. Private repositories run build checks without deploying the public site.
- [Hosted verification](https://github.com/Kuberwastaken/math-gambling/actions/runs/34465793815) accepted [launch-validation issue #1](https://github.com/Kuberwastaken/math-gambling/issues/1): 128 real tasks, 238,592 coefficient inputs, zero hits, and two cost-calibration epochs. Attribution explicitly identifies launch validation.
- The website, working paper, research archive, durable browser/local receipts, duplicate handling, and public-snapshot exporter have local validation recorded in [VALIDATION.md](VALIDATION.md).
- [Public Pages deployment](https://github.com/Kuberwastaken/math-gambling/actions/runs/34466521510) passed. The live browser worker completed 736 tasks, saved them locally, and stopped cleanly. These browser QA receipts have not been banked or counted as public contributions.
- The live cluster renders the accepted launch contribution, both calibration epochs, and the public Mac snapshot. Snapshot forwarding through ai-vps succeeded; the existing hourly monitor is configured to repeat it quietly.

## Personal-work environment

The first push from the Mac was blocked by its managed Git destination policy. The user subsequently clarified that Razorpay allotted `ai-vps` for personal work and explicitly requested its use. The project was transferred to `/Users/kuber.mehta/Projects/math-gambling` on that host and published using normal Git access there. No Mac Git hooks or managed settings were changed.

The live native campaign and its large ledger remain on the Mac. Snapshot forwarding transfers only two allowlisted public JSON files; it does not transfer the database, private logs, credentials, or frozen binaries. The VPS does not run an additional search campaign. The existing hourly monitor retains its battery, disk, stop, and recovery safeguards.
