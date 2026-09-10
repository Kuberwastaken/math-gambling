"""Adversarial receipt, crash-resumption, identity, and frozen-policy contracts."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import aggregate as ag
import ingest as ig
from search_core import make_task, run_task


def source(number=1, author="honest-person"):
    return {"id": f"issue:{number}:fixture", "kind": "issue", "number": number,
            "submitter": author, "url": f"https://github.com/example/test/issues/{number}"}


def bank(results, name="Example", github="claimed-handle"):
    return {"schema": "math-gambling-bank-v1", "contributor": {"name": name, "github": github},
            "tasks": [{"task": r["task"], "digest": r["digest"], "hits": r["hits"]} for r in results]}


class ClusterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.data = Path(self.temporary.name)
        self.results = [run_task(make_task("c00", 128 * i)) for i in range(4)]
        self.replay_count = 0

    def tearDown(self):
        self.temporary.cleanup()

    def replay(self, task):
        self.replay_count += 1
        return run_task(task), 2.5

    def submit(self, receipt, number=1, budget=None, author="honest-person"):
        return ig.process_receipt(receipt, source(number, author), self.data,
                                  budget or ig.Budget(), replay=self.replay)

    def test_duplicate_idempotence_and_signed_author_credit(self):
        receipt = bank(self.results[:1], github="someone-else")
        first = self.submit(receipt)
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(self.submit(receipt), first)
        second = self.submit(receipt, number=2, author="copying-person")
        self.assertEqual(len(second["duplicate_tasks"]), 1)
        self.assertEqual(self.replay_count, 1)
        report = ag.aggregate(self.data)
        self.assertEqual(report["totals"]["verified_unique_tasks"], 1)
        self.assertEqual(len(report["contributors"]), 1)
        person = report["contributors"][0]
        self.assertEqual(person["github"], "honest-person")
        self.assertEqual(person["claimed_github"], "someone-else")
        self.assertTrue(person["github_verified"])
        self.assertEqual(int(person["verified_computations"]), self.results[0]["counters"]["generators"])
        self.assertEqual(report["banks"][0]["bank_digest"], hashlib.sha256(ig.canonical(receipt).encode()).hexdigest())

    def test_profile_link_updates_only_from_credited_work(self):
        receipt = bank(self.results[:1], name="First alias")
        receipt["contributor"]["url"] = "https://example.org/me?q=1&b=2"
        self.assertEqual(self.submit(receipt)["status"], "accepted")
        person = ag.aggregate(self.data)["contributors"][0]
        self.assertEqual(person["url"], receipt["contributor"]["url"])
        copied = copy.deepcopy(receipt)
        copied["contributor"] = dict(name="Imposter", github="", url="https://evil.example")
        self.submit(copied, number=2, author="someone-else")
        self.assertEqual(ag.aggregate(self.data)["contributors"][0]["name"], "First alias")
        updated = bank(self.results[1:2], name="New alias")
        updated["contributor"]["url"] = "https://new.example/profile"
        self.submit(updated, number=3)
        person = ag.aggregate(self.data)["contributors"][0]
        self.assertEqual(person["name"], "New alias")
        self.assertEqual(person["url"], "https://new.example/profile")
        self.assertEqual(person["verified_tasks"], 2)
        self.submit(bank(self.results[2:3], name="No link"), number=4)
        self.assertNotIn("url", ag.aggregate(self.data)["contributors"][0])

    def test_unsafe_profile_links_are_stripped_without_losing_work(self):
        invalid = ["javascript:alert(1)", "data:text/html,hi", "//example.com",
                   "https://user:password@example.com", "https://example.com/\\evil",
                   "https://example.com/\nfoo", "https://example.com/with space",
                   "https://", "https://example.com:99999", "https://example.com/" + "a"*2048]
        for value in invalid:
            with self.subTest(url=value):
                self.assertNotIn("url", ig.contributor({"contributor": {"name": "X", "url": value}}))
        receipt = bank(self.results[:1])
        receipt["contributor"]["url"] = invalid[0]
        self.assertEqual(self.submit(receipt)["status"], "accepted")
        self.assertNotIn("url", ag.aggregate(self.data)["contributors"][0])

    def test_partial_bank_resumes_without_double_credit(self):
        receipt = bank(self.results[:3])
        first = self.submit(receipt, budget=ig.Budget(count=1))
        self.assertFalse(first["complete"])
        self.assertEqual(first["next_index"], 1)
        self.assertEqual(len(first["accepted_tasks"]), 1)
        final = self.submit(receipt, budget=ig.Budget(count=2))
        self.assertTrue(final["complete"])
        self.assertEqual(len(final["accepted_tasks"]), 3)
        self.assertEqual(final["duplicate_tasks"], [])
        self.assertEqual(self.replay_count, 3)
        self.assertEqual(ag.aggregate(self.data)["totals"]["verified_unique_tasks"], 3)

    def test_crash_after_task_write_before_cursor_recovery(self):
        receipt = bank(self.results[:2])
        real = ig.atomic_json
        crashed = False

        def write_then_crash(path, payload):
            nonlocal crashed
            real(path, payload)
            if payload.get("schema") == "math-gambling-verified-task-v1" and not crashed:
                crashed = True
                raise OSError("simulated power loss after durable task")

        with mock.patch.object(ig, "atomic_json", side_effect=write_then_crash):
            with self.assertRaises(OSError):
                self.submit(receipt)
        final = self.submit(receipt)
        self.assertEqual(len(final["accepted_tasks"]), 2)
        self.assertEqual(final["duplicate_tasks"], [])
        self.assertEqual(self.replay_count, 2)
        self.assertEqual(ag.aggregate(self.data)["totals"]["verified_unique_tasks"], 2)

    def test_invalid_digest_and_invented_counters_grant_no_coverage(self):
        receipt = bank(self.results[:1])
        receipt["tasks"][0]["digest"] = "0" * 64
        result = self.submit(receipt)
        self.assertEqual(result["status"], "rejected")
        full = {"schema": "math-gambling-receipt-v1", "contributor": {"name": "X", "github": "X"},
                "results": [copy.deepcopy(self.results[0])]}
        full["results"][0]["counters"]["generators"] += 10**50
        self.assertEqual(self.submit(full, 2)["status"], "rejected")
        self.assertEqual(ag.aggregate(self.data)["totals"]["verified_unique_tasks"], 0)

    def test_caps_and_unknown_fields_rejected_before_replay(self):
        examples = []
        too_many = bank(self.results[:1])
        too_many["tasks"] *= 257
        examples.append(too_many)
        enormous = bank(self.results[:1], name="x" * 60001)
        examples.append(enormous)
        arbitrary = bank(self.results[:1])
        arbitrary["tasks"][0]["command"] = "rm -rf /"
        examples.append(arbitrary)
        invalid_row = bank(self.results[:1])
        invalid_row["tasks"][0]["task"] = dict(invalid_row["tasks"][0]["task"], row="9" * 1000)
        examples.append(invalid_row)
        noninteger = bank(self.results[:1])
        noninteger["tasks"][0]["task"] = dict(noninteger["tasks"][0]["task"], block=True)
        examples.append(noninteger)
        for i, receipt in enumerate(examples, 1):
            self.assertEqual(self.submit(receipt, i)["status"], "rejected")
        self.assertEqual(self.replay_count, 0)
        with self.assertRaises(ValueError):
            ig.parse_json('{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            ig.parse_json('{"a":NaN}')
        with self.assertRaises(ValueError):
            ig.parse_json('"' + 'x' * 60001 + '"')

    def test_independent_identity_math_and_fault_injected_preservation(self):
        xyz = ["-159380", "134476", "117367"]  # Known k=39 fixture, not a claim for 114.
        self.assertEqual(ig.exact_triple(xyz, k=39), [int(x) for x in xyz])
        self.assertIsNone(ig.exact_triple(xyz))
        for invalid in ([True, "0", "0"], ["1e3", "0", "0"], ["9" * 129, "0", "0"], [1.5, 2, 3]):
            self.assertIsNone(ig.exact_triple(invalid))
        real_verifier = ig.exact_triple
        # Inject a known positive at k=39 to exercise hit persistence on an invalid receipt.
        with mock.patch.object(ig, "exact_triple", side_effect=lambda v: real_verifier(v, k=39)):
            result = self.submit({"schema": "bad", "contributor": {"name": "Finder"}, "hits": [{"xyz": xyz}]})
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(len(result["discoveries"]), 1)
        self.assertEqual(len(ag.load_kind(self.data, "hits")), 1)
        self.assertEqual(len(ag.load_kind(self.data, "tasks")), 0)

    def test_noisy_client_time_is_not_accepted_or_calibrated(self):
        receipt = bank(self.results[:1])
        receipt["hours"] = 10**20
        self.assertEqual(self.submit(receipt)["status"], "rejected")
        receipt.pop("hours")
        self.submit(receipt, 2)
        saved = ag.load_kind(self.data, "tasks")[0]
        self.assertEqual(saved["server_replay_cpu_ms"], 2.5)

    def test_policy_is_frozen_within_epoch(self):
        before = ag.aggregate(self.data)
        initial = (self.data / "strategy.json").read_bytes()
        self.assertEqual(before["totals"]["verified_unique_tasks"], 0)
        results = [run_task(make_task("c00", 128 * i)) for i in range(65)]
        self.submit(bank(results[:63]), 1)
        ag.aggregate(self.data)
        self.assertEqual(initial, (self.data / "strategy.json").read_bytes())
        self.submit(bank(results[63:64]), 2)
        updated = ag.aggregate(self.data)
        frozen = (self.data / "strategy.json").read_bytes()
        policy = json.loads(frozen)
        self.assertEqual(policy["epoch"], 1)
        self.assertEqual(policy["through_verified_tasks"], 64)
        self.assertAlmostEqual(sum(x["weight"] for x in policy["contexts"]), 1)
        self.assertTrue(all(x["weight"] >= 0.4 / 81 for x in policy["contexts"]))
        self.submit(bank(results[64:]), 3)
        ag.aggregate(self.data)
        self.assertEqual(frozen, (self.data / "strategy.json").read_bytes())
        self.assertEqual(len(updated["calibration_history"]), 1)

    def test_strict_full_result_backwards_compatibility(self):
        receipt = {"schema": "math-gambling-receipt-v1", "contributor": {"name": "X", "github": "X"},
                   "results": self.results[:1]}
        self.assertEqual(self.submit(receipt)["status"], "accepted")

    def test_untrusted_issue_text_never_executes(self):
        b = bank(self.results[:1], name="$(touch /tmp/should-never-exist)")
        issue = {"number": 7, "title": "[compute] bank", "body": "### Bank JSON\n\n```json\n" + ig.canonical(b) + "\n```",
                 "user": {"login": "signed-in-person"}, "updated_at": "2026-09-10T00:00:00Z"}
        parsed, origin = ig.parse_issue(issue, "example/test")
        self.assertEqual(parsed, b)
        self.assertEqual(origin["submitter"], "signed-in-person")
        self.assertIsNone(ig.parse_issue(dict(issue, title="Unrelated"), "example/test"))

    def test_one_real_isolated_replay(self):
        result, cpu = ig.replay_task(self.results[0]["task"])
        self.assertEqual(result, self.results[0])
        self.assertGreater(cpu, 0)

    def test_issue_poll_records_received_before_replay_and_resumes_pending(self):
        receipt = bank(self.results[:2])
        issue = {"number": 19, "title": "[compute] bank", "body": ig.canonical(receipt),
                 "user": {"login": "actual-author"}, "updated_at": "2026-09-10T01:02:03Z"}
        with mock.patch.object(ig, "api_request", return_value=[issue]):
            entries, poll = ig.collect_issues("example/test", "secret-not-logged", self.data)
        self.assertEqual(len(entries), 1)
        self.assertEqual(poll["since"], "2026-09-10T01:02:02Z")
        summary = ag.aggregate(self.data)
        self.assertEqual(summary["totals"]["verified_unique_tasks"], 0)
        self.assertEqual(summary["totals"]["pending_banks"], 1)
        self.assertEqual(summary["banks"][0]["bank_digest"], hashlib.sha256(ig.canonical(receipt).encode()).hexdigest())
        self.assertEqual(summary["banks"][0]["processed_tasks"], 0)
        calls = []

        def api(url, token, **kwargs):
            calls.append(url)
            return issue if url.endswith("/19") else []

        with mock.patch.object(ig, "api_request", side_effect=api):
            entries, _ = ig.collect_issues("example/test", "secret-not-logged", self.data)
        self.assertEqual(len(entries), 1)
        self.assertTrue(calls[0].endswith("/19"))
        self.assertIn("since=2026-09-10T01%3A02%3A02Z", calls[1])

    def test_unicode_bank_fingerprint_is_ascii_canonical(self):
        receipt = bank(self.results[:1], name="Zoë ∑ 🧮")
        result = self.submit(receipt)
        self.assertTrue(result["complete"])
        encoded = ig.canonical(receipt)
        self.assertTrue(encoded.isascii())
        self.assertIn("\\ud83e\\uddee", encoded)
        self.assertEqual(ag.aggregate(self.data)["banks"][0]["bank_digest"], hashlib.sha256(encoded.encode("ascii")).hexdigest())

    def test_more_than_four_pages_with_equal_timestamps_eventually_discovered(self):
        issues = [{"number": n, "title": "Unrelated", "body": "", "user": {"login": "person"},
                   "updated_at": "2026-09-10T00:00:00Z"} for n in range(1, 402)]
        issues[-1].update(title="[compute] last bank", body=ig.canonical(bank(self.results[:1])))

        def api(url, token, **kwargs):
            q = parse_qs(urlsplit(url).query)
            page = int(q["page"][0])
            return issues[(page - 1) * 100:page * 100]

        with mock.patch.object(ig, "api_request", side_effect=api):
            for _ in range(3):
                ig.collect_issues("example/test", "token", self.data)
        self.assertEqual(ag.aggregate(self.data)["banks"][0]["issue"], 401)

    def test_creation_sweep_recovers_update_offset_reordering(self):
        issues = [{"number": n, "title": "Unrelated", "body": "", "user": {"login": "person"},
                   "updated_at": "2026-09-10T00:00:00Z"} for n in range(1, 501)]
        issues[119].update(title="[compute] bank skipped by moving update order", body=ig.canonical(bank(self.results[:1])))
        update_calls = 0

        def api(url, token, **kwargs):
            nonlocal update_calls
            q = parse_qs(urlsplit(url).query)
            page = int(q["page"][0])
            if q["sort"] == ["updated"]:
                update_calls += 1
                ordered = issues if update_calls == 1 else issues[50:] + issues[:50]
            else:
                ordered = issues
            return ordered[(page - 1) * 100:page * 100]

        with mock.patch.object(ig, "api_request", side_effect=api):
            ig.collect_issues("example/test", "token", self.data)
        self.assertEqual(ag.aggregate(self.data)["banks"][0]["issue"], 120)

    def test_api_deadline_does_not_advance_scan_or_spend_unbounded_requests(self):
        with mock.patch.object(ig.time, "monotonic", side_effect=[0, 61]), mock.patch.object(ig, "api_request") as api:
            entries, poll = ig.collect_issues("example/test", "token", self.data)
        api.assert_not_called()
        self.assertEqual(entries, [])
        self.assertEqual(poll["scan_page"], 1)
        self.assertEqual(poll["reconcile_page"], 1)
        self.assertEqual(poll["deferred_reason"], "API time budget exhausted")

    def test_timeout_preserves_prior_credit_and_defers_without_false_negative(self):
        calls = 0

        def replay(task):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise subprocess.TimeoutExpired(["trusted-kernel"], 6)
            return run_task(task), 1.0

        result = ig.process_receipt(bank(self.results[:2]), source(), self.data, ig.Budget(), replay=replay)
        self.assertFalse(result["complete"])
        self.assertEqual(result["next_index"], 1)
        self.assertEqual(result["deferred_reason"], "replay_failed")
        self.assertEqual(len(result["accepted_tasks"]), 1)
        self.assertEqual(result["rejected_tasks"], [])
        self.submit(bank(self.results[2:3]), number=2)
        summary = ag.aggregate(self.data)
        self.assertEqual(summary["totals"]["verified_unique_tasks"], 2)
        self.assertEqual(summary["totals"]["pending_banks"], 1)


if __name__ == "__main__":
    unittest.main()
