#!/usr/bin/env python3

import os
import sys

def find_leaf(dir):
    leaf=True
    hasDicom=False

    #is it leaf?
    for x in os.listdir(dir):
        fulldir=os.path.join(dir, x)
        if os.path.isdir(fulldir):
            leaf=False
            continue

        #does it contain any .dcmfile?
        if x.lower().endswith(".dcm") or x.lower().endswith(".ima") or x.lower().startswith("mr."):
            hasDicom=True

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

