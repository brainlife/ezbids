"""Licence check and notices for the desktop aimport runtime (run by fetch-aimport.sh with the bundled Python).

    python -I -B runtime_licenses.py <out_file> [<name>=<licence file> ...]

Reads every installed distribution's metadata (importlib.metadata, so exactly the bundled site-packages), then
- fails (exit 1) if a package the desktop app must not ship is present (bioio-czi, aicspylibczi: GPL-3.0; CZI
  support is aimport's optional "czi" extra, installed in the Docker engine image only) or if any package is
  licensed GPL or AGPL only (an "X OR GPL" choice is fine; LGPL is listed, not refused);
- writes <out_file> (THIRD_PARTY_LICENSES.txt): one line per package with its licence, then each package's own
  licence files, then the extra licence files given on the command line (e.g. the Neuroglancer client's).
Standard library only.
"""
from __future__ import annotations

import re
import sys
from importlib.metadata import distributions
from pathlib import Path

# GPL-3.0: never in the desktop app (CREDITS.md "Licence notes")
FORBIDDEN = {"bioio-czi", "aicspylibczi"}
_STRONG = re.compile(r"\bA?GPL(?:v?\d|-|\b)|GNU (Affero )?General Public|GNU GPL", re.I)
_WEAK = re.compile(r"\bLGPL|GNU Lesser|GNU Library", re.I)
_LICENCE_FILE = re.compile(r"^(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", re.I)


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def licence_of(meta) -> str:
    """The SPDX expression, else a short License field, else the trove classifiers."""
    expr = (meta.get("License-Expression") or "").strip()
    if expr:
        return expr
    field = (meta.get("License") or "").strip()
    if field and "\n" not in field and len(field) <= 120 and field.upper() != "UNKNOWN":
        return field
    trove = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return "; ".join(trove) or "UNKNOWN"


def copyleft(licence: str) -> str:
    """'strong' when every alternative is GPL/AGPL, 'weak' for LGPL, else ''."""
    alternatives = re.split(r"\s+OR\s+|;\s*", licence)
    strong = [a for a in alternatives if _STRONG.search(_WEAK.sub("", a))]
    if strong and len(strong) == len(alternatives):
        return "strong"
    if any(_WEAK.search(a) for a in alternatives):
        return "weak"
    return ""


def licence_files(dist) -> list[Path]:
    out = []
    for f in dist.files or []:
        parts = Path(str(f)).parts
        if parts and parts[0].endswith(".dist-info") and (
                "licenses" in parts[1:-1] or "license_files" in parts[1:-1] or _LICENCE_FILE.match(parts[-1])):
            out.append(Path(dist.locate_file(f)))
    return sorted(out)


def main(argv: list[str]) -> int:
    out = Path(argv[1])
    extras = [a.split("=", 1) for a in argv[2:]]
    rows, bad, weak, unknown = [], [], [], []
    seen: dict[str, object] = {}
    for dist in distributions():
        name = dist.metadata.get("Name") or "?"
        if _norm(name) not in seen:
            seen[_norm(name)] = dist
    for key in sorted(seen):
        dist = seen[key]
        name, version = dist.metadata["Name"], dist.version
        lic = licence_of(dist.metadata)
        rows.append((name, version, lic))
        kind = copyleft(lic)
        if key in FORBIDDEN or kind == "strong":
            bad.append(f"{name} {version}: {lic}")
        elif kind == "weak":
            weak.append(f"{name} {version}: {lic}")
        elif lic == "UNKNOWN":
            unknown.append(f"{name} {version}")

    with out.open("w", encoding="utf-8") as fh:
        fh.write("Third-party software in the ezBIDS desktop aimport runtime\n"
                 "(Python packages from aimport/uv.lock, without the GPL-licensed \"czi\" extra)\n\n")
        width = max(len(f"{n} {v}") for n, v, _ in rows)
        for n, v, lic in rows:
            fh.write(f"{f'{n} {v}':<{width}}  {lic}\n")
        for n, v, _ in rows:
            for path in licence_files(seen[_norm(n)]):
                fh.write(f"\n{'=' * 78}\n{n} {v}: {path.name}\n{'=' * 78}\n")
                fh.write(path.read_text(encoding="utf-8", errors="replace"))
        for label, path in extras:
            fh.write(f"\n{'=' * 78}\n{label}: {Path(path).name}\n{'=' * 78}\n")
            fh.write(Path(path).read_text(encoding="utf-8", errors="replace"))

    print(f"  {len(rows)} packages, licences written to {out.name}")
    for title, items in (("LGPL (weak copyleft, allowed)", weak), ("licence not in metadata", unknown)):
        if items:
            print(f"  {title}:")
            for item in items:
                print(f"    {item}")
    if bad:
        print("ERROR: the desktop runtime must not ship these (GPL/AGPL or the CZI extra):", file=sys.stderr)
        for item in bad:
            print(f"    {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
