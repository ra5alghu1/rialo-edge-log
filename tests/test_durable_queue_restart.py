"""Offline regression tests for opt-in durable queue replay (no RPC / CLI)."""

import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway import archive_publisher, rialo_anchor
from gateway.queue_recovery import (
    QueueBoundaryError,
    eligible_for_restart,
    load_or_initialize_boundary,
)


class DurableAnchorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.batch_dir = self.root / "batches" / "edge"
        self.batch_dir.mkdir(parents=True)
        self.receipts = self.root / "receipts"
        self.receipts.mkdir()
        self.args = argparse.Namespace(
            include_existing=False, resume_after_restart=True,
            batch_dir=self.root / "batches", receipt_dir=self.receipts,
            program_id="current-program", once=True, registry=self.root / "registry.json",
            rpc_url="unused", wsl_project_dir="unused", rpc_wait_seconds=1,
            registration_dir=None, cli_rpc_url=None, cli_mode="native",
            retry_seconds=30, poll_seconds=1,
        )

    def batch(self, number, device="edge"):
        batch_id = f"{device}-{number}"
        path = self.batch_dir / f"{batch_id}.json"
        path.write_text(json.dumps({
            "batch_id": batch_id, "device_id": device, "last_sequence": number
        }))
        return path

    def test_first_start_skips_history_but_restart_recovers_downtime(self):
        old = self.batch(100)
        with patch.object(rialo_anchor, "submit_batch") as submit:
            self.assertEqual(rialo_anchor.watch_batches(self.args), 0)
            submit.assert_not_called()
        state = self.receipts / ".anchor-restart-boundary.json"
        self.assertTrue(state.exists())
        # Touching history must not make it eligible to broadcast.
        os.utime(old, None)
        new = self.batch(160)
        with patch.object(rialo_anchor, "submit_batch",
                          return_value=(self.root / "receipt", "sig", "workflow", "")) as submit:
            self.assertEqual(rialo_anchor.watch_batches(self.args), 0)
            submit.assert_called_once()
            self.assertEqual(submit.call_args.args[0], new)

    def test_program_switch_and_corrupt_boundary_fail_closed(self):
        old = self.batch(100)
        state = self.receipts / ".anchor-restart-boundary.json"
        load_or_initialize_boundary(state, "old-program", [old])
        with self.assertRaises(QueueBoundaryError):
            load_or_initialize_boundary(state, "new-program", [old])
        state.write_text("{broken")
        with self.assertRaises(QueueBoundaryError):
            load_or_initialize_boundary(state, "old-program", [old])

    def test_new_unknown_device_is_not_mass_replayed(self):
        old = self.batch(100)
        state = self.receipts / ".anchor-restart-boundary.json"
        floors = load_or_initialize_boundary(state, "current", [old])
        new_device = self.batch(100000, device="unregistered")
        self.assertFalse(eligible_for_restart(new_device, floors))

    def test_never_combine_with_include_existing(self):
        self.batch(100)
        self.args.include_existing = True
        with self.assertRaises(rialo_anchor.RialoAnchorError):
            rialo_anchor.watch_batches(self.args)


class CurrentProgramPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        self.batches = self.data / "batches" / "edge"
        self.batches.mkdir(parents=True)
        self.receipts = self.data / "receipts"
        self.receipts.mkdir()
        self.publications = self.data / "publications"
        self.publications.mkdir()
        self.args = argparse.Namespace(
            data_dir=self.data, publication_dir=self.publications,
            heartbeat_dir=self.data / "heartbeats",
            archive_url="https://example.invalid", ingest_token="not-a-real-token",
            include_existing=False, resume_current_program=True,
            program_id="current", once=True, poll_seconds=1,
            offline_retry_seconds=1,
        )

    def batch(self, name, program, status="RIALO_VERIFIED"):
        (self.batches / f"{name}.json").write_text(json.dumps({"batch_id": name}))
        (self.receipts / f"{name}-rialo.json").write_text(json.dumps({
            "schema_version": 1, "batch_id": name, "program_id": program, "status": status
        }))

    def test_only_current_verified_receipts_eligible(self):
        self.batch("current-1", "current")
        self.batch("old-1", "old")
        self.batch("bogus-1", "current", "SUBMITTED_UNVERIFIED")
        result = archive_publisher.list_publishable_batch_ids(
            self.data, self.publications, program_id="current"
        )
        self.assertEqual(result, ["current-1"])

    def test_restart_retries_current_receipt_not_legacy(self):
        self.batch("current-1", "current")
        self.batch("old-1", "old")
        with patch.object(archive_publisher, "publish_batch_id",
                          return_value=(self.publications / "receipt", {"status": "PUBLISHED"})) as submit:
            self.assertEqual(archive_publisher.watch_batches(self.args), 0)
            submit.assert_called_once()
            self.assertEqual(submit.call_args.args[0], "current-1")

    def test_requires_explicit_program_and_no_include_existing(self):
        self.args.program_id = None
        with self.assertRaises(archive_publisher.ArchivePublishError):
            archive_publisher.watch_batches(self.args)
        self.args.program_id = "current"
        self.args.include_existing = True
        with self.assertRaises(archive_publisher.ArchivePublishError):
            archive_publisher.watch_batches(self.args)


if __name__ == "__main__":
    unittest.main()
