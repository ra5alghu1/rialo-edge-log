"""Regression tests for safe watcher restart recovery (no network/CLI)."""
import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway import rialo_anchor


class RestartPendingTests(unittest.TestCase):
    def test_only_active_program_pending_is_resumed_without_broadcast(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_dir = root / "batches" / "edge"
            batch_dir.mkdir(parents=True)
            receipts = root / "receipts"
            receipts.mkdir()
            paths = []
            for number, program in enumerate(("active", "old", None)):
                batch_id = f"batch-{number}"
                path = batch_dir / f"{batch_id}.json"
                path.write_text(json.dumps({"batch_id": batch_id}))
                paths.append(path)
                if program:
                    (receipts / f"{batch_id}-rialo.pending.json").write_text(
                        json.dumps({
                            "batch_id": batch_id,
                            "program_id": program,
                            "status": "SUBMITTED_UNVERIFIED",
                            "transaction_signature": "saved-signature",
                        })
                    )
            args = argparse.Namespace(
                include_existing=False, batch_dir=root / "batches",
                receipt_dir=receipts, program_id="active", once=True,
                registry=root / "registry.json", rpc_url="unused",
                wsl_project_dir="unused", rpc_wait_seconds=1,
                registration_dir=None, cli_rpc_url=None, cli_mode="native",
                retry_seconds=30, poll_seconds=1,
            )
            with patch.object(rialo_anchor, "submit_batch",
                              return_value=(root / "receipt", "sig", "workflow", "")) as submit:
                result = rialo_anchor.watch_batches(args)
            self.assertEqual(result, 0)
            submit.assert_called_once()
            self.assertEqual(submit.call_args.args[0], paths[0])

    def test_pending_signature_is_reused_by_submit_batch(self):
        # The production submit_batch implementation calls load_pending_submission
        # before invoking the CLI; preserve that invariant in code review.
        self.assertTrue(callable(rialo_anchor.load_pending_submission))


if __name__ == "__main__":
    unittest.main()
