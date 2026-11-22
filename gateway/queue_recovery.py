"""Fail-closed restart boundary for telemetry anchor batches.

The first opt-in run snapshots the highest observed sequence *per device*.
Later runs may replay only higher sequences, including files written during
service downtime. No previously observed batch is ever replayed just because
its modification time was changed. This is NOT an on-chain deduplication lock.
"""

import json
import os
from pathlib import Path


class QueueBoundaryError(ValueError):
    pass


def _sequences(batch_files):
    maximum = {}
    for path in batch_files:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        device = value.get("device_id")
        last = value.get("last_sequence")
        if not isinstance(device, str) or not device or type(last) is not int or last < 0:
            continue
        maximum[device] = max(maximum.get(device, -1), last)
    return maximum


def load_or_initialize_boundary(state_path: Path, program_id: str, initial_files: list[Path]) -> dict[str, int]:
    """Create an immutable per-program floor. Fail closed on corrupt state."""
    if state_path.exists():
        try:
            saved = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise QueueBoundaryError(f"cannot read queue boundary {state_path}: {exc}") from exc
        if not isinstance(saved, dict) or saved.get("schema_version") != 1 or saved.get("program_id") != program_id:
            raise QueueBoundaryError("queue boundary is invalid or belongs to a different program; operator review required")
        floors = saved.get("last_sequences")
        if not isinstance(floors, dict) or not all(
            isinstance(k, str) and k and type(v) is int and v >= 0 for k, v in floors.items()
        ):
            raise QueueBoundaryError("queue boundary sequence map is invalid")
        return floors

    floors = _sequences(initial_files)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "schema_version": 1, "program_id": program_id, "last_sequences": floors
    }, ensure_ascii=False, indent=2) + "\n"
    # O_EXCL avoids replacing an existing boundary if two watcher instances race.
    # The service must run as a single instance; unexpected existing state fails closed.
    try:
        fd = os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise QueueBoundaryError("queue boundary was created concurrently; restart and inspect") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        # Never silently reset the floor on failure; operator must review partial state.
        raise
    return floors


def eligible_for_restart(path: Path, floors: dict[str, int]) -> bool:
    """Only known devices and sequences beyond their initial floor are replayed."""
    try:
        batch = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(batch, dict):
        return False
    device = batch.get("device_id")
    last = batch.get("last_sequence")
    return (
        isinstance(device, str)
        and device in floors
        and type(last) is int
        and last > floors[device]
    )
