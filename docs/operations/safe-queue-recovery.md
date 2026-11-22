# Safe queue recovery after watcher restarts (opt-in)

The recovery PR adds two **opt-in** watcher modes. Existing production service
arguments are unchanged. The options are designed for the October 2026 Devnet
migration where many old historical batches and two old-program receipts must
**not** be replayed.

## Anchor (home Ubuntu)

Use `gateway.rialo_anchor watch --resume-after-restart` **without**
`--include-existing`, only after reviewing a read-only queue audit and
backing up `data/receipts`.

On its **first** use, the anchor writes
`receipts/.anchor-restart-boundary.json` with the active program ID and the
highest observed `last_sequence` per device. Existing historical batches are
left untouched; previously submitted `SUBMITTED_UNVERIFIED` markers belonging
to the active program are still eligible for verification.

On a **later** start, unreceipted batches above that immutable per-device floor
are eligible even if they were created while the watcher was stopped. The
existing `submit_batch` code reuses an active-program pending signature instead
of issuing a new transaction. Old sequence numbers do not become eligible by
changing a file modification timestamp.

**Safeguards:** a corrupt boundary or a mismatch with the configured program ID
fails closed; it does not create a new baseline. Unrecognized device IDs are
also not auto-replayed (onboard these separately). This is a local sequence
boundary, **not** an on-chain transaction lock; a crash between successful CLI
broadcast and writing the pending marker still requires operator review.
Do not run two anchor instances concurrently.

## Publisher (home Ubuntu)

Use `gateway.archive_publisher watch --resume-current-program
--program-id <CURRENT_PROGRAM_ID>` **without** `--include-existing`.
Supply the remaining current production flags (`--data-dir`,
`--publication-dir`, `--heartbeat-dir`, `--archive-url`,
`--ingest-token`) as before.

This mode recovers all unpublished, locally `RIALO_VERIFIED` receipts whose
`program_id` equals the configured current program, including receipts created
during publisher downtime. Old-program receipts are kept on disk but excluded,
and no fake publication markers are created. A persistent HTTP 400 now has a
300-second retry interval rather than being logged every poll.

**Important:** being locally verified does not guarantee the archive's
independent on-chain verification will succeed. Monitor `[PUBLISHED]` and
`[FAILED]` and never classify an HTTP 400 as publication success.

## Deployment separation

The PR does **not** edit any host's systemd overrides or environment files,
does not run live Rialo operations, and does not affect Orbinum or Telegram.
After code review and a green CI, schedule a **separate** backup, a dry-run
queue audit, and explicit approval before changing actual service commands.
Retain the existing temporary `--include-existing`-free service overrides
until then.

Offline regression tests:

```bash
python3 -m unittest tests.test_durable_queue_restart tests.test_anchor_restart_pending
python3 -m unittest discover -s tests -p 'test_*.py'
```
