"""Unit tests for ezBIDS_core.py series-mapping heuristics.

ezBIDS_core.py runs the whole pipeline when imported (it reads sys.argv[1] and chdirs into it),
so these tests pull the functions they need out of the source with ast and run them in a
namespace that holds only the BIDS-schema globals they use.

Run in the handler image, from the repo root (the bids-specification submodule must be checked out):
    docker run --rm --platform linux/amd64 -v $PWD:/app --entrypoint bash ezbids-handler:local \
        -c 'pip3 install -q pytest && cd /app/handler/ezBIDS_core && python3 -m pytest -q test_ezBIDS_core.py'
"""
import ast
import os
import re
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "ezBIDS_core.py"
SCHEMA = HERE.parents[1] / "bids-specification" / "src" / "schema"
FUNCTIONS = ["determine_unique_series", "create_lookup_info", "datatype_suffix_identification"]


@pytest.fixture(scope="module")
def core():
    if not (SCHEMA / "objects" / "datatypes.yaml").exists():
        pytest.skip("bids-specification submodule is not checked out")
    tree = ast.parse(SOURCE.read_text())
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS]
    assert sorted(d.name for d in defs) == sorted(FUNCTIONS)
    ns = {
        "os": os,
        "re": re,
        "yaml": yaml,
        "datatypes_yaml": yaml.safe_load(open(SCHEMA / "objects" / "datatypes.yaml")),
        "suffixes_yaml": yaml.safe_load(open(SCHEMA / "objects" / "suffixes.yaml")),
        "datatype_suffix_rules": str(SCHEMA / "rules" / "datatypes"),
        "accepted_datatypes": ["anat", "dwi", "fmap", "func", "perf", "pet", "meg"],
        "analyzer_dir": "",
    }
    exec(compile(ast.Module(body=defs, type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns


def acquisition(series_description, json_path, sidecar, **kw):
    """One entry of dataset_list as generate_dataset_list builds it (fields these heuristics read)."""
    sidecar = {"Manufacturer": "Siemens", "Modality": "MR", **sidecar}  # dcm2niix always writes these
    d = {
        "SeriesDescription": series_description,
        "ProtocolName": series_description,
        "descriptor": "SeriesDescription",
        "ImageType": sidecar.get("ImageType", ["ORIGINAL", "PRIMARY", "M", "NONE"]),
        "RepetitionTime": sidecar.get("RepetitionTime", 0),
        "EchoNumber": sidecar.get("EchoNumber"),
        "EchoTime": sidecar.get("EchoTime", 0),
        "datatype": "",
        "suffix": "",
        "series_idx": 0,
        "direction": "",
        "NumVolumes": 1,
        "ndim": 3,
        "error": None,
        "message": None,
        "type": "",
        "json_path": json_path,
        "paths": [json_path, json_path.replace(".json", ".nii.gz")],
        "finalized_match": False,
        "sidecar": sidecar,
    }
    d.update(kw)
    return d


def identify(core, dataset_list):
    _, unique = core["determine_unique_series"](dataset_list, False)
    return core["datatype_suffix_identification"](unique, core["create_lookup_info"](), False)


def test_bold_run_with_fa_in_task_name_is_func_bold(core):
    # dcm_qa_xa30 series 7: dcm2niix guesses dwi/_FA because "_fa" is in "func-bold_task-fa_run-1"
    sidecar = {
        "BidsGuess": ["dwi", "_FA"],
        "ImageType": ["ORIGINAL", "PRIMARY", "FMRI", "NONE"],
        "RepetitionTime": 0.8,
        "EchoTime": 0.03,
    }
    bold = acquisition("func-bold_task-fa_run-1", "./In/7_func-bold_task-fa_run-1/sn-7.json", sidecar,
                       NumVolumes=20, ndim=4)
    (series,) = identify(core, [bold])
    assert series["type"] == "func/bold", series["message"]


def test_dwi_fa_map_is_still_excluded(core):
    # dcm_qa_xa30 series DWI_dir80_PA_FA: a scanner-derived FA map, which BIDS does not define
    sidecar = {
        "BidsGuess": ["dwi", "_FA"],
        "ImageType": ["DERIVED", "PRIMARY", "DIFFUSION", "FA"],
        "RepetitionTime": 3.4,
        "EchoTime": 0.068,
    }
    fa = acquisition("DWI_dir80_PA_FA", "./In/13_DWI_dir80_PA_FA/sn-13.json", sidecar)
    (series,) = identify(core, [fa])
    assert series["type"] == "exclude"
