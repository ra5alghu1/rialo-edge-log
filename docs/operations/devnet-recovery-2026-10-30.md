# Rialo Devnet recovery — 2026-10-30

This document records an **observed recovery** of the physical `edge-77BD19` deployment. It is an operational record, **not** a claim that a Devnet reset was officially announced. Never run the historical commands below blindly on a live node.

## Incident and diagnosis

- Former deployed program: `GVJpRi8SVURsjKbLC84Azk24vV2cK3ib74aXRk5hdatF`.
- `getAccountInfo` on both `http://devnet.rialo.io:4100` and `https://devnet.rialo.io:4101` returned `null` for that program.
- The network itself responded to RPC. An on-chain state reset is a plausible explanation, but its cause is not confirmed.
- The anchor's `watch --include-existing` risked attempting thousands of historical, unanchored batches (12,883 batch files at recovery).
- The publisher's `watch --include-existing` repeatedly retried two September 15 receipts whose old on-chain proofs could no longer be checked: `edge-77BD19-721-780-20260915T001647340932Z` and `edge-77BD19-13621-13680-20260915T181150044582Z`.
- The archive correctly rejected these bundles with HTTP 400, rather than falsely marking them verified.

## Backups and deployed program

- Full state/config backup on the home host: `/var/backups/rialo-edge-log/20261030-103352` (including historical batches/receipts/registrations).
- An additional pre-change environment backup was saved at `/etc/rialo-edge-log/edge.env.before-rialo-recovery-20261030`.
- The Venus PolkaVM artifact was built in the `rialo-edge` user's writable `/var/lib/rialo-edge-log/venus-build` directory; the original repository was not overwritten.
- Replacement executable program: `CA3hK7KpnCnKwQXYPMFpdmupBgF2QqcLmh3WKBxm5qRE`, verified by `getAccountInfo` on both endpoints.
- Fee payer / CLI wallet public address: `2bmtDvEfj4wkp1cXjJqoFJbTEpRtbyhQ8aSeyM4bNHaf`.
- A single explicitly named test batch was submitted, registering the device against the replacement program and producing `RIALO VERIFIED`; old registration history was preserved under `registrations/network-history/`.
- Updated `RIALO_PROGRAM_ID` in `/etc/rialo-edge-log/edge.env`.

**Security:** Do not commit or print the wallet's private JSON key, ingest token, `edge.env` secrets, or backup contents.

## Temporary systemd safeguards (local only)

Two host-specific drop-ins prevent historical replay on service restart:

- `/etc/systemd/system/rialo-edge-anchor.service.d/10-new-batches-only.conf` removes `--include-existing` from `gateway.rialo_anchor watch`.
- `/etc/systemd/system/rialo-edge-publisher.service.d/10-new-publications-only.conf` removes `--include-existing` from `gateway.archive_publisher watch`.

The remainder of each original `ExecStart` command, including RPC, project, data, heartbeat, and authentication environment arguments, is unchanged.

**Critical limitation:** Without `--include-existing`, both watchers skip files that already exist when they start. They can therefore miss batches or receipts created **during downtime**, even if those files belong to the *current* Devnet/program. These overrides are incident mitigation, **not** a reliable final queue implementation. Do not restore `--include-existing` until an appropriate bounded replay/filtering strategy is implemented and tested; otherwise the historic backlog can cause mass on-chain submissions.

No change was made to the independent Orbinum validator or Telegram services.

## Observed end-to-end verification

| Local time (+05), October 30 | Observation |
| --- | --- |
| 10:47:05 | Manually anchored test batch `388408-388467` published by the archive publisher. |
| 10:49:41 | Anchor restarted without `--include-existing`; log: `12883 existing file(s) left untouched`. |
| 10:52–10:53 | New batch `388529-388590` automatically detected, anchored, workflow created, and receipt written; publication receipt exists. |
| 10:56:26 | Publisher restarted without `--include-existing`; log: `2 existing batch(es) left private`. |
| 10:57:54 | Next batch `edge-77BD19-388591-388651-20261030T055748585026Z` automatically **ANCHORED**. |
| 10:58:00 | The same batch automatically **PUBLISHED** to the VPS archive. |
| 10:59:04 | Publisher heartbeat continues; gateway, anchor, and publisher all reported `active`. |

Thus automatic sensor → signing/batching → current Devnet proof → archive publication was verified *after* both service overrides. Historical receipts remain locally preserved and are not represented as current Devnet-verified.

## Wallet, faucet, and website

- On October 30 at 11:01 local, the wallet held `0.394152880 RLO`; after the program deployment the balance had dropped from `1 RLO`.
- `gateway.rialo_balance_guard` remained `active` and reported balances approximately every 5 minutes.
- Code defaults: **below** `0.25 RLO` triggers an attempt to request `1 RLO` from the Devnet faucet, with a 15-minute retry cooldown. Successful faucet issuance was **not** observed during this recovery.
- Correct site endpoint is `/api/network-status`, not `/api/network`. It reported the matching fee-payer wallet and its correct live balance.
- The website's `estimated_spend_24h_rlo` was `0` because the most recent transaction's RPC `meta.fee` was `0`. This does **not** establish that all state/storage/program operations are free; the wallet balance declined during recovery.

## Follow-up work (separate reviewed code PRs)

1. **Reliable bounded replay:** replace first-run `--include-existing` all-or-nothing behavior with a durable cursor or an explicit current-epoch/current-program scope and verified receipt/publication checks. Handle crashes, power loss, service restarts, and bundles produced during downtime. Add tests verifying historical batches cannot be resubmitted en masse.
2. **Network history:** separate legacy program registration/receipts from current ones without deleting or forging records. Reject or quarantine uncheckable historical bundles as **historical/unverified**, not published. Preserve auditability.
3. **Site expense estimate:** distinguish RPC transaction fee from actual wallet balance changes and one-off deploy/storage charges; avoid displaying a misleading unconditional `0 RLO/day` as a complete operating-cost estimate.
4. **Faucet visibility:** expose unsuccessful airdrop attempts and alert on low balance; don't assume the testnet faucet always succeeds.

## Read-only checks for operators

```bash
systemctl is-active rialo-edge-gateway.service rialo-edge-anchor.service rialo-edge-publisher.service rialo-edge-balance-guard.service
systemctl show rialo-edge-anchor.service -p ExecStart --no-pager
systemctl show rialo-edge-publisher.service -p ExecStart --no-pager
sudo journalctl -u rialo-edge-anchor.service -u rialo-edge-publisher.service --since '30 minutes ago' --no-pager | grep -E '\[FOUND\]|\[ANCHORED\]|\[WORKFLOW\]|\[RECEIPT\]|\[PUBLISHED\]|\[FAILED\]|\[HEARTBEAT\]' | tail -n 50
sudo journalctl -u rialo-edge-balance-guard.service --since '30 minutes ago' --no-pager | tail -n 20
curl -fsS https://rialo-edge-log.xyz/api/network-status | python3 -m json.tool
```

Do **not** deploy, refill, replay old batches, restart the services, or modify live host settings as part of this documentation-only change.
