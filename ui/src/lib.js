
exports.setIntendedFor = $root=>{

    // Loop through subjects
    for (const subject in $root.subs) {
        
        // Loop through sessions
        const sessions = $root.subs[subject].sess
        for (const session in sessions) {

            // Determine unique sectionIDs
            let allSectionIDs = sessions[session].objects.map(function (e) {
                return e.analysisResults.section_ID
            });
            let sectionIDs = Array.from(new Set(allSectionIDs))

            // Loop through sections
            sectionIDs.forEach(sectionID=> {

                // Determine func/bold objects
                let funcObjs = sessions[session].objects.filter(function (e) {
                    return (e._type == 'func/bold' && !e._exclude && e.analysisResults.section_ID == sectionID)
                });

                // Determine dwi/dwi objects
                let dwiObjs = sessions[session].objects.filter(function (e) {
                    return (e._type == 'dwi/dwi' && !e._exclude && e.analysisResults.section_ID == sectionID)
                });

                // Determine spin-echo fmap objects meant for func/bold
                let fmapFuncObjs = sessions[session].objects.filter(function (e) {
                    return ((e._type.startsWith('fmap') && !e._exclude && e.forType == 'func/bold' && e.analysisResults.section_ID == sectionID) && (!e._type.includes('mag') || !e._type.includes('phase')))
                });

                // Determine spin-echo fmap objects meant for dwi/dwi
                let fmapDwiObjs = sessions[session].objects.filter(function (e) {
                    return ((e._type.startsWith('fmap') && !e._exclude && e.forType == 'dwi/dwi' && e.analysisResults.section_ID == sectionID) && (!e._type.includes('mag') || !e._type.includes('phase')))
                });

                // Determine magnitude/phasediff fmap objects meant for func/bold
                let fmapMagPhasediffObjs = sessions[session].objects.filter(function (e) {
                    return ((e._type.startsWith('fmap') && !e._exclude && e.forType == 'func/bold' && e.analysisResults.section_ID == sectionID) && (e._type.includes('mag') || e._type.includes('phasediff')))
                });

                // Determine magnitude/phase fmap objects meant for func/bold
                let fmapMagPhaseObjs = sessions[session].objects.filter(function (e) {
                    return ((e._type.startsWith('fmap') && !e._exclude && e.forType == 'func/bold' && e.analysisResults.section_ID == sectionID) && (e._type.includes('mag') || e._type.includes('phase1') || e._type.includes('phase2')))
                });

                // Perform fmap QA
                if (funcObjs.length > 0) {

                    let funcIntendedFor = funcObjs.map(function (e) {
                        return e.idx
                    });

                    // Remove all spin-echo fmaps except for last two
                    if (fmapFuncObjs.length > 2) {
                        let badObjs = fmapFuncObjs.slice(0,-2)
                        let goodObjs = fmapFuncObjs.slice(-2)
                        badObjs.forEach(obj=> {
                            obj._exclude = true
                            obj.errors = 'Multiple spin echo field map pairs detected in section; only selecting last pair for BIDS conversion. The other pair acquisition(s) in this section will not be included in the BIDS output'
                        });

                        // Check the final two fmaps for proper PEDs
                        let fmapFuncPEDs = goodObjs.map(function (e) {
                            return e.items[0].sidecar.PhaseEncodingDirection
                        });

                        if (fmapFuncPEDs[0].toString().split('').reverse().join('').slice(-1) == fmapFuncPEDs[1].toString().split('').reverse().join('').slice(-1)) {
                            if ((fmapFuncPEDs[0].length == 2 && fmapFuncPEDs[1].length == 1) || (fmapFuncPEDs[0].length == 1 && fmapFuncPEDs[1].length == 2)) {
                                {}
                            } else {
                                fmapFuncObjs.forEach(obj=> {
                                    obj._exclude = true
                                    obj.errors = 'Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output'
                                });
                            }
                        } else {
                            fmapFuncObjs.forEach(obj=> {
                                obj._exclude = true
                                obj.errors = 'Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output'
                            });
                        }
                    }

                    // Remove spin-echo fmap if only 1 found
                    if (fmapFuncObjs.length == 1) {
                        fmapFuncObjs.forEach(obj=> {
                            obj._exclude = true
                            obj.errors = 'Only one spin echo field map found; need pair. This acquisition will not be included in the BIDS output'
                        });
                    }

                    // Check for proper PEDs for spin-echo pairs
                    if (fmapFuncObjs.length == 2) {
                        let fmapFuncPEDs = fmapFuncObjs.map(function (e) {
                            return e.items[0].sidecar.PhaseEncodingDirection
                        });

                        if (fmapFuncPEDs[0].toString().split('').reverse().join('').slice(-1) == fmapFuncPEDs[1].toString().split('').reverse().join('').slice(-1)) {
                            if ((fmapFuncPEDs[0].length == 2 && fmapFuncPEDs[1].length == 1) || (fmapFuncPEDs[0].length == 1 && fmapFuncPEDs[1].length == 2)) {
                                {}
                            } else {
                                fmapFuncObjs.forEach(obj=> {
                                    obj._exclude = true
                                    obj.errors = 'Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output'
                                });
                            }
                        } else {
                            fmapFuncObjs.forEach(obj=> {
                                obj._exclude = true
                                obj.errors = 'Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output'
                            });
                        }

                        // // For spin-echo field maps, do not include func/bold acquisitions where the PEDs don't match
                        // funcObjs.forEach((obj, idx)=> {
                        //     if (!fmapFuncPEDs.includes(obj.items[0].sidecar.PhaseEncodingDirection)) {
                        //         let funcIntendedFor = funcIntendedFor.filter(e=>e != idx)
                        //     }
                        // });

                        fmapFuncObjs.forEach(obj=> {
                            obj.IntendedFor = funcIntendedFor
                        });

                    }
   

                    // Remove magnitudes & phasediff if less than 3
                    if (fmapMagPhasediffObjs.length < 3) {
                        fmapMagPhasediffObjs.forEach(obj=> {
                            obj._exclude = true
                            obj.errors = 'Need triplet for magnitude/phasediff field maps. This acquisition will not be included in the BIDS output'
                        });
                    }

                    // Remove all magnitudes and phasediff except for last 3
                    if (fmapMagPhasediffObjs.length > 3) {
                        let badObjs = fmapMagPhasediffObjs.slice(0,-3)
                        let goodObjs = fmapMagPhasediffObjs.slice(-3)
                        badObjs.forEach(obj=> {
                            obj._exclude = true
                            obj.errors = 'More than three magnitude/phasediff field map acquisitions found in section. Only selecting most recent three. Others will not be included in the BIDS output'
                        });

                        goodObjs.forEach(obj=> {
                            obj.IntendedFor = funcIntendedFor
                        });

                    }

                    // Remove magnitudes and phases if less than 4
                    if (fmapMagPhaseObjs.length < 4) {
                        fmapMagPhaseObjs.forEach(obj=> {
                            obj._exclude = true
                            obj.errors = 'Need four images (2 magnitude, 2 phase). This acquisition will not be included in the BIDS output'
                        });
                    }

                    // Remove all magnitudes and phases except for last 4
                    if (fmapMagPhaseObjs.length < 4) {
                        let badObjs = fmapMagPhaseObjs.slice(0,-4)
                        let goodObjs = fmapMagPhaseObjs.slice(-4)
                        badObjs.forEach(obj=> {
                            obj._exclude = true
                            obj.errors = 'Multiple images sets of (2 magnitude, 2 phase) field map acquisitions found in section. Only selecting most recent set. Other(s) will not be included in the BIDS output'
                        });

                        goodObjs.forEach(obj=> {
                            obj.IntendedFor = funcIntendedFor
                        });
                    }
                } else {
                    fmapFuncObjs.forEach(obj=> {
                        obj._exclude = true
                        obj.errors = 'No valid func/bold acquisitions found in section, spin echo field map pair will not be included in the BIDS output'
                    });

                    fmapMagPhasediffObjs.forEach(obj=> {
                        obj._exclude = true
                        obj.errors = 'No valid func/bold acquisitions found in section, magnitude & phasediff field maps will not be included in the BIDS output'
                    });

                    fmapMagPhaseObjs.forEach(obj=> {
                        obj._exclude = true
                        obj.errors = 'No valid func/bold acquisitions found in section, magnitude & phase field maps will not be included in the BIDS output'
                    });
                }

                // Remove fmap meant for dwi/dwi acquisition(s) if no valid dwi/dwi found in section
                if (dwiObjs.length == 0 && fmapDwiObjs.length > 0) {
                    fmapDwiObjs.forEach(obj=> {
                        obj._exclude = true
                        obj.errors = 'No valid dwi/dwi acquisitions found in section, spin echo field map will not be included in the BIDS output'
                    });
                }

                // Remove fmap meant for dwi/dwi if more than 1 fmap
                if (fmapDwiObjs.length > 1) {
                    fmapDwiObjs.forEach(obj=> {
                        obj._exclude = true
                        obj.errors = 'Multiple spin echo field maps (meant for dwi/dwi) detected in section; only selecting last one for BIDS conversion. The other fmap acquisition(s) in this section will not be included in the BIDS output'
                    });
                }

                if (fmapDwiObjs.length == 1) {
                    let dwiIntendedFor = dwiObjs.map(function (e) {
                        return e.idx
                    });

                    fmapDwiObjs.forEach(obj=> {
                        obj.IntendedFor = dwiIntendedFor
                    });
                }                
            });
        }
    }     
}
