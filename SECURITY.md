# Security

If a bug can expose keys, wallet material, archive credentials or bypass proof
verification, please do not open a public issue.

Use GitHub private vulnerability reporting / Security Advisories for the repo
when available.

Useful reports should include:

- affected component;
- reproduction steps;
- expected vs actual behavior;
- likely impact.

Please never commit:

- Wi-Fi passwords;
- device private keys;
- wallet files or seed material;
- archive ingestion tokens;
- SSH private keys;
- production env files with credentials.

The most sensitive areas in this repo are signature verification, device
registration, batch digest generation, archive ingest auth, the RPC proxy and
proof-bundle verification.

Rialo Devnet outages and resets are outside the scope of this repository.
