from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "linux-edge"


class LinuxEdgeDeploymentTests(unittest.TestCase):
    def test_installer_does_not_start_services_before_configuration(self) -> None:
        installer = (DEPLOY / "install.sh").read_text(encoding="utf-8")
        self.assertIn("systemctl daemon-reload", installer)
        self.assertNotIn("systemctl enable --now", installer)
        self.assertIn("Preserved existing", installer)
        self.assertIn('"${script_dir}"/*.timer', installer)

    def test_workers_use_dedicated_state_directory(self) -> None:
        gateway = (DEPLOY / "rialo-edge-gateway.service").read_text(encoding="utf-8")
        anchor = (DEPLOY / "rialo-edge-anchor.service").read_text(encoding="utf-8")
        publisher = (DEPLOY / "rialo-edge-publisher.service").read_text(encoding="utf-8")
        self.assertIn("/var/lib/rialo-edge-log/data", gateway)
        self.assertIn("/var/lib/rialo-edge-log/data", anchor)
        self.assertIn("/var/lib/rialo-edge-log/data", publisher)
        self.assertIn("--cli-mode native", anchor)

    def test_rpc_tunnel_requires_host_key_checking(self) -> None:
        tunnel = (DEPLOY / "rialo-edge-rpc-tunnel.service").read_text(encoding="utf-8")
        self.assertIn("StrictHostKeyChecking=yes", tunnel)
        self.assertIn("ExitOnForwardFailure=yes", tunnel)
        self.assertIn("BatchMode=yes", tunnel)

    def test_healthcheck_timer_is_read_only_and_runs_every_five_minutes(self) -> None:
        service = (DEPLOY / "rialo-edge-healthcheck.service").read_text(
            encoding="utf-8"
        )
        timer = (DEPLOY / "rialo-edge-healthcheck.timer").read_text(
            encoding="utf-8"
        )

        self.assertIn("Type=oneshot", service)
        self.assertIn("User=@SERVICE_USER@", service)
        self.assertIn(
            "ExecStart=@REPO_ROOT@/.venv/bin/python -m gateway.healthcheck",
            service,
        )
        self.assertNotIn("Restart=", service)
        self.assertIn("ProtectSystem=strict", service)

        self.assertIn("OnBootSec=2min", timer)
        self.assertIn("OnUnitActiveSec=5min", timer)
        self.assertIn("Persistent=true", timer)
        self.assertIn("Unit=rialo-edge-healthcheck.service", timer)
        self.assertIn("WantedBy=timers.target", timer)

    @unittest.skipUnless(
        shutil.which("systemd-analyze"), "systemd-analyze not installed"
    )
    def test_healthcheck_units_pass_systemd_verify(self) -> None:
        service = (DEPLOY / "rialo-edge-healthcheck.service").read_text(
            encoding="utf-8"
        )
        service = service.replace("@SERVICE_USER@", "nobody")
        service = service.replace("WorkingDirectory=@REPO_ROOT@", "WorkingDirectory=/tmp")
        service = service.replace(
            "ExecStart=@REPO_ROOT@/.venv/bin/python -m gateway.healthcheck",
            "ExecStart=/bin/true",
        )
        timer = (DEPLOY / "rialo-edge-healthcheck.timer").read_text(
            encoding="utf-8"
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service_path = root / "rialo-edge-healthcheck.service"
            timer_path = root / "rialo-edge-healthcheck.timer"
            service_path.write_text(service, encoding="utf-8")
            timer_path.write_text(timer, encoding="utf-8")

            completed = subprocess.run(
                ["systemd-analyze", "verify", str(service_path), str(timer_path)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(
            completed.returncode,
            0,
            msg=completed.stdout + completed.stderr,
        )


if __name__ == "__main__":
    unittest.main()
