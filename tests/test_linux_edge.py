from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
