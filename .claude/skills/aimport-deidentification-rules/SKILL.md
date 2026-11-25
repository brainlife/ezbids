---
name: aimport-deidentification-rules
description: Use when changing anything in aimport/ that reads input, harvests or redacts identifying terms, names subjects, sessions or samples, shifts dates, writes output, talks to a model, reads remote data, or adds a test dataset; also when someone asks whether a field may be kept or uploaded.
---

# aimport de-identification rules

Every aimport change keeps these invariants. Run the named tests after the change; a red one is a leak, not a flaky test.

## Rules and where they are tested

| Rule | Code | Test |
|---|---|---|
| Nothing identifying leaves the machine: input, headers, paths, pre-deface images, pseudonym key. The model sees only the scrubbed view (`[x]`) | `scrub.scrubbed_view`, `scrub.redact` | `tests/test_end_to_end.py`, `tests/test_micr_end_to_end.py::test_micr_e2e_no_leak`, `tests/test_ephys_end_to_end.py::test_ephys_e2e_no_leak` |
| Terms are harvested from headers, paths, tables and vendor metadata, not typed by hand | `scrub.identifying_terms`, `micr/names.path_terms`, `ephys/headers.py` (`_raw_terms`) | `tests/test_scrub.py`, `tests/test_micr_discover.py::test_path_terms`, `tests/test_micr_readers.py::test_tiff_terms_every_tag_and_vendor_metadata` |
| BIDS words from the schema are never terms (`sub` must always be usable); the values next to them stay terms (`sub-July11` gives `July11`) | `schema.bids_words`, `scrub.without_bids_words` (one rule for harvest, redaction, writer, ephys gate, micr reference check) | `tests/test_scrub.py::test_bids_words_come_from_the_schema`, `::test_without_bids_words_keeps_the_values`, `tests/test_ephys_gate.py::test_gate_never_flags_bids_words`, `tests/test_micr_discover.py::test_bids_words_in_micr_names_are_never_terms`, `tests/test_micr_reference.py::test_reference_term_scan_skips_bids_words` |
| Pixel size and unit are never invented: unknown stays unknown until a person sets it; the writer refuses without it | `micr/readers.py`, `writer.py` | `tests/test_micr_convert.py::test_pixel_size_unknown_until_set`, `::test_writer_refuses_missing_pixel_size`, `tests/test_micr_readers.py::test_ngff_axes_without_units_leave_the_unit_unknown` |
| Labels from input names are kept only if safe (not a term anywhere), else renumbered | `micr/names.py`, `ephys/events.py` | `tests/test_micr_bids_input.py::test_unsafe_sample_label_renumbered`, `::test_safe_label_that_is_a_term_elsewhere_renumbered`, `tests/test_ephys_events.py::test_safe_labels_kept` |
| Ephys final gate re-reads every written file for terms, original dates, copied source bytes, head-shape points; a finding fails the run | `ephys/gate.check` | `tests/test_ephys_gate.py`, `tests/test_ephys_write.py::test_gate_failure_sets_aside` |
| Micr reference (OME-Zarr read in place) metadata gets a term scan; array attributes dropped | `micr/reference.check_terms` | `tests/test_micr_reference.py::test_array_attributes_dropped` |
| Dates shifted by one offset per subject (intervals kept); each empty room gets its own shift | `pseudonyms.py`, `ephys/write.py` | `tests/test_pseudonyms.py::test_two_sessions_share_offset`, `tests/test_ephys_write.py::test_scans_shifted_and_no_original_date`, `tests/test_ephys_snirf_nwb.py::test_each_emptyroom_has_its_own_daysback` |
| Large data is never copied or downloaded whole: range reads under a byte cap | `micr/remote.py` (`open_store`, `ByteCounter`) | `tests/test_micr_remote.py::test_byte_budget_stops_a_read`, `::test_unbounded_read_refused`, `tests/test_modality.py::test_stage_excludes_claimed_roots` |
| aimport drops `InstitutionName` (and address, department) | `scrub.scrub_sidecar`, `ephys/write.ALWAYS_DROP` | `tests/test_scrub.py::test_scrub_sidecar_drops_and_redacts` |

## Data rules

- Every new test or validation dataset gets a row in `aimport/tests/DATASETS.md`: pinned commit or date, licence, status, which tests use it, planted identifiers.
- No CMC (`apex-connects` bucket) pixels are committed or downloaded whole: no licence is stated. Read by range in `network`-marked tests only.
- Planted identifiers go in `tests/conftest.py` (`MICR_PLANTED` and friends) so the leak tests look for them.

## Not an aimport rule

Classic ezBIDS web (`handler/`) keeps `InstitutionName` in sidecars: a PI decision. Do not "fix" it there; only aimport strips it.

## Common mistakes

- Adding a BIDS word (`sub`, `task`, `eeg`) or an entity key as a term: redaction then breaks every BIDS file name. Filter through `scrub.without_bids_words`.
- Dropping the value with the key: `XAtest_sub-July11` must still yield `XAtest` and `July11`.
- Defaulting a missing pixel size to 1 µm, or a missing unit to micrometre.
- Keeping a folder name as `sample-`/`ses-` label without checking it against the run's terms.
- Copying a remote store "to make the test simpler", or committing a CMC chunk as a fixture.
- Adding a fixture dataset without its DATASETS.md row and licence.
