#!/usr/bin/env python3

import sys
sys.path.insert(1, '../handler/ezBIDS_core')
from ezBIDS_core import correct_pe, determine_direction


def test_correct_pe():
    proper_pe_direction = correct_pe('y-', 'LAS')
    assert proper_pe_direction == 'j-'


def test_determine_direction():
    ped = determine_direction('j-', 'LAS')
    assert ped == 'AP'
