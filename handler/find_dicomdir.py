#!/usr/bin/env python3

import os
import sys

def find_leaf(dir):
    leaf=True

    #is it leaf?
    for x in os.listdir(dir):
        fulldir=os.path.join(dir, x)
        if os.path.isdir(fulldir):
            #print(fulldir+" is directory")
            leaf=False
            continue

    #if it contains DICOMDIR, treat it as leaf
    if not leaf:
        for x in os.listdir(dir):
            if x == "DICOMDIR":
                #print("dicomdir detected")
                leaf=True

    if leaf:
        #print(dir+" is leaf - no sub directory")
        print(dir)
    else:
        #recurse to all child dirs
        for x in os.listdir(dir):
            fulldir=os.path.join(dir, x)
            if os.path.isdir(fulldir):
                find_leaf(fulldir)

os.chdir(sys.argv[1])

find_leaf('.')

