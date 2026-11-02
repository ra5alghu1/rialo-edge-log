"""Regression tests for safe watcher restart recovery (no network/CLI)."""
import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_path = root / "batch.json"
            batch_path.write_text('{"batch_id":"batch-1"}')
            receipt_dir = root / "receipts"
            receipt_dir.mkdir()
            saved_signature = "previously-submitted-signature"
            (receipt_dir / "batch-1-rialo.pending.json").write_text(
                json.dumps({
                    "batch_id": "batch-1",
                    "program_id": "active",
                    "status": "SUBMITTED_UNVERIFIED",
                    "transaction_signature": saved_signature,
                })
            )
            batch = {
                "batch_id": "batch-1",
                "device_public_key_fingerprint": "fingerprint",
            }
            client = Mock()
            transaction = {"meta": {"err": None}}
            client.get_transaction.return_value = transaction
            client.get_account_info.return_value = {"data": ["", "base64"]}
            state = {"verified": True}
            with (
                patch.object(rialo_anchor, "load_verified_batch", return_value=(batch, {})),
                patch.object(rialo_anchor, "invoke_rialo_cli") as broadcast,
                patch.object(rialo_anchor, "extract_workflow_address", return_value="workflow"),
                patch.object(rialo_anchor, "decode_account_state", return_value=state),
                patch.object(rialo_anchor, "compare_batch_to_state", return_value=[]),
                patch.object(rialo_anchor, "save_receipt", return_value=receipt_dir / "batch-1-rialo.json") as save,
            ):
                receipt, signature, workflow, output = rialo_anchor.submit_batch(
                    batch_path, root / "registry.json", receipt_dir, "active",
                    "unused", "unused", 1, client=client,
                )
            broadcast.assert_not_called()
            client.get_transaction.assert_called_once_with(saved_signature)
            save.assert_called_once()
            self.assertEqual(signature, saved_signature)
            self.assertEqual(workflow, "workflow")
            self.assertIn("Resuming submitted transaction", output)
            self.assertFalse((receipt_dir / "batch-1-rialo.pending.json").exists())

    def test_unreadable_pending_does_not_broadcast_or_delete_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_path = root / "batch.json"
            batch_path.write_text('{"batch_id":"batch-1"}')
            receipt_dir = root / "receipts"
            receipt_dir.mkdir()
            marker = receipt_dir / "batch-1-rialo.pending.json"
            marker.write_text(json.dumps({
                "batch_id": "batch-1",
                "program_id": "active",
                "status": "SUBMITTED_UNVERIFIED",
                "transaction_signature": "saved-signature",
            }))
            batch = {
                "batch_id": "batch-1",
                "device_public_key_fingerprint": "fingerprint",
            }
            client = Mock()
            client.get_transaction.side_effect = rialo_anchor.RialoVerificationError("HTTP 404")
            with (
                patch.object(rialo_anchor, "load_verified_batch", return_value=(batch, {})),
                patch.object(rialo_anchor, "invoke_rialo_cli") as broadcast,
                patch.object(rialo_anchor.time, "monotonic", side_effect=[0.0, 2.0]),
            ):
                with self.assertRaises(rialo_anchor.RialoAnchorError):
                    rialo_anchor.submit_batch(
                        batch_path, root / "registry.json", receipt_dir,
                        "active", "unused", "unused", 1, client=client,
                    )
            broadcast.assert_not_called()
            self.assertTrue(marker.exists())


if __name__ == "__main__":
    unittest.main()
