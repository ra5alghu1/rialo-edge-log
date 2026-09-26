# Rialo Edge Log

[![CI](https://github.com/ra5alghu1/rialo-edge-log/actions/workflows/tests.yml/badge.svg)](https://github.com/ra5alghu1/rialo-edge-log/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![ESP8266](https://img.shields.io/badge/ESP8266-physical%20sensor-lightgrey)
![Rialo Devnet](https://img.shields.io/badge/Rialo-Devnet-lightgrey)

**Tamper-evident IoT telemetry with an ESP8266.**

Rialo Edge Log is a small open-source experiment for making later changes to IoT telemetry detectable.

A physical DS18B20 sensor produces temperature readings that are signed directly on an ESP8266, verified on an Ubuntu edge host, grouped into deterministic batches, and anchored on Rialo Devnet.

The raw telemetry stays off-chain.

[**Open the live deployment →**](https://rialo-edge-log.xyz)

![Rialo Edge Log](portal/og-image.png)

---

## Why this exists

Typical IoT telemetry asks you to trust the server that stores the measurements.

Rialo Edge Log uses a different model:

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
Browser independently verifies the proof
```

The blockchain does **not** store the raw sensor data.

It stores a small cryptographic commitment that lets anyone detect whether an archived batch was changed after publication.

---

## What can be verified?

For every published batch, the verifier can check:

- ✅ the reading signatures
- ✅ the registered device public key
- ✅ the deterministic batch digest
- ✅ the Rialo workflow state
- ✅ the anchoring transaction
- ✅ the published archive contents

If an archived temperature value is changed after publication, verification fails.

### What this does **not** prove

The project does not claim that blockchain makes a sensor truthful.

It cannot prove that:

- the sensor was calibrated correctly;
- the probe was installed where claimed;
- the hardware was uncompromised before signing;
- the physical environment matched the digital measurement.

The proof starts at the device signature.

That boundary is intentional.

---

## Live deployment

The current deployment uses real hardware rather than simulated telemetry.

```text
DS18B20
   ↓
ESP8266 NodeMCU
   ↓ USB serial
Ubuntu edge host
   ↓
Rialo Devnet
```

Current device:

```text
edge-77BD19
```

Current sensor:

```text
DS18B20 on D4 / GPIO2
```

The Ubuntu host runs the gateway, anchor, publisher and balance guard as `systemd` services.

[**Browse real published batches →**](https://rialo-edge-log.xyz)

---

## Architecture

![Rialo Edge Log system architecture](docs/architecture.svg)

Editable Mermaid source: [`docs/architecture.mmd`](docs/architecture.mmd)

At a high level:

1. The ESP8266 reads the DS18B20.
2. The reading is signed using the device's ECDSA P-256 key.
3. The Ubuntu gateway verifies the signature.
4. Multiple readings are grouped into a deterministic batch.
5. A SHA-256 digest of the batch is produced.
6. The digest is recorded in a Rialo Venus workflow.
7. The confirmed batch and proof metadata are published to the archive.
8. The browser recalculates the digest and checks the relevant chain records.

Private device keys, wallet files and archive ingestion credentials never leave the edge host.

---

## Try the proof

Open:

**https://rialo-edge-log.xyz**

Choose a device, open a published batch, and run verification.

The browser checks the original readings, signatures, registered device identity, batch digest and corresponding Rialo records.

No wallet connection is required to inspect an existing proof.

---

## Project components

| Component | Role |
|---|---|
| `firmware/nodemcu_signed` | DS18B20 collection and device-side signing |
| `gateway` | serial ingestion, validation, batching and anchoring |
| `rialo/edge-log-proof` | Rialo Venus workflow |
| `archive` | public archive and API |
| `portal` | RU/EN browser UI and proof verifier |
| `deploy/linux-edge` | Ubuntu edge deployment |
| `deploy/vps-docker` | public archive deployment |

---

## Current project state

The current deployment includes:

- a physical DS18B20 connected to an ESP8266 NodeMCU;
- ECDSA P-256 signatures on device readings;
- deterministic batching on the Ubuntu edge host;
- one-time on-chain registration of the device ID and public-key fingerprint;
- SHA-256 batch commitments anchored on Rialo Devnet;
- a public HTTPS archive;
- browser-based independent verification;
- one-minute signed heartbeats for device presence;
- schema-3 boot-session, reset-reason and optional tamper telemetry;
- CSV export for analysis;
- proof JSON export for independent verification;
- `systemd` supervision on the edge host;
- Docker deployment for the public archive.

The current Venus program ID is:

[`GVJpRi8SVURsjKbLC84Azk24vV2cK3ib74aXRk5hdatF`](https://devnet.rialoscan.org/address/GVJpRi8SVURsjKbLC84Azk24vV2cK3ib74aXRk5hdatF)

Current confirmed transactions and workflows are shown in the [live archive](https://rialo-edge-log.xyz).

Fixed transaction examples are intentionally not kept in this README because Rialo Devnet can reset.

---

## Device identity

The project currently documents two registrar identities:

- historical Windows registrar:  
  `BBjJpGwN3aV3BrMPw6BCZHZue8btcqTTfXouG9Nv9Sz6`
- active Ubuntu registrar:  
  `2bmtDvEfj4wkp1cXjJqoFJbTEpRtbyhQ8aSeyM4bNHaf`

The historical identity remains relevant to already published prototype history.

New Ubuntu device registrations use the active registrar.

---

## Hardware history

![NodeMCU V3 used by Rialo Edge Log](docs/hardware/nodemcu-v3-prototype.jpg)

The first version of the project used a NodeMCU V3 and simulated readings.

That deployment is retained as documented prototype history.

The current deployment uses a different ESP8266 NodeMCU with USB-C and a physical DS18B20 connected to `D4/GPIO2`.

The historical device identity was not silently reused or re-keyed during the migration.

---

## Deployment history

The original Windows prototype produced signed simulated telemetry until the edge host was taken offline on **September 9, 2026**.

The second deployment moved the edge stack to Ubuntu and switched to a physical DS18B20 sensor.

The Ubuntu deployment was validated end-to-end on **September 15, 2026**:

- signed telemetry;
- local batching;
- device registration;
- Rialo anchoring;
- archive publication;
- live heartbeats;
- browser verification;
- automatic `systemd` restart.

No continuity is claimed for the period when the edge device was offline.

---

## Verification model

The proof shows that a published batch matches:

1. readings signed by the registered device key;
2. the deterministic batch digest;
3. the digest recorded on Rialo;
4. the public archive payload presented to the verifier.

Schema-3 readings also bind:

- device boot session;
- ESP8266 reset reason;
- optional enclosure-tamper state.

Heartbeat delivery is operational metadata. The archive accepts it only after verifying the latest reading and matching the key to a previously published device.

---

## Browser proof transport

The default browser verifier uses the archive's same-origin `/api/rpc` endpoint.

That endpoint forwards only the read-only RPC calls needed by the verifier and does not submit transactions.

Current protections include:

- only `getTransaction`;
- base64 `getAccountInfo`;
- request size limit;
- response size limit;
- upstream timeout;
- concurrency limit;
- no caller-selected upstream URL;
- no redirects;
- no batch requests.

Signatures and digests are still checked in the browser.

Because chain responses travel through the archive operator's server in the default setup, this transport is not fully independent of the archive operator.

Independent operators can call `verifyProofBundle` with their own trusted `rpcUrl` or `rpcCall`.

---

## Exporting readings

Open a batch in the portal and choose **Download readings CSV**.

The CSV contains readings in archive order, including:

- temperature;
- sequence;
- uptime;
- available boot fields;
- available tamper fields;
- receipt-time metadata.

CSV export is intended for analysis, not signature verification.

Use the separate proof JSON download for cryptographic verification.

---

## Run it yourself

The repository contains setup notes for each layer.

Start here for the current physical edge deployment:

[`deploy/linux-edge/README.md`](deploy/linux-edge/README.md)

Other useful entry points:

- [`gateway/README.md`](gateway/README.md)
- [`archive`](archive)
- [`portal`](portal)
- [`rialo/edge-log-proof`](rialo/edge-log-proof)

---

## Security notes

Do not commit:

- Wi-Fi passwords;
- private device keys;
- wallet files;
- archive ingestion tokens;
- generated private telemetry.

Rialo Devnet can reset without notice.

Receipts from an earlier network state remain useful as local history, but they do not prove current on-chain availability after a network reset.

---

## Next steps

The project is functionally complete enough for continuous use. Current work is focused more on reliability and presentation than adding features.

Possible next improvements:

- make workflow identifiers easier to trace across long-running deployments;
- add an automated end-to-end regression for physical collection through browser verification;
- simplify public proof navigation further;
- replace temporary RPC routing when Rialo exposes a universally reachable HTTPS endpoint;
- evaluate a lower anchoring frequency for longer unattended runs.

---

## Status

This is an independent open-source experiment on Rialo Devnet.

It is not affiliated with or endorsed by Rialo Labs or Subzero Labs and is not official Rialo software.
