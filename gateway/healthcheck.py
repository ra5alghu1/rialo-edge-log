#!/usr/bin/env python3
"""Operational healthcheck for the Ubuntu Rialo Edge Log deployment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from gateway.rialo_verify import (
    DEFAULT_DEVICE_REGISTRARS,
    KELVINS_PER_RLO,
    RialoRpcClient,
    RialoVerificationError,
    verify_registration_receipt,
)


DEFAULT_DATA_DIR = Path("/var/lib/rialo-edge-log/data")
DEFAULT_ENV_FILE = Path("/etc/rialo-edge-log/edge.env")
DEFAULT_SERVICES = (
    "rialo-edge-gateway.service",
    "rialo-edge-anchor.service",
    "rialo-edge-publisher.service",
    "rialo-edge-balance-guard.service",
)
STATUS_RANK = {"OK": 0, "WARN": 1, "FAIL": 2}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    message: str


@dataclass(frozen=True)
class HealthcheckConfig:
    data_dir: Path = DEFAULT_DATA_DIR
    env_file: Path = DEFAULT_ENV_FILE
    heartbeat_warn_seconds: float = 180.0
    heartbeat_fail_seconds: float = 600.0
    receipt_warn_seconds: float = 900.0
    receipt_fail_seconds: float = 3600.0
    queue_warn: int = 3
    queue_fail: int = 12
    balance_warn_rlo: float = 0.25
    balance_fail_rlo: float = 0.01
    services: tuple[str, ...] = DEFAULT_SERVICES


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_env(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read environment file {path}: {exc}") from exc
    values: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def newest_record(
    directory: Path,
    pattern: str,
    timestamp_field: str,
) -> tuple[Path, datetime] | None:
    newest: tuple[Path, datetime] | None = None
    if not directory.exists():
        return None
    for path in directory.glob(pattern):
        if not path.is_file():
            continue
        try:
            value = read_json(path)
            raw_timestamp = value.get(timestamp_field)
            if not isinstance(raw_timestamp, str):
                continue
            timestamp = parse_utc(raw_timestamp)
        except (ValueError, TypeError):
            continue
        if newest is None or timestamp > newest[1]:
            newest = (path, timestamp)
    return newest


def age_result(
    name: str,
    record: tuple[Path, datetime] | None,
    now: datetime,
    warn_seconds: float,
    fail_seconds: float,
) -> CheckResult:
    if record is None:
        return CheckResult(name, "FAIL", "no valid record found")
    path, timestamp = record
    age = max(0.0, (now - timestamp).total_seconds())
    if age >= fail_seconds:
        status = "FAIL"
    elif age >= warn_seconds:
        status = "WARN"
    else:
        status = "OK"
    return CheckResult(
        name,
        status,
        f"{path.name} is {age:.0f}s old",
    )


def systemd_service_state(
    service: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[bool, str]:
    try:
        completed = runner(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return False, f"systemctl failed: {exc}"
    state = completed.stdout.strip() or completed.stderr.strip() or f"exit {completed.returncode}"
    return completed.returncode == 0 and state == "active", state


def service_result(
    service: str,
    checker: Callable[[str], tuple[bool, str]],
) -> CheckResult:
    active, detail = checker(service)
    return CheckResult(
        f"service:{service}",
        "OK" if active else "FAIL",
        detail,
    )


def batch_created_at(path: Path) -> datetime | None:
    try:
        value = read_json(path)
        raw = value.get("created_at_utc")
        return parse_utc(raw) if isinstance(raw, str) else None
    except (ValueError, TypeError):
        return None


def count_anchor_queue(data_dir: Path, after: datetime | None) -> int:
    receipt_dir = data_dir / "receipts"
    total = 0
    for path in (data_dir / "batches").glob("*/*.json"):
        if not path.is_file():
            continue
        batch_id = path.stem
        if (receipt_dir / f"{batch_id}-rialo.json").is_file():
            continue
        created = batch_created_at(path)
        if created is None:
            continue
        # Ignore deliberate historical gaps that pre-date the most recent
        # successful anchor. Only the queue accumulated after that recovery
        # point represents current operational debt.
        if after is not None and created <= after:
            continue
        total += 1
    return total


def receipt_verified_at(path: Path) -> datetime | None:
    try:
        value = read_json(path)
        raw = value.get("verified_at_utc")
        return parse_utc(raw) if isinstance(raw, str) else None
    except (ValueError, TypeError):
        return None


def count_publish_queue(data_dir: Path, after: datetime | None) -> int:
    publication_dir = data_dir / "publications-vps"
    total = 0
    receipt_dir = data_dir / "receipts"
    if not receipt_dir.exists():
        return 0
    for path in receipt_dir.glob("*-rialo.json"):
        if not path.is_file():
            continue
        batch_id = path.name.removesuffix("-rialo.json")
        if (publication_dir / f"{batch_id}-publication.json").is_file():
            continue
        verified = receipt_verified_at(path)
        if verified is None:
            continue
        if after is not None and verified <= after:
            continue
        total += 1
    return total


def queue_result(name: str, count: int, warn: int, fail: int) -> CheckResult:
    if count >= fail:
        status = "FAIL"
    elif count >= warn:
        status = "WARN"
    else:
        status = "OK"
    return CheckResult(name, status, f"{count} pending")


def balance_result(
    client: RialoRpcClient,
    fee_payer: str,
    warn_rlo: float,
    fail_rlo: float,
) -> CheckResult:
    try:
        kelvins = client.get_balance(fee_payer)
    except RialoVerificationError as exc:
        return CheckResult("rlo_balance", "FAIL", str(exc))
    balance = kelvins / KELVINS_PER_RLO
    status = "FAIL" if balance < fail_rlo else "WARN" if balance < warn_rlo else "OK"
    return CheckResult("rlo_balance", status, f"{balance:.9f} RLO")


def program_result(client: RialoRpcClient, program_id: str) -> CheckResult:
    try:
        client.get_account_info(program_id)
    except RialoVerificationError as exc:
        return CheckResult("rialo_program", "FAIL", str(exc))
    return CheckResult("rialo_program", "OK", f"{program_id} is readable")


def registrations_result(
    client: RialoRpcClient,
    data_dir: Path,
    program_id: str,
) -> CheckResult:
    registration_dir = data_dir / "registrations"
    paths = sorted(registration_dir.glob("*-rialo-registration.json"))
    if not paths:
        return CheckResult("device_registrations", "FAIL", "no registration receipts found")

    verified_count = 0
    pruned_count = 0
    for path in paths:
        try:
            receipt = read_json(path)
            device_id = receipt.get("device_id")
            fingerprint = receipt.get("public_key_fingerprint")
            if not isinstance(device_id, str) or not isinstance(fingerprint, str):
                raise RialoVerificationError("registration receipt is incomplete")
            verified = verify_registration_receipt(
                device_id,
                fingerprint,
                receipt,
                client,
                expected_program_id=program_id,
                expected_registrar=DEFAULT_DEVICE_REGISTRARS,
            )
        except (ValueError, RialoVerificationError) as exc:
            return CheckResult(
                "device_registrations",
                "FAIL",
                f"{path.name}: {exc}",
            )
        verified_count += 1
        if verified.get("transaction_history_pruned"):
            pruned_count += 1

    suffix = (
        f"; {pruned_count} registration transaction(s) pruned but live workflow verified"
        if pruned_count
        else ""
    )
    return CheckResult(
        "device_registrations",
        "OK",
        f"{verified_count} registration(s) verified{suffix}",
    )


def overall_status(checks: Sequence[CheckResult]) -> str:
    highest = max((STATUS_RANK.get(check.status, 2) for check in checks), default=2)
    return ("HEALTHY", "DEGRADED", "FAILED")[highest]


def run_healthcheck(
    config: HealthcheckConfig,
    *,
    client: RialoRpcClient | None = None,
    service_checker: Callable[[str], tuple[bool, str]] = systemd_service_state,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    checks: list[CheckResult] = []

    for service in config.services:
        checks.append(service_result(service, service_checker))

    heartbeat = newest_record(
        config.data_dir / "heartbeats", "*.json", "received_at_utc"
    )
    checks.append(
        age_result(
            "heartbeat_freshness",
            heartbeat,
            current,
            config.heartbeat_warn_seconds,
            config.heartbeat_fail_seconds,
        )
    )

    latest_receipt = newest_record(
        config.data_dir / "receipts", "*-rialo.json", "verified_at_utc"
    )
    checks.append(
        age_result(
            "anchor_freshness",
            latest_receipt,
            current,
            config.receipt_warn_seconds,
            config.receipt_fail_seconds,
        )
    )
    anchor_after = latest_receipt[1] if latest_receipt else None
    checks.append(
        queue_result(
            "anchor_queue",
            count_anchor_queue(config.data_dir, anchor_after),
            config.queue_warn,
            config.queue_fail,
        )
    )

    latest_publication = newest_record(
        config.data_dir / "publications-vps",
        "*-publication.json",
        "published_at_utc",
    )
    checks.append(
        age_result(
            "publication_freshness",
            latest_publication,
            current,
            config.receipt_warn_seconds,
            config.receipt_fail_seconds,
        )
    )
    publish_after = latest_publication[1] if latest_publication else None
    checks.append(
        queue_result(
            "publication_queue",
            count_publish_queue(config.data_dir, publish_after),
            config.queue_warn,
            config.queue_fail,
        )
    )

    try:
        env = load_env(config.env_file)
    except ValueError as exc:
        checks.append(CheckResult("configuration", "FAIL", str(exc)))
        return {
            "overall": overall_status(checks),
            "checked_at_utc": current.isoformat().replace("+00:00", "Z"),
            "checks": [asdict(check) for check in checks],
        }

    required = ("RIALO_RPC_URL", "RIALO_PROGRAM_ID", "RIALO_FEE_PAYER")
    missing = [name for name in required if not env.get(name)]
    if missing:
        checks.append(
            CheckResult(
                "configuration",
                "FAIL",
                "missing " + ", ".join(missing),
            )
        )
    else:
        checks.append(CheckResult("configuration", "OK", "required values present"))
        active_client = client or RialoRpcClient(env["RIALO_RPC_URL"])
        checks.append(
            balance_result(
                active_client,
                env["RIALO_FEE_PAYER"],
                config.balance_warn_rlo,
                config.balance_fail_rlo,
            )
        )
        checks.append(program_result(active_client, env["RIALO_PROGRAM_ID"]))
        checks.append(
            registrations_result(
                active_client,
                config.data_dir,
                env["RIALO_PROGRAM_ID"],
            )
        )

    return {
        "overall": overall_status(checks),
        "checked_at_utc": current.isoformat().replace("+00:00", "Z"),
        "checks": [asdict(check) for check in checks],
    }


def print_text_report(report: dict[str, Any]) -> None:
    for check in report["checks"]:
        print(f"[{check['status']}] {check['name']}: {check['message']}")
    print(f"OVERALL: {report['overall']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--heartbeat-warn-seconds", type=float, default=180.0)
    parser.add_argument("--heartbeat-fail-seconds", type=float, default=600.0)
    parser.add_argument("--receipt-warn-seconds", type=float, default=900.0)
    parser.add_argument("--receipt-fail-seconds", type=float, default=3600.0)
    parser.add_argument("--queue-warn", type=int, default=3)
    parser.add_argument("--queue-fail", type=int, default=12)
    parser.add_argument("--balance-warn-rlo", type=float, default=0.25)
    parser.add_argument("--balance-fail-rlo", type=float, default=0.01)
    parser.add_argument(
        "--skip-services",
        action="store_true",
        help="skip systemd checks, useful for containers and CI",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if (
        args.heartbeat_warn_seconds < 0
        or args.heartbeat_fail_seconds < args.heartbeat_warn_seconds
        or args.receipt_warn_seconds < 0
        or args.receipt_fail_seconds < args.receipt_warn_seconds
        or args.queue_warn < 0
        or args.queue_fail < args.queue_warn
        or args.balance_fail_rlo < 0
        or args.balance_warn_rlo < args.balance_fail_rlo
    ):
        print("ERROR: invalid healthcheck thresholds", file=sys.stderr)
        return 2

    config = HealthcheckConfig(
        data_dir=args.data_dir,
        env_file=args.env_file,
        heartbeat_warn_seconds=args.heartbeat_warn_seconds,
        heartbeat_fail_seconds=args.heartbeat_fail_seconds,
        receipt_warn_seconds=args.receipt_warn_seconds,
        receipt_fail_seconds=args.receipt_fail_seconds,
        queue_warn=args.queue_warn,
        queue_fail=args.queue_fail,
        balance_warn_rlo=args.balance_warn_rlo,
        balance_fail_rlo=args.balance_fail_rlo,
        services=() if args.skip_services else DEFAULT_SERVICES,
    )
    report = run_healthcheck(config)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)

    return {"HEALTHY": 0, "DEGRADED": 1, "FAILED": 2}[report["overall"]]


if __name__ == "__main__":
    raise SystemExit(main())
