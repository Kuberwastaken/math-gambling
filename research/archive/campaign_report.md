# Completed two-hour search for 114

**No solution was found.** The campaign ended at **02:06:12 IST on 9 September 2026**, at its scheduled deadline after draining the last tiles. Computation has stopped, and its follow-up automation is paused. The ledger and checkpoints are preserved.

## What completed

| Measure | Final value |
|---|---:|
| Completed work tiles | 76,714 |
| Unfinished tiles | 0 |
| Curve-interval checks | 80,860,107,980 |
| Quotient positions classified by the modular pipeline | 14,217,406,281,533 |
| Arbitrary-precision final candidate tests | 32,650,862 |
| Verified solutions | 0 |
| Failed or recovered jobs | 0 |

The 612,578,918,479 generator inputs include classified exclusions and sign-equivalent proposals; they are not that many tested integer triples. The residue wheel skips excluded quotient positions in bulk, so the quotient total does not imply that many expensive square tests.

An independent final ledger audit found valid database integrity, disjoint gapless reservations, no unfinished jobs, and agreement between stored totals and completed tile records. Every job had exactly one attempt. The sum of modulo243 exclusions, parity exclusions, first-rejecting-prime counts, and exact final tests equals the quotient-position total exactly. Source and executable hashes still match the audited campaign configuration, including its recorded operational-cap upgrade.

The [non-overlap proof and exact certificate](NONOVERLAP.md) apply to this specific geometry: completed tiles do not repeat `(D,r,z)` candidate positions. The same curve `(D,r)` can appear in different, disjoint z bands, so80.86billion is an interval-check count rather than a count of distinct curves. This is selective coverage, not an exhaustive coordinate-height bound.

## Parallelism and measured learning

The campaign first ran with four workers. At the user's request it stopped cleanly at7,026 tiles, calibrated4/8/12/15 workers, and resumed the same ledger with twelve. The original final deadline was retained.

| Production phase | Elapsed phase time | Curve checks | Observed curve checks/second |
|---|---:|---:|---:|
| Four workers | 24min58sec | 8,018,590,746 | 5.35million |
| Twelve workers | 92min15sec | 72,841,517,234 | 13.16million |

There was a roughly2min50sec controlled upgrade/calibration gap. The observed production throughput ratio was2.46×. This is consistent with the matched-workload calibration's2.49× gain; the production phases themselves processed different inputs and are not a randomized comparison. Fifteen workers were slightly slower than twelve in calibration.

For execution-policy analysis, I restricted observations to the twelve-worker phase, using tiles containing at least one million generator inputs, and compared aggregate input throughput separately within each exact context:

| Ratio band | Observed adaptive/fixed throughput improvement across the six contexts |
|---|---:|
| `(0,64]` | 0.8–1.9% |
| `(64,256]` | 2.0–3.8% |
| `(256,4096]` | 13.5–15.5% |

These observations agree with the earlier identical-input calibration, but they are not themselves a causal matched comparison. The15% tail improvement is not a15% improvement to the whole campaign. The learner found cheaper ways to execute valid work; it did not learn a location or calibrated probability for a solution.

## Remaining limitations

The run recorded34,420,834,825 proposals with a noninvertible root denominator and no unsupported large-D cases. The denominator failures were counted explicitly, not claimed to prove those D values rootless. The separate small arithmetic audit showed that many such failures have simple local obstructions, and a narrow5-adic fallback can recover some other roots; those changes were not installed in this campaign.

The finite coefficient families cover only selected ideal generators and unit shapes. The historical-frontier exclusion relies on the published search description rather than a retrieved complete work-unit manifest for114. Neither zero hits nor the non-overlap certificate proves that114 has no solution or that nearby unvisited regions are less promising.

## Next experiment justified by the evidence

The strongest immediate engineering step is to integrate the **certified signed-sum filters modulo8 and361** into a separate worker version, then benchmark identical input tiles. Their small deterministic audit excluded18.1% of ordinary root candidates before quotient enumeration; this is an exclusion fraction, not a measured total-runtime gain. The change should preserve final results, record its exclusions, and pass the existing arithmetic/endpoint tests plus independent residue-table checks.

The next coverage experiment should use **exact norm-shell inversion across previously missing unit-shape ranges**. The isolated shell worker already preserved complete small-domain results and gained9–20% in the tested shorter intervals, but only2–5% in the longest ones. Its value is also that it can select a precisely defined norm shell while avoiding empty coefficient intervals. New shape bounds and worker ownership must be certified before launch so the new experiment does not duplicate the completed campaign.

This follows the structured-search direction of [Booker–Sutherland](https://arxiv.org/abs/2007.01209) and the norm method of [Grantham–Walsh](https://arxiv.org/abs/2211.12149). The [research audit](research_audit.md) explains why these methods, geometric searches, and direct optimization precedents do not establish a Mac-hours success probability. The existing blind benchmark supplied too few discoveries to justify a trained solution-location model.

I did not automatically repeat the same campaign. A fresh long run should follow a demonstrated gain in useful coverage or execution cost, with a new version/checkpoint plan and an explicit finite budget. No calibrated high-probability route to solving114 in hours has emerged from this run.

## Evidence

- [Final status and totals](../../docs/ARCHIVE.md)
- [Reconciled contexts, execution phases, policies, and rejection counts](runs/campaign-analysis.json)
- [Final non-overlap certificate](runs/nonoverlap-certificate.json)
- [Scaling calibration](runs/wide-parallelism.json)
- [Norm-shell experiment](experiments/shell/README.md)
- [Certified filters and root-recovery analysis](root_recovery_proposal.md)
- [Unit-shape bounds](unit_shape_proposal.md)
