import base64
import json
import struct
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from gateway.healthcheck import (
    HealthcheckConfig,
    count_anchor_queue,
    overall_status,
    run_healthcheck,
)
from gateway.rialo_args import build_registration_arguments, registration_workflow_slug
from gateway.rialo_verify import DEFAULT_DEVICE_REGISTRARS


class HealthcheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        for name in ("batches/edge-A1B2C3", "heartbeats", "receipts", "registrations", "publications-vps"):
            (self.data / name).mkdir(parents=True, exist_ok=True)
        self.now = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
        self.program_id = "PROGRAM123"
        self.fee_payer = DEFAULT_DEVICE_REGISTRARS[1]
        self.env = self.root / "edge.env"
        self.env.write_text(
            "\n".join(
                (
                    "RIALO_RPC_URL=http://rpc.invalid",
                    f"RIALO_PROGRAM_ID={self.program_id}",
                    f"RIALO_FEE_PAYER={self.fee_payer}",
                )
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def stamp(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    def write_batch(self, batch_id: str, created_at: datetime) -> Path:
        path = self.data / "batches" / "edge-A1B2C3" / f"{batch_id}.json"
        path.write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "device_id": "edge-A1B2C3",
                    "created_at_utc": self.stamp(created_at),
                }
            ),
            encoding="utf-8",
        )
        return path

    def write_receipt(self, batch_id: str, verified_at: datetime) -> Path:
        path = self.data / "receipts" / f"{batch_id}-rialo.json"
        path.write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "status": "RIALO_VERIFIED",
                    "verified_at_utc": self.stamp(verified_at),
                }
            ),
            encoding="utf-8",
        )
        return path

    def write_publication(self, batch_id: str, published_at: datetime) -> Path:
        path = self.data / "publications-vps" / f"{batch_id}-publication.json"
        path.write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "status": "PUBLISHED",
                    "published_at_utc": self.stamp(published_at),
                }
            ),
            encoding="utf-8",
        )
        return path

    def write_heartbeat(self, received_at: datetime) -> None:
        (self.data / "heartbeats" / "edge-A1B2C3.json").write_text(
            json.dumps(
                {
                    "message_type": "device_heartbeat",
                    "device_id": "edge-A1B2C3",
                    "received_at_utc": self.stamp(received_at),
                }
            ),
            encoding="utf-8",
        )

    def write_registration(self) -> None:
        fingerprint = "11" * 32
        path = self.data / "registrations" / "edge-A1B2C3-rialo-registration.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "RIALO_DEVICE_REGISTERED",
                    "device_id": "edge-A1B2C3",
                    "public_key_fingerprint": fingerprint,
                    "program_id": self.program_id,
                    "transaction_signature": "TRANSACTION",
                    "workflow_address": "WORKFLOW",
                    "workflow_slug": registration_workflow_slug("edge-A1B2C3"),
                    "registrar": self.fee_payer,
                }
            ),
            encoding="utf-8",
        )

    def test_historical_unanchored_gap_is_ignored_after_recovery_anchor(self) -> None:
        historical = self.now - timedelta(hours=4)
        recovered = self.now - timedelta(minutes=10)
        current = self.now - timedelta(minutes=5)

        self.write_batch("old-gap", historical)
        self.write_batch("recovery", recovered)
        self.write_receipt("recovery", recovered + timedelta(minutes=1))
        self.write_batch("current-gap", current)

        count = count_anchor_queue(
            self.data,
            recovered + timedelta(minutes=1),
        )
        self.assertEqual(count, 1)

    def test_overall_status_uses_highest_severity(self) -> None:
        from gateway.healthcheck import CheckResult

        self.assertEqual(
            overall_status(
                [
                    CheckResult("one", "OK", "fine"),
                    CheckResult("two", "WARN", "late"),
                ]
            ),
            "DEGRADED",
        )
        self.assertEqual(
            overall_status(
                [
                    CheckResult("one", "WARN", "late"),
                    CheckResult("two", "FAIL", "broken"),
                ]
            ),
            "FAILED",
        )

    def test_healthy_report_covers_services_freshness_queues_and_chain(self) -> None:
        heartbeat_at = self.now - timedelta(seconds=30)
        batch_at = self.now - timedelta(minutes=5)
        verified_at = self.now - timedelta(minutes=4)
        published_at = self.now - timedelta(minutes=3)

        self.write_heartbeat(heartbeat_at)
        self.write_batch("latest", batch_at)
        self.write_receipt("latest", verified_at)
        self.write_publication("latest", published_at)
        self.write_registration()

        class FakeClient:
            def get_balance(inner_self, address: str) -> int:
                self.assertEqual(address, self.fee_payer)
                return 1_000_000_000

            def get_account_info(inner_self, address: str) -> dict:
                self.assertEqual(address, self.program_id)
                return {"owner": "loader", "data": ["", "base64"]}

        with patch(
            "gateway.healthcheck.verify_registration_receipt",
            return_value={
                "workflow_address": "WORKFLOW",
                "registrar": self.fee_payer,
                "transaction_history_pruned": True,
            },
        ):
            report = run_healthcheck(
                HealthcheckConfig(data_dir=self.data, env_file=self.env),
                client=FakeClient(),
                service_checker=lambda _service: (True, "active"),
                now=self.now,
            )

        self.assertEqual(report["overall"], "HEALTHY")
        statuses = {item["name"]: item["status"] for item in report["checks"]}
        self.assertEqual(statuses["heartbeat_freshness"], "OK")
        self.assertEqual(statuses["anchor_freshness"], "OK")
        self.assertEqual(statuses["anchor_queue"], "OK")
        self.assertEqual(statuses["publication_queue"], "OK")
        self.assertEqual(statuses["rlo_balance"], "OK")
        self.assertEqual(statuses["device_registrations"], "OK")

    def test_running_services_do_not_hide_a_stalled_anchor(self) -> None:
        self.write_heartbeat(self.now - timedelta(seconds=20))
        old = self.now - timedelta(hours=2)
        self.write_batch("old", old - timedelta(minutes=1))
        self.write_receipt("old", old)
        self.write_publication("old", old)
        self.write_registration()

        class FakeClient:
            def get_balance(inner_self, _address: str) -> int:
                return 1_000_000_000

            def get_account_info(inner_self, _address: str) -> dict:
                return {"owner": "loader", "data": ["", "base64"]}

        with patch(
            "gateway.healthcheck.verify_registration_receipt",
            return_value={
                "workflow_address": "WORKFLOW",
                "registrar": self.fee_payer,
                "transaction_history_pruned": False,
            },
        ):
            report = run_healthcheck(
                HealthcheckConfig(data_dir=self.data, env_file=self.env),
                client=FakeClient(),
                service_checker=lambda _service: (True, "active"),
                now=self.now,
            )

        self.assertEqual(report["overall"], "FAILED")
        anchor = next(
            item for item in report["checks"] if item["name"] == "anchor_freshness"
        )
        self.assertEqual(anchor["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
