
exports.setIntendedFor = $root=>{

    for (const subject in $root.subs) {
        const sessions = $root.subs[subject].sess

        for (const session in sessions) {


            let sectionIDs = sessions[session].objects.map(function (e) {
                return e.analysisResults.section_ID
            });
            console.log(sectionIDs)

            let funcIndices = sessions[session].objects.map(function (e) {
                if (e._type == 'func/bold' && !e._exclude) {
                    return e.idx
                }
            });
            console.log(funcIndices)



            // let dwiIndices = []
            // let dwiPEDs = []
            // let fmapFuncIndices = []
            // let fmapDwiIndices = []
            // let fmapMagPhaseIndices = []
            // let fmapMagPhasediffIndices = []
            // let fmapFuncPEDs = []
            // let fmapDwiPEDs = []
            // let funcIndices = []
            // let funcPEDs = []

            // section.forEach(object=> {
            //     console.log(object.analysisResults.section_ID)
            // });

            //     // Go through objects list and get values    
            //     if (object._type == 'func/bold' && !object._exclude) {
            //         funcIndices.push(object.idx)
            //         funcPEDs.push(object.items[0].sidecar.PhaseEncodingDirection)
            //     }

            //     if (object._type == 'dwi/dwi' && !object._exclude) {
            //         object.items.forEach(item=>{
            //             if (item.name == 'json') {
            //                 dwiIndices.push(object.idx)
            //                 dwiPEDs.push(item.sidecar.PhaseEncodingDirection)
            //             }
            //         });
            //     }

            //     if (object._type.startsWith('fmap') && !object._exclude) {
            //         if (object._type.includes('mag') || object._type.includes('phasediff')) {
            //             fmapMagPhasediffIndices.push(object.idx)
            //         } else if (object._type.includes('mag') || object._type.includes('phase1') || object._type.includes('phase2')) {
            //             fmapMagPhaseIndices.push(object.idx)
            //         } else {
            //             if (object.forType == 'func/bold') {
            //                 fmapFuncIndices.push(object.idx)
            //                 fmapFuncPEDs.push(object.items[0].sidecar.PhaseEncodingDirection)
            //             } else {
            //                 fmapDwiIndices.push(object.idx)
            //                 fmapDwiPEDs.push(object.items[0].sidecar.PhaseEncodingDirection)
            //             }
            //         }
            //     }
            // });

            // section.forEach(object=> {

            //     if (funcIndices.length > 0) {
            //         // Remove spin-echo fmap if only 1 found in section
            //         if (fmapFuncIndices.length == 1) {
            //             for (const i of fmapFuncIndices) {
            //                 console.log(object.exclude)
            //                 object[i].exclude = true
            //                 object[i].errors = 'Only one spin echo field map found; need pair. This acquisition will not be included in the BIDS output'
            //             }
            //         // Remove all spin-echo fmaps except for last two
            //         } else if (fmapFuncIndices.length > 2) {
            //             let bad = fmapFuncIndices.slice(-2)
            //             for (const i of bad) {
            //                 $root.object[i].exclude = true
            //                 $root_objects[i].errors = 'Multiple spin echo field map pairs detected in section; only selecting last pair for BIDS conversion. The other pair acquisition(s) in this section will not be included in the BIDS output'
            //             }
            //         // Check that spin-echo pair has opposite PEDs
            //         } else if (fmapFuncIndices.length == 2) {
            //             if (fmapFuncPEDs[0].toString().split('').reverse().join('').slice(-1) == fmapFuncPEDs[1].toString().split('').reverse().join('').slice(-1)) {
            //                 if ((fmapFuncPEDs[0].length == 2 && fmapFuncPEDs[1].length == 1) || (fmapFuncPEDs[0].length == 1 && fmapFuncPEDs[1].length == 2)) {
            //                     {}
            //                 } else {
            //                     $root_objects[i].exclude = true
            //                     $root_objects[i].errors = 'Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output'
            //                 }
            //             } else {
            //                 $root.objects[i].exclude = true
            //                 $root_objects[i].errors = 'Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output'
            //             }

            //         // Remove magnitudes & phasediff if less than 3
            //         } else if (fmapMagPhasediffIndices.length < 3) {
            //             for (const i of fmapMagPhasediffIndices) {
            //                 $root.objects[i].exclude = true
            //                 $root.objects[i].errors = 'Need triplet for magnitude/phasediff field maps. This acquisition will not be included in the BIDS output'
            //             }
            //         // Remove all magnitudes and phasediff except for last 3
            //         } else if (fmapMagPhasediffIndices.length > 3) {
            //             let bad = fmapMagPhasediffIndices.slice(-3)
            //             for (const i of bad) {
            //                 $root.objects[i].exclude = true
            //                 $root.objects[i].errors = 'More than three magnitude/phasediff field map acquisitions found in section. Only selecting most recent three. Others will not be included in the BIDS output'
            //             }
            //         // Remove magnitudes and phases if less than 4
            //         } else if (fmapMagPhaseIndices.length < 4) {
            //             for (const i of fmapMagPhaseIndices) {
            //                 $root.objects[i].exclude = true
            //                 $root.objects[i].errors = 'Need four images (2 magnitude, 2 phase). This acquisition will not be included in the BIDS output'
            //             }
            //         // Remove all magnitudes and phases except for last 4
            //         } else if (fmapMagPhaseIndices.length > 4) {
            //             let bad = fmapMagPhaseIndices.slice(-4)
            //             for (const i of bad) {
            //                 $root.objects[i].exclude = true
            //                 $root.objects[i].errors = 'Multiple images sets of (2 magnitude, 2 phase) field map acquisitions found in section. Only selecting most recent set. Other(s) will not be included in the BIDS output'
            //             }
            //         }
            //     } else {
            //         if (fmapFuncIndices.length > 0) {
            //             for (const i of fmapFuncIndices) {
            //                 $root.objects[i].exclude = true
            //                 $root_objects[i].errors = 'No valid func/bold acquisitions found in section, spin echo field map pair will not be included in the BIDS output'
            //             }
            //         } else if (fmapMagPhasediffIndices.length > 0) {
            //             for (const i of fmapMagPhasediffIndices) {
            //                 $root.objects[i].exclude = true
            //                 $root.objects[i].errors = 'No valid func/bold acquisitions found in section, magnitude & phasediff field maps will not be included in the BIDS output'
            //             }
            //         } else if (fmapMagPhaseIndices.length > 0) {
            //             for (const i of fmapMagPhaseIndices) {
            //                 $root.objects[i].exclude = true
            //                 $root.objects[i].errors = 'No valid func/bold acquisitions found in section, magnitude & phase field maps will not be included in the BIDS output'
            //             }
            //         }
            //     }

            //     if (dwiIndices.length == 0 && fmapDwiIndices.length > 0) {
            //         for (const i of fmapDwiIndices) {
            //             $root.objects[i].exclude = true
            //             $root.objects[i].errors = 'No valid dwi/dwi acquisitions found in section, field map will not be included in the BIDS output'
            //         }
            //     }

            //     // For spin-echo field maps, do not include func/bold (or dwi/dwi) acquisitions where the PEDs don't match
            //     let intendedFor = funcIndices
            //     if (funcPEDs.length > 0 && fmapFuncPEDs.length > 0) {
            //         funcIndices.forEach((funcIndex, idx)=>{
            //             if (!fmapFuncPEDs.includes(funcPEDs[idx])) {
            //                 intendedFor = intendedFor.filter(v=>v != funcIndex)
            //                 $root.objects[funcIndex].IntendedFor = intendedFor
            //             }
            //         });
            //     }

            //     // Enter the IntendedFor fields for the fmaps
            //     for (const i of fmapFuncIndices) {
            //         $root.objects[i].IntendedFor = funcIndices
            //     }
            //     for (const i of fmapMagPhasediffIndices) {
            //         $root.objects[i].IntendedFor = funcIndices
            //     }
            //     for (const i of fmapMagPhaseIndices) {
            //         $root.objects[i].IntendedFor = funcIndices
            //     }
            // });
            // console.log(funcIndices)
        }
    }     
}
