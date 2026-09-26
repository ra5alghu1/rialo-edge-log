# Contributing

Thanks for taking an interest in Rialo Edge Log.

The project is intentionally small and focused: signed physical telemetry,
deterministic batching, on-chain commitments, and independent browser
verification.

## Good contribution areas

Useful contributions include:

- clearer setup or troubleshooting documentation;
- tests for gateway, archive, verifier, or firmware behavior;
- small reliability fixes;
- improvements to proof inspection and traceability;
- portability improvements for other ESP8266 or Linux edge setups.

Please avoid unrelated framework rewrites or large feature additions unless
there is a clear problem they solve.

## Before opening a pull request

1. Fork the repository and create a focused branch.
2. Keep the change as small as practical.
3. Do not commit secrets, device keys, wallet files, Wi-Fi credentials,
   tokens, or generated private telemetry.
4. Run the relevant tests.

Python tests:

```bash
python -m unittest discover -s tests -v
```

Browser verifier and CSV tests:

```bash
node --test tests/test_browser_verifier.mjs tests/test_csv.mjs
```

For firmware changes, make sure the physical-sensor sketch still compiles for
the NodeMCU target.

## Pull requests

A good pull request should explain:

- what problem it fixes or improves;
- what changed;
- how it was tested;
- whether it changes the proof model, trust boundary, or deployment behavior.

If a change affects verification or security assumptions, please update the
relevant documentation in the same pull request.

## Proof model

Please preserve the project's core distinction:

Rialo Edge Log can prove that archived telemetry matches data signed by the
registered device key and committed on-chain. It does not prove that a physical
sensor was calibrated correctly, installed correctly, or uncompromised before
signing.

That boundary should remain explicit in code, UI, and documentation.
