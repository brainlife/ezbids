import os
import stat

import pytest

from aimport.pseudonyms import KeyLockedError, PseudonymKey


def test_same_person_two_imports_same_id(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1")
    a = k.subject_id("MRN0042", existing=set())
    k.save()
    k.close()
    k2 = PseudonymKey.load(tmp_path, "p1")
    assert k2.subject_id("MRN0042", existing={a}) == a


def test_same_original_twice_same_session(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1")
    assert k.subject_id("A", set()) == k.subject_id("A", set())
    assert k.subject_id("B", set()) != k.subject_id("A", set())


def test_skips_existing_project_ids(tmp_path):
    assert PseudonymKey.load(tmp_path, "p1").subject_id("X", existing={"01", "02"}) == "03"


def test_proposed_used_when_valid_and_free(tmp_path):
    assert PseudonymKey.load(tmp_path, "p1").subject_id("X", set(), proposed="abc9") == "abc9"


def test_proposed_collision_falls_back_to_generated(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1")
    assert k.subject_id("X", {"abc"}, proposed="abc") == "01"
    assert k.subject_id("Y", set(), proposed="01") == "02"  # collides with key
    assert k.subject_id("Z", set(), proposed="bad-id") == "03"  # not alphanumeric


def test_two_sessions_share_offset(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1")
    sid = k.subject_id("MRN0042", set())
    off = k.date_offset_days(sid)
    assert off == k.date_offset_days(sid)
    assert -3650 <= off <= -365
    k.save()
    k.close()
    assert PseudonymKey.load(tmp_path, "p1").date_offset_days(sid) == off


def test_key_file_private(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1")
    k.subject_id("A", set())
    k.save()
    path = tmp_path / "p1.aimport-key.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    os.chmod(path, 0o644)
    k.save()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_load_creates_private_file(tmp_path):
    PseudonymKey.load(tmp_path / "keys", "p1")
    assert stat.S_IMODE((tmp_path / "keys" / "p1.aimport-key.json").stat().st_mode) == 0o600


@pytest.mark.parametrize("bad", ["", "..", "a/b", "a\\b", "../x", ".", "a\0b"])
def test_invalid_project_id_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        PseudonymKey.load(tmp_path, bad)


def test_atomic_save_keeps_previous_on_failure(tmp_path, monkeypatch):
    k = PseudonymKey.load(tmp_path, "p1")
    a = k.subject_id("A", set())
    k.save()
    path = tmp_path / "p1.aimport-key.json"
    before = path.read_bytes()
    k.subject_id("B", set())

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        k.save()
    k.close()
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["p1.aimport-key.json", "p1.aimport-key.lock"]
    assert PseudonymKey.load(tmp_path, "p1").subject_id("A", set()) == a


def test_second_load_in_other_process_is_locked(tmp_path):
    import subprocess
    import sys

    code = (
        "import sys; from pathlib import Path; from aimport.pseudonyms import PseudonymKey, KeyLockedError\n"
        "try:\n    PseudonymKey.load(Path(sys.argv[1]), 'p1')\nexcept KeyLockedError:\n    sys.exit(7)\n"
    )
    k = PseudonymKey.load(tmp_path, "p1")
    assert subprocess.run([sys.executable, "-c", code, str(tmp_path)]).returncode == 7
    k.close()
    assert subprocess.run([sys.executable, "-c", code, str(tmp_path)]).returncode == 0


def test_second_load_same_process_is_locked_then_free_after_close(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1")
    with pytest.raises(KeyLockedError):
        PseudonymKey.load(tmp_path, "p1")
    k.close()
    k.close()  # idempotent
    PseudonymKey.load(tmp_path, "p1").close()


def test_context_manager_releases_lock(tmp_path):
    with PseudonymKey.load(tmp_path, "p1") as k:
        k.subject_id("A", set())
        k.save()
    with PseudonymKey.load(tmp_path, "p1") as k2:
        assert k2.subject_id("A", set()) == "01"


def test_save_after_close_raises(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1")
    k.close()
    with pytest.raises(RuntimeError):
        k.save()


def test_load_tightens_permissions(tmp_path):
    PseudonymKey.load(tmp_path, "p1").close()
    for n in ("p1.aimport-key.json", "p1.aimport-key.lock"):
        os.chmod(tmp_path / n, 0o644)
    PseudonymKey.load(tmp_path, "p1").close()
    for n in ("p1.aimport-key.json", "p1.aimport-key.lock"):
        assert stat.S_IMODE((tmp_path / n).stat().st_mode) == 0o600


@pytest.mark.parametrize("content", ["{not json", '{"version": 2}', '{"version": 3, "subjects": {}, "offsets": {}}',
                                     '{"version": 2, "subjects": {}, "offsets": {}, "sessions": []}', "[]"])
def test_corrupt_key_file_raises_valueerror_and_releases_lock(tmp_path, content):
    path = tmp_path / "p1.aimport-key.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="p1.aimport-key.json"):
        PseudonymKey.load(tmp_path, "p1")
    path.write_text('{"version": 2, "subjects": {}, "offsets": {}, "sessions": {}}', encoding="utf-8")
    PseudonymKey.load(tmp_path, "p1").close()


def test_old_key_version_refused_clearly(tmp_path):
    (tmp_path / "p1.aimport-key.json").write_text('{"version": 1, "subjects": {"A": "01"}, "offsets": {}}')
    with pytest.raises(ValueError, match="older aimport"):
        PseudonymKey.load(tmp_path, "p1")
    with pytest.raises(ValueError):  # not KeyLockedError: the lock was released
        PseudonymKey.load(tmp_path, "p1")


def test_sessions_saved(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1")
    sid = k.subject_id("A", set())
    k.sessions.setdefault(sid, {})["study:1.2.3"] = "1"
    k.save()
    k.close()
    assert PseudonymKey.load(tmp_path, "p1").sessions == {sid: {"study:1.2.3": "1"}}
