# Ubuntu Edge Deployment

This deployment runs the serial gateway, Rialo anchor, archive publisher, and
optional Devnet helpers as isolated `systemd` services. It does not modify
Docker or the Orbinum validator.

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
the firmware build directory. Preserve the existing published registrar wallet
when it is available. A registrar rotation must be documented and added as a
second trusted identity rather than silently replacing the old one.

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

The former Windows device remains historical evidence. No telemetry continuity
is claimed for the period when that host was offline.
