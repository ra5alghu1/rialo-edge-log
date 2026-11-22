"""Tests for read-only queue audit."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.audit_queue_readonly import audit


class QueueAuditTests(unittest.TestCase):
    def test_separates_current_program_from_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "batches" / "edge").mkdir(parents=True)
            (root / "receipts").mkdir()
            (root / "publications-vps").mkdir()
            for name in ("current", "old", "pending", "unsubmitted"):
                (root / "batches" / "edge" / (name + ".json")).write_text(json.dumps({"batch_id": name, "created_at_utc": "2026-11-01T00:00:00Z"}))
            (root / "receipts" / "current-rialo.json").write_text(json.dumps({"program_id": "new"}))
            (root / "receipts" / "old-rialo.json").write_text(json.dumps({"program_id": "old"}))
            (root / "receipts" / "pending-rialo.pending.json").write_text(json.dumps({
                "batch_id": "pending", "program_id": "new", "status": "SUBMITTED_UNVERIFIED", "transaction_signature": "saved-signature"
            }))
            counts = audit(root, "new")["counts"]
            self.assertEqual(counts["active_receipt_unpublished"], 1)
            self.assertEqual(counts["historical_or_unknown_receipt"], 1)
            self.assertEqual(counts["active_pending_unverified"], 1)
            self.assertEqual(counts["unsubmitted_or_unknown"], 1)


if __name__ == "__main__":
    unittest.main()
