# Contributing

Small, focused changes are welcome.

Good targets are docs, tests, reliability fixes, proof inspection, and making
the edge setup easier to run on another ESP8266/Linux host.

Please avoid large rewrites unless they solve a concrete problem.

Before opening a PR:

1. keep the change focused;
2. do not commit keys, wallets, Wi-Fi credentials, tokens or private telemetry;
3. run the tests that touch your change.

Python:

```bash
python -m unittest discover -s tests -v
```

Browser verifier / CSV:

```bash
node --test tests/test_browser_verifier.mjs tests/test_csv.mjs
```

For firmware changes, make sure the NodeMCU sketch still compiles.

A PR description only needs to answer three things:

- what was wrong or missing;
- what changed;
- how you tested it.

If the change touches signatures, device identity, digest generation or proof
verification, also mention whether the trust model changed.

One project rule matters more than the rest: this system proves that archived
data matches what the registered device signed and what was committed on-chain.
It does not prove that the physical sensor was correct before signing.
