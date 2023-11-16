# Changelog

All notable changes pertaining to the ezBIDS project will be stored in this file

## 1.0.0 - (November 20, 2023)

ezBIDS has been under development for several years now, yet has only recently had a CHANGELOG to document changes
to the codebase. This provides details regarding recent enhancements [ENH] and fixes [FIX].

### Enhancements
[ENH] Add login page (PR 94)
[ENH] Enable users to enter metadata to the JSON sidecars, currently only available for perfusion (PR 99)
[ENH] Enable user to initialize DWI pipeline on brainlife.io from ezBIDS (PR 87)
[ENH] Add login functionality to ezBIDS (PR 101)
[ENH] Add dcm2niix's BIDSGuess heuristic to ezBIDS Core (issue 88)
[ENH] Enabler faster checks on Dataset Review page, preventing lagging with larger dataset (commit bde5212)
[ENH] Improve subject mapping (commit ff74c94)

### Fixes
[FIX] Improve how the run entity label is set (commit e2a4a91)
