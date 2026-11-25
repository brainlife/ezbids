"""Write a synthetic T1w MR DICOM series (no real person): the MNI152 2 mm template the app ships, one file per axial
slice, with made-up identifiers only. Used by test/smoke-test-aimport.ts; run with the bundled aimport python.

    python -I make-synthetic-dicom.py <template.nii.gz> <out_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid


def main(template: str, out: str) -> None:
    img = nib.as_closest_canonical(nib.load(template))  # RAS
    data = np.asarray(img.dataobj, dtype=np.float32)
    data = np.clip(data / max(float(data.max()), 1.0) * 1000.0, 0, 4095).astype(np.uint16)
    nx, ny, nz = data.shape
    dx, dy, dz = (float(v) for v in img.header.get_zooms()[:3])
    origin = img.affine[:3, 3]
    study, series, frame = generate_uid(), generate_uid(), generate_uid()
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    for k in range(nz):
        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = MRImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds = FileDataset(str(dest / f"IM{k + 1:04d}.dcm"), {}, file_meta=meta, preamble=b"\0" * 128)
        ds.SOPClassUID, ds.SOPInstanceUID = MRImageStorage, meta.MediaStorageSOPInstanceUID
        ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.FrameOfReferenceUID = study, series, frame
        ds.Modality, ds.Manufacturer, ds.MagneticFieldStrength = "MR", "SIEMENS", 3
        ds.PatientName, ds.PatientID, ds.PatientSex, ds.PatientAge = "Synthetic^CI", "CI0001", "O", "030Y"
        ds.StudyDate = ds.SeriesDate = ds.AcquisitionDate = "20250101"
        ds.StudyTime = ds.SeriesTime = "120000"
        ds.AcquisitionTime = f"1200{k % 60:02d}.000000"
        ds.StudyID, ds.SeriesNumber, ds.AcquisitionNumber, ds.InstanceNumber = "1", 2, 1, k + 1
        ds.SeriesDescription = ds.ProtocolName = "T1w_MPRAGE"
        ds.ScanningSequence, ds.SequenceVariant, ds.MRAcquisitionType = "GR\\IR", "SK\\SP\\MP", "3D"
        ds.ImageType = ["ORIGINAL", "PRIMARY", "M", "ND"]
        ds.RepetitionTime, ds.EchoTime, ds.InversionTime, ds.FlipAngle = 2300, 2.98, 900, 9
        ds.SliceThickness, ds.SpacingBetweenSlices = dz, dz
        # DICOM patient space is LPS, the volume RAS: pixel (row r, column c) is voxel (nx-1-c, ny-1-r, k), so
        # moving along a row (c+1) goes to the left (+x in LPS), down a column (r+1) to the back (+y in LPS)
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        x0, y0, z0 = origin[0] + (nx - 1) * dx, origin[1] + (ny - 1) * dy, origin[2] + k * dz
        ds.ImagePositionPatient = [-x0, -y0, z0]  # RAS -> LPS
        ds.SliceLocation = z0
        ds.PixelSpacing = [dy, dx]
        ds.Rows, ds.Columns = ny, nx
        ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, "MONOCHROME2"
        ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 12, 11, 0
        plane = data[::-1, ::-1, k].T.copy()
        ds.PixelData = plane.astype("<u2").tobytes()
        ds.save_as(dest / f"IM{k + 1:04d}.dcm", enforce_file_format=True)
    print(f"wrote {nz} slices of {nx}x{ny} to {dest}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
