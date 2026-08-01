#!/usr/bin/env python3
"""Turn `.security-exceptions.yml` into pip-audit ignore flags.

`pip-audit` has no severity-threshold option, so the CI scan fails on every
known advisory. Accepted risks are recorded in `.security-exceptions.yml` with a
reviewer and an expiry date, and are suppressed only while unexpired: an expired
exception is dropped here, which makes the scan fail again and forces a review.

Writes `ignore_flags` to `$GITHUB_OUTPUT` when running in GitHub Actions and
prints the flags on stdout otherwise. Exits non-zero when the file is malformed.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

EXCEPTIONS_FILE = Path(__file__).resolve().parents[2] / ".security-exceptions.yml"
MAX_DAYS = {"critical": 30, "high": 30, "medium": 90, "low": 90}


def _parse_expiry(value: object, advisory_id: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise SystemExit(
                f"Exception {advisory_id}: 'expires' must be YYYY-MM-DD"
            ) from exc
    raise SystemExit(f"Exception {advisory_id}: missing 'expires' date")


def collect(document: object, today: date | None = None) -> tuple[list[str], list[str]]:
    """Return (active advisory IDs, human-readable notes about dropped ones)."""
    today = today or date.today()
    if document is None:
        document = {}
    if not isinstance(document, dict):
        raise SystemExit(".security-exceptions.yml must be a mapping")

    entries = document.get("exceptions") or []
    if not isinstance(entries, list):
        raise SystemExit(".security-exceptions.yml: 'exceptions' must be a list")

    active: list[str] = []
    notes: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit(".security-exceptions.yml: each exception must be a mapping")
        advisory_id = str(entry.get("id") or "").strip()
        if not advisory_id:
            raise SystemExit(".security-exceptions.yml: every exception needs an 'id'")

        severity = str(entry.get("severity") or "").strip().lower()
        if severity not in MAX_DAYS:
            raise SystemExit(
                f"Exception {advisory_id}: severity must be one of {sorted(MAX_DAYS)}"
            )
        if not str(entry.get("reviewer") or "").strip():
            raise SystemExit(f"Exception {advisory_id}: 'reviewer' is required")
        if not str(entry.get("reason") or "").strip():
            raise SystemExit(f"Exception {advisory_id}: 'reason' is required")

        expires = _parse_expiry(entry.get("expires"), advisory_id)
        if expires < today:
            notes.append(f"{advisory_id}: exception expired on {expires.isoformat()}")
            continue
        if (expires - today).days > MAX_DAYS[severity]:
            raise SystemExit(
                f"Exception {advisory_id}: {severity} exceptions may not exceed "
                f"{MAX_DAYS[severity]} days"
            )
        active.append(advisory_id)

    return active, notes


def main() -> int:
    if EXCEPTIONS_FILE.exists():
        try:
            document = yaml.safe_load(EXCEPTIONS_FILE.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            print(f"ERROR: .security-exceptions.yml is not valid YAML: {exc}")
            return 1
    else:
        document = {}

    active, notes = collect(document)
    for note in notes:
        print(f"NOTICE: {note} - the scan will fail until it is re-reviewed")
    if active:
        print("Suppressing unexpired accepted advisories: " + ", ".join(active))
    else:
        print("No active vulnerability exceptions.")

    flags = " ".join(f"--ignore-vuln {advisory_id}" for advisory_id in active)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"ignore_flags={flags}\n")
    else:
        print(flags)
    return 0


if __name__ == "__main__":
    sys.exit(main())
