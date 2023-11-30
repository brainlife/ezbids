#!/usr/bin/env python3

import sys
sys.path.insert(1, '../handler/ezBIDS_core')
import ezBIDS_core as ezBIDS_core_functions


def test_correct_pe():
    proper_pe_direction = ezBIDS_core_functions.correct_pe('j-', 'LAS')
    assert proper_pe_direction == 'j-'
