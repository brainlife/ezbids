#!/usr/bin/env python3

import os
import sys

def find_leaf(dir):
    leaf=True
    hasDicom=False

    #is it leaf?
    for x in os.listdir(dir):
        fulldir=os.path.join(dir, x)

        #don't consider parent directory as leaf
        if os.path.isdir(fulldir):
            leaf=False
            continue

        #does it contain any .dcmfile?
        if x.lower().endswith(".dcm") or x.lower().endswith(".ima") or x.lower().startswith("mr."):
            hasDicom=True

    #don't consider a leaf directory with nothing but .nii or .nii.gz
    #otherwise dcm2niix gets run on that directory and it will fail
    #it could still fail if directory doesn't have any dcm
    #if leaf:
    #    allNifty=True
    #    for x in os.listdir(dir):
    #        if not x.endswith(".nii") and not x.endswith(".nii.gz"):
    #            allNifty=False
    #            break
    #    if allNifty:
    #        hasDicom=False

    #if it contains DICOMDIR, treat it as leaf
    if not leaf:
        for x in os.listdir(dir):
            if x.lower() == "dicomdir":
                leaf=True
                hasDicom=True

    if leaf:
        if hasDicom:
            print(dir)
        else:
            #it's leaf but no dicom files.. let's not run dcm2niix
            pass
    else:
        #recurse to all child dirs
        for x in os.listdir(dir):
            fulldir=os.path.join(dir, x)
            if os.path.isdir(fulldir):
                find_leaf(fulldir)

os.chdir(sys.argv[1])

find_leaf('.')

