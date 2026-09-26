# Security Policy

Rialo Edge Log handles device signatures, wallet operations, archive ingestion,
and browser verification. Security-sensitive changes deserve extra care.

## Reporting a vulnerability

Please do **not** open a public issue for a vulnerability that could expose
private keys, wallet material, archive credentials, or allow proof verification
to be bypassed.

Use GitHub's private vulnerability reporting / Security Advisories for this
repository when available.

Include:

- the affected component;
- a clear reproduction path;
- the expected and observed behavior;
- the potential impact;
- any suggested mitigation.

## Secrets

Never commit:

- Wi-Fi passwords;
- private device keys;
- wallet files or seed material;
- archive ingestion tokens;
- SSH private keys;
- production environment files containing credentials.

## Scope

Security reports are especially useful for problems involving:

- signature verification;
- device identity registration;
- batch digest generation;
- archive ingest authentication;
- RPC proxy restrictions;
- proof-bundle verification;
- unsafe handling of untrusted archive data.

Rialo Devnet availability or reset behavior is outside this repository's
control.
