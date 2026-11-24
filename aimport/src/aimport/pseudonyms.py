"""Pseudonym key: original identifiers -> subject IDs and per-subject date offsets.

The key file holds identifying data. It lives in a user-chosen folder (never under the
output folder), is never uploaded, and is always written with mode 0600.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import secrets
import tempfile
from pathlib import Path

KEY_VERSION = 1
SUBJECT_RE = re.compile(r"^[a-zA-Z0-9]+$")
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
OFFSET_MIN, OFFSET_MAX = -3650, -365


class KeyLockedError(Exception):
    """Another import into the same project holds the key."""


class PseudonymKey:
    def __init__(self, path: Path, subjects: dict[str, str], offsets: dict[str, int], lock_fd: int | None = None):
        self.path = path
        self._lock_fd = lock_fd
        self.subjects = subjects  # original -> subject id
        self.offsets = offsets  # subject id -> days

    @classmethod
    def load(cls, keys_dir: Path, project_id: str) -> PseudonymKey:
        if not PROJECT_ID_RE.fullmatch(project_id) or ".." in project_id:
            raise ValueError(f"invalid project_id: {project_id!r}")
        keys_dir = Path(keys_dir)
        keys_dir.mkdir(parents=True, exist_ok=True)
        path = keys_dir / f"{project_id}.aimport-key.json"
        lock_path = keys_dir / f"{project_id}.aimport-key.lock"
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            os.chmod(lock_path, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise KeyLockedError(
                    f"another import into project {project_id!r} is running (key is locked: {lock_path})"
                ) from None
            if path.exists():
                os.chmod(path, 0o600)
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    version = data.get("version")
                    if version != KEY_VERSION:
                        raise ValueError(f"unsupported key file version {version!r}")
                    subjects = {str(k): str(v) for k, v in data["subjects"].items()}
                    offsets = {str(k): int(v) for k, v in data["offsets"].items()}
                except ValueError as e:
                    raise ValueError(f"invalid key file {path}: {e}") from e
                except (KeyError, TypeError, AttributeError) as e:
                    raise ValueError(f"invalid key file {path}: missing or malformed field ({e!r})") from e
                return cls(path, subjects, offsets, fd)
            key = cls(path, {}, {}, fd)
            key.save()
            return key
        except BaseException:
            os.close(fd)
            raise

    def close(self) -> None:
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(self._lock_fd)
                self._lock_fd = None

    def __enter__(self) -> PseudonymKey:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def subject_id(self, original: str, existing: set[str], proposed: str | None = None) -> str:
        if original in self.subjects:
            return self.subjects[original]
        taken = set(existing) | set(self.subjects.values())
        if proposed is not None and SUBJECT_RE.fullmatch(proposed) and proposed not in taken:
            sid = proposed
        else:
            n = 1
            while f"{n:02d}" in taken:
                n += 1
            sid = f"{n:02d}"
        self.subjects[original] = sid
        return sid

    def date_offset_days(self, subject_id: str) -> int:
        if subject_id not in self.offsets:
            self.offsets[subject_id] = OFFSET_MIN + secrets.randbelow(OFFSET_MAX - OFFSET_MIN + 1)
        return self.offsets[subject_id]

    def save(self) -> None:
        if self._lock_fd is None:
            raise RuntimeError("key is closed; cannot save without holding the lock")
        payload = json.dumps(
            {"version": KEY_VERSION, "subjects": self.subjects, "offsets": self.offsets},
            indent=2, ensure_ascii=False,
        )
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".aimport-key-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:  # mkstemp creates 0600
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise
