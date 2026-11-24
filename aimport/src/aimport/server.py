"""The loopback API: the engine's only interface (``bl aimport`` and the brainlife-lite /aimport page).

State lives in ``work_dir`` (``scan.json``, ``plan.json``, ``status.json``, ``output-state.json``), so a
restarted server resumes: the plan and the ezBIDS output are reloaded from disk, the pseudonym key is
acquired again only when an operation needs it. Nothing identifying is ever written to those files or
sent in a response: messages, errors and validator issues are redacted with the run's terms.

Security: every route needs ``Authorization: Bearer <token>`` (constant-time compare). CORS is
enabled for ``allowed_origins`` only, and preflights are answered with
``Access-Control-Allow-Private-Network: true`` (Starlette's allow_private_network) so an https page may call the loopback server. Inside
the container ``serve`` binds 0.0.0.0; ``bl aimport`` must publish the port on 127.0.0.1 only
(``-p 127.0.0.1:<port>:<port>``), or the token is the only protection.

The browser viewer never sees the token: ``POST /viewer/session`` (bearer) returns a one-time code (single
use, 60 s) and ``GET /viewer/open?code=`` trades it for an HttpOnly, SameSite=Strict session cookie. The
cookie is accepted only on ``/viewer/*`` and ``/qa/*`` (not ``/viewer/session``); every other route stays
bearer-only.
"""
from __future__ import annotations

import asyncio
import copy
import gzip
import hmac
import json
import logging
import os
import secrets
import shutil
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from .agent import client_from_env
from .ancillary import (
    Generated,
    find_ancillary,
    id_maps,
    path_terms,
    plan_ancillary,
    write_ancillary,
)
from .deface import deface
from .ezbids_runner import CoreResult, parse_core, run_ezbids, stage_input
from .plan import NEVER_KEEP, OLD_PLAN, Plan
from .planner import DATASET_NAME_MAX, README_MAX, apply_plan_edits, build_plan, run_terms
from .pseudonyms import KeyLockedError, PseudonymKey
from .schema import load_schema
from .scrub import redact
from .validate import validate_bids
from .viewer import VIEWER_CSP, entry_state, index_page, neuroglancer_client_dir, state_url
from .writer import _Writer, write_bids

log = logging.getLogger("aimport")

BUSY = ("scanning", "executing")
TERMINAL = ("idle", "planned", "validated", "invalid", "failed")
DONE = ("validated", "invalid")  # executed: the output matches the plan (invalid: with validation errors)
MAX_ISSUES = 200  # validator issues listed in the status (the counts are always complete)
MAX_EVENTS = 500
OUTPUT_STATE = "output-state.json"
# subject_idx -> the subject ID the key records for that subject's original (pseudonyms only: the originals
# stay in the key), so an edited subject ID can be recorded in the key for the right person on execute
SUBJECT_IDS = "subject-ids.json"
VIEWER_PREFIXES = ("/viewer/", "/qa/")  # the browser pages: they also accept the session cookie
VIEWER_COOKIE = "aimport_viewer_"  # + a random suffix per server run: cookies ignore the port, so two engines on
# the same host would otherwise replace each other's session
VIEWER_CODE_TTL_S = 60
# set explicitly: the Python mimetypes table varies by version and platform, and responses are nosniff
MEDIA_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css",
               ".wasm": "application/wasm", ".map": "application/json", ".json": "application/json",
               ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2"}


def _now() -> float:
    return time.monotonic()


def _overlap(a: Path, b: Path) -> bool:
    return a == b or a in b.parents or b in a.parents


def _write_json(path: Path, data: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _nonempty(path: Path) -> bool:
    return path.exists() and (not path.is_dir() or path.is_symlink() or any(path.iterdir()))


def _file_inside(root: Path, rel: str) -> Path | None:
    """root/rel when rel is a relative path without '..' that reaches a regular file inside root through no
    symlink (checked at every component), else None."""
    pure = PurePosixPath(rel)
    if not rel or pure.is_absolute() or any(part in ("..", ".") for part in rel.split("/")):
        return None
    path = root
    for part in pure.parts:
        path = path / part
        if path.is_symlink():
            return None
    if root.resolve() not in path.resolve().parents or not path.is_file():
        return None
    return path


def _clear(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _redact_obj(value: Any, terms: set[str]) -> Any:
    if isinstance(value, str):
        return redact(value, terms)
    if isinstance(value, dict):
        return {k: _redact_obj(v, terms) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_obj(v, terms) for v in value]
    return value


SHIFTED_AT_WRITE = "(shifted at write)"


def _mask_columns(table: str, columns: set[str]) -> str:
    lines = table.split("\n")
    header = lines[0].split("\t")
    cols = [i for i, h in enumerate(header) if h in columns]
    for n in range(1, len(lines)):
        if lines[n]:
            cells = lines[n].split("\t")
            for i in cols:
                if i < len(cells):
                    cells[i] = SHIFTED_AT_WRITE
            lines[n] = "\t".join(cells)
    return "\n".join(lines)


class ScanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    existing_subjects: list[str] = []
    existing_sessions: dict[str, list[str]] = {}  # subject id -> session labels already in the project
    target: Literal["bids", "datatypes"] = "bids"


class PatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edits: list[dict] | None = None
    ancillary_edits: list[dict] | None = None
    dataset_description: dict | None = None
    dataset_name: str | None = None
    readme: str | None = None


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deface_method: Literal["pydeface", "quickshear"] | None = None


class Server:
    def __init__(self, input_dir: Path, work_dir: Path, keys_dir: Path) -> None:
        self.input_dir, self.work, self.keys_dir = input_dir, work_dir, keys_dir
        self.staged = work_dir / "ezbids"
        self.out = work_dir / "output" / "bids"
        self.failed_out = work_dir / "output" / "bids.failed"  # what a failed execute left: never uploaded
        self.ezbids_log = work_dir / "ezbids.log"  # ezBIDS's own output (identifying; local only)
        self.pre = work_dir / "pre-deface"
        self.lock = threading.RLock()  # stage, events, key
        self.plan_lock = threading.RLock()  # load-modify-save of plan.json
        self.events: list[dict] = []  # the last MAX_EVENTS
        self.event_count = 0  # events ever emitted: a reader's position, safe across truncation
        self.key: PseudonymKey | None = None
        self.core: CoreResult | None = None
        self.terms: set[str] | None = None
        self.schema = None
        self.thread: threading.Thread | None = None
        self.status: dict = {"stage": "idle", "message": ""}
        self.viewer_codes: dict[str, float] = {}  # one-time code -> expiry (_now())
        self.viewer_sessions: set[str] = set()  # session cookies, for this server run
        self.viewer_cookie = VIEWER_COOKIE + secrets.token_hex(4)  # the session cookie's name, for this run
        saved = _read_json(work_dir / "status.json")
        if saved and isinstance(saved.get("stage"), str):
            self.status = saved
            if saved["stage"] in BUSY:
                self.status = {"stage": "failed", "message": "the server restarted during the run: start it again"}
        elif (work_dir / "plan.json").exists():
            self.status = {"stage": "planned", "message": "plan loaded"}
        self.events.append({"stage": self.status["stage"], "message": self.status.get("message", "")})
        self.event_count = 1

    # --- viewer sessions ---

    def new_viewer_code(self) -> str:
        with self.lock:
            now = _now()
            self.viewer_codes = {c: t for c, t in self.viewer_codes.items() if t > now}
            code = secrets.token_hex(16)
            self.viewer_codes[code] = now + VIEWER_CODE_TTL_S
            return code

    def redeem_viewer_code(self, code: str) -> str | None:
        """A new session cookie for a live code (used up either way), None for an unknown or expired one."""
        with self.lock:
            expiry = self.viewer_codes.pop(code, None)
            if expiry is None or expiry <= _now():
                return None
            session = secrets.token_hex(32)
            self.viewer_sessions.add(session)
            return session

    def viewer_session_ok(self, cookie: str | None) -> bool:
        if not cookie:
            return False
        with self.lock:
            sessions = list(self.viewer_sessions)
        return any(hmac.compare_digest(cookie.encode(), s.encode()) for s in sessions)

    # --- stage and events ---

    def set_status(self, stage: str, message: str, **extra: Any) -> None:
        with self.lock:
            self.status = {"stage": stage, "message": message, **extra}
            self.events.append({"stage": stage, "message": message})
            self.event_count += 1
            del self.events[:-MAX_EVENTS]
            _write_json(self.work / "status.json", self.status)

    def busy(self) -> bool:
        return self.status["stage"] in BUSY

    # --- redaction ---

    def get_core(self) -> CoreResult | None:
        with self.lock:
            if self.core is None:
                path = self.staged / "ezBIDS_core.json"
                if not path.exists():
                    return None
                self.core = parse_core(path)
            return self.core

    def get_terms(self) -> set[str] | None:
        with self.lock:
            if self.terms is None:
                core = self.get_core()
                if core is None:
                    return None
                self.terms = run_terms(core, self.input_dir)
            return self.terms

    def clean(self, text: str) -> str:
        """text with the run's terms redacted; text that cannot be checked is withheld."""
        try:
            terms = self.get_terms()
        except Exception:
            terms = None
        if terms is None:
            return "(details withheld: the identifying terms of this run are not known yet)"
        return redact(text, terms)

    def clean_obj(self, value: Any) -> Any:
        """value (strings anywhere inside) with the run's terms redacted; reviewer text is stored this way."""
        try:
            terms = self.get_terms()
        except Exception:
            terms = None
        if terms is None:
            raise HTTPException(409, "the ezBIDS output is missing: scan again")
        return _redact_obj(value, terms)

    def failure(self, exc: BaseException) -> str:
        return f"{type(exc).__name__}: {self.clean(str(exc))}"

    # --- key ---

    def scan_info(self) -> dict | None:
        return _read_json(self.work / "scan.json")

    def acquire_key(self) -> PseudonymKey:
        """The held key, or the project's key loaded now (KeyLockedError when another import holds it)."""
        with self.lock:
            if self.key is None:
                info = self.scan_info()
                if info is None:
                    raise HTTPException(409, "no scan yet: POST /scan first")
                self.key = PseudonymKey.load(self.keys_dir, info["project_id"])
            return self.key

    @contextmanager
    def borrowed_key(self):
        """The key for one request: a key this server already holds stays held; one loaded here is released."""
        with self.lock:
            held = self.key is not None
            key = self.acquire_key()
            try:
                yield key
            finally:
                if not held:
                    self.release_key()

    # --- subject IDs ---

    def subject_ids(self) -> dict[int, str]:
        data = _read_json(self.work / SUBJECT_IDS) or {}
        return {int(k): str(v) for k, v in data.items()}

    def save_subject_ids(self, ids: dict[int, str]) -> None:
        _write_json(self.work / SUBJECT_IDS, {str(k): v for k, v in sorted(ids.items())})

    def renamed_subjects(self, plan: Plan) -> dict[int, str]:
        """subject_idx -> edited subject ID, for the subjects whose ID differs from the key's."""
        recorded = self.subject_ids()
        changed = {e.subject_idx: e.subject for e in plan.entries if e.subject != recorded.get(e.subject_idx)}
        if any(i not in recorded for i in changed):
            raise HTTPException(409, "the subject IDs of this scan are not known: scan again")
        return changed

    def check_subject_ids(self, plan: Plan) -> None:
        """422 when an edited subject ID belongs to someone else: another original in the key, or a subject
        already in the brainlife project (existing_subjects). A subject's own recorded ID is always fine."""
        changed = self.renamed_subjects(plan)
        if not changed:
            return
        existing = set((self.scan_info() or {}).get("existing_subjects", []))
        with self.borrowed_key() as key:
            held = set(key.subjects.values())
        for sid in sorted(set(changed.values())):
            if sid in held or sid in existing:
                raise HTTPException(422, f"subject ID {sid!r} is already used by another subject of this project")

    def record_subject_ids(self, plan: Plan, key: PseudonymKey) -> dict[int, str]:
        """Point the key's originals at the edited subject IDs (offset and session records follow); in memory:
        the caller saves the key once the output is written. Returns the new subject_idx -> ID map."""
        recorded = self.subject_ids()
        changed = self.renamed_subjects(plan)
        for idx, new in changed.items():
            old = recorded[idx]
            original = next((o for o, sid in key.subjects.items() if sid == old), None)
            if original is None or new in key.subjects.values():
                raise RuntimeError("the pseudonym key changed since the scan: scan again")
            key.subjects[original] = new
            if old in key.offsets:
                key.offsets.setdefault(new, key.offsets[old])
            if old in key.sessions:
                key.sessions[new] = key.sessions.pop(old)
        return recorded | changed

    def release_key(self) -> None:
        with self.lock:
            key, self.key = self.key, None
        if key is not None:
            key.close()

    def finish(self, key: PseudonymKey, stage: str, message: str, **extra: Any) -> None:
        """End a run: this worker's key is released BEFORE the terminal status is visible, so a request
        that follows the status cannot load or reuse a key this worker is about to close."""
        with self.lock:
            if self.key is key:
                self.key = None
            key.close()
            self.set_status(stage, message, **extra)

    def close(self) -> None:
        self.release_key()

    # --- plan ---

    def load_plan(self) -> Plan:
        path = self.work / "plan.json"
        if not path.exists():
            raise HTTPException(404, "no plan: POST /scan first")
        try:
            return Plan.load(path)
        except ValueError as e:
            if str(e) == OLD_PLAN:
                raise HTTPException(409, OLD_PLAN) from None
            raise

    def save_plan(self, plan: Plan) -> None:
        tmp = self.work / "plan.json.tmp"
        plan.save(tmp)
        os.replace(tmp, self.work / "plan.json")

    def get_schema(self):
        if self.schema is None:
            self.schema = load_schema()
        return self.schema

    # --- scan ---

    def start(self, target) -> None:
        self.thread = threading.Thread(target=target, daemon=True, name="aimport-worker")
        self.thread.start()

    def reset_output(self) -> None:
        """A new scan is a new plan: output this server produced earlier is discarded."""
        if _read_json(self.work / OUTPUT_STATE) is not None:
            _clear(self.out)
            _clear(self.pre)
            _clear(self.failed_out)
            (self.work / OUTPUT_STATE).unlink(missing_ok=True)

    def scan(self, info: dict, key: PseudonymKey) -> None:
        try:
            self.reset_output()
            _clear(self.staged)
            self.set_status("scanning", "staging the input")
            staged = stage_input(self.input_dir, self.work)
            self.set_status("scanning", "running ezBIDS")
            # ezBIDS's output stays on this computer, in the work folder: it holds original paths and names,
            # so a failure names the file instead of quoting it
            with open(self.ezbids_log, "w", encoding="utf-8") as log_file:
                run_ezbids(staged, log=lambda line: print(line, file=log_file, flush=True))
            core = parse_core(staged / "ezBIDS_core.json")
            terms = run_terms(core, self.input_dir)
            with self.lock:
                self.core, self.terms = core, terms
            self.set_status("scanning", "building the plan")
            plan = build_plan(core, self.input_dir, key, set(info["existing_subjects"]), client_from_env(),
                              self.get_schema(), info["target"], staged_dir=staged,
                              existing_sessions=info.get("existing_sessions") or {})
            plan.scan_id = info["scan_id"]
            self.save_subject_ids({e.subject_idx: e.subject for e in plan.entries})
            key.save()
            with self.plan_lock:
                self.save_plan(plan)
            self.set_status("planned", "plan ready for review")
        except Exception as e:
            note = f"; ezBIDS output: {self.ezbids_log}" if self.ezbids_log.exists() else ""
            self.fail(e, key, note)

    def fail(self, exc: BaseException, key: PseudonymKey, note: str = "") -> None:
        """note: the engine's own text (paths in the work folder, like output_dir), appended as is."""
        msg = self.failure(exc) + note
        log.warning("failed: %s", msg)
        self.finish(key, "failed", msg)

    # --- execute ---

    def execute(self, plan: Plan, scan_id: str, key: PseudonymKey) -> None:
        try:
            terms = self.get_terms()
            core = self.get_core()
            if terms is None or core is None:
                raise RuntimeError("the ezBIDS output is missing: scan again")
            for p in (self.out, self.pre, self.failed_out):
                if _nonempty(p):
                    _clear(p)
            (self.work / OUTPUT_STATE).unlink(missing_ok=True)
            _write_json(self.work / OUTPUT_STATE, {"scan_id": scan_id, "complete": False})
            self.set_status("executing", "writing the BIDS dataset")
            manifest: dict[str, list[str]] = {}
            refused: list[str] = []
            ids = self.record_subject_ids(plan, key)  # before writing, so edited subjects keep their offsets
            write_bids(plan, core, self.input_dir, terms, key, self.get_schema(), self.out,
                       staged_dir=self.staged, manifest=manifest, refused=refused)
            key.save()  # the edited subject IDs, and the date offsets the writer creates in memory
            self.save_subject_ids(ids)
            self.set_status("executing", "defacing the anatomical images")
            moved = deface(self.out, plan, plan.deface_method, self.pre, manifest)
            pre_root = self.pre.resolve()
            defaced: dict[str, list[str]] = {}
            for eid, paths in moved.items():
                defaced[eid] = [Path(p).resolve().relative_to(pre_root).as_posix() for p in paths]
            _write_json(self.work / OUTPUT_STATE,
                        {"scan_id": scan_id, "complete": True, "manifest": manifest, "defaced": defaced})
            self.set_status("executing", "validating the BIDS dataset")
            result = validate_bids(self.out)
            pterms = path_terms(terms)
            validation = _redact_obj({
                "ok": result.ok,
                "error_count": len(result.errors),
                "warning_count": len(result.warnings),
                "errors": result.errors[:MAX_ISSUES],
                "warnings": result.warnings[:MAX_ISSUES],
                "validator_version": result.validator_version,
                "bids_version": result.bids_version,
            }, pterms)
            outcome = ("no validation errors" if result.ok else f"{len(result.errors)} validation error(s)")
            self.finish(key, "validated" if result.ok else "invalid", outcome, output_dir=str(self.out),
                        validation=validation, refused=_redact_obj(refused, terms))
        except Exception as e:
            self.fail(e, key, self.set_aside(scan_id))

    def set_aside(self, scan_id: str) -> str:
        """After a failed execute: <work>/output/bids (possibly complete but not defaced or validated) is
        renamed to bids.failed, replacing an earlier one, so nothing uploadable is left; pre-deface is kept."""
        try:
            if not self.out.exists():
                return ""
            _clear(self.failed_out)
            os.replace(self.out, self.failed_out)
            _write_json(self.work / OUTPUT_STATE, {"scan_id": scan_id, "complete": False,
                                                    "failed_output": str(self.failed_out)})
            return f"; the incomplete output was moved to {self.failed_out} (not for upload)"
        except OSError as e:
            log.warning("could not move the failed output aside: %s", type(e).__name__)
            return "; the incomplete output could not be moved aside: do not upload it"

    # --- ancillary preview ---

    def ancillary_content(self, plan: Plan, entry_id: str) -> dict:
        entry = next((a for a in plan.ancillary if a.id == entry_id), None)
        if entry is None:
            raise HTTPException(404, "unknown ancillary id")
        out = {"path": entry.path, "kind": entry.kind, "content": None, "flags": entry.flags,
               "locked": entry.locked, "locked_columns": entry.locked_columns}
        if entry.locked or entry.kind == "folder" or entry.source.split("/")[0] in NEVER_KEEP \
                or entry.path.split("/")[0] in NEVER_KEEP:
            return out  # never listed or read: the flags describe a folder, a locked file has no content
        core, terms = self.get_core(), self.get_terms()
        if core is None or terms is None:
            raise HTTPException(409, "the ezBIDS output is missing: scan again")
        if entry.action == "drop":
            return out  # nothing will be written
        schema = self.get_schema()
        with self.lock:  # no run starts while the offsets are copied
            mask = self.busy()
            if mask:
                # a run owns the key: nothing can be shifted with the real offsets, so every shifted value
                # is replaced below; this placeholder only lets the writer run and its output is not shown
                scratch_key = PseudonymKey(self.work / "placeholder-key-never-saved", {}, {})
            else:
                # a copy (with no lock, so it can never be saved): a preview never adds offsets to the real key;
                # a key loaded only for this preview is released again (KeyLockedError: the caller answers 409)
                with self.borrowed_key() as key:
                    scratch_key = PseudonymKey(self.work / "placeholder-key-never-saved", dict(key.subjects),
                                               dict(key.offsets), sessions=copy.deepcopy(key.sessions))
                try:  # edited subject IDs take their offsets as they will on execute
                    self.record_subject_ids(plan, scratch_key)
                except (HTTPException, RuntimeError):
                    pass
            self.preview_entry(plan, entry, out, core, terms, schema, scratch_key, mask)
        return out

    def preview_entry(self, plan: Plan, entry, out: dict, core: CoreResult, terms: set[str], schema,
                      scratch_key: PseudonymKey, mask: bool) -> None:
        root = self.work / "preview"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            tmp_path = Path(tmp)
            # the written image names, so companions (events, physio) find their image
            writer = _Writer(plan, core, self.input_dir, terms, scratch_key, schema, tmp_path / "unused",
                             self.staged)
            try:
                items = writer.items()
                written = {os.path.normpath(str(it.nifti)): it.rel for it in items}
                ids = id_maps(core, [it.entry for it in items], written=written)
            except Exception:
                ids = id_maps(core, plan.entries)
            all_ids = id_maps(core, plan.entries)
            defaults = plan_ancillary(find_ancillary(self.input_dir, schema), self.input_dir, terms, all_ids, schema)
            default = next((d for d in defaults if d.source == entry.source), None)
            if default is None or default.locked:
                return
            # the reviewer's action, columns and content, through the same lock checks as a PATCH
            edit: dict[str, Any] = {"id": default.id, "action": entry.action}
            if entry.action == "edit":
                edit["content"] = entry.content
            if default.columns:
                edit["columns"] = {c: a for c, a in entry.columns.items() if c in default.columns}
            scratch = Plan(target=plan.target, entries=plan.entries, ancillary=[default])
            try:
                scratch.apply_ancillary_edits([edit])
            except (KeyError, ValueError):
                return
            scratch.approved = True
            produced = write_ancillary(scratch, self.input_dir, tmp_path / "out", terms, ids, scratch_key,
                                       schema=schema, generated=Generated())
            files = [p for p in produced if p.is_file() and p.name != "dataset_description.json"]
            if len(files) != 1:
                return
            p = files[0]
            if p.name.endswith(".json"):
                out["content"] = json.loads(p.read_text(encoding="utf-8"))
            elif p.name.endswith(".gz"):
                out["content"] = gzip.decompress(p.read_bytes()).decode("utf-8", errors="replace")
            else:
                out["content"] = p.read_text(encoding="utf-8", errors="replace")
            if mask and isinstance(out["content"], str):
                out["content"] = _mask_columns(out["content"],
                                               {c for c, act in default.columns.items() if act == "shift_date"})


def create_app(input_dir: Path, work_dir: Path, keys_dir: Path, token: str, allowed_origins: list[str],
               allowed_hosts: list[str] | None = None) -> FastAPI:
    """allowed_hosts: the Host header values served (host:port, e.g. "127.0.0.1:8765"), anything else gets 421
    (DNS rebinding). None allows only the loopback names, with any port."""
    if not token:
        raise ValueError("a token is required")
    hosts = {h.lower() for h in allowed_hosts} if allowed_hosts is not None else None
    input_dir, work_dir, keys_dir = Path(input_dir).resolve(), Path(work_dir).resolve(), Path(keys_dir).resolve()
    if _overlap(keys_dir, work_dir):
        raise ValueError("the keys folder and the work folder (which holds the output) must not contain each other")
    if _overlap(input_dir, work_dir) or _overlap(input_dir, keys_dir):
        raise ValueError("the input folder must not overlap the work or keys folder")
    work_dir.mkdir(parents=True, exist_ok=True)
    srv = Server(input_dir, work_dir, keys_dir)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        srv.close()

    def authorize(request: Request, authorization: str | None = Header(default=None)) -> None:
        path = request.url.path
        if path == "/viewer/open":
            return  # the one-time code is the credential, checked by the route
        scheme, _, given = (authorization or "").partition(" ")
        if scheme.lower() == "bearer" and hmac.compare_digest(given.encode(), token.encode()):
            return
        if (path.startswith(VIEWER_PREFIXES) and path != "/viewer/session"
                and srv.viewer_session_ok(request.cookies.get(srv.viewer_cookie))):
            return
        raise HTTPException(401, "missing or invalid token", headers={"WWW-Authenticate": "Bearer"})

    app = FastAPI(title="aimport", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan,
                  dependencies=[Depends(authorize)])
    app.state.server = srv
    if allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(allowed_origins), allow_methods=["GET", "POST", "PATCH"],
                           allow_headers=["Authorization", "Content-Type"], allow_private_network=True,
                           max_age=600)

    @app.middleware("http")
    async def viewer_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(VIEWER_PREFIXES):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            if response.headers.get("content-type", "").startswith("text/html"):
                response.headers["Content-Security-Policy"] = VIEWER_CSP
        return response

    @app.middleware("http")
    async def no_private_network_for_others(request: Request, call_next):
        response = await call_next(request)  # Starlette adds the header even to a refused preflight
        if request.headers.get("origin") not in allowed_origins:
            del response.headers["Access-Control-Allow-Private-Network"]
        return response

    @app.middleware("http")  # added last: outermost, before CORS and the token check
    async def host_check(request: Request, call_next):
        host = request.headers.get("host", "").lower()
        if hosts is not None:
            ok = host in hosts
        else:
            ok = host.rsplit(":", 1)[0] in {"127.0.0.1", "localhost", "[::1]"} or host in {"[::1]"}
        if not ok:
            return JSONResponse({"detail": "host not allowed"}, status_code=421)
        return await call_next(request)

    def conflict(message: str) -> HTTPException:
        return HTTPException(409, message)

    def key_locked(e: KeyLockedError) -> HTTPException:
        return conflict(str(e))

    @app.post("/scan", status_code=202)
    def post_scan(body: ScanBody) -> dict:
        with srv.lock:
            if srv.busy():
                raise conflict(f"busy: {srv.status['stage']}")
            srv.release_key()  # a re-scan replaces the plan; the old key lock would block the new load
            try:
                key = PseudonymKey.load(keys_dir, body.project_id)
            except KeyLockedError as e:
                raise key_locked(e) from None
            except ValueError as e:
                raise HTTPException(422, str(e)) from None
            srv.key = key
            info = {"project_id": body.project_id, "existing_subjects": body.existing_subjects,
                    "existing_sessions": body.existing_sessions, "target": body.target, "scan_id": uuid.uuid4().hex}
            with srv.plan_lock:  # a new scan replaces the plan: the old one must not survive a failed scan
                (work_dir / "plan.json").unlink(missing_ok=True)
            _write_json(work_dir / "scan.json", info)
            with srv.lock:
                srv.core = srv.terms = None
            srv.set_status("scanning", "starting")
            srv.start(lambda: srv.scan(info, key))
        return {"stage": "scanning"}

    @app.get("/status")
    def get_status() -> dict:
        with srv.lock:
            status = dict(srv.status)
        try:
            status["warnings"] = srv.load_plan().warnings
        except (HTTPException, ValueError):
            pass
        if status["stage"] in DONE:
            state = _read_json(work_dir / OUTPUT_STATE)
            if state and state.get("complete"):
                status["manifest"] = state.get("manifest") or {}
        return status

    @app.get("/events")
    async def get_events() -> StreamingResponse:
        with srv.lock:
            current, index = dict(srv.status), srv.event_count

        def line(stage: str, message: str) -> str:
            return "data: " + json.dumps({"stage": stage, "message": message}) + "\n\n"

        async def stream():
            yield line(current["stage"], current.get("message", ""))
            nonlocal index
            if current["stage"] in TERMINAL:
                return
            idle = 0
            while True:
                with srv.lock:
                    missed = min(srv.event_count - index, len(srv.events))  # the oldest may be gone
                    new = srv.events[len(srv.events) - missed:] if missed > 0 else []
                    index = srv.event_count
                for ev in new:
                    yield line(ev["stage"], ev["message"])
                    if ev["stage"] in TERMINAL:
                        return
                idle = 0 if new else idle + 1
                if idle >= 150:  # keepalive every ~15 s
                    idle = 0
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.1)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/plan")
    def get_plan() -> dict:
        with srv.plan_lock:
            return asdict(srv.load_plan())

    @app.patch("/plan")
    def patch_plan(body: PatchBody) -> dict:
        given = body.model_fields_set
        if not given:
            raise HTTPException(422, "nothing to change")
        if body.dataset_name is not None and not (body.dataset_name.strip() and len(body.dataset_name) <= DATASET_NAME_MAX):
            raise HTTPException(422, f"dataset_name must be 1 to {DATASET_NAME_MAX} characters")
        if body.readme is not None and len(body.readme) > README_MAX:
            raise HTTPException(422, f"readme must be at most {README_MAX} characters")
        with srv.lock, srv.plan_lock:
            if srv.busy():
                raise conflict(f"busy: {srv.status['stage']}")
            plan = srv.load_plan()
            # reviewer-typed text is stored redacted with the run's terms, so plan.json and every response hold none
            ancillary_edits = body.ancillary_edits
            if ancillary_edits:
                ancillary_edits = [{**e, "content": srv.clean_obj(e["content"])} if e.get("content") is not None else e
                                   for e in ancillary_edits]
            description = srv.clean_obj(body.dataset_description) if body.dataset_description is not None else None
            dataset_name = srv.clean_obj(body.dataset_name) if body.dataset_name is not None else None
            readme = srv.clean_obj(body.readme) if body.readme is not None else None
            try:
                if body.edits:
                    apply_plan_edits(plan, body.edits, srv.get_schema())
                    if any(isinstance(e, dict) and "subject" in e for e in body.edits):
                        srv.check_subject_ids(plan)
                if ancillary_edits:
                    plan.apply_ancillary_edits(ancillary_edits)
                if description is not None:
                    plan.set_dataset_description(description)
            except KeyError as e:
                raise HTTPException(422, srv.clean(f"unknown id {e.args[0]!r}")) from None
            except KeyLockedError as e:
                raise key_locked(e) from None
            except (ValueError, TypeError, AttributeError) as e:
                raise HTTPException(422, srv.clean(str(e))) from None
            if dataset_name is not None:
                plan.dataset_name = dataset_name.strip()
            if readme is not None:
                plan.readme = readme
            if given & {"dataset_name", "readme", "dataset_description"}:
                plan.metadata_source = "person"
            plan.approved = False
            srv.save_plan(plan)
            if srv.status["stage"] in DONE:  # the output no longer matches the plan
                srv.set_status("planned", "plan edited: execute again")
            return asdict(plan)

    @app.post("/approve")
    def post_approve(body: ApproveBody | None = None) -> dict:
        with srv.lock, srv.plan_lock:
            if srv.busy():
                raise conflict(f"busy: {srv.status['stage']}")
            plan = srv.load_plan()
            if body is not None and body.deface_method is not None:
                plan.deface_method = body.deface_method
            plan.approved = True
            srv.save_plan(plan)
            return asdict(plan)

    @app.post("/execute", status_code=202)
    def post_execute() -> dict:
        with srv.lock, srv.plan_lock:
            if srv.busy():
                raise conflict(f"busy: {srv.status['stage']}")
            try:
                plan = srv.load_plan()
            except HTTPException as e:
                raise conflict(e.detail) from None
            if not plan.approved:
                raise conflict("the plan has not been approved")
            info = srv.scan_info()
            if info is None or srv.get_core() is None:
                raise conflict("no scan yet: POST /scan first")
            if plan.scan_id != info.get("scan_id"):
                raise conflict("the plan was not built by the last scan: scan again")
            state = _read_json(work_dir / OUTPUT_STATE)
            if (_nonempty(srv.out) or _nonempty(srv.pre)) and not (state and state.get("scan_id") == info["scan_id"]):
                raise conflict("the output folder is not empty and was not produced by this server for this plan")
            try:
                key = srv.acquire_key()
            except KeyLockedError as e:
                raise key_locked(e) from None
            srv.set_status("executing", "starting")
            srv.start(lambda: srv.execute(plan, info["scan_id"], key))
        return {"stage": "executing"}

    @app.get("/ancillary/{entry_id}")
    def get_ancillary(entry_id: str) -> dict:
        with srv.plan_lock:
            plan = srv.load_plan()
        try:
            return srv.ancillary_content(plan, entry_id)
        except KeyLockedError as e:
            raise key_locked(e) from None

    def output_state() -> dict:
        """The complete output state of the current scan, after execute (validated or invalid), else 404."""
        state = _read_json(work_dir / OUTPUT_STATE)
        info = _read_json(work_dir / "scan.json") or {}
        if (srv.status["stage"] not in DONE or not state or not state.get("complete")
                or state.get("scan_id") != info.get("scan_id")):
            raise HTTPException(404, "nothing to preview: execute the plan first")
        return state

    def output_file(entry_id: str, index: int, which: str, subpath: str = "") -> Path:
        """A written image of the output manifest (which=original: the pre-deface copy, for a defaced entry).
        subpath: empty, or the file's own name, for a manifest file; a path inside a manifest directory."""
        state = output_state()
        files = (state.get("manifest") or {}).get(entry_id)
        if not files or not 0 <= index < len(files):
            raise HTTPException(404, "no such image")
        rel, root = files[index], srv.out
        defaced = (state.get("defaced") or {}).get(entry_id)
        if which == "original" and defaced and index < len(defaced):
            root, rel = srv.pre, defaced[index]
        if subpath and not (subpath == PurePosixPath(rel).name and (root / rel).is_file()):
            rel = f"{rel}/{subpath}"  # inside a manifest directory: _file_inside refuses anything else
        path = _file_inside(root, rel)
        if path is None:
            raise HTTPException(404, "no such image")
        return path

    @app.get("/preview/{entry_id}")
    def get_preview(entry_id: str, which: Literal["original", "defaced"] = "defaced",
                    index: int = Query(default=0, ge=0)) -> FileResponse:
        return FileResponse(output_file(entry_id, index, which), media_type="application/octet-stream")

    @app.get("/qa/data/{entry_id}/{index}/{subpath:path}")
    def get_qa_data(entry_id: str, index: str, subpath: str,
                    which: Literal["original", "defaced"] = "defaced") -> FileResponse:
        if not (index.isascii() and index.isdigit()):
            raise HTTPException(404, "no such image")
        return FileResponse(output_file(entry_id, int(index), which, subpath), media_type="application/octet-stream")

    @app.post("/viewer/session")
    def post_viewer_session() -> dict:
        code = srv.new_viewer_code()
        return {"code": code, "url": f"/viewer/open?code={code}"}

    @app.get("/viewer/open")
    def get_viewer_open(code: str = "") -> RedirectResponse:
        session = srv.redeem_viewer_code(code)
        if session is None:
            raise HTTPException(401, "invalid or expired code: open the viewer again")
        response = RedirectResponse("/viewer/", status_code=303)
        response.set_cookie(srv.viewer_cookie, session, httponly=True, samesite="strict", path="/")
        return response

    def written() -> tuple[dict, list]:
        """The output state and the plan entries it holds images for, in plan order."""
        state = output_state()
        manifest = state.get("manifest") or {}
        with srv.plan_lock:
            plan = srv.load_plan()
        return state, [e for e in plan.entries if manifest.get(e.id)]

    @app.get("/viewer/")
    def get_viewer_index() -> HTMLResponse:
        state, entries = written()
        rows = [{"id": e.id, "paths": state["manifest"][e.id],
                 "nifti": state["manifest"][e.id][0].endswith((".nii", ".nii.gz")),
                 "defaced": bool((state.get("defaced") or {}).get(e.id))} for e in entries]
        return HTMLResponse(index_page(rows))

    @app.get("/viewer/entry/{entry_id}")
    def get_viewer_entry(entry_id: str, request: Request, compare: bool = False) -> RedirectResponse:
        state, entries = written()
        entry = next((e for e in entries if e.id == entry_id), None)
        files = state["manifest"][entry_id] if entry else None
        if not files or not files[0].endswith((".nii", ".nii.gz")):
            raise HTTPException(404, "no such image")
        originals = (state.get("defaced") or {}).get(entry_id)
        base = str(request.base_url).rstrip("/")  # the Host check allows only this server's own names
        return RedirectResponse(state_url(entry_state(asdict(entry), files, originals, base, compare=compare)),
                                status_code=303)

    @app.get("/viewer/ng/{path:path}")
    def get_neuroglancer(path: str) -> FileResponse:
        try:
            base = neuroglancer_client_dir()
        except RuntimeError as e:
            raise HTTPException(404, str(e)) from None
        file = (base / (path or "index.html")).resolve()
        if base not in file.parents or not file.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(file, media_type=MEDIA_TYPES.get(file.suffix, "application/octet-stream"))

    return app
