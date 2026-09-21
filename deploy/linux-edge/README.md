# Ubuntu Edge Deployment

This deployment runs the serial gateway, Rialo anchor, archive publisher, and
optional Devnet helpers as isolated `systemd` services. It does not modify
unrelated services running on the same host.

The installer creates a dedicated unprivileged `rialo-edge` account, grants it
serial access through the `dialout` group, keeps writable state under
`/var/lib/rialo-edge-log`, and stores configuration under
`/etc/rialo-edge-log`. It installs unit files but deliberately does not enable
or start anything before configuration is reviewed.

## Prerequisites

```bash
sudo apt update
sudo apt install -y git python3 python3-venv openssh-client
sudo git clone https://github.com/robotek8/rialo-edge-log.git /opt/rialo-edge-log
cd /opt/rialo-edge-log
sudo ./deploy/linux-edge/install.sh
```

Install the Rialo CLI and wallet for the `rialo-edge` service account. Do not
copy a device private key into the server; `device_secrets.h` belongs only in
the firmware build directory.

The production Ubuntu migration uses registrar
`2bmtDvEfj4wkp1cXjJqoFJbTEpRtbyhQ8aSeyM4bNHaf`. The historical Windows
registrar `BBjJpGwN3aV3BrMPw6BCZHZue8btcqTTfXouG9Nv9Sz6` remains trusted for
previously published history. Registrar rotation must always add a documented
trust root rather than silently replacing an existing one.

## Configure without starting

Edit `/etc/rialo-edge-log/edge.env` as root. Set the detected serial path, the
current program ID, archive URL, private ingest token, and RPC URLs. The example
contains no working secret.

Do not start the anchor until the active wallet is also a registrar trusted by
the public verifier. If the original registrar wallet is unavailable, first add
the replacement as a second documented trust root; do not silently overwrite
the historical registrar.

List serial ports before starting the gateway:

```bash
sudo -u rialo-edge /opt/rialo-edge-log/.venv/bin/python \
  -m gateway.edge_gateway ports
```

When the physical USB device has been identified, prefer a stable udev symlink
over `/dev/ttyUSB0`; numeric tty names can change after reboot.

## Staged activation

Start only the gateway first:

```bash
sudo systemctl enable --now rialo-edge-gateway.service
sudo journalctl -u rialo-edge-gateway.service -n 50 --no-pager
```

The log must show a new `edge-XXXXXX` identity, a DS18B20 reading, successful
local enrollment, and `simulated=false`. Only then enable anchoring and
publication:

```bash
sudo systemctl enable --now rialo-edge-anchor.service
sudo systemctl enable --now rialo-edge-publisher.service
sudo systemctl enable --now rialo-edge-balance-guard.service
```

If the ISP blocks Devnet port `4100`, authorize a new restricted SSH key on the
VPS, switch both RPC URLs to `http://127.0.0.1:44100`, and enable
`rialo-edge-rpc-tunnel.service`. Never reuse or publish the old Windows tunnel
private key.

## Status and logs

```bash
systemctl --no-pager --full status \
  rialo-edge-gateway.service \
  rialo-edge-anchor.service \
  rialo-edge-publisher.service
journalctl -u 'rialo-edge-*' --since today --no-pager
```

A running systemd process does not prove that the complete telemetry pipeline is
making progress. Run the operational healthcheck as the service account:

```bash
sudo -u rialo-edge -H bash -lc '
cd /opt/rialo-edge-log
/opt/rialo-edge-log/.venv/bin/python -m gateway.healthcheck
'
```

The command checks the four core services, heartbeat freshness, latest Rialo
receipt, new unanchored backlog since the last successful anchor, archive
publication freshness and queue, RLO balance, the current Venus program, and
all saved device registration workflows. It returns exit code `0` for
`HEALTHY`, `1` for `DEGRADED`, and `2` for `FAILED`.

For monitoring integrations, add `--json`. Historical gaps older than the
latest successful anchor are deliberately ignored, so a recovery point does not
leave the deployment permanently unhealthy.

The former Windows device remains historical evidence. No telemetry continuity
is claimed for the period when that host was offline.

The current validated physical deployment is `edge-77BD19` on Ubuntu with a
DS18B20 connected to `D4/GPIO2`. Its first public proof was registered,
anchored, published, and independently verified on September 15, 2026.
