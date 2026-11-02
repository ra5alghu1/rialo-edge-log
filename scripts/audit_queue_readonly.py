"""Read-only audit of Rialo batch, pending, receipt and publication state.

Does not import gateway modules or contact RPC/archive endpoints.
"""
import argparse
import json
from collections import Counter
from pathlib import Path


def audit(data_dir: Path, program_id: str) -> dict:
    counts = Counter()
    samples = {}
    for batch in sorted((data_dir / "batches").glob("*/*.json")):
        counts["batches"] += 1
        batch_id = batch.stem
        receipt = data_dir / "receipts" / f"{batch_id}-rialo.json"
        pending = data_dir / "receipts" / f"{batch_id}-rialo.pending.json"
        publication = data_dir / "publications-vps" / f"{batch_id}-publication.json"
        category = "unsubmitted_or_unknown"
        try:
            if receipt.is_file():
                payload = json.loads(receipt.read_text(encoding="utf-8"))
                if payload.get("program_id") == program_id:
                    category = "active_receipt_published" if publication.is_file() else "active_receipt_unpublished"
                else:
                    category = "historical_or_unknown_receipt"
            elif pending.is_file():
                payload = json.loads(pending.read_text(encoding="utf-8"))
                if payload.get("program_id") == program_id and payload.get("status") == "SUBMITTED_UNVERIFIED":
                    category = "active_pending_unverified"
                else:
                    category = "historical_or_unknown_pending"
        except (OSError, ValueError, AttributeError):
            category = "invalid_metadata"
        counts[category] += 1
        if category not in samples:
            samples[category] = batch_id
    return {"program_id": program_id, "counts": dict(counts), "example_batch_ids": samples}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--program-id", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.data_dir, args.program_id), indent=2))


if __name__ == "__main__":
    main()
