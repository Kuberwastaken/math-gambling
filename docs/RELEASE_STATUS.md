# Release status — 10 September 2026

The implementation is committed and tested locally. The intended remote is `https://github.com/Kuberwastaken/math-gambling.git`; the intended Pages address is `https://kuber.studio/math-gambling/`.

## Publication blocker

The attempted push was rejected by this Mac's managed Razorpay Git pre-push hook:

> Reason: destination is not in the managed allow-list

The hook identifies the destination owner as `kuberwastaken` and requires a security-approved exception for approved open-source work. This is a managed Git policy rejection, not a failed code test or a Codex automatic approval rejection. The hook has not been disabled or bypassed. No request to another person has been sent.

No code was pushed. The GitHub repository remains private and empty; no bank issues were submitted and no hosted Actions or Pages runs occurred. Local fixtures and browser test receipts have not been presented as public community contributions.

## Completed locally

- Browser and local search, durable receipts, manual issue bank-in, independent Python replay, deduplicated credit, leaderboard and cost calibration.
- Website, working paper, research archive, native campaign snapshot exporter, build audit, and deployment workflows.
- Cross-language search, adversarial ingestion, runner recovery, browser lifecycle, exporter tests, and a real 128-task local bank-to-calibration integration check. Details are in [VALIDATION.md](VALIDATION.md).
- Desktop and mobile visual inspection. Source and downloadable-runner licenses and archive provenance are included.

The existing native Mac campaign and its hourly monitor were not changed by the website release. Public snapshot publishing is implemented but has not been scheduled or pushed.

## Designated personal-work environment

The user subsequently clarified that Razorpay allotted `ai-vps` for personal work and explicitly requested its use. The source repository has been transferred to `/Users/kuber.mehta/Projects/math-gambling` there for normal Git publication and bounded release tests. No Mac Git hooks or managed settings were changed. The live native campaign and its ledger remain on the Mac. Hosted publication checks are still pending.

## Remaining release checks

1. Push the committed source through the approved Git route and run the hosted build and verification checks while the repository remains private.
2. Submit the prepared real validation bank with explicit attribution, inspect hosted replay and duplicate handling, and inspect the published aggregate. Keep its provenance visible as launch validation.
3. Once checks pass, make the repository public as requested and configure Pages to use the included Actions workflow. The project inherits `kuber.studio` from the existing user site; do not add a project `CNAME`.
4. Verify all five public pages, project-subpath assets, runner download, issue form, and a real browser bank. Wire the existing hourly monitor to the reviewed snapshot publisher once the approved remote is usable.

The packaged source is a local review and handoff artifact, not an alternate route around the managed publishing policy.
