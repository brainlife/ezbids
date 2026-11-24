"""Validate a BIDS dataset with the image's bids-validator-2 against the pinned schema."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

VALIDATOR = "bids-validator-2"
SCHEMA_PATH = Path("/opt/bids-schema/schema.json")
TIMEOUT_S = 1800

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class ValidationError(RuntimeError):
    """The validator crashed, timed out, or printed something that is not its JSON report."""


@dataclass
class ValidationResult:
    ok: bool
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    validator_version: str = ""
    bids_version: str = ""


def _issue(raw: dict, messages: dict) -> dict:
    """One issue as {code, severity, message, files}; files are dataset-relative paths."""
    paths = list(raw.get("affects") or [])
    if raw.get("location"):
        paths.append(raw["location"])
    code = raw.get("code", "")
    message = raw.get("issueMessage") or messages.get(code, "")
    out = {
        "code": code,
        "severity": raw.get("severity", ""),
        "message": message.strip(),
        "files": [p.lstrip("/") for p in paths],
    }
    if raw.get("subCode"):
        out["sub_code"] = raw["subCode"]
    return out


def parse_report(stdout: str) -> tuple[list[dict], list[dict]]:
    """Split the validator's --format json output into (errors, warnings)."""
    try:
        report = json.loads(stdout)
        block = report["issues"]
        raw_issues = block["issues"]
        messages = block.get("codeMessages", {})
    except (ValueError, KeyError, TypeError) as e:
        raise ValidationError(f"validator did not print a JSON report: {stdout[:300]!r}") from e
    issues = [_issue(i, messages) for i in raw_issues]
    return (
        [i for i in issues if i["severity"] == "error"],
        [i for i in issues if i["severity"] == "warning"],
    )


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as e:
        raise ValidationError(f"{VALIDATOR} timed out after {TIMEOUT_S}s") from e
    except OSError as e:
        raise ValidationError(f"could not run {VALIDATOR}: {e}") from e


def _validator_version() -> str:
    proc = _run([VALIDATOR, "--version"])
    text = _ANSI.sub("", proc.stdout).strip()
    m = re.search(r"\d+\.\d+\.\d+\S*", text)
    return m.group(0) if m else text


def _bids_version(schema_path: Path) -> str:
    try:
        return json.loads(schema_path.read_text())["bids_version"]
    except (OSError, ValueError, KeyError) as e:
        raise ValidationError(f"cannot read bids_version from {schema_path}: {e}") from e


def validate_bids(bids_dir: Path) -> ValidationResult:
    """Run the validator over every TSV row; ok means no errors (warnings are kept)."""
    proc = _run(
        [
            VALIDATOR,
            str(bids_dir),
            "--format",
            "json",
            "--schema",
            f"file://{SCHEMA_PATH}",
            "--max-rows",
            "-1",
        ]
    )
    # exit code 16 means "errors found"; pass/fail comes from the parsed issues, and stderr
    # carries Deno build-script noise, so only stdout is read
    try:
        errors, warnings = parse_report(proc.stdout)
    except ValidationError as e:
        raise ValidationError(f"{e} (exit {proc.returncode}): {proc.stderr[-500:]}") from e
    return ValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        validator_version=_validator_version(),
        bids_version=_bids_version(SCHEMA_PATH),
    )
