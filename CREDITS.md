# Credits, citations and licences

ezBIDS and aimport build on the work of many open-source projects and on the BIDS community. This file lists what to cite, every tool we build on, its licence, and where each citation was checked. A machine-readable version of the main citations is in [`CITATION.cff`](CITATION.cff).

Contents: [How to cite ezBIDS](#how-to-cite-ezbids) · [Funding](#funding) · [BIDS and its extensions](#bids-and-its-extensions) · [Tools](#tools) ([conversion and de-identification](#conversion-and-de-identification), [BIDS tools](#bids-tools), [microscopy](#microscopy-aimport), [electrophysiology and NIRS](#electrophysiology-and-nirs-aimport-meg-also-on-the-web), [AI](#ai-aimport-optional), [viewers](#viewers)) · [Not verified](#not-verified) · [Also built with](#also-built-with) · [Licence notes](#licence-notes)

## How to cite ezBIDS

Cite the ezBIDS paper when you publish data converted with ezBIDS or aimport (source: publisher, Crossref):

> Levitas, D., Hayashi, S., Vinci-Booher, S., Heinsfeld, A., Bhatia, D., Lee, N., Galassi, A., Niso, G. & Pestilli, F. (2024). ezBIDS: Guided standardization of neuroimaging data interoperable with major data archives and platforms. *Scientific Data*, 11, 179. [doi:10.1038/s41597-024-02959-0](https://doi.org/10.1038/s41597-024-02959-0)

ezBIDS and aimport are developed by the Pestilli Lab at The University of Texas at Austin (brainlife.io); please also acknowledge The University of Texas at Austin and the funding below.

## Funding

ezBIDS and aimport are developed by the Pestilli Lab at The University of Texas at Austin with funding from the grants below (checked on NIH RePORTER, the NSF award search and Europe PMC Grant Finder). NSF awards transferred to The University of Texas at Austin are listed with their transfer number.

| Funder | Award | Title |
|---|---|---|
| NIH NINDS | [U24NS140384](https://reporter.nih.gov/project-details/U24NS140384) | BRAIN CONNECTS: The Axonal Projectome EXchange (APEX) |
| NIH NIMH | [R01MH126699](https://reporter.nih.gov/project-details/R01MH126699) | Community-driven development of BIDS |
| NIH NIBIB | [R01EB030896](https://reporter.nih.gov/project-details/R01EB030896) | CRCNS US-France: open science and cloud computing of MEEG |
| NIH NIBIB | [R01EB029272](https://reporter.nih.gov/project-details/R01EB029272) | CRCNS US-France: lowering the barrier of entry to network neuroscience |
| NSF | [BCS-1636893](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1636893), [2148729](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2148729) | BD Spokes: Advanced Computational Neuroscience Network |
| NSF | [BCS-1734853](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1734853), [2203524](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2203524) | NCS-FO: Connectome mapping algorithms |
| NSF | [IIS-1912270](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1912270), [2148700](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2148700) | CRCNS US-German: DataLad |
| NSF | [ACI-1916518](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1916518) | BD Hubs: Midwest Big Data Hub |
| Wellcome Trust | [226486](https://grantnav.threesixtygiving.org/grant/360G-Wellcome-226486_Z_22_Z) | Developing an international governance framework to advance global brain and mental health data equity and innovation |

## BIDS and its extensions

The [BIDS specification asks](https://bids-specification.readthedocs.io/en/stable/introduction.html#citing-bids) you to cite the original BIDS paper and the extension for your data type (source: BIDS specification v1.11.2 "Citing BIDS", checked against Crossref).

| Data | Paper |
|---|---|
| All data (BIDS) | Gorgolewski et al. (2016). The brain imaging data structure, a format for organizing and describing outputs of neuroimaging experiments. *Scientific Data*, 3, 160044. [doi:10.1038/sdata.2016.44](https://doi.org/10.1038/sdata.2016.44) |
| PET | Norgaard et al. (2022). PET-BIDS, an extension to the brain imaging data structure for positron emission tomography. *Scientific Data*, 9, 65. [doi:10.1038/s41597-022-01164-1](https://doi.org/10.1038/s41597-022-01164-1) |
| MEG | Niso et al. (2018). MEG-BIDS, the brain imaging data structure extended to magnetoencephalography. *Scientific Data*, 5, 180110. [doi:10.1038/sdata.2018.110](https://doi.org/10.1038/sdata.2018.110) |
| EEG | Pernet et al. (2019). EEG-BIDS, an extension to the brain imaging data structure for electroencephalography. *Scientific Data*, 6, 103. [doi:10.1038/s41597-019-0104-8](https://doi.org/10.1038/s41597-019-0104-8) |
| iEEG | Holdgraf et al. (2019). iEEG-BIDS, extending the Brain Imaging Data Structure specification to human intracranial electrophysiology. *Scientific Data*, 6, 102. [doi:10.1038/s41597-019-0105-7](https://doi.org/10.1038/s41597-019-0105-7) |
| NIRS | Luke et al. (2025). NIRS-BIDS: Brain Imaging Data Structure Extended to Near-Infrared Spectroscopy. *Scientific Data*, 12, 159. [doi:10.1038/s41597-024-04136-9](https://doi.org/10.1038/s41597-024-04136-9) |
| Microscopy | Bourget et al. (2022). Microscopy-BIDS: An Extension to the Brain Imaging Data Structure for Microscopy Data. *Frontiers in Neuroscience*, 16, 871228. [doi:10.3389/fnins.2022.871228](https://doi.org/10.3389/fnins.2022.871228) |
| ASL (perfusion MRI) | Clement et al. (2022). ASL-BIDS, the brain imaging data structure extension for arterial spin labeling. *Scientific Data*, 9, 543. [doi:10.1038/s41597-022-01615-9](https://doi.org/10.1038/s41597-022-01615-9) |
| EMG | No paper yet ("publication forthcoming" in the specification); cite the [BIDS specification v1.11.2](https://doi.org/10.5281/zenodo.10175845) (EMG was added as BEP042). |

## Tools

Cite the tools your conversion used. Licences are the projects' own; versions are the ones pinned in [`handler/Dockerfile`](handler/Dockerfile), [`aimport/uv.lock`](aimport/uv.lock) and [`aimport/viewer-client/package.json`](aimport/viewer-client/package.json). Every citation was taken from the project's own citation file, README or docs, or from the publisher; the last column says which. Where a project has no paper we give its Zenodo DOI or repository only.

### Conversion and de-identification

| Tool | What it does here | Licence | Cite | Source of the citation |
|---|---|---|---|---|
| [dcm2niix](https://github.com/rordenlab/dcm2niix) | DICOM to NIfTI + JSON sidecars | BSD-style | Li, X., Morgan, P.S., Ashburner, J., Smith, J. & Rorden, C. (2016). The first step for neuroimaging data analysis: DICOM to NIfTI conversion. *J Neurosci Methods*, 264, 47-56. [doi:10.1016/j.jneumeth.2016.03.001](https://doi.org/10.1016/j.jneumeth.2016.03.001) | dcm2niix README; Crossref |
| [pydicom](https://github.com/pydicom/pydicom) | Reads DICOM headers | MIT | [doi:10.5281/zenodo.1291985](https://doi.org/10.5281/zenodo.1291985) (Zenodo) | README Zenodo badge (concept DOI) |
| [NiBabel](https://github.com/nipy/nibabel) | Reads and writes NIfTI | MIT | [doi:10.5281/zenodo.591597](https://doi.org/10.5281/zenodo.591597) (Zenodo) | CITATION.cff |
| [PET2BIDS](https://github.com/openneuropet/PET2BIDS) (pypet2bids) | PET (ECAT, DICOM) to BIDS | MIT | Galassi, A., Norgaard, M., Thomas, A.G. et al. PET2BIDS (software), [github.com/openneuropet/PET2BIDS](https://github.com/openneuropet/PET2BIDS) | CITATION.cff |
| [pydeface](https://github.com/poldracklab/pydeface) | Defacing (option "pydeface") | MIT | Gulban, O.F., Nielson, D., Markiewicz, C. et al. pydeface, [doi:10.5281/zenodo.3524400](https://doi.org/10.5281/zenodo.3524400) | README Zenodo badge (concept DOI) |
| [FSL](https://fsl.fmrib.ox.ac.uk/) (FLIRT, used by pydeface) | Registration to the face mask | FSL licence (non-commercial) | Jenkinson, M., Beckmann, C.F., Behrens, T.E., Woolrich, M.W. & Smith, S.M. (2012). FSL. *NeuroImage*, 62, 782-790. [doi:10.1016/j.neuroimage.2011.09.015](https://doi.org/10.1016/j.neuroimage.2011.09.015) | FSL docs; Crossref |
| [quickshear](https://github.com/nipy/quickshear) | Defacing (option "quickshear") | BSD-3-Clause | Schimke, N. & Hale, J. (2011). Quickshear defacing for neuroimages. *Proceedings of the 2nd USENIX Conference on Health Security and Privacy* | quickshear README |
| [ROBEX](https://www.nitrc.org/projects/robex) | Brain mask for quickshear | BSD-style (NITRC) | Iglesias, J.E., Liu, C.-Y., Thompson, P.M. & Tu, Z. (2011). Robust brain extraction across datasets and comparison with publicly available methods. *IEEE Trans Med Imaging*, 30(9), 1617-1634. [doi:10.1109/TMI.2011.2138152](https://doi.org/10.1109/TMI.2011.2138152) | NITRC page; Crossref |
| [allineate](https://github.com/neurolabusc/allineate) (port of AFNI 3dAllineate) | Face mask in ezBIDS desktop and its AI import (beta) | Public domain (AFNI) | Cox, R.W. (1996). AFNI: software for analysis and visualization of functional magnetic resonance neuroimages. *Comput Biomed Res*, 29(3), 162-173. [doi:10.1006/cbmr.1996.0014](https://doi.org/10.1006/cbmr.1996.0014) | AFNI citations page; Crossref |
| [7-Zip](https://www.7-zip.org/) | Unpacks .7z uploads | LGPL-2.1+ (unRAR restriction for some code) | [7-zip.org](https://www.7-zip.org/) | 7-zip.org |

### BIDS tools

| Tool | What it does here | Licence | Cite | Source of the citation |
|---|---|---|---|---|
| [BIDS specification](https://github.com/bids-standard/bids-specification) v1.11.2 | The standard; its schema drives the mapping | CC-BY-4.0 | Papers above; specification [doi:10.5281/zenodo.10175845](https://doi.org/10.5281/zenodo.10175845) | bids-specification CITATION.cff |
| [bids-validator](https://github.com/bids-standard/bids-validator) (`@bids/validator` 2.4.1; 1.14.8 in the web service) | Validates every output | MIT | [doi:10.5281/zenodo.3688706](https://doi.org/10.5281/zenodo.3688706) (Zenodo) | CITATION.cff |
| [bidsschematools](https://github.com/bids-standard/bids-specification) | Reads the BIDS schema (aimport) | MIT | With the BIDS specification | bids-specification |

### Microscopy (aimport)

| Tool | What it does here | Licence | Cite | Source of the citation |
|---|---|---|---|---|
| [BioIO](https://github.com/bioio-devs/bioio) + bioio-czi, bioio-nd2, bioio-lif | Reads CZI, ND2, LIF and other vendor files | BSD-3-Clause; bioio-czi GPL-3.0 (aicspylibczi; optional extra `aimport[czi]`, Docker engine image only); bioio-nd2 MIT; bioio-lif BSD-3-Clause | BioIO Contributors, [doi:10.5281/zenodo.22755965](https://doi.org/10.5281/zenodo.22755965) | CITATION.cff |
| [tifffile](https://github.com/cgohlke/tifffile) | Reads and writes OME-TIFF | BSD-3-Clause | Gohlke, C. tifffile, [doi:10.5281/zenodo.6795860](https://doi.org/10.5281/zenodo.6795860) | README |
| [ome-types](https://github.com/imaging-formats/ome-types) | OME-XML metadata | MIT | [github.com/imaging-formats/ome-types](https://github.com/imaging-formats/ome-types) | repo (no citation file) |
| [OME-NGFF / OME-Zarr](https://ngff.openmicroscopy.org/) | Format for large images, read in place | CC-BY-4.0 (spec) | Moore, J. et al. (2021). OME-NGFF: a next-generation file format for expanding bioimaging data-access strategies. *Nature Methods*, 18, 1496-1498. [doi:10.1038/s41592-021-01326-w](https://doi.org/10.1038/s41592-021-01326-w); Moore, J. et al. (2023). OME-Zarr: a cloud-optimized bioimaging file format with international community support. *Histochem Cell Biol*, 160, 223-251. [doi:10.1007/s00418-023-02209-1](https://doi.org/10.1007/s00418-023-02209-1) | ome/ngff index.md (2021); Crossref (2023) |
| [ngff-zarr](https://github.com/thewtex/ngff-zarr) | Writes OME-Zarr | MIT | McCormick, M., Soltwedel, J., Vierdag, W.-M., Boussot, V. & Moore, J. (2026). ngff-zarr: A Lean and Kind OME-Zarr Toolkit for Bioimaging. *Proceedings of the 25th Python in Science Conference*, 295-302. [doi:10.25080/gewj5574](https://doi.org/10.25080/gewj5574) | CITATION.cff |
| [zarr-python](https://github.com/zarr-developers/zarr-python) | Zarr arrays | MIT | [doi:10.5281/zenodo.3773449](https://doi.org/10.5281/zenodo.3773449) (Zenodo) | README Zenodo badge (concept DOI) |
| [Dask](https://github.com/dask/dask), [fsspec](https://github.com/fsspec/filesystem_spec) | Chunked and remote reads | BSD-3-Clause | Project sites | repo (no citation file) |
| [SciPy](https://scipy.org/) | Resampling and image maths | BSD-3-Clause | Virtanen, P. et al. (2020). SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python. *Nature Methods*, 17, 261-272. [doi:10.1038/s41592-019-0686-2](https://doi.org/10.1038/s41592-019-0686-2) | CITATION.bib |

### Electrophysiology and NIRS (aimport; MEG also on the web)

| Tool | What it does here | Licence | Cite | Source of the citation |
|---|---|---|---|---|
| [MNE-Python](https://mne.tools/) | Reads EEG, MEG, iEEG, NIRS, EMG | BSD-3-Clause | Gramfort, A. et al. (2013). MEG and EEG data analysis with MNE-Python. *Frontiers in Neuroscience*, 7. [doi:10.3389/fnins.2013.00267](https://doi.org/10.3389/fnins.2013.00267) | CITATION.cff |
| [MNE-BIDS](https://mne.tools/mne-bids) | Writes the BIDS ephys files | BSD-3-Clause | Appelhoff, S. et al. (2019). MNE-BIDS: Organizing electrophysiological data into the BIDS format and facilitating their analysis. *Journal of Open Source Software*, 4(44), 1896. [doi:10.21105/joss.01896](https://doi.org/10.21105/joss.01896) | CITATION.cff |
| [edfio](https://github.com/the-siesta-group/edfio) | Writes EDF | Apache-2.0 | [github.com/the-siesta-group/edfio](https://github.com/the-siesta-group/edfio) | repo (no citation file) |
| [pybv](https://github.com/bids-standard/pybv) | Writes BrainVision | BSD-3-Clause | Appelhoff, S. et al. pybv, [doi:10.5281/zenodo.5539451](https://doi.org/10.5281/zenodo.5539451) | CITATION.cff |
| [PyNWB](https://github.com/NeurodataWithoutBorders/pynwb) | Reads NWB | BSD-3-Clause | Rübel, O. et al. (2022). The Neurodata Without Borders ecosystem for neurophysiological data science. *eLife*, 11, e78362. [doi:10.7554/eLife.78362](https://doi.org/10.7554/eLife.78362) | pynwb README "Citing NWB" |
| [h5py](https://www.h5py.org/) | HDF5 (NWB, SNIRF) | BSD-3-Clause | [h5py.org](https://www.h5py.org/) | site (no citation file) |
| [Matplotlib](https://matplotlib.org/) | QA figures | Matplotlib licence (PSF-based) | Hunter, J.D. (2007). Matplotlib: A 2D graphics environment. *Computing in Science & Engineering*, 9(3), 90-95. [doi:10.1109/MCSE.2007.55](https://doi.org/10.1109/MCSE.2007.55) | CITATION.cff |
| [defusedxml](https://github.com/tiran/defusedxml) | Safe XML parsing of vendor headers | PSF | [github.com/tiran/defusedxml](https://github.com/tiran/defusedxml) | repo (no citation file) |

### AI (aimport, optional)

| Tool | What it does here | Licence | Cite | Source of the citation |
|---|---|---|---|---|
| [Anthropic API](https://www.anthropic.com/api) (Claude) | Default model for the mapping agent; sees only de-identified metadata | Service (SDK Apache-2.0) | Name the model and version you used | service |
| [AutoBIDSify](https://github.com/NeuroJSON/autobidsify) 0.9.9.1 | Routes the agent to OpenAI or Qwen models | MIT | Liu, Y. et al. AutoBIDSify (software), [github.com/NeuroJSON/autobidsify](https://github.com/NeuroJSON/autobidsify), version 0.9.9.1 | PyPI metadata; repo README |

### Viewers

| Tool | What it does here | Licence | Cite | Source of the citation |
|---|---|---|---|---|
| [NiiVue](https://github.com/niivue/niivue) | Image previews in the web UI | BSD-2-Clause | [doi:10.5281/zenodo.5786269](https://doi.org/10.5281/zenodo.5786269) (Zenodo) | README Zenodo badge |
| [Neuroglancer](https://github.com/google/neuroglancer) 2.41.2 | aimport QA viewer for images | Apache-2.0 | [doi:10.5281/zenodo.5573293](https://doi.org/10.5281/zenodo.5573293) (Zenodo) | README Zenodo badge (concept DOI) |
| [uPlot](https://github.com/leeoniya/uPlot) 1.6.32 | aimport trace viewer for recordings | MIT | [github.com/leeoniya/uPlot](https://github.com/leeoniya/uPlot) | repo (no citation file) |

## Example and test data

- **CMC** (connects.brainlife.io/publications/CMC; public bucket `apex-connects`): PS-OCT, light-sheet (VISoR) and exaSPIM data used to test aimport's remote microscopy reads and the QA viewer. Permissive licence (confirmed by the dataset's PI); please credit the CMC dataset and BRAIN CONNECTS APEX (NIH U24NS140384) when showing it.
- Other test and example datasets, with their licences and sources, are listed in [aimport/tests/DATASETS.md](aimport/tests/DATASETS.md).

## Not verified

No paper could be verified for these, so they are credited by repository, version and licence (or a Zenodo DOI) only:

- AutoBIDSify 0.9.9.1 (no citation file; author from PyPI).
- PET2BIDS (its CITATION.cff has no paper; cite the PET-BIDS paper for the format).
- pydeface, pydicom, zarr-python, tifffile, BioIO, NiiVue, Neuroglancer (Zenodo DOI only).
- 7-Zip, h5py, Dask, fsspec, edfio, ome-types, defusedxml, uPlot (link only).
- allineate (a port of AFNI 3dAllineate; credited through the AFNI paper).
- EMG: no paper yet; the BIDS specification says "publication forthcoming" (BEP042).
- Anthropic API: a service, named rather than cited.

## Also built with

ezBIDS and aimport are also built with [Vue](https://vuejs.org/), [Element Plus](https://element-plus.org/), [FastAPI](https://fastapi.tiangolo.com/) and, for the desktop app, [Electron](https://www.electronjs.org/). `bl aimport`, the command-line front end, is part of brainlife's Python CLI, [pybrainlife](https://github.com/brainlife/pybrainlife/tree/enh/cli#bl-aimport) (branch `enh/cli`).

## Licence notes

ezBIDS is [MIT](LICENSE). The licences of the tools above are compatible with using them from ezBIDS; these points need care when the tools are **redistributed** (Docker images, the desktop app):

- **FSL** (FLIRT, used by pydeface) is free for **non-commercial use only**. The web handler image copies FSL binaries from `dlevitas/FSL_binaries`, a repository with no licence file; redistributing them should be confirmed with Oxford University Innovation. The desktop app does not bundle FSL (it defaces with allineate) and should not.
- **bioio-czi and aicspylibczi are GPL-3.0.** Resolved for the desktop app: CZI support is the optional extra `aimport[czi]`, installed in the aimport Docker engine image (`--extra czi`) and left out of the desktop runtime, where a `.czi` file is planned `unsupported` ("CZI support is not installed in this build ..."). The engine image still carries them (GPL text and source offer apply if the image is distributed).
- **snirf (pysnirf2) is GPL-3.0** (its PyPI metadata also lists an MIT classifier; its LICENSE file is the GPL). It comes in through AutoBIDSify, whose MAT-to-SNIRF converter is the only code importing it; aimport never calls that and reads SNIRF with MNE. The desktop runtime leaves it out (`fetch-aimport.sh`: `--no-emit-package snirf`); the engine image still has it.
- **Desktop licence check:** `fetch-aimport.sh` runs `electron/aimport/runtime_licenses.py` with the bundled Python: the build fails if bioio-czi, aicspylibczi or any GPL/AGPL-only package is in the runtime, and it writes `THIRD_PARTY_LICENSES.txt` (each package's licence and licence files, plus Neuroglancer's and uPlot's) into the runtime. Neuroglancer's and uPlot's LICENSE files are also copied next to the built viewer client.
- **ROBEX** is downloaded through NITRC's click-through (`i_agree=1`); NITRC lists a BSD-style licence, but the licence text inside the archive has not been reviewed. It is in the web and aimport images only.
- **Publishing the images** (`.github/workflows/publish-images.yml`, `docker.io/brainlife/ezbids-handler` and `docker.io/brainlife/aimport`) redistributes FSL and ROBEX to anyone who pulls them: settle the two points above before the first `aimport-v*` tag. The aimport image also carries the GPL-3.0 bioio-czi, aicspylibczi and snirf (see above), so it needs the GPL text and a source offer.
- **Texts the desktop installer must ship:** 7-Zip's `License.txt` (LGPL-2.1+, unRAR restriction on part of 7z.dll); dcm2niix's `license.txt` (BSD-style: binaries must reproduce the notice); allineate's public-domain notice (the licence of the MNI template and mask files shipped with it has not been checked); Neuroglancer's Apache-2.0 LICENSE (and NOTICE, if any) with the built viewer client. Neuroglancer's LICENSE (it has no NOTICE) now ships in the runtime. Still open: the 7z, allineate and dcm2niix assets `fetch-binaries.sh` downloads (ezbids-binaries release and the official dcm2niix zip) contain the binaries only, no licence file, so those three texts must be added to the brainlife/ezbids-binaries release (or taken from the projects' tagged sources) before installers are published. The dcm2niix PyPI wheel AutoBIDSify pulls into the runtime does carry its `license.txt`, which is in `THIRD_PARTY_LICENSES.txt`.
- **AutoBIDSify** says MIT in its README and on PyPI, but its repository has no LICENSE file; aimport also calls its private `_call_llm`.
- The BIDS specification and schema and the OME-NGFF specification are CC-BY-4.0; this file provides the attribution. The Anthropic, OpenAI and Qwen APIs are services under their own terms of use.
