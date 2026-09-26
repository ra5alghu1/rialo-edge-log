# Rialo Edge Log

[![CI](https://github.com/ra5alghu1/rialo-edge-log/actions/workflows/tests.yml/badge.svg)](https://github.com/ra5alghu1/rialo-edge-log/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![ESP8266](https://img.shields.io/badge/ESP8266-physical%20sensor-lightgrey)
![Rialo Devnet](https://img.shields.io/badge/Rialo-Devnet-lightgrey)

**Tamper-evident IoT telemetry with an ESP8266.**

Rialo Edge Log records real DS18B20 temperature readings, signs them on an
ESP8266, groups them into batches on an Ubuntu edge host, and anchors each batch
digest on Rialo Devnet.

The readings themselves stay off-chain.

[**Open the live deployment →**](https://rialo-edge-log.xyz)

![Rialo Edge Log](portal/og-image.png)

## Why I built it

If telemetry is stored on a normal server, you usually have to trust that the
stored history was not edited later.

This project adds a simple verification path:

```text
Physical sensor
      ↓
ESP8266 signs each reading
      ↓
Ubuntu edge gateway verifies it
      ↓
Readings are grouped into a deterministic batch
      ↓
SHA-256 batch digest is anchored on Rialo
      ↓
Public archive
      ↓
Browser verifies the proof
```

Rialo stores the batch commitment, not the raw telemetry. If somebody changes
an archived value later, the batch no longer matches the on-chain digest.

## What the proof checks

For a published batch, the verifier checks:

- device signatures;
- the registered device public key;
- the deterministic batch digest;
- Rialo workflow state;
- the anchoring transaction;
- the archive contents being shown to the user.

Change an archived temperature value and verification fails.

### What it does not prove

This does not prove that the sensor was calibrated correctly, installed in the
right place, or uncompromised before signing.

The proof starts at the device signature. It proves integrity from that point
forward, not physical truth.

## Live deployment

The current setup uses a real sensor, not simulated telemetry.

```text
DS18B20
   ↓
ESP8266 NodeMCU
   ↓ USB serial
Ubuntu edge host
   ↓
Rialo Devnet
```

Current device: `edge-77BD19`

Sensor: `DS18B20 on D4 / GPIO2`

The Ubuntu host runs the gateway, anchor, publisher and balance guard as
`systemd` services.

[**Browse published batches →**](https://rialo-edge-log.xyz)

## Architecture

![Rialo Edge Log system architecture](docs/architecture.svg)

Editable Mermaid source: [`docs/architecture.mmd`](docs/architecture.mmd)

The main path is:

1. ESP8266 reads the DS18B20.
2. The device signs the reading with its ECDSA P-256 key.
3. The Ubuntu gateway verifies the signature.
4. Readings are grouped into a deterministic batch.
5. The batch gets a SHA-256 digest.
6. The digest is written to a Rialo Venus workflow.
7. The confirmed batch and proof metadata are published to the archive.
8. The browser recalculates the digest and reads the matching chain records.

Private device keys, wallet files and archive ingestion credentials stay on the
edge host.

## Try it

Open **https://rialo-edge-log.xyz**, choose a device, open a batch and run
verification.

No wallet connection is required to inspect an existing proof.

## Repository map

| Component | Role |
|---|---|
| `firmware/nodemcu_signed` | DS18B20 collection and device-side signing |
| `gateway` | serial ingest, verification, batching and anchoring |
| `rialo/edge-log-proof` | Rialo Venus workflow |
| `archive` | public archive and API |
| `portal` | RU/EN browser UI and verifier |
| `deploy/linux-edge` | Ubuntu edge deployment |
| `deploy/vps-docker` | public archive deployment |

## Current state

The live deployment currently has:

- a physical DS18B20 on an ESP8266 NodeMCU;
- ECDSA P-256 signatures on readings;
- deterministic batching on Ubuntu;
- one-time on-chain device registration;
- SHA-256 batch commitments on Rialo Devnet;
- a public HTTPS archive;
- browser verification;
- signed one-minute heartbeats;
- schema-3 boot-session, reset-reason and optional tamper fields;
- CSV export;
- proof JSON export;
- `systemd` supervision;
- Docker deployment for the public archive.

Current Venus program ID:

[`GVJpRi8SVURsjKbLC84Azk24vV2cK3ib74aXRk5hdatF`](https://devnet.rialoscan.org/address/GVJpRi8SVURsjKbLC84Azk24vV2cK3ib74aXRk5hdatF)

Current transactions and workflows are shown in the
[live archive](https://rialo-edge-log.xyz).

I do not keep fixed transaction examples here because Rialo Devnet can reset.

## Device identity

The project has two documented registrar identities:

- historical Windows registrar: `BBjJpGwN3aV3BrMPw6BCZHZue8btcqTTfXouG9Nv9Sz6`
- active Ubuntu registrar: `2bmtDvEfj4wkp1cXjJqoFJbTEpRtbyhQ8aSeyM4bNHaf`

The Windows registrar stays in the trust list for old proof history. New Ubuntu
registrations use the active registrar.

## Hardware history

![NodeMCU V3 used by Rialo Edge Log](docs/hardware/nodemcu-v3-prototype.jpg)

The first version used a NodeMCU V3 with simulated readings. I kept that history
in the repo instead of pretending it was always a physical-sensor project.

The current deployment uses a different ESP8266 NodeMCU with USB-C and a
physical DS18B20 on `D4/GPIO2`. The old device identity was not reused.

## Deployment history

The Windows prototype stopped on **September 9, 2026**.

The Ubuntu deployment switched to the physical DS18B20 and was checked
end-to-end on **September 15, 2026**: signing, batching, registration, anchoring,
publication, heartbeats, browser verification and `systemd` restart behavior.

There is no claimed telemetry continuity for the period when the edge host was
offline.

## Verification details

A valid published batch must match:

1. readings signed by the registered device key;
2. the locally calculated batch digest;
3. the digest stored on Rialo;
4. the archive payload being verified.

Schema-3 readings also include the device boot session, ESP8266 reset reason and
optional enclosure-tamper state.

Heartbeat data is treated as operational metadata. The archive accepts a
heartbeat only after verifying its latest reading and matching the key to an
already published device.

## Browser RPC path

The browser verifier uses the archive's same-origin `/api/rpc` endpoint by
default.

That proxy only forwards the read-only calls used by the verifier. It does not
submit transactions. It also rejects caller-selected upstream URLs, redirects,
batch requests and oversized requests/responses.

Signatures and digests are still checked in the browser.

The tradeoff is that the default RPC transport goes through the archive
operator. If you want a fully separate RPC path, `verifyProofBundle` accepts a
trusted `rpcUrl` or `rpcCall`.

## Exporting readings

The portal can export the selected batch as CSV. The CSV includes temperature,
sequence, uptime and the available boot/tamper fields.

CSV is for analysis. Use the proof JSON when you want to verify the original
records.

## Run it yourself

For the current physical edge setup, start here:

[`deploy/linux-edge/README.md`](deploy/linux-edge/README.md)

Other useful entry points:

- [`gateway/README.md`](gateway/README.md)
- [`archive`](archive)
- [`portal`](portal)
- [`rialo/edge-log-proof`](rialo/edge-log-proof)

## Security notes

Do not commit Wi-Fi passwords, private device keys, wallet files, archive
ingestion tokens or private telemetry.

Rialo Devnet can reset. Old receipts are still useful as local history, but they
do not prove that the same chain state still exists after a reset.

## Next

The project already does what I originally wanted it to do, so most new work is
around reliability and usability rather than adding more features.

Things I may still improve:

- easier tracing of workflow IDs in long-running deployments;
- an end-to-end regression from physical reading to browser verification;
- simpler proof navigation;
- removing the temporary RPC routing once Rialo has a generally reachable HTTPS endpoint;
- testing a lower anchoring frequency for longer unattended runs.

## Status

Independent open-source experiment on Rialo Devnet.

Not affiliated with or endorsed by Rialo Labs or Subzero Labs.
