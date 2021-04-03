
exports.fmapQA = $root=>{

    // Loop through subjects
    for (const subject in $root.subs) {
        
        // Loop through sessions
        const sessions = $root.subs[subject].sess
        for (const session in sessions) {

            // Determine unique sectionIDs
            let allSectionIDs = sessions[session].objects.map(e=>e.analysisResults.section_ID)
            let sectionIDs = Array.from(new Set(allSectionIDs))

            // Loop through sections (no excluded acquisitions included)
            sectionIDs.forEach(s=> {
                let section = sessions[session].objects.filter(e=>e.analysisResults.section_ID == s && !e._exclude)

                let funcObjs = section.filter(e=>e._type == 'func/bold')
                let dwiObjs = section.filter(e=>e._type == 'dwi/dwi')
                let fmapSpinEchoFuncObjs = section.filter(e=>e._type.startsWith('fmap/epi') && e.forType == 'func/bold')
                let fmapSpinEchoDwiObjs = section.filter(e=>e._type.startsWith('fmap/epi') && e.forType == 'dwi/dwi')
                let fmapMagPhaseObjs = section.filter(function (e) {
                    return e._type.startsWith('fmap/magnitude1') ||
                    e._type.startsWith('fmap/magnitude2')
                    e._type.includes('phase1') ||
                    e._type.includes('phase2')
                });
                let fmapMagPhasediffObjs = section.filter(function (e) {
                    return e._type.startsWith('fmap/magnitude1') || 
                    e._type.startsWith('fmap/magnitude2') ||
                    e._type.includes('phasediff')
                });
                let fmapMagFieldmapObjs = section.filter(function (e) {
                    return e._type.startsWith('fmap/magnitude') ||
                    e._type.includes('fieldmap')
                })

                // Perform fmap QA
                if (funcObjs.length > 0) {

                    // Determine functional indices
                    let funcIntendedFor = funcObjs.map(e=>e.idx)

                    // Remove all spin-echo fmaps except for last two
                    if (fmapSpinEchoFuncObjs.length > 2) {
                        let fmapFuncBadObjs = fmapSpinEchoFuncObjs.slice(0,-2)
                        let fmapFuncGoodObjs = fmapSpinEchoFuncObjs.slice(-2)
                        fmapFuncBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.errors = 'Multiple spin echo field map pairs detected in section; only selecting last pair for BIDS conversion. The other pair acquisition(s) in this section will not be included in the BIDS output'
                        });
                    }

                    // Remove spin-echo fmap if only 1 found
                    if (fmapSpinEchoFuncObjs.length == 1) {
                        fmapSpinEchoFuncObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.errors = 'Only one spin echo field map found; need pair. This acquisition will not be included in the BIDS output'
                        });
                    }

                    // Re-determine spin-echo fmaps meant for func/bold (in event that some were set for exclusion)
                    fmapSpinEchoFuncObjs = fmapSpinEchoFuncObjs.filter(e=>!e.exclude)

                    // Check for proper PEDs for spin-echo pairs
                    if (fmapSpinEchoFuncObjs.length == 2) {
                        let fmapFuncPEDs = fmapSpinEchoFuncObjs.map(e=>e.items[0].sidecar.PhaseEncodingDirection)

                        if (fmapFuncPEDs[0].toString().split('').reverse().join('').slice(-1) == fmapFuncPEDs[1].toString().split('').reverse().join('').slice(-1)) {
                            if ((fmapFuncPEDs[0].length == 2 && fmapFuncPEDs[1].length == 1) || (fmapFuncPEDs[0].length == 1 && fmapFuncPEDs[1].length == 2)) {
                                {}
                            } else {
                                fmapSpinEchoFuncObjs.forEach(obj=> {
                                    obj.exclude = true
                                    obj.errors = 'Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output'
                                });
                            }
                        } else {
                            fmapSpinEchoFuncObjs.forEach(obj=> {
                                obj.exclude = true
                                obj.errors = 'Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output'
                            });
                        }
                    }
   
                    // Remove magnitudes & phasediff if less than 3
                    if (fmapMagPhasediffObjs.length < 3) {
                        fmapMagPhasediffObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.errors = 'Need triplet for magnitude/phasediff field maps. This acquisition will not be included in the BIDS output'
                        });
                    }

                    // Remove all magnitudes and phasediff except for last 3
                    if (fmapMagPhasediffObjs.length > 3) {
                        let fmapMagPhasediffBadObjs = fmapMagPhasediffObjs.slice(0,-3)
                        let fmapMagPhasediffGoodObjs = fmapMagPhasediffObjs.slice(-3)
                        fmapMagPhasediffBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.errors = 'More than three magnitude/phasediff field map acquisitions found in section. Only selecting most recent three. Others will not be included in the BIDS output'
                        });
                    }

                    // Remove magnitudes and phases if less than 4
                    if (fmapMagPhaseObjs.length < 4) {
                        fmapMagPhaseObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.errors = 'Need four images (2 magnitude, 2 phase). This acquisition will not be included in the BIDS output'
                        });
                    }

                    // Remove all magnitudes and phases except for last 4
                    if (fmapMagPhaseObjs.length > 4) {
                        let fmapMagPhaseBadObjs = fmapMagPhaseObjs.slice(0,-4)
                        let fmapMagPhaseGoodObjs = fmapMagPhaseObjs.slice(-4)
                        fmapMagPhaseBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.errors = 'Multiple images sets of (2 magnitude, 2 phase) field map acquisitions found in section. Only selecting most recent set. Other(s) will not be included in the BIDS output'
                        });
                    }

                    // Remove all magnitudes & fieldmaps except for last 2
                    if (fmapMagFieldmapObjs.length > 2) {
                        let fmapMagFieldmapBadObjs = fmapMagFieldmapObjs.slice(0,-2)
                        let fmapMagFieldmapGoodObjs = fmapMagFieldmapObjs.slice(-2)
                        fmapMagFieldmapBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.errors = 'Multiple image sets of magnitude & fieldmap field map acquistions found in section. Only selecting most recent pair. Other(s) will not be included in BIDS output'
                        });
                    }

                    // Remove all magnitudes & fieldmaps if less than 2
                    if (fmapMagFieldmapObjs.length < 2) {
                        fmapMagFieldmapObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.errors = 'Need pair (magnitude & fieldmap). This acquisition will not be included in BIDS output'
                        });
                    }

                } else {
                    fmapSpinEchoFuncObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.errors = 'No valid func/bold acquisitions found in section, spin echo field map pair will not be included in the BIDS output'
                    });

                    fmapMagPhasediffObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.errors = 'No valid func/bold acquisitions found in section, magnitude & phasediff field maps will not be included in the BIDS output'
                    });

                    fmapMagPhaseObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.errors = 'No valid func/bold acquisitions found in section, magnitude & phase field maps will not be included in the BIDS output'
                    });

                    fmapMagFieldmapObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.errors = 'No valid func/bold acquisitions found in section, magnitude & fieldmap will not be included in the BIDS output'
                    })
                }

                // Remove fmap meant for dwi/dwi acquisition(s) if no valid dwi/dwi found in section
                if (dwiObjs.length == 0 && fmapSpinEchoDwiObjs.length > 0) {
                    fmapSpinEchoDwiObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.errors = 'No valid dwi/dwi acquisitions found in section, spin echo field map will not be included in the BIDS output'
                    });
                }

                // Remove fmap meant for dwi/dwi if more than 1 fmap
                if (fmapSpinEchoDwiObjs.length > 1) {
                    fmapSpinEchoDwiObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.errors = 'Multiple spin echo field maps (meant for dwi/dwi) detected in section; only selecting last one for BIDS conversion. The other fmap acquisition(s) in this section will not be included in the BIDS output'
                    });
                }            
            });           
        }
    }     
}

exports.setIntendedFor = $root=>{

    // Loop through subjects
    for (const subject in $root.subs) {
        
        // Loop through sessions
        const sessions = $root.subs[subject].sess
        for (const session in sessions) {

            // Determine unique sectionIDs
            let allSectionIDs = sessions[session].objects.map(e=>e.analysisResults.section_ID)
            let sectionIDs = Array.from(new Set(allSectionIDs))

            // Loop through sections (no excluded acquisitions included)
            sectionIDs.forEach(s=> {
                let section = sessions[session].objects.filter(e=>e.analysisResults.section_ID == s && !e._exclude)

                let funcObjs = section.filter(e=>e._type == 'func/bold')
                let dwiObjs = section.filter(e=>e._type == 'dwi/dwi')
                let fmapFuncObjs = section.filter(e=>e._type.startsWith('fmap') && e.forType == 'func/bold')
                let fmapDwiObjs = section.filter(e=>e._type.startsWith('fmap') && e.forType == 'dwi/dwi')

                // Assign IntendedFor information 
                if (fmapFuncObjs.length > 0) {

                    fmapFuncObjs.forEach(obj=> {
                        obj.IntendedFor = funcObjs.map(e=>e.idx)
                    });
                }

                if (fmapDwiObjs.length > 0) {

                    fmapDwiObjs.forEach(obj=> {
                        obj.IntendedFor = dwiObjs.map(e=>e.idx)
                    });
                }
            });
        }
    }
}
