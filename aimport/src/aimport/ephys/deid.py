"""In-memory de-identification of an opened recording, before anything is written (Task 9).

``clean`` changes only ``raw.info`` and ``raw.annotations``; the samples stay on disk (no data load). What
it does, in order:

- channels named in ``renames`` (old -> new, the inverse of ``work/ephys/channels.json``) are renamed;
- ``info["subject_info"]`` keeps only ``sex`` and ``hand`` (age goes to participants.tsv from the local
  birthday); ``experimenter``, ``description``, ``proj_name``, ``proj_id``, ``device_info``, ``helium_info``,
  ``file_id``, ``meas_id`` and ``utc_offset`` are cleared;
- head-shape points (``FIFFV_POINT_EXTRA``) are dropped unless ``keep_headshape``; cardinal, HPI and EEG
  electrode points are kept;
- every annotation description becomes its label (``labels``: normalised original -> safe label or code)
  shown as the plan's display name (``event_names``: code -> name); ``extras`` are dropped and the
  per-annotation ``ch_names`` follow the channel renames.

MNE-BIDS anonymize (``daysback``) then shifts the measurement date when the recording is written.
"""
from __future__ import annotations

from . import events

CLEARED = ("experimenter", "description", "proj_name", "proj_id", "device_info", "helium_info", "file_id",
           "meas_id", "utc_offset")
SUBJECT_KEYS = ("sex", "hand")


def clean(raw, *, renames: dict[str, str], labels: dict[str, str], event_names: dict[str, str],
          keep_headshape: bool):
    """De-identify ``raw`` in place (info and annotations only) and return it.

    A description that is not in ``labels`` raises ValueError without its text (it was never coded).
    """
    import mne
    from mne._fiff.constants import FIFF

    present = {old: new for old, new in renames.items() if old in raw.ch_names}
    if present:
        raw.rename_channels(present, verbose="error")
    info = raw.info
    subject = info.get("subject_info") or {}
    kept = {k: subject[k] for k in SUBJECT_KEYS if subject.get(k) is not None}
    with info._unlock():
        info["subject_info"] = kept or None
        for k in CLEARED:
            if k in info:
                info[k] = None
        if info.get("dig") and not keep_headshape:
            info["dig"] = [d for d in info["dig"] if d["kind"] != FIFF.FIFFV_POINT_EXTRA]
    ann = raw.annotations
    descriptions = []
    for text in ann.description:
        label = events.label(text, labels)
        descriptions.append(event_names.get(label, label))
    ch_names = [tuple(present.get(c, renames.get(c, c)) for c in chs) for chs in ann.ch_names]
    raw.set_annotations(mne.Annotations(onset=ann.onset, duration=ann.duration, description=descriptions,
                                        orig_time=ann.orig_time, ch_names=ch_names), verbose="error")
    return raw
