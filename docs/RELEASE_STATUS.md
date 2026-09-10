# Release status — 10 September 2026

Source and verified launch data have been pushed to [Kuberwastaken/math-gambling](https://github.com/Kuberwastaken/math-gambling). The intended Pages address is `https://kuber.studio/math-gambling/`.

## Release evidence

- The source and complete test suite passed on both the Mac and the designated personal VPS.
- [Private hosted build](https://github.com/Kuberwastaken/math-gambling/actions/runs/34465664060) passed. Private repositories run build checks without deploying the public site.
- [Hosted verification](https://github.com/Kuberwastaken/math-gambling/actions/runs/34465793815) accepted [launch-validation issue #1](https://github.com/Kuberwastaken/math-gambling/issues/1): 128 real tasks, 238,592 coefficient inputs, zero hits, and two cost-calibration epochs. Attribution explicitly identifies launch validation.
- The website, working paper, research archive, durable browser/local receipts, duplicate handling, and public-snapshot exporter have local validation recorded in [VALIDATION.md](VALIDATION.md).
- Public Pages deployment and live URL checks are pending the final release step.

## Personal-work environment

The first push from the Mac was blocked by its managed Git destination policy. The user subsequently clarified that Razorpay allotted `ai-vps` for personal work and explicitly requested its use. The project was transferred to `/Users/kuber.mehta/Projects/math-gambling` on that host and published using normal Git access there. No Mac Git hooks or managed settings were changed.

The live native campaign and its large ledger remain on the Mac. Snapshot forwarding transfers only two allowlisted public JSON files; it does not transfer the database, private logs, credentials, or frozen binaries. The VPS does not run an additional search campaign. The existing hourly monitor retains its battery, disk, stop, and recovery safeguards.
