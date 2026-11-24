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
cookie is accepted only on ``GET``/``HEAD`` of ``/viewer/*`` and ``/qa/*`` (not ``/viewer/session``) and on
one write route, ``POST /qa/channels/<entry id>`` (the trace viewer's bad-channel marks), there only with an
``X-Aimport-Viewer: 1`` header and an ``Origin`` equal to the engine's own (CSRF); every other route stays
bearer-only.
"""
from __future__ import annotations

import asyncio
import copy
import gzip
import hmac
import inspect
import json
import logging
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Sequence
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
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
from . import modality
from .ezbids_runner import CoreResult, EzbidsError, has_files, parse_core, run_ezbids, stage_input
from .modality import (
    CLAIM_FILE,
    EMPTY_CORE,
    Claim,
    claim_terms,
    claimed_roots,
    drop_overlaps,
    module_dir,
    normalize_root,
    redact_paths,
)
from .plan import EMPTY_ROOM_SUBJECT, NEVER_KEEP, OLD_PLAN, Plan
from .planner import DATASET_NAME_MAX, README_MAX, apply_plan_edits, build_plan, run_terms
from .micr import reference as micr_reference
from .micr.reference import CHUNK_MAP_NAME, write_chunk_map  # in <work>/output/, next to bids/
from .pseudonyms import KeyLockedError, PseudonymKey
from .schema import load_schema
from .scrub import REDACTED, redact
from .validate import validate_bids
from .ephys import bad_channels as ephys_bad
from .ephys import module as ephys_module
from .ephys import qa as ephys_qa
from .viewer import (STATIC_DIR, VIEWER_CSP, entry_state, index_page, neuroglancer_client_dir, ngff_parts, oct_group,
                     state_url, traces_page)
from .writer import _Writer, write_bids

log = logging.getLogger("aimport")

BUSY = ("scanning", "executing")
TERMINAL = ("idle", "planned", "validated", "invalid", "failed")
DONE = ("validated", "invalid")  # executed: the output matches the plan (invalid: with validation errors)
MAX_ISSUES = 200  # validator issues listed in the status (the counts are always complete)
MAX_EVENTS = 500
OUTPUT_STATE = "output-state.json"
NOTHING_TO_WRITE = "nothing to write: every entry is excluded or unsupported"
# preprocess.sh's error when the staged input has no MRI, PET or MEG file (only tables and text)
EZBIDS_NO_IMAGING = "Could not find any MRI, PET, or MEG imaging files"
# subject_idx -> the subject ID the key records for that subject's original (pseudonyms only: the originals
# stay in the key), so an edited subject ID can be recorded in the key for the right person on execute
SUBJECT_IDS = "subject-ids.json"
VIEWER_PREFIXES = ("/viewer/", "/qa/")  # the browser pages: they also accept the session cookie (GET, HEAD)
VIEWER_READS = ("GET", "HEAD")
CHANNELS_ROUTE = re.compile(r"/qa/channels/[^/]+")  # the one write route the cookie is accepted on (POST)
VIEWER_HEADER = "x-aimport-viewer"  # sent by the trace viewer's own script; a cross-site form cannot set it
CHANNELS_MAX_BODY = 256 * 1024
CSRF_REFUSED = "refused: the request did not come from the QA viewer page"
VIEWER_COOKIE = "aimport_viewer_"  # + a random suffix per server run: cookies ignore the port, so two engines on
# the same host would otherwise replace each other's session
VIEWER_CODE_TTL_S = 60
# /qa/data for a referenced OME-Zarr chunk at a URL: the most bytes one proxied response may carry
QA_MAX_RESPONSE_BYTES = 64 * 2**20
# decoded (and stored) bytes of the pyramid level read through the chunk map for a reference's display window
QA_WINDOW_MAX_BYTES = 32 * 2**20
# the level a reference's display window is computed from: largest x/y size closest to this, within the cap
QA_WINDOW_TARGET_SIDE = 1024
NO_SUCH_CHUNK = "no such chunk"
_CONTENT_RANGE = re.compile(r"bytes (?:[0-9]+-[0-9]+/(?:[0-9]+|\*)|\*/[0-9]+)")
# set explicitly: the Python mimetypes table varies by version and platform, and responses are nosniff
MEDIA_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css",
               ".wasm": "application/wasm", ".map": "application/json", ".json": "application/json",
               ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2"}


SAFE_ENTRY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")  # a plan entry id usable as a folder name


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


def project_subjects(plan: Plan) -> dict[int, str]:
    """subject_idx -> subject ID of the plan's project subjects: every entry's subject except the literal
    empty-room subject of MEG noise recordings, which is never recorded in the key or as a project subject."""
    return {e.subject_idx: e.subject for e in plan.entries
            if not (e.modality == "ephys" and e.subject == EMPTY_ROOM_SUBJECT)}


def _module_plan(m, work: Path, key: PseudonymKey, existing: set[str], client, schema, target: str,
                 subjects: dict[str, dict]):
    """m.plan, passing the MRI subjects by folder label to a module whose plan takes them."""
    try:
        takes = "subjects" in inspect.signature(m.plan).parameters
    except (TypeError, ValueError):
        takes = False
    if takes:
        return m.plan(work, key, existing, client, schema, target, subjects=subjects)
    return m.plan(work, key, existing, client, schema, target)

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
    # remote sources (https:// or s3://) for the modality modules; local-only: never written to scan.json
    remote: list[str] = []


REMOTE_SCHEMES = ("https", "s3")


def _check_remote(urls: list[str]) -> None:
    """422 unless every remote source is an https:// or s3:// URL (the URL itself is never echoed)."""
    for url in urls:
        try:
            parts = urlsplit(url.strip())
        except ValueError:
            parts = None
        if parts is None or parts.scheme.lower() not in REMOTE_SCHEMES or not parts.netloc:
            raise HTTPException(422, "remote sources must be https:// or s3:// URLs")


class PatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edits: list[dict] | None = None
    ancillary_edits: list[dict] | None = None
    dataset_description: dict | None = None
    dataset_name: str | None = None
    readme: str | None = None
    event_names: dict[str, str] | None = None


class ChannelMark(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    status: Literal["good", "bad"]
    description: str | None = None


class ChannelsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channels: list[ChannelMark]


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deface_method: Literal["pydeface", "quickshear"] | None = None


class Server:
    def __init__(self, input_dir: Path, work_dir: Path, keys_dir: Path) -> None:
        self.input_dir, self.work, self.keys_dir = input_dir, work_dir, keys_dir
        self.staged = work_dir / "ezbids"
        self.out = work_dir / "output" / "bids"
        self.failed_out = work_dir / "output" / "bids.failed"  # what a failed execute left: never uploaded
        # where the chunks of referenced OME-Zarr arrays are (input paths, URLs): local only, never uploaded
        self.chunk_map = work_dir / "output" / CHUNK_MAP_NAME
        self.ezbids_log = work_dir / "ezbids.log"  # ezBIDS's own output (identifying; local only)
        self.pre = work_dir / "pre-deface"
        self.lock = threading.RLock()  # stage, events, key
        self.plan_lock = threading.RLock()  # load-modify-save of plan.json
        self.events: list[dict] = []  # the last MAX_EVENTS
        self.event_count = 0  # events ever emitted: a reader's position, safe across truncation
        self.key: PseudonymKey | None = None
        self.core: CoreResult | None = None
        self.terms: set[str] | None = None
        self.scan_claims: list[Claim] = []  # the running scan's claims, before (or without) claim.json
        self.schema = None
        self.thread: threading.Thread | None = None
        self.status: dict = {"stage": "idle", "message": ""}
        self._stream_client: Any = None  # the QA chunk proxy's pooled httpx client: this app's own, closed with it
        self._stream_lock = threading.Lock()
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
                terms = run_terms(core, self.input_dir, exclude=self.claimed_roots())
                for m in modality.modules():
                    terms |= m.terms(module_dir(self.work, m))
                self.terms = terms
            return self.terms

    # --- modality modules ---

    def claims(self) -> dict[str, Claim]:
        """Each registered module's claim, as saved by the scan (local-only: never served)."""
        out = {}
        for m in modality.modules():
            path = module_dir(self.work, m) / CLAIM_FILE
            out[m.name] = Claim.load(path) if path.exists() else Claim()
        return out

    def claimed_roots(self) -> list[str]:
        return claimed_roots(self.claims().values())

    def hidden(self) -> tuple[set[str], set[str]]:
        """(path prefixes, terms) never shown: the input folder, the claimed roots and remote URLs (whole
        paths, tails included), and the claimed roots' path components."""
        try:
            claims = list(self.claims().values())
        except Exception:
            claims = []
        claims += self.scan_claims
        inp = Path(self.input_dir)
        prefixes = {str(inp), os.path.abspath(inp), str(inp.resolve())}
        for c in claims:
            prefixes.update(c.roots)
            prefixes.update(c.remote)
        return prefixes, claim_terms(claims)

    def clear_modules(self) -> None:
        for m in modality.modules():
            _clear(module_dir(self.work, m))

    def clean(self, text: str) -> str:
        """text with the run's terms redacted; text that cannot be checked is withheld."""
        try:
            terms = self.get_terms()
        except Exception:
            terms = None
        if terms is None:
            return "(details withheld: the identifying terms of this run are not known yet)"
        prefixes, hidden = self.hidden()
        return redact(redact_paths(text, prefixes, REDACTED), terms | hidden)

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
        changed = {i: sid for i, sid in project_subjects(plan).items() if sid != recorded.get(i)}
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
        with self._stream_lock:
            client, self._stream_client = self._stream_client, None
        if client is not None:
            client.close()

    def stream_client(self) -> Any:
        """This app's pooled httpx client for the QA chunk proxy (remote.new_stream_client), made on first use."""
        from .micr.remote import new_stream_client

        with self._stream_lock:
            if self._stream_client is None:
                self._stream_client = new_stream_client()
            return self._stream_client

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
        """A new scan is a new plan: output this server produced earlier, and the modules' scan state
        (``<work>/<name>/``), are discarded."""
        self.clear_modules()
        if _read_json(self.work / OUTPUT_STATE) is not None:
            _clear(self.out)
            _clear(self.pre)
            _clear(self.failed_out)
            (self.work / OUTPUT_STATE).unlink(missing_ok=True)
        self.chunk_map.unlink(missing_ok=True)

    def scan(self, info: dict, key: PseudonymKey, remote: Sequence[str] = ()) -> None:
        """remote: the scan's remote sources, passed to the modules' claims (kept out of scan.json)."""
        try:
            # staged first: while claim.json is gone, get_terms finds no ezBIDS output and never walks
            _clear(self.staged)
            self.reset_output()
            mods = modality.modules()
            claims: dict[str, Claim] = {}
            self.scan_claims = []
            for m in mods:
                claim = m.claim(self.input_dir, list(remote))
                self.scan_claims.append(claim)
                claim.roots = [normalize_root(r) for r in claim.roots]
                claims[m.name] = claim
            drop_overlaps(list(claims.values()))  # each input path is read by one module
            for m in mods:
                claims[m.name].save(module_dir(self.work, m) / CLAIM_FILE)
            roots = claimed_roots(claims.values())
            self.set_status("scanning", "staging the input")
            # claimed input is never staged (a module reads it in place); phase-1 calls stay unchanged
            staged = (stage_input(self.input_dir, self.work, exclude=roots) if roots
                      else stage_input(self.input_dir, self.work))
            claimed = any(c.roots or c.remote for c in claims.values())
            if claimed and not has_files(staged):
                _write_json(staged / "ezBIDS_core.json", EMPTY_CORE)  # nothing left for ezBIDS
            else:
                self.set_status("scanning", "running ezBIDS")
                # ezBIDS's output stays on this computer, in the work folder: it holds original paths and
                # names, so a failure names the file instead of quoting it
                try:
                    with open(self.ezbids_log, "w", encoding="utf-8") as log_file:
                        run_ezbids(staged, log=lambda line: print(line, file=log_file, flush=True))
                except EzbidsError:
                    # only tables and text are left beside the claimed images (a BIDS micr dataset): no MRI
                    if not (claimed and EZBIDS_NO_IMAGING in self.ezbids_log.read_text(errors="replace")):
                        raise
                    _write_json(staged / "ezBIDS_core.json", EMPTY_CORE)
            core = parse_core(staged / "ezBIDS_core.json")
            hidden = claim_terms(claims.values())
            for m in mods:
                self.set_status("scanning", f"reading the {m.name} input")
                m.scan(self.input_dir, claims[m.name], module_dir(self.work, m),
                       lambda msg: self.set_status("scanning", redact(str(msg), hidden)))
            module_terms: set[str] = set()
            for m in mods:
                module_terms |= m.terms(module_dir(self.work, m))
            terms = run_terms(core, self.input_dir, exclude=roots) | module_terms
            with self.lock:
                self.core, self.terms = core, terms
            self.set_status("scanning", "building the plan")
            client, schema = client_from_env(), self.get_schema()
            existing = set(info["existing_subjects"])
            # module planners run inside build_plan, after the MRI subjects took their IDs
            planners = [lambda subjects, m=m: _module_plan(m, module_dir(self.work, m), key, existing, client,
                                                           schema, info["target"], subjects)
                        for m in mods]
            plan = build_plan(core, self.input_dir, key, existing, client, schema, info["target"],
                              staged_dir=staged, existing_sessions=info.get("existing_sessions") or {},
                              exclude=roots, extra_terms=frozenset(module_terms), planners=planners)
            plan.scan_id = info["scan_id"]
            self.save_subject_ids(project_subjects(plan))
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
            self.chunk_map.unlink(missing_ok=True)
            _write_json(self.work / OUTPUT_STATE, {"scan_id": scan_id, "complete": False})
            self.set_status("executing", "writing the BIDS dataset")
            manifest: dict[str, list[str]] = {}
            refused: list[str] = []
            ids = self.record_subject_ids(plan, key)  # before writing, so edited subjects keep their offsets
            roots = self.claimed_roots()
            mods = modality.modules() if any(e.modality != "mri" for e in plan.entries) else ()
            extra: dict[str, Any] = {"exclude": roots} if roots else {}
            chunks: dict[str, Any] = {}
            if mods:  # phase-1 calls stay unchanged
                extra.update(modules=mods, work_dir=self.work, chunk_map=chunks,
                             progress=lambda msg: self.set_status("executing", self.clean(str(msg))))
            write_bids(plan, core, self.input_dir, terms, key, self.get_schema(), self.out,
                       staged_dir=self.staged, manifest=manifest, refused=refused, **extra)
            done: dict[str, Any] = {}
            if chunks.get("arrays"):
                write_chunk_map(self.chunk_map, chunks["arrays"])
                done["chunk_map"] = self.chunk_map.relative_to(self.work).as_posix()
            key.save()  # the edited subject IDs, and the date offsets the writer creates in memory
            self.save_subject_ids(ids)
            self.set_status("executing", "defacing the anatomical images")
            moved = deface(self.out, plan, plan.deface_method, self.pre, manifest)
            pre_root = self.pre.resolve()
            defaced: dict[str, list[str]] = {}
            for eid, paths in moved.items():
                defaced[eid] = [Path(p).resolve().relative_to(pre_root).as_posix() for p in paths]
            _write_json(self.work / OUTPUT_STATE,
                        {"scan_id": scan_id, "complete": True, "manifest": manifest, "defaced": defaced, **done})
            self.render_qa(plan, manifest)
            self.set_status("executing", "validating the BIDS dataset")
            stage, outcome, validation = self.validate_output(terms)
            self.finish(key, stage, outcome, output_dir=str(self.out),
                        validation=validation, refused=_redact_obj(refused, terms))
        except Exception as e:
            self.fail(e, key, self.set_aside(scan_id))

    def validate_output(self, terms: set[str]) -> tuple[str, str, dict]:
        """(stage, message, validation) of the BIDS validator's run on the output: validated or invalid."""
        result = validate_bids(self.out)
        validation = _redact_obj({
            "ok": result.ok,
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
            "errors": result.errors[:MAX_ISSUES],
            "warnings": result.warnings[:MAX_ISSUES],
            "validator_version": result.validator_version,
            "bids_version": result.bids_version,
        }, path_terms(terms))
        outcome = ("no validation errors" if result.ok else f"{len(result.errors)} validation error(s)")
        return ("validated" if result.ok else "invalid"), outcome, validation

    def render_qa(self, plan: Plan, manifest: dict[str, list[str]]) -> None:
        """The QA snapshots of each written electrophysiology recording (ephys.qa.render), into
        <work>/ephys/qa/<entry id>/ (local only). A failure is logged by type and never fails the run."""
        root = ephys_qa.qa_root(self.work)
        ephys_qa.clear_cache()
        shutil.rmtree(root, ignore_errors=True)
        ids = [e.id for e in plan.entries if e.modality == "ephys" and manifest.get(e.id)
               and SAFE_ENTRY_ID.fullmatch(e.id)]
        if not ids:
            return
        self.set_status("executing", "rendering the QA snapshots")
        for eid in ids:
            self.render_entry_qa(eid, manifest[eid], dict(plan.event_names or {}))

    def render_entry_qa(self, eid: str, files: list[str], event_names: dict[str, str]) -> None:
        """One recording's QA snapshots (again); a failure is logged by type only."""
        try:
            ephys_qa.render(eid, self.out / files[ephys_qa.primary_file(files)], ephys_qa.qa_root(self.work) / eid,
                            event_names=event_names)
        except Exception as e:
            log.warning("QA snapshot failed: %s", type(e).__name__)

    def set_aside(self, scan_id: str) -> str:
        """After a failed execute: <work>/output/bids (possibly complete but not defaced or validated) is
        renamed to bids.failed, replacing an earlier one, so nothing uploadable is left; pre-deface is kept."""
        self.chunk_map.unlink(missing_ok=True)  # nothing of a failed execute is uploadable
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
            roots = self.claimed_roots()
            # the written image names, so companions (events, physio) find their image
            writer = _Writer(plan, core, self.input_dir, terms, scratch_key, schema, tmp_path / "unused",
                             self.staged, exclude=roots)
            try:
                items = writer.items()
                written = {os.path.normpath(str(it.nifti)): it.rel for it in items}
                ids = id_maps(core, [it.entry for it in items], written=written)
            except Exception:
                ids = id_maps(core, plan.entries)
            all_ids = id_maps(core, plan.entries)
            defaults = plan_ancillary(find_ancillary(self.input_dir, schema, roots), self.input_dir, terms,
                                      all_ids, schema)
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


class _UpstreamStream(StreamingResponse):
    """A proxied chunk body that always closes its upstream response when the response ends, also when the
    viewer disconnects mid-stream (a cancelled chunk must not hold a pooled connection): the body generator
    is closed in a finally, whichever way streaming stopped (a send error, a cancelled task group)."""

    def __init__(self, content: Any, upstream: Any, **kwargs: Any) -> None:
        super().__init__(content, **kwargs)
        self.upstream = upstream

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await self.body_iterator.aclose()
            self.upstream.close()  # also when the body never started (the client left before the first part)


def _proxy_chunk(url: str, range_header: str | None, client: Any, head: bool = False) -> Response:
    """A referenced chunk at url, streamed to the viewer: only Range goes upstream; only the status, Content-Range
    and Content-Length come back (never Location, Server, X-Amz-* or the URL); at most QA_MAX_RESPONSE_BYTES.
    A Range that is not a single bytes= range gets 416 here (never an un-ranged upstream GET).
    head: a HEAD (Neuroglancer asks for a shard's size before reading its index from the end).
    client: the server's pooled httpx client."""
    import httpx
    from starlette.concurrency import run_in_threadpool

    from .micr.remote import RangeUnsupported, RemoteRefused, open_stream

    try:
        upstream = open_stream(url, range_header, "HEAD" if head else "GET", client)
    except RangeUnsupported:
        return Response(status_code=416, headers={"Accept-Ranges": "bytes"})
    except RemoteRefused:
        raise HTTPException(404, NO_SUCH_CHUNK) from None
    except httpx.HTTPError as e:
        log.warning("chunk source did not answer: %s", type(e).__name__)
        raise HTTPException(502, "the chunk source did not answer") from None
    status = upstream.status_code
    streaming = False
    try:
        if status in (403, 404, 410):  # S3 answers 403 for a missing key when listing is not allowed
            raise HTTPException(404, NO_SUCH_CHUNK)
        if status not in (200, 206, 416):
            log.warning("chunk source answered %s", status)
            raise HTTPException(502, "the chunk source failed")
        headers = {"Accept-Ranges": "bytes"}
        content_range = upstream.headers.get("content-range", "")
        if _CONTENT_RANGE.fullmatch(content_range):
            headers["Content-Range"] = content_range
        length = upstream.headers.get("content-length", "")
        if length.isascii() and length.isdigit():
            if int(length) > QA_MAX_RESPONSE_BYTES and not head:
                raise HTTPException(502, "the chunk response is too large")
            headers["Content-Length"] = length
        if head:
            return Response(status_code=status, headers=headers, media_type="application/octet-stream")
        cap = QA_MAX_RESPONSE_BYTES

        async def body():
            parts = upstream.iter_raw()
            sent = 0
            try:
                while (part := await run_in_threadpool(next, parts, None)) is not None:
                    sent += len(part)
                    if sent > cap:
                        raise RuntimeError("the chunk response is too large")
                    yield part
            finally:
                upstream.close()

        streaming = True
        return _UpstreamStream(body(), upstream, status_code=status, headers=headers,
                               media_type="application/octet-stream")
    finally:
        if not streaming:
            upstream.close()


def _default_window(window: Any, dtype: Any, source_windows: bool | None = None) -> bool:
    """Whether an omero window is the placeholder reference.py writes when the source had none: the dtype's
    range for integers, 0..1 otherwise (or no window at all). source_windows: whether the source had an omero
    window per channel (scan records, reference.has_source_windows); then its windows, 0..1 included, are
    real and kept. None (not recorded): judged by the values alone."""
    import numpy as np

    if not isinstance(window, dict) or not all(isinstance(window.get(k), (int, float)) for k in ("start", "end")):
        return True
    if source_windows is True:
        return False
    if source_windows is False:
        return True
    dt = np.dtype(dtype)
    lo, hi = (float(np.iinfo(dt).min), float(np.iinfo(dt).max)) if dt.kind in "iu" else (0.0, 1.0)
    return (float(window["start"]), float(window["end"])) == (lo, hi)


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
        if path.startswith(VIEWER_PREFIXES) and path != "/viewer/session":
            reads = request.method in VIEWER_READS
            write = request.method == "POST" and CHANNELS_ROUTE.fullmatch(path) is not None
            if (reads or write) and srv.viewer_session_ok(request.cookies.get(srv.viewer_cookie)):
                if write and not same_origin_viewer(request):
                    raise HTTPException(403, CSRF_REFUSED)
                return
        raise HTTPException(401, "missing or invalid token", headers={"WWW-Authenticate": "Bearer"})

    def same_origin_viewer(request: Request) -> bool:
        """The viewer page's own request: its X-Aimport-Viewer header, and an Origin equal to this engine's (the
        Host header, already checked by host_check). A cross-site form can set neither."""
        origin = (request.headers.get("origin") or "").lower()
        own = "http://" + request.headers.get("host", "").lower()
        return request.headers.get(VIEWER_HEADER) == "1" and bool(origin) and hmac.compare_digest(origin, own)

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
            _check_remote(body.remote)
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
            remote = list(body.remote)
            srv.start(lambda: srv.scan(info, key, remote))
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
                if state.get("chunk_map"):
                    status["chunk_map"] = state["chunk_map"]  # work-relative; never its content
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

    def plan_view(plan: Plan) -> dict:
        """The plan as served: each electrophysiology entry carries ``bad_channels``, the number of bad channels
        in its written channels.tsv once a reviewer saved marks (else 0), and "<n> bad channels" at the end of
        its description; never the names or reasons."""
        out = asdict(plan)
        counts = ephys_bad.counts(work_dir / ephys_module.NAME)
        for e in out["entries"]:
            if e.get("modality") != "ephys":
                continue
            n = e["bad_channels"] = counts.get(e["id"], 0)
            if n:
                note = f"{n} bad channel{'' if n == 1 else 's'}"
                e["description"] = f"{e['description']} · {note}" if e.get("description") else note
        return out

    @app.get("/plan")
    def get_plan() -> dict:
        with srv.plan_lock:
            return plan_view(srv.load_plan())

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
            if body.event_names is not None:
                # stored redacted like all reviewer text; a name the redaction changes is refused, and no error echoes it
                event_names = srv.clean_obj(body.event_names)
                if event_names != body.event_names:
                    raise HTTPException(400, "event name contains an identifying term")
                try:
                    plan.set_event_names(event_names)
                except ValueError as e:
                    raise HTTPException(400, str(e)) from None
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
            return plan_view(plan)

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
            return plan_view(plan)

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
            if not any(e.datatype and e.status == "ok" and not e.exclude for e in plan.entries):
                raise HTTPException(400, NOTHING_TO_WRITE)
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

    def output_file(entry_id: str, index: int, which: str, subpath: str = "", need_original: bool = False) -> Path:
        """A written image of the output manifest (which=original: the pre-deface copy, for a defaced entry; with
        need_original, 404 when there is none instead of the written image, as /preview gives).
        subpath: empty, or the file's own name, for a manifest file; a path inside a manifest directory."""
        state = output_state()
        files = (state.get("manifest") or {}).get(entry_id)
        if not files or not 0 <= index < len(files):
            raise HTTPException(404, "no such image")
        rel, root = files[index], srv.out
        defaced = (state.get("defaced") or {}).get(entry_id)
        if which == "original" and defaced and index < len(defaced):
            root, rel = srv.pre, defaced[index]
        elif which == "original" and need_original:
            raise HTTPException(404, "no original for this image")
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

    def chunk_map() -> dict | None:
        return micr_reference.load_chunk_map(srv.chunk_map)

    def reference_source(entry_id: str, index: int, subpath: str) -> Path | str:
        """The source of a chunk of a referenced OME-Zarr image of the manifest (reference.resolve, only for an
        array strictly inside that image's .ome.zarr folder); 404 'no such chunk' for anything else."""
        state = output_state()
        files = (state.get("manifest") or {}).get(entry_id) or []
        rel = files[index] if 0 <= index < len(files) else ""
        chunks = chunk_map() if rel.endswith(".ome.zarr") and state.get("chunk_map") else None
        if not chunks or not subpath:
            raise HTTPException(404, NO_SUCH_CHUNK)
        try:
            return micr_reference.resolve(chunks, f"{rel}/{subpath}", srv.input_dir, within=rel)
        except ValueError:
            raise HTTPException(404, NO_SUCH_CHUNK) from None

    # HEAD too: Neuroglancer asks for a sharded chunk's size before reading the shard index at its end
    @app.api_route("/qa/data/{entry_id}/{index}/{subpath:path}", methods=["GET", "HEAD"])
    def get_qa_data(entry_id: str, index: str, subpath: str, request: Request,
                    which: Literal["original", "defaced"] = "defaced") -> Any:
        if not (index.isascii() and index.isdigit()):
            raise HTTPException(404, "no such image")
        try:
            return FileResponse(output_file(entry_id, int(index), which, subpath, need_original=True),
                                media_type="application/octet-stream")
        except HTTPException as e:
            if e.status_code != 404 or which == "original" or not subpath:
                raise
        # not written locally: a chunk of a referenced OME-Zarr, read from its source through the chunk map
        source = reference_source(entry_id, int(index), subpath)
        if isinstance(source, Path):
            if not source.is_file():
                raise HTTPException(404, NO_SUCH_CHUNK)
            return FileResponse(source, media_type="application/octet-stream")
        return _proxy_chunk(source, request.headers.get("range"), srv.stream_client(), head=request.method == "HEAD")

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
        defaced = state.get("defaced") or {}
        rows = [{"id": e.id, "index": i, "path": path, "nifti": path.endswith((".nii", ".nii.gz")),
                 "zarr": path.endswith(".ome.zarr"), "reference": e.write_mode == "reference",
                 "defaced": i < len(defaced.get(e.id) or [])}
                for e in entries for i, path in enumerate(state["manifest"][e.id])]
        qa_root = ephys_qa.qa_root(work_dir)
        for e in entries:  # an electrophysiology recording: its snapshots and the trace viewer
            files = state["manifest"][e.id]
            if e.modality != "ephys" or not SAFE_ENTRY_ID.fullmatch(e.id):
                continue
            try:
                primary = ephys_qa.primary_file(files)
            except ValueError:
                continue
            row = next(r for r in rows if r["id"] == e.id and r["index"] == primary)
            row["traces"] = True
            row["pngs"] = [k for k in ephys_qa.KINDS if (qa_root / e.id / f"{k}.png").is_file()]
        return HTMLResponse(index_page(rows))

    @app.get("/viewer/brainlife-mark.svg")
    def get_viewer_logo() -> Response:
        """The brainlife.io logo of the index page (the engine's own copy: no request to another host)."""
        from importlib import resources

        svg = resources.files("aimport.data").joinpath("brainlife-mark.svg").read_bytes()
        return Response(svg, media_type="image/svg+xml",
                        headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})

    window_cache: dict[tuple, dict] = {}

    def zarr_attrs(state: dict, entry: Any, rel: str) -> dict:
        """The written NGFF group attributes of an OME-Zarr image, for the viewer. A reference whose source had
        no display window (reference.py wrote the dtype's range, or 0..1) gets the 0.5/99.5 percentiles of its
        coarsest level, read through the chunk map within QA_WINDOW_MAX_BYTES; on any failure the written
        window stays."""
        import zarr

        root = srv.out / rel
        doc = _read_json(root / "zarr.json")
        attrs = (doc or {}).get("attributes") if doc and "attributes" in doc else _read_json(root / ".zattrs")
        if not isinstance(attrs, dict):
            raise HTTPException(404, "no such image")
        if entry.write_mode != "reference":
            return attrs
        try:  # each execute rewrites the output state: a window of an earlier execute is never reused
            generation = (work_dir / OUTPUT_STATE).stat().st_mtime_ns
        except OSError:
            generation = None
        key = (state.get("scan_id"), generation, rel)
        if key in window_cache:
            return window_cache[key]
        attrs = json.loads(json.dumps(attrs))
        multiscale, omero = ngff_parts(attrs)
        channels = omero.get("channels") or []
        datasets = multiscale.get("datasets") or []
        try:
            dtype = zarr.open_array(str(root / str(datasets[0]["path"])), mode="r").dtype
            had = source_windows(entry)
            if channels and all(_default_window(c.get("window"), dtype, had) for c in channels):
                axes = [a.get("name") for a in multiscale.get("axes") or []]
                windows = reference_windows(rel, [str(d["path"]) for d in datasets], axes, dtype, len(channels))
                for ch, window in zip(channels, windows):
                    if window is not None:  # else the written default stays
                        ch["window"] = window
        except Exception:  # noqa: BLE001 - the written window is a fine fallback; nothing is reported
            log.info("display window of a reference not computed")
            return attrs  # not cached: the next view tries again
        window_cache[key] = attrs
        return attrs

    def reference_windows(rel: str, paths: list[str], axes: list, dtype: Any, n: int) -> list[dict | None]:
        """Per channel, the 0.5/99.5 percentiles of the finite values (NaN, ±inf and the background - the fill
        value, and 0 when it covers at least a fifth of the sample - ignored) of the pyramid level
        whose largest x/y size is closest to QA_WINDOW_TARGET_SIDE among those whose decoded size fits
        QA_WINDOW_MAX_BYTES (so a coarser one when a finer does not fit); a channel that is all NaN or constant
        there is taken from the next finer level that fits, else None (the written default stays). Read errors
        propagate (the caller does not cache them)."""
        from .micr.convert import window_or_none

        chunks = chunk_map() or {}
        xy = [axes.index(a) for a in ("x", "y") if a in axes]
        fits: list[tuple[int, int]] = []  # (level, largest x/y size) of the levels within the cap
        fills: dict[int, Any] = {}  # each level's fill_value: background, never part of the window
        for i, path in enumerate(paths):
            meta = (chunks.get("arrays") or {}).get(f"{rel}/{path}")
            level = srv.out / rel / path
            doc = _read_json(level / "zarr.json") or _read_json(level / ".zarray")
            if not isinstance(meta, dict) or not isinstance(doc, dict):
                continue
            try:
                size = micr_reference._decoded_bytes(meta, doc, len(list(micr_reference.chunk_keys(meta))))
            except (ValueError, KeyError, TypeError):
                continue
            fills[i] = doc.get("fill_value")
            if size <= QA_WINDOW_MAX_BYTES:
                fits.append((i, max((int(meta["shape"][k]) for k in xy), default=0)))
        if not fits:
            return [None] * n
        start = min(fits, key=lambda f: (abs(f[1] - QA_WINDOW_TARGET_SIDE), -f[0]))[0]
        order = [i for i, _ in sorted(fits, reverse=True) if i <= start]  # the start level, then finer ones
        read: dict[int, Any] = {}
        out: list[dict | None] = [None] * n
        for k in range(n):
            for i in order:
                if i not in read:
                    read[i] = micr_reference.read_array(chunks, srv.out, f"{rel}/{paths[i]}", srv.input_dir,
                                                        QA_WINDOW_MAX_BYTES)
                values = read[i].take(k, axis=axes.index("c")) if "c" in axes else read[i]
                out[k] = window_or_none(values, dtype, fills.get(i))
                if out[k] is not None:
                    break
        return out

    def source_windows(entry: Any) -> bool | None:
        """Whether a reference entry's source had an omero window per channel (its scan record), or None."""
        from .micr.module import MICR_INDEX_BASE, MicrModule, load_records

        try:
            records = load_records(module_dir(srv.work, MicrModule()))
            rec = records[entry.series_idx - MICR_INDEX_BASE] if entry.series_idx >= MICR_INDEX_BASE else None
            value = ((rec or {}).get("info") or {}).get("reference_layout", {}).get("source_windows")
        except (OSError, ValueError, IndexError, TypeError, AttributeError):
            return None
        return value if isinstance(value, bool) else None

    def level0_xy(rel: str, attrs: dict) -> list[int] | None:
        """Level 0's x and y sizes, from its written array metadata."""
        multiscale, _ = ngff_parts(attrs)
        axes = [a.get("name") for a in multiscale.get("axes") or []]
        try:
            level = srv.out / rel / str(multiscale["datasets"][0]["path"])
            doc = _read_json(level / "zarr.json") or _read_json(level / ".zarray") or {}
            shape = doc["shape"]
            return [int(shape[axes.index("x")]), int(shape[axes.index("y")])]
        except (KeyError, IndexError, ValueError, TypeError):
            return None

    @app.get("/viewer/entry/{entry_id}")
    def get_viewer_entry(entry_id: str, request: Request, compare: bool = False, index: int = 0) -> RedirectResponse:
        state, entries = written()
        entry = next((e for e in entries if e.id == entry_id), None)
        files = state["manifest"][entry_id] if entry else None
        if not files or not 0 <= index < len(files) or not files[index].endswith((".nii", ".nii.gz", ".ome.zarr")):
            raise HTTPException(404, "no such image")
        base = str(request.base_url).rstrip("/")  # the Host check allows only this server's own names
        if files[index].endswith(".ome.zarr"):
            by_id = {e.id: e for e in entries}
            group = oct_group(asdict(entry), [asdict(e) for e in entries])
            images = []
            for g in group:
                i = index if g["id"] == entry_id else 0
                rel = state["manifest"][g["id"]][i]
                if rel.endswith(".ome.zarr"):
                    attrs = zarr_attrs(state, by_id[g["id"]], rel)
                    images.append({"id": g["id"], "index": i, "file": rel, "attrs": attrs,
                                   "shape_xy": level0_xy(rel, attrs)})
            state_ = entry_state(asdict(entry), files, None, base, index=index, zarr=images)
        else:
            originals = (state.get("defaced") or {}).get(entry_id)
            state_ = entry_state(asdict(entry), files, originals, base, compare=compare, index=index)
        return RedirectResponse(state_url(state_), status_code=303)

    def ephys_output(entry_id: str) -> tuple[Path, Path, dict[str, str]]:
        """(the data file, its QA folder, the plan's event names) of a written electrophysiology entry of the
        manifest, else 404."""
        state = output_state()
        files = (state.get("manifest") or {}).get(entry_id)
        if not files or not SAFE_ENTRY_ID.fullmatch(entry_id):
            raise HTTPException(404, "no such recording")
        with srv.plan_lock:
            plan = srv.load_plan()
        entry = next((e for e in plan.entries if e.id == entry_id), None)
        if entry is None or entry.modality != "ephys":
            raise HTTPException(404, "no such recording")
        try:
            index = ephys_qa.primary_file(files)
        except ValueError:
            raise HTTPException(404, "no such recording") from None
        return (output_file(entry_id, index, "defaced"), ephys_qa.qa_root(work_dir) / entry_id,
                dict(plan.event_names or {}))

    @app.get("/qa/png/{entry_id}/{kind}.png")
    def get_qa_png(entry_id: str, kind: str) -> FileResponse:
        ephys_output(entry_id)
        if kind not in ephys_qa.KINDS:
            raise HTTPException(404, "no such snapshot")
        file = _file_inside(ephys_qa.qa_root(work_dir), f"{entry_id}/{kind}.png")
        if file is None:
            raise HTTPException(404, "no such snapshot")
        return FileResponse(file, media_type="image/png")

    @app.get("/qa/traces/{entry_id}")
    def get_qa_traces(entry_id: str, t0: float = 0.0, t1: float = ephys_qa.DEFAULT_WINDOW_S,
                      ch: str = "") -> dict:
        path, qa_dir, event_names = ephys_output(entry_id)
        picks: list[int] | None = None
        if ch:
            parts = ch.split(",")
            if len(parts) > ephys_qa.MAX_CHANNELS:
                raise HTTPException(400, f"more than {ephys_qa.MAX_CHANNELS} channels")
            if not all(p.isascii() and p.isdigit() and len(p) <= 6 for p in parts):
                raise HTTPException(400, "ch: channel indices separated by commas")
            picks = [int(p) for p in parts]
        try:
            return ephys_qa.window(entry_id, path, t0, t1, picks, qa_dir=qa_dir, event_names=event_names)
        except ephys_qa.WindowError as e:
            raise HTTPException(400, str(e)) from None
        except Exception as e:
            log.warning("trace window failed: %s", type(e).__name__)
            raise HTTPException(500, "the recording could not be read") from None

    def ephys_table(entry_id: str) -> tuple[Any, list[str], Path]:
        """(the plan entry, its manifest files, its written channels.tsv) of a written recording, else 404."""
        ephys_output(entry_id)  # 404 unless a written ephys entry of the manifest, after execute
        files = output_state()["manifest"][entry_id]
        rel = ephys_bad.tsv_of(files)
        tsv = _file_inside(srv.out, rel) if rel else None
        if tsv is None:
            raise HTTPException(404, "the recording has no channels.tsv")
        with srv.plan_lock:
            entry = next(e for e in srv.load_plan().entries if e.id == entry_id)
        return entry, files, tsv

    @app.get("/qa/channels/{entry_id}")
    def get_qa_channels(entry_id: str) -> dict:
        """The written channels.tsv of a recording: name, type, status and status_description per channel."""
        _, _, tsv = ephys_table(entry_id)
        return {"channels": ephys_bad.table(tsv), "max_reason": ephys_bad.MAX_REASON,
                "reasons": list(ephys_bad.QUICK_REASONS)}

    @app.post("/qa/channels/{entry_id}")
    async def post_qa_channels(entry_id: str, request: Request) -> dict:
        """Mark channels good or bad (with an optional reason) in a written recording's channels.tsv; then the
        ephys gate on the rewritten files, the BIDS validator on the output, the recording's QA snapshots."""
        ctype = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            raise HTTPException(415, "Content-Type must be application/json")
        length = request.headers.get("content-length")
        if length is not None and (not length.isdigit() or int(length) > CHANNELS_MAX_BODY):
            raise HTTPException(413, f"the body is larger than {CHANNELS_MAX_BODY // 1024} KiB")
        raw = bytearray()
        async for chunk in request.stream():
            raw += chunk
            if len(raw) > CHANNELS_MAX_BODY:
                raise HTTPException(413, f"the body is larger than {CHANNELS_MAX_BODY // 1024} KiB")
        try:
            body = ChannelsBody.model_validate(json.loads(bytes(raw)))
        except ValueError:  # JSON and pydantic errors: never echoed (a reason may hold identifying text)
            raise HTTPException(400, 'the body must be {"channels": [{"name", "status": "good"|"bad", '
                                     '"description"}]}') from None
        return await run_in_threadpool(mark_channels, entry_id, [m.model_dump() for m in body.channels])

    def mark_channels(entry_id: str, marks: list[dict]) -> dict:
        ephys_dir = work_dir / ephys_module.NAME
        with srv.lock, srv.plan_lock:
            if srv.busy():
                raise conflict(f"busy: {srv.status['stage']}")
            entry, files, tsv = ephys_table(entry_id)
            terms = srv.get_terms()
            if terms is None:
                raise conflict("the ezBIDS output is missing: scan again")
            try:
                checked = ephys_bad.check_marks(tsv, marks, terms)
            except ephys_bad.MarkError as e:
                raise HTTPException(400, str(e)) from None
            before = dict(srv.status)
            extras = {k: v for k, v in before.items() if k not in ("stage", "message")}  # output_dir, refused, ...
            srv.set_status("executing", "applying the channel marks")
        rel = tsv.relative_to(srv.out).as_posix()
        scratch = ephys_dir / "marks-scratch"
        try:
            # the new files are written beside the output, checked by the gate, and only then renamed into it
            shutil.rmtree(scratch, ignore_errors=True)
            text, bad, _ = ephys_bad.render(tsv, checked)
            staged = {tsv: scratch / rel}
            staged[tsv].parent.mkdir(parents=True)
            staged[tsv].write_text(text, encoding="utf-8")
            doc = ephys_bad.described(ephys_bad.sidecar(tsv))
            if doc is not None:
                staged[ephys_bad.sidecar(tsv)] = ephys_bad.sidecar(scratch / rel)
                staged[ephys_bad.sidecar(tsv)].write_text(doc, encoding="utf-8")
            if ephys_module.check_rewritten(list(staged.values()), scratch, ephys_dir, input_dir, terms,
                                            entry.series_idx):
                with srv.lock:
                    srv.set_status(before["stage"], before.get("message", ""), **extras)
                raise HTTPException(400, ephys_bad.REASON_REFUSED)
            for dest, src in staged.items():
                os.replace(src, dest)
            saved = ephys_bad.load(ephys_dir)
            mine = saved.setdefault(entry_id, {})
            mine["channels"] = {**(mine.get("channels") or {}), **checked}
            mine["bad"] = bad
            ephys_bad.save(ephys_dir, saved)
            ephys_qa.clear_cache()
            with srv.plan_lock:
                event_names = dict(srv.load_plan().event_names or {})
            srv.render_entry_qa(entry_id, files, event_names)
            srv.set_status("executing", "validating the BIDS dataset")
            stage, outcome, validation = srv.validate_output(terms)
        except HTTPException:
            raise
        except Exception as e:
            log.warning("channel marks failed: %s", type(e).__name__)
            with srv.lock:
                srv.set_status("failed", "the channel marks could not be applied: execute again")
            raise HTTPException(500, "the channel marks could not be applied: execute again") from None
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        extras.pop("validation", None)
        with srv.lock:
            srv.set_status(stage, outcome, **extras, validation=validation)
        return {"channels": ephys_bad.table(tsv), "bad": bad, "stage": stage,
                "validation": {"ok": validation["ok"], "error_count": validation["error_count"]}}

    @app.get("/viewer/traces/{entry_id}")
    def get_viewer_traces(entry_id: str) -> HTMLResponse:
        path, _, _ = ephys_output(entry_id)
        return HTMLResponse(traces_page(entry_id, path.name))

    @app.get("/viewer/assets/{path:path}")
    def get_viewer_asset(path: str) -> FileResponse:
        """The trace viewer's own files (aimport/static/) and uPlot (<client>/vendor/uplot/, uplot/...)."""
        if path.startswith("uplot/"):
            try:
                base = neuroglancer_client_dir() / "vendor" / "uplot"
            except RuntimeError:
                raise HTTPException(404, "not found") from None
            path = path[len("uplot/"):]
        else:
            base = STATIC_DIR
        base = base.resolve()
        file = (base / path).resolve()
        if not path or base not in file.parents or not file.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(file, media_type=MEDIA_TYPES.get(file.suffix, "application/octet-stream"))

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
