# Negative-result audits

The public ingestion job no longer has to replay every submitted negative task. New compact banks from accounts with at least 256 previously replay-verified tasks use **independent 1-in-20 sampling**. New accounts, existing pending banks and legacy full receipts retain full replay. Every supplied candidate identity receives an exact check regardless of sampling or queue budget.

**An unreplayed claim earns no verified leaderboard credit, supplies no model-training counters or timings, and enters no exact completed-task or mathematical-coverage index.** It is retained in the issue audit as `unreplayed_tasks`. A bank labelled `sampled` is processed, not certified as wholly correct. The site's leaderboard continues to mean what it says: replay-verified inputs. Sampling does not multiply a sampled score by twenty.

## Selection and failures

The verifier generates a fresh 256-bit random salt after receiving the immutable bank body, and durably records it before executing any task. SHA-256 of the salt, body digest and canonical task ID selects each negative task with probability approximately 1/20. A resumed job reuses its original challenge; it does not reroll. Selection is not a client-visible task-ID partition that can be avoided before submission. A small bank can receive no sampled tasks at all; that earns no verified credit.

A sampled digest mismatch disables sampling for the account, both for remaining new banks in that job and later jobs. Remaining tasks in the failed bank receive full replay. Previously skipped tasks remain unverified; a failure does not somehow certify or erase them. A later full replay can establish their result. Public salts and recorded digests make each completed audit reproducible, but do not make the work attribution cryptographically provable. An edited issue is a new body, never an alteration to its previous audit.

## What this saves, and what it costs

For eligible newly submitted negatives, expected replay task count falls by 95%. This is not a claim that total Action runtime falls by 95%: checkout, issue polling, ledger I/O, model fitting and publication remain. After accelerating clients, the remaining Python replay may still dominate. Measure it rather than assuming linear scaling.

There is less new **certified coverage** per bank. Unsampled tasks can be selected again by another client because an unverified claim is not a valid exclusion. Counting them as completed would let a dishonest client suppress an actual solution. Submitted logical counts alone also cannot support a throughput model; training continues exclusively on exact replays.

Random audits detect widespread cheating more readily than isolated omissions. If a fixed fraudulent task has a 5% audit probability, its omission escapes that audit 95% of the time. For 100 independently selected fraudulent tasks the chance all escape is about 0.6%. These are audit-sampling calculations, not solution probabilities. Probation does not prove future honesty. This implementation deliberately does **not** convert a passed sample into a claim about all other tasks in that batch.

The shell-count and progression-conservation identities are useful additional checks, but a client can fabricate those counts. They cannot replace a proof of execution. GitHub issues remain the transport, with up to 256 tasks per bank and one automatic bank/minute per runner. There is no per-computer account restriction; deduplication and first verified attribution still apply.

## Operations

```sh
python tools/ingest.py --issues --sample-negatives 20
```

Without `--sample-negatives`, ingestion retains full replay. The live workflow explicitly selects the policy, so local fixtures and manual full audits remain conservative. `cluster.json` separately publishes `unreplayed_claims` (submission claims, not deduplicated coverage), `sampled_banks`, and each bank's unreplayed count. All history and audit decisions remain on `cluster-data`.

A future probabilistic-coverage ledger would require its own labels, adversarial analysis, reservation/redundancy policy, and contributor-credit rules. It must not be silently merged into the existing exact ledger.
