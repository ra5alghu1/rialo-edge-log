"""Read-only Rialo queue inventory. No network access or writes.

A batch timestamp alone does NOT establish which Devnet epoch it belongs to.
Only a matching receipt/pending program ID is authoritative locally.
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _load(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def audit(data_dir: Path, program_id: str, publication_dir: Path | None = None,
          epoch_start: str | None = None) -> dict:
    publication_dir = publication_dir or data_dir / "publications-vps"
    cutoff = datetime.fromisoformat(epoch_start.replace("Z", "+00:00")) if epoch_start else None
    if cutoff is not None and cutoff.tzinfo is None:
        raise ValueError("epoch_start must contain a timezone")
    counts = Counter()
    samples = {}
    dates = {}
    for batch_path in sorted((data_dir / "batches").glob("*/*.json")):
        counts["batches"] += 1
        batch = _load(batch_path)
        batch_id = batch_path.stem
        category = "unsubmitted_or_unknown"
        if batch is None or batch.get("batch_id") != batch_id:
            category = "invalid_batch"
        else:
            receipt_path = data_dir / "receipts" / f"{batch_id}-rialo.json"
            pending_path = data_dir / "receipts" / f"{batch_id}-rialo.pending.json"
            publication_path = publication_dir / f"{batch_id}-publication.json"
            if receipt_path.exists():
                receipt = _load(receipt_path)
                if receipt is None:
                    category = "invalid_receipt"
                elif receipt.get("program_id") == program_id:
                    if publication_path.exists():
                        publication = _load(publication_path)
                        category = ("active_receipt_published_marker" if
                                    publication is not None and publication.get("batch_id") == batch_id
                                    else "invalid_publication_marker")
                    else:
                        category = "active_receipt_unpublished"
                else:
                    category = "historical_or_unknown_receipt"
            elif pending_path.exists():
                pending = _load(pending_path)
                if pending is None:
                    category = "invalid_pending"
                elif (pending.get("program_id") == program_id and
                      pending.get("batch_id") == batch_id and
                      pending.get("status") == "SUBMITTED_UNVERIFIED" and
                      isinstance(pending.get("transaction_signature"), str) and
                      pending["transaction_signature"]):
                    category = "active_pending_unverified"
                else:
                    category = "historical_or_unknown_pending"
        counts[category] += 1
        samples.setdefault(category, batch_id)
        if category == "unsubmitted_or_unknown":
            raw = batch.get("created_at_utc")
            try:
                created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if created.tzinfo is None:
                    raise ValueError("missing timezone")
                day = created.astimezone(timezone.utc).date().isoformat()
                dates[day] = dates.get(day, 0) + 1
                if cutoff is not None:
                    counts["unsubmitted_after_supplied_cutoff"] += int(created >= cutoff)
                    counts["unsubmitted_before_supplied_cutoff"] += int(created < cutoff)
            except (AttributeError, ValueError, TypeError):
                counts["unsubmitted_invalid_date"] += 1
    return {
        "program_id": program_id,
        "publication_directory": str(publication_dir),
        "epoch_start_supplied_not_verified": epoch_start,
        "counts": dict(counts),
        "example_batch_ids": samples,
        "unsubmitted_by_utc_day": dict(sorted(dates.items())),
        "warning": "Local markers do not prove archive delivery or on-chain confirmation. "
                   "Date cutoff is informational, not permission to replay.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--program-id", required=True)
    parser.add_argument("--publication-dir", type=Path)
    parser.add_argument("--epoch-start", help="Optional UTC ISO timestamp for reporting only")
    args = parser.parse_args()
    print(json.dumps(audit(args.data_dir, args.program_id,
                           args.publication_dir, args.epoch_start), indent=2))


if __name__ == "__main__":
    main()
