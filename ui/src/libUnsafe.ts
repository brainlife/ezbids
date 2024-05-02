import e from 'cors';
// import * as fs from 'fs';

import { Series, IObject, OrganizedSession, OrganizedSubject, IEzbids, IBIDSEvent, MetadataFields } from './store';

import aslYaml from '../src/assets/schema/rules/sidecars/asl.yaml';
import petYaml from '../src/assets/schema/rules/sidecars/pet.yaml';

import metadata_types from '../src/assets/schema/rules/sidecars/metadata_types.yaml';
import { faNewspaper } from '@fortawesome/free-solid-svg-icons';

//deepEqual and isPrimitive functions come from https://stackoverflow.com/a/45683145
export function deepEqual(obj1: any, obj2: any) {
    //Determines if two arrays are equal or not. Better then JSON.stringify
    //because this accounts for different ordering; only cares about whether
    //keys and values match.

    if (obj1 === obj2)
        // it's just the same object. No need to compare.
        return true;

    if (isPrimitive(obj1) && isPrimitive(obj2))
        // compare primitives
        return obj1 === obj2;

    if (Object.keys(obj1).length !== Object.keys(obj2).length) return false;

    // compare objects with same number of keys
    for (let key in obj1) {
        if (!(key in obj2)) return false; //other object doesn't have this prop
        if (!deepEqual(obj1[key], obj2[key])) return false;
    }

    return true;
}

export function isPrimitive(obj: any) {
    return obj !== Object(obj);
}

export function setVolumeThreshold($root: IEzbids) {
    /*
    Determine volume threshold for all func/bold acquisitions in dataset and set
    to exclude if the number of volumes does not meet the volume threshold. Threshold 
    calculated based on the expected number of volumes collected in a 1-minute time frame,
    with the formula (60-sec / tr), where tr == RepetitionTime
    */
    $root.objects.forEach((o: IObject) => {
        //update analysisResults.warnings in case user went back to Series and adjusted things
        if (o._type === 'func/bold') {
            let tr: number = o.items[0].sidecar.RepetitionTime;
            let numVolumes: any = o.analysisResults.NumVolumes;
            let numVolumes1min: number = Math.floor(60 / tr);
            if (numVolumes <= numVolumes1min) {
                o.exclude = true;
                o._exclude = true;
                o.analysisResults.warnings = [
                    `This func/bold sequence contains ${numVolumes} volumes, which is \
                less than the threshold value of ${numVolumes1min} volumes, calculated by the expected number of \
                volumes in a 1 min time frame. This acquisition will thus be excluded from BIDS conversion unless \
                unexcluded. Please modify if incorrect.`,
                ];
            }
        } else {
            // In case user changes sequence on dataset review to func/bold and then back, remove the volume threshold warning
            if (o.analysisResults.warnings.length) {
                for (const warn in o.analysisResults.warnings) {
                    let index: number = o.analysisResults.warnings[warn].indexOf('This func/bold sequence contains');
                    if (index !== -1) {
                        o.analysisResults.warnings.splice(index, 1);
                    }
                }
            }
        }
    });
}

export function setSectionIDs($root: IEzbids) {
    /*
    Set section_id value for each acquisition, beginning with value of 1. A section is
    ezBIDS jargin for each time participant comes out and then re-enters scanner. Each time
    a non-adjacent localizer is detected, the section_id value is increased by 1. The
    section_id value helps for determining fmap IntendedFor mapping, where field maps
    cannot be applied to acquisitions from different sections.
    */

    $root._organized.forEach((subGroup: OrganizedSubject) => {
        subGroup.sess.forEach((sesGroup: OrganizedSession) => {
            let protocol: IObject[] = sesGroup.objects;
            let sectionID = 1;
            let obj_idx = 0;
            let message = '';
            let previousMessage = '';
            protocol.forEach((obj: IObject) => {
                if ($root.series[protocol[obj_idx].series_idx]) {
                    message = $root.series[protocol[obj_idx].series_idx].message;
                }

                if (obj_idx !== 0 && $root.series[protocol[obj_idx - 1].series_idx]) {
                    previousMessage = $root.series[protocol[obj_idx - 1].series_idx].message;
                }

                if (
                    obj_idx !== 0 &&
                    message.includes('localizer') &&
                    (previousMessage === '' || !previousMessage.includes('localizer'))
                ) {
                    sectionID++;
                    obj.analysisResults.section_id = sectionID;
                } else {
                    obj.analysisResults.section_id = sectionID;
                }
                obj_idx++;
            });
        });
    });
}

export function funcQA($root: IEzbids) {
    /*
    1). If func/bold acquisition is excluded, warn users that corresponding
    func/sbref, and func/bold (part-phase) should all excluded as well,
    if they exist.

    2). Warn users about func/sbref if its PhaseEncodingDirection (PED) is different
    from the corresponding func/bold PED.
    */
    $root.objects.forEach((o: IObject) => {
        // // #1

        // //update analysisResults.warnings in case user went back to Series and adjusted things
        // if (o._type == "func/bold" && o.exclude == false && (!o._entities.part || o._entities.part == "mag")) {
        //     let funcBoldEntities = o._entities
        //     let goodFuncSBRef = $root.objects.filter(e=>e._type == "func/sbref" && deepEqual(e._entities, funcBoldEntities))
        //     let goodFuncBoldPhase = $root.objects.filter(e=>e._type == "func/bold" && e._entities.part == "phase" && deepEqual(Object.keys(e._entities).filter(e=>e != "part"), funcBoldEntities))

        //     for (const good of [goodFuncSBRef, goodFuncBoldPhase]) {
        //         good.forEach((g:IObject) => {
        //             g.analysisResults.warnings = []
        //         })
        //     }
        // }

        // //now check for corresponding func/bold === exclude, and go from there
        // if (o._type === "func/bold" && o.exclude && (!o._entities.part || o._entities.part == "mag" || o._entities.part == "part")) {
        //     let funcBoldEntities = o._entities
        //     let badFuncSBRef = $root.objects.filter(e=>e._type == "func/sbref" && deepEqual(e._entities, funcBoldEntities))
        //     let badFuncBoldPhase = $root.objects.filter(e=>e._type == "func/bold" && e._entities.part == "phase" && deepEqual(Object.keys(e._entities).filter(e=>e != "part"), funcBoldEntities))

        //     for (const bad of [badFuncSBRef, badFuncBoldPhase]) {
        //         bad.forEach((b:IObject) => {
        //             o.exclude = true
        //             o.analysisResults.warnings = [`The corresponding func/bold (#${o.series_idx}) to this acquisition \
        //             has been set to exclude from BIDS conversion. Since this func/sbref is linked, it will also be \
        //             excluded from conversion. Please modify if incorrect.`]
        //         })
        //     }
        // }

        // #2
        if (o._type === 'func/bold' && !o.exclude && (!o._entities.part || o._entities.part === 'mag')) {
            let boldEntities = o._entities;
            let boldPED = o.items[0].sidecar.PhaseEncodingDirection;
            let badSBRef = $root.objects
                .filter(
                    (e) =>
                        e._type === 'func/sbref' &&
                        deepEqual(e._entities, boldEntities) &&
                        e.items[0].sidecar.PhaseEncodingDirection != boldPED
                )
                .map((e) => e.idx);
            badSBRef.forEach((bad) => {
                // $root.objects[bad].exclude = true
                $root.objects[bad].analysisResults.warnings = [
                    `Functional sbref has a different PhaseEncodingDirection than its corresponding functional bold (#${o.series_idx}). This is likely a data error, therefore this sbref should be excluded from BIDS conversion.`,
                ];
            });
        }
    });
}

export function fmapQA($root: IEzbids) {
    /* Generate warning(s) duplicate field maps (or not enough) are detected.

    TODO: generate warning(s) if Pepolar field maps don't have opposite phase encoding directions
    */

    $root._organized.forEach((subGroup: OrganizedSubject) => {
        subGroup.sess.forEach((sesGroup: OrganizedSession) => {
            // Determine unique sectionIDs
            let allSectionIDs: number[] = sesGroup.objects.map((e) => e.analysisResults.section_id);
            let sectionIDs = Array.from(new Set(allSectionIDs));

            // Loop through sections
            sectionIDs.forEach((s: number) => {
                let section = sesGroup.objects.filter(
                    (o) => o.analysisResults.section_id === s && !o._exclude && o._type != 'exclude'
                );

                // https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#types-of-fieldmaps

                // case #1: Phase-difference map and at least one magnitude sequence
                let fmapMagPhasediffObjs = section.filter(function (o) {
                    return (
                        o._type === 'fmap/magnitude1' || o._type === 'fmap/magnitude2' || o._type === 'fmap/phasediff'
                    );
                });

                let fmapMagPhasediffCheck = fmapMagPhasediffObjs.filter((o) => o._type === 'fmap/phasediff'); //since cases 1 & 2 can have "fmap/magnitude1", check for "fmap/phasediff to determine case 1"
                if (!fmapMagPhasediffCheck.length) {
                    fmapMagPhasediffObjs = [];
                }

                // case #2: Two phase maps and two magnitude maps
                let fmapMagPhaseObjs = section.filter(function (o) {
                    return (
                        o._type === 'fmap/magnitude1' ||
                        o._type === 'fmap/magnitude2' ||
                        o._type === 'fmap/phase1' ||
                        o._type === 'fmap/phase2'
                    );
                });

                let fmapMagPhaseCheck = fmapMagPhaseObjs.filter((o) => o._type === 'fmap/phase1'); //since cases 1 & 2 can have "fmap/magnitude1", check for "fmap/phase1 to determine case 2"
                if (!fmapMagPhaseCheck.length) {
                    fmapMagPhaseObjs = [];
                }

                // case #3: Direct field mapping
                let fmapDirectObjs = section.filter(function (o) {
                    return o._type === 'fmap/magnitude' || o._type === 'fmap/fieldmap';
                });

                //case #4: Multiple phase encoding direction ("pepolar")
                let fmapPepolar = section.filter((o) => o._type === 'fmap/epi');

                /*
                In addition to the fmap cases listed above, other field maps exist.
                For list of these [quantitative MRI] field maps, see
                https://github.com/bids-standard/bids-specification/blob/master/src/schema/rules/datatypes/fmap.yaml and
                https://bids-specification.readthedocs.io/en/stable/99-appendices/11-qmri.html
                */

                let fmapTB1DAM = section.filter((o) => o._type === 'fmap/TB1DAM'); //pair
                let fmapTB1EPI = section.filter((o) => o._type === 'fmap/TB1EPI'); //pair
                let fmapTB1AFI = section.filter((o) => o._type === 'fmap/TB1AFI'); //pair
                let fmapTB1TFL = section.filter((o) => o._type === 'fmap/TB1TFL'); //pair
                let fmapTB1RFM = section.filter((o) => o._type === 'fmap/TB1RFM'); //pair
                let fmapRB1COR = section.filter((o) => o._type === 'fmap/RB1COR'); //pair
                let fmapTB1SRGE = section.filter((o) => o._type === 'fmap/TB1SRGE'); //pair
                let fmapTB1map = section.filter((o) => o._type === 'fmap/TB1map'); //single
                let fmapRB1map = section.filter((o) => o._type === 'fmap/RB1map'); //single

                /* Check for duplicate fmaps (or not enough fmaps). If so, generate validation
                warning for the duplicate(s) or missing field maps. ezBIDS assumes that the duplicates
                are the first fmap [sets], and then the last fmap(s) in the section are what user want.
                If not, they can ignore the warning(s) or make modifications as they see fit.
                */

                if (fmapMagPhasediffObjs.length) {
                    // for case #1, there can be a pair (magnitude1, phasediff) or a triplet (magnitude1, magnitude2, phasediff)
                    if (fmapMagPhasediffObjs.length == 1) {
                        fmapMagPhasediffObjs.forEach((o: IObject) => {
                            o.analysisResults.warnings.push(
                                "There doesn't appear to be a full field map pair (magnitude1, phasediff) or triplet (magnitude1, magnitude2, phasediff). It is highly recommended that this acquistion be excluded from BIDS conversion, as it doesn't form a complete pair/triplet."
                            );
                        });
                    }
                    if (fmapMagPhasediffObjs.length > 3) {
                        fmapMagPhasediffObjs.forEach((o: IObject) => {
                            o.analysisResults.warnings.push(
                                'There appear to be too many field maps of this kind, the max allowed for this kind of field map is a triplet (magnitude1, magnitude2, phasediff). There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.'
                            );
                        });
                    }
                }

                if (fmapMagPhaseObjs.length) {
                    // for case #2, there must be a set of 4 (phase1, phase2, magnitude1, magnitude2)
                    if (fmapMagPhaseObjs.length < 4) {
                        fmapMagPhaseObjs.forEach((o: IObject) => {
                            o.analysisResults.warnings.push(
                                "There doesn't appear to be a full field map set (phase1, phase2, magnitude1, magnitude2) for this kind of field maps. It is highly recommended that this fmap acquisition be excluded from BIDS conversion, as it is incomplete (i.e. doesn't form complete set of 4)."
                            );
                        });
                    }
                    if (fmapMagPhaseObjs.length > 4) {
                        fmapMagPhaseObjs.forEach((o: IObject) => {
                            o.analysisResults.warnings.push(
                                'There appear to be too many field maps of this kind, only a set (phase1, phase2, magnitude1, magnitude2) is allowed for this kind of field map. There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.'
                            );
                        });
                    }
                }

                if (fmapDirectObjs.length) {
                    // for case #3, there must be a pair (magnitude, fieldmap)
                    if (fmapDirectObjs.length < 2) {
                        fmapDirectObjs.forEach((o: IObject) => {
                            o.analysisResults.warnings.push(
                                "There doesn't appear to be a field map pair (magnitude, fieldmap) for this kind of field map. It is highly recommended that this fmap acquisition be excluded from BIDS conversion, as it is incomplete (i.e. doesn't form pair)."
                            );
                        });
                    }
                    if (fmapDirectObjs.length > 2) {
                        fmapDirectObjs.forEach((o: IObject) => {
                            o.analysisResults.warnings.push(
                                'There appear to be too many field maps of this kind, only a pair (magnitude, fieldmap) is allowed for this kind of field map. There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.'
                            );
                        });
                    }
                }

                if (fmapDirectObjs.length > 0) {
                    // for case #4, there must be a pair (epi, epi)
                    if (fmapPepolar.length < 2) {
                        fmapPepolar.forEach((o: IObject) => {
                            o.analysisResults.warnings.push(
                                "There doesn't appear to be a pair for this kind of field map. It is highly recommended that this fmap acquisition be excluded from BIDS conversion, as it is incomplete (i.e. doesn't form pair)."
                            );
                        });
                    }
                    if (fmapPepolar.length > 2) {
                        fmapPepolar.forEach((o: IObject) => {
                            o.analysisResults.warnings.push(
                                'There appear to be too many field maps of this kind, only a pair is allowed for this kind of field map. There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.'
                            );
                        });
                    }
                }

                // several of the quantitative MRI field maps come in pairs, so validate them the same way
                for (const fmap of [
                    fmapTB1EPI,
                    fmapTB1AFI,
                    fmapTB1TFL,
                    fmapTB1RFM,
                    fmapRB1COR,
                    fmapTB1SRGE,
                    fmapTB1DAM,
                ]) {
                    if (fmap.length) {
                        if (fmap.length < 2) {
                            fmap.forEach((o: IObject) => {
                                o.analysisResults.warnings.push(
                                    "There doesn't appear to be a pair for this kind of field map. It is highly recommended that this fmap acquisition be excluded from BIDS conversion, as it is incomplete (i.e. doesn't form pair)."
                                );
                            });
                        }
                        if (fmap.length > 2) {
                            fmap.forEach((o: IObject) => {
                                o.analysisResults.warnings.push(
                                    'There appear to be too many field maps of this kind, only a pair is allowed for this kind of field map. There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.'
                                );
                            });
                        }
                    }
                }
                // some of the quantitative MRI field maps come as a single acquisition, so validate them the same way
                for (const fmap of [fmapTB1map, fmapRB1map]) {
                    if (fmap.length) {
                        if (fmap.length > 1) {
                            fmap.forEach((o: IObject) => {
                                o.analysisResults.warnings.push(
                                    'There appear to be too many field maps of this kind, only a single acquisition for this kind of field map is allowed. There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.'
                                );
                            });
                        }
                    }
                }
            });
        });
    });
}

export function setRun($root: IEzbids) {
    // Set run entity label for all objects, if appropriate.
    // Applied on the Dataset Review page.

    // Loop through subjects
    $root._organized.forEach((subGroup: OrganizedSubject) => {
        // Loop through sessions
        subGroup.sess.forEach((sesGroup: OrganizedSession) => {
            sesGroup.objects.forEach((obj: IObject) => {
                // leave two entity labels out for now: part and run. The part entity could have a pairing (mag/phase or real/imag), and we're interested in the run entity

                let targetEntities = Object.fromEntries(
                    Object.entries(obj._entities).filter(([key]) => key !== 'part' && key !== 'run' && key !== 'echo')
                ); // REFERENCE
                // let targetEntities = Object.fromEntries(Object.entries(obj._entities).filter(([key])=>key !== "part" && key !== "run"))

                let initialGrouping = sesGroup.objects.filter(
                    (e) =>
                        e._type !== 'exclude' &&
                        !e._exclude &&
                        e._type === obj._type &&
                        e._type !== 'func/events' && // let users specify the run number for func/events files
                        deepEqual(
                            Object.fromEntries(
                                Object.entries(e._entities).filter(
                                    ([key]) => key !== 'part' && key !== 'run' && key !== 'echo'
                                )
                            ),
                            targetEntities
                        )
                );

                if (initialGrouping.length) {
                    // Sort this new array by idx (i.e. order in which the sequences were collected in the scanner)
                    initialGrouping.sort((a, b) => a.idx - b.idx);

                    let setRun = false;
                    if (initialGrouping.length > 1) {
                        setRun = true;
                        // } else if (initialGrouping.length === 1 && (initialGrouping[0]._type.includes("anat") || initialGrouping[0]._type.includes("func"))) { // might need to add conditional for not having func/events
                    } else if (initialGrouping.length === 1 && initialGrouping[0]._type.includes('func')) {
                        // might need to add conditional for not having func/events
                        setRun = true;
                    }

                    if (setRun) {
                        let run = 1;
                        initialGrouping.forEach((o: IObject) => {
                            if (o._entities.part) {
                                if (['mag', 'real'].includes(o._entities.part)) {
                                    if (o._entities.echo) {
                                        if (o._entities.echo === '1') {
                                            o._entities.run = run.toString();
                                            o.entities.run = o._entities.run;
                                            run++;
                                        } else {
                                            // echo > 1
                                            o._entities.run = (run - 1).toString();
                                            o.entities.run = o._entities.run;
                                        }
                                    } else {
                                        // no echo entity
                                        o._entities.run = run.toString();
                                        o.entities.run = o._entities.run;
                                        run++;
                                    }
                                } else if (['phase', 'imag'].includes(o._entities.part)) {
                                    // part entity is "phase" or "imag"

                                    let corresponding_part = '';
                                    if (o._entities.part === 'phase') {
                                        corresponding_part = 'mag';
                                    } else {
                                        corresponding_part = 'real';
                                    }

                                    if (o._entities.echo) {
                                        let correspondingFuncMag = initialGrouping.filter(
                                            (e) =>
                                                e._entities.part === corresponding_part &&
                                                e._type === o._type &&
                                                e._entities.echo === o._entities.echo
                                        );

                                        if (!correspondingFuncMag.length) {
                                            o._exclude = true;
                                            o.exclude = true;
                                            o.validationWarnings = [
                                                'There is no corresponding ' +
                                                    o._type +
                                                    ' (part-' +
                                                    corresponding_part +
                                                    ', echo-' +
                                                    o._entities.echo +
                                                    ') sequence, therefore this sequence will be excluded from BIDS conversion',
                                            ];
                                        } else {
                                            let correspondingFuncMagFinal = correspondingFuncMag.filter(
                                                (e) =>
                                                    e.ModifiedSeriesNumber ===
                                                    (Number(o.ModifiedSeriesNumber) - 1).toString()
                                            );
                                            if (!correspondingFuncMagFinal.length) {
                                                o._exclude = true;
                                                o.exclude = true;
                                                o.validationWarnings = [
                                                    'There is no corresponding ' +
                                                        o._type +
                                                        ' (part-part-' +
                                                        corresponding_part +
                                                        ') sequence, therefore this sequence will be excluded from BIDS conversion',
                                                ];
                                            } else {
                                                o._entities.run = correspondingFuncMagFinal[0]._entities.run;
                                                o.entities.run = o._entities.run;
                                            }
                                        }
                                    } else {
                                        // no echo entity
                                        let correspondingFuncMag = initialGrouping.filter(
                                            (e) =>
                                                e._entities.part === corresponding_part &&
                                                ((e.idx === o.idx - 1 && e._type === o._type) ||
                                                    (e.idx === o.idx - 2 && e._type === o._type))
                                        );

                                        if (!correspondingFuncMag.length) {
                                            o._exclude = true;
                                            o.exclude = true;
                                            o.validationWarnings = [
                                                'There is no corresponding ' +
                                                    o._type +
                                                    ' (part-part-' +
                                                    corresponding_part +
                                                    ') sequence, therefore this sequence will be excluded from BIDS conversion',
                                            ];
                                        } else {
                                            o._entities.run = correspondingFuncMag[0]._entities.run;
                                            o.entities.run = o._entities.run;
                                        }
                                    }
                                }
                            } else {
                                // no part entity
                                if (o._entities.echo) {
                                    if (o._entities.echo === '1') {
                                        o._entities.run = run.toString();
                                        o.entities.run = o._entities.run;
                                        run++;
                                    } else {
                                        o._entities.run = (run - 1).toString();
                                        o.entities.run = o._entities.run;
                                    }
                                } else {
                                    o._entities.run = run.toString();
                                    o.entities.run = o._entities.run;
                                    run++;
                                }
                            }
                        });
                    } else {
                        initialGrouping.forEach((o: IObject) => {
                            o._entities.run = '';
                            o.entities.run = o._entities.run;
                        });
                    }
                }
            });
        });
    });
}

export function setIntendedFor($root: IEzbids) {
    // Apply fmap intendedFor mapping, based on user specifications on Series page.

    function isNumberInObject(obj: number[], number: number) {
        for (const key in obj) {
            if (obj.hasOwnProperty(key) && obj[key] === number) {
                return true;
            }
        }
        return false;
    }

    // Loop through subjects
    $root._organized.forEach((subGroup: OrganizedSubject) => {
        subGroup.sess.forEach((sesGroup: OrganizedSession) => {
            // Determine unique sectionIDs
            let allSectionIDs = sesGroup.objects.map((e) => e.analysisResults.section_id);
            let sectionIDs = Array.from(new Set(allSectionIDs));

            // Loop through sections
            sectionIDs.forEach((s: number) => {
                let section = sesGroup.objects.filter(
                    (e) => e.analysisResults.section_id === s && !e._exclude && e._type !== 'exclude'
                );

                let allDWIs = section.filter((d) => d._type === 'dwi/dwi');
                let allDWIfmaps = section.filter(
                    (d) => d._type === 'fmap/epi' && d.message.includes('corresponding bval/bvec files')
                );

                let DWIfmapWorflow = false;
                if (allDWIs.length === allDWIfmaps.length) {
                    DWIfmapWorflow = true;
                }

                section.forEach((obj: IObject) => {
                    //add IntendedFor information
                    if (obj._type.startsWith('fmap/') || obj._type === 'perf/m0scan') {
                        // if user changes datatype/suffix to fmap of some kind
                        if (!obj.hasOwnProperty('IntendedFor')) {
                            Object.assign(obj, { IntendedFor: [] });
                        } else {
                            if (obj.IntendedFor === null) {
                                obj.IntendedFor = [];
                            }
                        }

                        /*
                        Could have an issue where the fmap/epi pertains to a DWI b0map sequence. In certain cases,
                        there may be a one-to-one correspondence, so don't let this fmap pertain to all if that's
                        the case.
                        */
                        if (obj.message.includes('corresponding bval/bvec files')) {
                            if (DWIfmapWorflow) {
                                // one-to-one correspondence between DWI and a DWI b0map (mapped as fmap/epi)
                                let correspondingDWI = section.filter(
                                    (c) =>
                                        c._type === 'dwi/dwi' &&
                                        c._entities.direction.split('').reverse().join('') ===
                                            obj._entities.direction &&
                                        c._entities.run === obj._entities.run
                                );
                                if (correspondingDWI.length === 1) {
                                    let IntendedForID = correspondingDWI[0].idx;
                                    if (obj.IntendedFor !== undefined) {
                                        if (!isNumberInObject(obj.IntendedFor, IntendedForID)) {
                                            obj.IntendedFor = obj.IntendedFor.concat(IntendedForID);
                                        }
                                    }
                                }
                            }
                        } else {
                            // Otherwise, proceed as usual
                            let correspindingSeriesIntendedFor = $root.series[obj.series_idx].IntendedFor;

                            if (
                                correspindingSeriesIntendedFor !== undefined &&
                                correspindingSeriesIntendedFor !== null
                            ) {
                                correspindingSeriesIntendedFor.forEach((i: number) => {
                                    let IntendedForIDs = section
                                        .filter((o) => o.series_idx === i && o._type !== 'func/events')
                                        .map((o) => o.idx);
                                    if (obj.IntendedFor !== undefined) {
                                        for (const IntendedForID of IntendedForIDs) {
                                            if (!isNumberInObject(obj.IntendedFor, IntendedForID)) {
                                                obj.IntendedFor = obj.IntendedFor.concat(IntendedForID);
                                            }
                                        }
                                    }
                                });
                            }
                        }

                        if (Object.keys(obj.IntendedFor).length !== 0) {
                            obj.IntendedFor?.forEach((e) => {
                                let IntendedForObj = $root.objects.filter((o: IObject) => o.idx === e)[0];
                                if (IntendedForObj.exclude || IntendedForObj._exclude) {
                                    let badIndexKey: number = obj.IntendedFor.indexOf(e);
                                    delete obj.IntendedFor[badIndexKey];
                                }
                            });
                        }
                        if (obj._type.startsWith('fmap/')) {
                            if (Object.keys(obj.IntendedFor).length === 0) {
                                obj.validationWarnings = [
                                    'It is recommended that field map (fmap) sequences have IntendedFor set to at least 1 series ID. This is necessary if you plan on using processing BIDS-apps such as fMRIPrep',
                                ];
                                obj.analysisResults.warnings = obj.validationWarnings;
                            } else {
                                obj.analysisResults.warnings = [];
                                obj.validationWarnings = [];
                            }
                        } else if (obj._type === 'perf/m0scan') {
                            if (Object.keys(obj.IntendedFor).length === 0) {
                                obj.validationErrors = [
                                    'It is required that perfusion m0scan sequences have IntendedFor set to at least 1 series ID.',
                                ];
                            } else {
                                obj.validationErrors = [];
                            }
                        }
                    }

                    // check B0FieldIdentifier and B0FieldSource information
                    if (
                        obj._type &&
                        !obj._type.includes('exclude') &&
                        !obj._type.includes('events') &&
                        !obj._type.startsWith('meg') &&
                        !obj._type.startsWith('pet')
                    ) {
                        Object.assign(obj, { B0FieldIdentifier: [] });
                        Object.assign(obj, { B0FieldSource: [] });
                        if ('B0FieldIdentifier' in $root.series[obj.series_idx]) {
                            let correspindingSeriesB0FieldIdentifier = $root.series[obj.series_idx].B0FieldIdentifier;
                            if (correspindingSeriesB0FieldIdentifier) {
                                for (const k of correspindingSeriesB0FieldIdentifier) {
                                    obj.B0FieldIdentifier.push(k);
                                }
                            }
                        }

                        if ('B0FieldSource' in $root.series[obj.series_idx]) {
                            let correspindingSeriesB0FieldSource = $root.series[obj.series_idx].B0FieldSource;
                            if (correspindingSeriesB0FieldSource) {
                                for (const k of correspindingSeriesB0FieldSource) {
                                    obj.B0FieldSource.push(k);
                                }
                            }
                        }
                    }
                });
            });
        });
    });
}

function findMostCommonValue(arr: any) {
    /* Function comes from https://stackoverflow.com/a/20762713

    This function acts as a mode (i.e. finds the most common value in an array).
    */

    return arr
        .sort(
            (a: number | string, b: number | string) =>
                arr.filter((v: number | string) => v === a).length - arr.filter((v: number | string) => v === b).length
        )
        .pop();
}

export function alignEntities($root: IEzbids) {
    /*
    Applied on Dataset Review page
    There are two ways entities are stored:
        1). entities - more top level and reflects user modifications
        2). _entities - more ezBIDS backend and what is automatically displayed
    
    Since we want to give users final say, let their edits/modifications (entities) take precedent.
    */
    $root.objects.forEach((o: IObject) => {
        if (!o._exclude) {
            for (const [key, value] of Object.entries(o.entities)) {
                if (key !== 'subject' && key !== 'session' && value !== '') {
                    o._entities[key] = value;
                }
            }
        }
    });
}

export function validate_B0FieldIdentifier_B0FieldSource(info: Series | IObject) {
    let B0FieldIdentifier = info.B0FieldIdentifier;
    let B0FieldSource = info.B0FieldSource;

    //validate B0FieldIdentifier (only alphanumeric, dash [-], and underscore [_] characters allowed)
    if (B0FieldIdentifier) {
        for (const k of B0FieldIdentifier) {
            if (k && !/^[a-zA-Z0-9-_]*$/.test(k)) {
                info.validationErrors.push(
                    'B0FieldIdentifier ("+k+" selection) contains non-alphanumeric character(s). \
                    The (dash [-] and underscore [_] characters are acceptable'
                );
            }
        }
    }

    //validate B0FieldSource (only alphanumeric, dash [-], and underscore [_] characters allowed)
    if (B0FieldSource) {
        for (const k of B0FieldSource) {
            if (k && !/^[a-zA-Z0-9-_]*$/.test(k)) {
                info.validationErrors.push(
                    'B0FieldSource (#"+k+"-indexed selection) contains non-alphanumeric character(s). \
                    The (dash [-] and underscore [_] characters are acceptable)'
                );
            }
        }
    }
}

export function dwiQA($root: IEzbids) {
    /*
    DWI acquisitions are typically acquired in two ways:

    1). Flipped PED pairs.
    2). One or more DWI acquisitions with one PED and a corresponding b0/fieldmap with opposite PED.

    This QA function checks to see if one of these two conditions are met. If not, a validation warning is
    generated to alert user.
    */
    $root._organized.forEach((subGroup: OrganizedSubject) => {
        subGroup.sess.forEach((sesGroup: OrganizedSession) => {
            let dwiInfo: any[] = [];
            let fmapInfo: any[] = [];
            let protocolObjects: IObject[] = sesGroup.objects;

            for (const protocol of protocolObjects) {
                Object.keys(protocol).forEach((key: string) => {
                    if (key === '_type' && protocol[key] === 'dwi/dwi' && !protocol._exclude) {
                        dwiInfo.push({
                            series_idx: protocol.series_idx,
                            idx: protocol.idx,
                            direction: protocol.PED,
                            fmap: false,
                            oppDWI: false,
                        });
                    }
                });
            }
            let fmapIntendedFor = protocolObjects.filter((t) => t._type.startsWith('fmap/') && !t._exclude);
            fmapIntendedFor.forEach((f) => {
                if (f.IntendedFor === null) {
                    f.IntendedFor = [];
                }
                fmapInfo.push({ IntendedFor: f.IntendedFor });
            });

            if (dwiInfo.length) {
                let dwiDirs = dwiInfo.map((e) => e.direction);

                if (fmapInfo.length) {
                    fmapInfo.forEach((f) => {
                        dwiInfo.forEach((d) => {
                            if (f.IntendedFor.includes(d.series_idx)) {
                                d.fmap = true;
                            }
                            if (dwiDirs.includes(d.direction.split('').reverse().join(''))) {
                                d.oppDWI = true;
                            }
                        });
                    });
                } else {
                    dwiInfo.forEach((d) => {
                        if (dwiDirs.includes(d.direction.split('').reverse().join(''))) {
                            d.oppDWI = true;
                        }
                    });
                }

                dwiInfo.forEach((d) => {
                    let corrProtocolObj = protocolObjects.filter((e) => e.idx == d.idx)[0]; //will always be an index of 1, so just grab the first (i.e. only) index
                    if (!d.fmap && !d.oppDWI) {
                        corrProtocolObj.analysisResults.warnings = [
                            "This dwi/dwi acquisition doesn't appear to have a corresponding dwi/dwi or fmap sequence with a 180 degree flipped phase encoding direction. You may wish to exclude this from BIDS conversion, unless there is a reason for keeping it.",
                        ];
                    } else {
                        corrProtocolObj.analysisResults.warnings = [];
                    }
                });
            }
        });
    });
}

export function petQA($root: IEzbids) {
    $root.objects.forEach((o: IObject) => {
        if (o._type === 'pet/blood') {
            let tsv = o.items.find((e) => e.name === 'tsv');
            let json = o.items.find((e) => e.name === 'json');
            if (tsv !== undefined && json !== undefined) {
                let tsv_headers = Object.values(tsv.headers);
                let metadata = JSON.parse(json.sidecar_json);

                for (const [key, value] of Object.entries(metadata)) {
                    if (key === 'PlasmaAvail' && value === true) {
                        if (!tsv_headers.includes('plasma_radioactivity')) {
                            metadata[key] = false;
                        }
                    }
                    if (key === 'MetaboliteAvail' && value === true) {
                        if (!tsv_headers.includes('metabolite_parent_fraction')) {
                            metadata[key] = false;
                        }
                    }
                    if (key === 'WholeBloodAvail' && value === true) {
                        if (!tsv_headers.includes('whole_blood_radioactivity')) {
                            metadata[key] = false;
                        }
                    }
                    if (key === 'MetaboliteRecoveryCorrectionApplied' && value === true) {
                        if (!tsv_headers.includes('hplc_recovery_fractions')) {
                            metadata[key] = false;
                        }
                    }
                }
                json.sidecar_json = JSON.stringify(metadata, null, 2);
            }
        }
    });
}

export function validateEntities(level: string, info: any) {
    /*
    Ensure entity labels are BIDS appropriate (e.g., specific part entities labels accepted, dir entity
    label capitalized, etc.)
    */
    let entities: any = [];
    if (level === 'Series') {
        entities = info.entities;
    } else if (level === 'Objects') {
        entities = info._entities;
    }

    for (let k in entities) {
        //validate entity (only alpha numeric values allowed)
        if (entities[k] && !/^[a-zA-Z0-9]*$/.test(entities[k])) {
            info.validationErrors.push('The ' + k + ' entity label contains non-alphanumeric character(s).');
        } else {
            // Check specific entities
            if (k === 'direction') {
                /* 
                Ensure direction (dir) entity labels are capitalized (e.g. AP, not ap).
                Can occur when user adds this themselves. Only do this if we have PED
                info (e.g. Philips scanners don't provide this).
                */
                if (entities[k] && entities[k] !== '') {
                    if (entities[k] !== entities[k].toUpperCase()) {
                        info.validationErrors.push(
                            'Please ensure that the phase-encoding direction (dir) entity label is fully capitalized.'
                        );
                    }

                    if (entities[k].toUpperCase() !== info.PED && info.PED !== '') {
                        info.validationWarnings.push(
                            `ezBIDS detects that the direction should be ${info.PED}, not ${entities[k]}. Please verify before continuing`
                        );
                    }
                }
            } else if (k === 'part') {
                // Only mag, phase, real, or imag allowed
                let values = ['mag', 'phase', 'real', 'imag'];
                if (entities[k] && entities[k] !== '') {
                    if (!['mag', 'phase', 'real', 'imag'].includes(entities[k])) {
                        info.validationErrors.push(
                            'Only accepted part entity values are: mag, phase, real, imag. Value must be lower-case'
                        );
                    }
                    for (const i of values) {
                        if (i !== 'imag') {
                            if (i !== 'mag') {
                                if (
                                    entities[k] === i &&
                                    level === 'Series' &&
                                    !info.ImageType.includes(i.toUpperCase())
                                ) {
                                    info.validationWarnings.push(
                                        `ezBIDS detects that this sequence is not part-${i}. Please verify before continuing`
                                    );
                                }
                            }
                        } else {
                            if (entities[k] === i && level === 'Series' && !info.ImageType.includes('IMAGINARY')) {
                                info.validationWarnings.push(
                                    'ezBIDS detects that this sequence is not part-imag. Please verify before continuing'
                                );
                            }
                        }
                    }
                }
            } else if (k === 'mtransfer') {
                // Only on, off values allowed
                if (entities[k] && entities[k] !== '') {
                    if (!['on', 'off'].includes(entities[k])) {
                        info.validationErrors.push(
                            'Only accepted mtransfer entity values are: on, off. Value must be lower-case'
                        );
                    }
                }
            } else if (k === 'hemisphere') {
                // Only R, L values allowed
                if (entities[k] && entities[k] !== '') {
                    if (!['L', 'R'].includes(entities[k])) {
                        info.validationErrors.push(
                            'Only accepted hemisphere entity values are: R, L. Value must be upper-case'
                        );
                    }
                }
            } else if (['run', 'echo', 'flip', 'inversion', 'split', 'chunk'].includes(k)) {
                if (entities[k] && entities[k] !== '') {
                    if (!/^[0-9]*$/.test(entities[k])) {
                        info.validationErrors.push('The ' + k + ' entity can only contain an integer/numeric value.');
                    }
                }
            }
        }
    }
}

export function find_separator(filePath: string, fileData: any) {
    if (filePath.indexOf('.tsv') > -1) {
        return /[ \t]+/;
    } else if (filePath.indexOf('.out') > -1 || filePath.indexOf('.csv') > -1) {
        return /[ ,]+/;
    } else if (filePath.indexOf('.txt') > -1) {
        const data = fileData;
        const lines = data
            .trim()
            .split('\n')
            .map((l: any) => l.trim());
        if (lines[0].indexOf(',') > -1) {
            return /[ ,]+/;
        } else {
            return /[ \t]+/;
        }
    } else if (filePath.indexOf('.xlsx') > -1) {
        return /[ ,]+/;
    } else {
        console.log('ignoring', filePath);
    }

    throw 'unknown file extension';
}

function parseEprimeEvents(fileData: any) {
    const lines = fileData
        .trim()
        .split(/\r|\n/)
        .map((l: any) => l.trim());

    //parse each line
    const trials: any[] = [];
    let headers = null;
    let block: any = {};
    const timing_info = [];
    lines.forEach((line: string) => {
        switch (line) {
            case '*** Header Start ***':
                block = {};
                break;
            case '*** Header End ***':
                headers = block;
                break;
            case '*** LogFrame Start ***':
                block = {};
                break;
            case '*** LogFrame End ***':
                trials.push(block);
                break;
            default:
                const kv = line.split(': ');
                const k = kv[0].toLowerCase();
                const v = kv[1];
                block[k] = v;
        }
        trials.push(block);
    });
    timing_info.push(trials);

    return timing_info[0];
}

export function parseEvents(fileData: any, sep: any) {
    const lines = fileData
        .trim()
        .split(/\r|\n/)
        .map((l: any) => l.trim().replace(/['"]+/g, ''));
    const trials: any[] = [];
    let headers = lines.shift().split(sep);
    const timing_info = [];

    lines.forEach((line: string) => {
        const tokens = line.split(sep);
        if (tokens.length > 1) {
            //need at least two columns for onset and duration
            if (tokens.filter((t) => t.replace(/[^0-9a-z]/gi, '')).length) {
                //filter out lines consisting of only non-alphanumeric characters
                const block: any = {};
                for (let i = 0; i < tokens.length; ++i) {
                    try {
                        const k = headers[i].toLowerCase();
                        const v = tokens[i];
                        block[k] = v;
                    } catch (err) {
                        const k = headers[i];
                        const v = tokens[i];
                        block[k] = v;
                    }
                }
                trials.push(block);
            }
        }
    });
    timing_info.push(trials);

    return timing_info[0];
}

function parseExcelEvents(fileData: any) {
    // Code from https://stackoverflow.com/questions/30859901/parse-xlsx-with-node-and-create-json
    let workbook = fileData;
    let sheet_name_list = workbook.SheetNames;
    let trials: any[] = [];
    sheet_name_list.forEach(function (y: any) {
        let worksheet = workbook.Sheets[y];
        let headers: any = {};
        let data: any[] = [];
        for (const z in worksheet) {
            if (z[0] === '!') continue;
            //parse out the column, row, and value
            let col: string = z.substring(0, 1);
            let row: number = parseInt(z.substring(1));
            let value = worksheet[z].v;

            //store header names
            if (row == 1) {
                headers[col] = value.toLowerCase();
                continue;
            }

            if (!data[row]) data[row] = {};
            data[row][headers[col]] = value;
        }
        //drop those first two rows which are empty
        data.shift();
        data.shift();
        trials.push(data);
    });

    return trials[0];
}

export function createEventObjects(ezbids: IEzbids, files: any) {
    /*
    This function receives files, an array of object containing fullpath and data.
    Data is the actual file content of the file,
    */
    const eventObjects: any = []; //new event objects to add

    // Identify some terms for decoding purposes
    const subjects = Array.from(new Set(ezbids.subjects.filter((e) => e.exclude == false).map((e) => e.subject)));
    const sessionsArray = Array.from(
        new Set(
            ezbids.subjects
                .map((e) => e.sessions)[0]
                .filter((e) => e.exclude == false)
                .map((e) => e.session)
        )
    );
    const sessions = sessionsArray.filter(function (e) {
        return e;
    }); // remove empty strings & spaces (i.e. no session(s) present
    const tasks = Array.from(
        new Set(
            ezbids.objects
                .map((e) => e._entities)
                .filter(
                    (e) => (e.part == '' || e.part == 'mag') && e.task != '' && e.task != 'rest' && e.task !== undefined
                )
                .map((e) => e.task)
        )
    );
    const runs = Array.from(
        new Set(
            ezbids.objects
                .filter((e) => e._entities.task != '' && e._entities.task != undefined)
                .map((e) => e._entities.run)
        )
    );
    const numEventFiles = files.length;

    // // Try to determine inheritance level (dataset, subject, session, or individual runs)
    // const occurrences = {
    //     'Dataset': 1,
    //     'Subject': subjects.length,
    //     'Session': sessions.length,
    //     'Run': runs.length}
    // const closest = Object.values(occurrences).reduce(function (prev, curr) {
    //     return Math.abs(curr - numEventFiles) < Math.abs(prev - numEventFiles) ? curr : prev;
    // });

    // /*
    // Chance that multiple occurrences values could be the same, therefore, default to lowest level.
    // Assumption is that the lower the level, the more common it is.
    // */
    // // const inheritance_level = Object.keys(occurrences).filter(key=>occurrences[key] == closest).slice(-1)[0]

    //set random entity values that can be updated later on if events mapping doesn't work properly
    let randSubID = 1;
    let randSesID = 1;
    let randTaskName = 'unknown';
    let randRunID = 1;

    // Sort through events file(s) list
    files.forEach((file: any) => {
        const fileExt: string = file.path.split('.').pop();

        // Parse the data, depending on the file extension (and header information)
        let events;
        switch (fileExt) {
            // Excel workbook formats (.xlsx, .xlsm, .xls)
            case 'xlsx':
                events = parseExcelEvents(file.data);
                break;
            default: // Non-Excel formats
                const data = file.data;
                const lines = data
                    .trim()
                    .split('\n')
                    .map((l: any) => l.trim());
                if (lines[0].indexOf('Header Start') > -1) {
                    // E-prime file format
                    events = parseEprimeEvents(file.data);
                } else {
                    // "Regular" file format (.csv .tsv .txt .out)
                    const sep = find_separator(file.path, file.data); // Read events file(s) data
                    events = parseEvents(file.data, sep);
                }
        }

        // Array to help map ezBIDS information to events timing files
        const eventsMappingInfo = {
            subject: {
                MappingKeys: [
                    'sub',
                    'subid',
                    'subname',
                    'subj',
                    'subjid',
                    'subjname',
                    'subject',
                    'subjectid',
                    'subjectname',
                    'participant',
                    'participantid',
                    'participantname',
                ],
                ezBIDSvalues: subjects,
                eventsValue: '',
                detectionMethod: '',
            },
            session: {
                MappingKeys: [
                    'ses',
                    'sesid',
                    'sesname',
                    'sess',
                    'sessid',
                    'sessname',
                    'session',
                    'sessionid',
                    'sessionname',
                ],
                ezBIDSvalues: sessions,
                eventsValue: '',
                detectionMethod: '',
            },
            task: {
                MappingKeys: [
                    'exp',
                    'expid',
                    'expname',
                    'task',
                    'taskid',
                    'taskname',
                    'experiment',
                    'experimentid',
                    'experimentname',
                ],
                ezBIDSvalues: tasks,
                eventsValue: '',
                detectionMethod: '',
            },
            run: {
                MappingKeys: ['run', 'runid', 'runname'],
                ezBIDSvalues: runs,
                eventsValue: '',
                detectionMethod: '',
            },
        };

        const sepChars = ['.', '-', '_', '/']; //used for parsing file path for identifying information, if we need to use file path
        const colNames = Object.keys(events[0]); //selecting the first column of the events timing file, which contains the column names
        for (const entity in eventsMappingInfo) {
            const info = eventsMappingInfo[entity as keyof typeof eventsMappingInfo];

            /* 1st stage: examine column names and data of event file(s) to
            see if identifying information (sub, ses, task, and/or run) is contained there.
            */
            let identifyingCol: any | undefined = undefined;

            for (const colName of colNames) {
                const safeCol = colName.toLowerCase().replace(/[^0-9a-z]/gi, ''); //make lowercase and remove non-alphanumeric characters
                if (info.MappingKeys.includes(safeCol)) {
                    identifyingCol = safeCol;
                    break;
                }
            }
            if (identifyingCol) {
                const identifyingColValues = events.map((e: any) => e[identifyingCol]);
                info.eventsValue = findMostCommonValue(identifyingColValues); //columns may contain multiple values, so find the most common value
                info.detectionMethod = 'identifying information found from value in identifying column name';
            }

            //2nd stage: examine file path for identifying information
            if (info.eventsValue === '') {
                const lowerCaseFilePath = file.path.toLowerCase();
                Object.values(info.MappingKeys).forEach((mappingKey) => {
                    const splitFilePath = lowerCaseFilePath.split(mappingKey);
                    if (splitFilePath.length > 1) {
                        //if a mappingKey is in the file path, the length of the splitFilePath array will be > 1
                        let lastSplit = splitFilePath.slice(-1)[0]; //splitFilePath.slice(-1) is an array of length 1, so grab the first (i.e. entire) array
                        const lastSplitFirstChar = lastSplit[0];

                        Object.values(sepChars).forEach((sepChar) => {
                            //remove leading separator character(s), if they exist
                            if (sepChar === lastSplitFirstChar) {
                                lastSplit = lastSplit.substring(1).replace(sepChar, '');
                            }
                        });
                        lastSplit = lastSplit.replace('/', '-');

                        let value = lastSplit.split(/[._-]+/)[0];
                        let regex = new RegExp(value, 'gi');
                        info.eventsValue = file.path.match(regex)[0]; //since we used a case-insensitive search, let eventsValue be the case-sensitive value from the file path
                        info.detectionMethod = 'identifying information found in file path';
                    }
                });
            }

            /* 3rd stage: ignore zero-padding in subject, session, and run eventsValue if the zero-padded
            value doesn't exist in corresponding ezBIDSvalues. For example, if subject ID in ezBIDS
            is "1", but the corresponding events subject ID is "01", simply assume the two are the same.
            */
            if (entity !== 'task' && info.eventsValue !== '') {
                if (
                    !info.ezBIDSvalues.includes(info.eventsValue) &&
                    info.ezBIDSvalues.includes(info.eventsValue.replace(/^0+/, ''))
                ) {
                    info.eventsValue = info.eventsValue.replace(/^0+/, '');
                    info.detectionMethod = 'ignoring zero-padding led to proper match';
                }
                info.ezBIDSvalues.forEach((ezBIDSvalue: string) => {
                    if (
                        !info.eventsValue.includes(ezBIDSvalue) &&
                        info.eventsValue.includes(ezBIDSvalue.replace(/^0+/, ''))
                    ) {
                        info.eventsValue = info.eventsValue.replace(/^0+/, '');
                        info.detectionMethod = 'ignoring zero-padding led to proper match';
                    }
                });
            }

            /* 4th stage: if task eventValue can't be determined, look for task name(s) used in ezBIDS in event files
            values (not just column names).
            */
            if (entity === 'task') {
                if (eventsMappingInfo.task.eventsValue === '') {
                    const taskNames = eventsMappingInfo.task.ezBIDSvalues.map((v) => v.toLowerCase());
                    events.forEach((event: any) => {
                        for (const key in event) {
                            if (taskNames.includes(event[key])) {
                                info.eventsValue = event[key];
                                info.detectionMethod =
                                    'task identifying information was found in events file (not column name)';
                            }
                        }
                    });
                } else {
                    // Make sure task id aligns correctly
                    let ezbids_tasks: string[] = eventsMappingInfo.task.ezBIDSvalues;
                    let events_task: string = eventsMappingInfo.task.eventsValue;
                    if (ezbids_tasks.length) {
                        let task_match_id = ezbids_tasks.map((t) => t.toLowerCase()).indexOf(events_task.toLowerCase());
                        if (task_match_id !== -1) {
                            eventsMappingInfo.task.eventsValue = ezbids_tasks[task_match_id];
                        }
                    }
                }
            }
        }

        /*
        Time to create func/events object(s). If mapping isn't perfect, we'll make a standalone mapping
        for the func/events object(s) that users can then adjust accordingly. This is so that ezBIDS doesn't
        crash if the mapping isn't perfect, and because we don't want to assume a mapping if we can't
        excplitly map it.
        */

        let section_id = 1; //default value unless otherwise determined
        let ModifiedSeriesNumber = '00'; //default value unless otherwise determined
        let sidecar = {};

        //create new events object
        const object = {
            exclude: false,
            type: 'func/events',
            // series_idx: series_idx, //don't need, I think
            subject_idx: -1,
            session_idx: -1,
            ModifiedSeriesNumber: ModifiedSeriesNumber,

            entities: {
                subject: '',
                session: '',
                task: '',
                acquisition: '',
                ceagent: '',
                reconstruction: '',
                direction: '',
                run: '',
                echo: '',
                part: '',
            },
            items: [
                {
                    name: fileExt,
                    events, //here goes the content of the event object parsed earlier
                    path: file.path, //let's use the original file.path as "path" - although it's not..
                },
                {
                    name: 'json',
                    path: file.path,
                    sidecar,
                    sidecar_json: JSON.stringify(sidecar),
                },
            ],
            //these aren't used, but I believe we have to initialize it
            analysisResults: {
                section_id: section_id,
                errors: [],
                warnings: [],
            },
            paths: [],
            validationErrors: [],
            validationWarnings: [],
        };

        //modify object values
        for (const entity of ['subject', 'session', 'task', 'run']) {
            let ezBIDSvalues = eventsMappingInfo[entity as keyof typeof eventsMappingInfo].ezBIDSvalues;
            let eventsValue = eventsMappingInfo[entity as keyof typeof eventsMappingInfo].eventsValue;
            if (eventsValue) {
                object.entities[entity as keyof typeof eventsMappingInfo] = eventsValue;
            }

            let subjectsInfo = ezbids.subjects;

            //update subject_idx
            if (entity === 'subject' && ezBIDSvalues.includes(eventsValue)) {
                object.subject_idx = subjectsInfo.findIndex(function (subjectsInfo) {
                    return subjectsInfo.subject === eventsMappingInfo.subject.eventsValue;
                });
            }

            //update session_idx
            if (
                entity === 'session' &&
                object.subject_idx &&
                eventsMappingInfo.session.ezBIDSvalues.length > 0 &&
                ezBIDSvalues.includes(eventsValue)
            ) {
                let sessionsInfo = subjectsInfo[object.subject_idx].sessions;

                object.session_idx = sessionsInfo.findIndex(function (sessionsInfo) {
                    return sessionsInfo.session === eventsMappingInfo.session.eventsValue;
                });
            }
        }

        //set subject_idx and session_idx to 0 if they're still undefined at this point, and adjust task & run entity labels
        if (object.subject_idx === -1) {
            object.subject_idx = 0;
            if (!eventsMappingInfo.subject.eventsValue) {
                object.entities.subject = 'XX' + randSubID.toString(); //set the subjectID to a new value, which user would then correct.
                randSubID++;
            } else {
                object.entities.subject = eventsMappingInfo.subject.eventsValue;
            }
        }

        if (object.session_idx === -1) {
            object.session_idx = 0;
            if (eventsMappingInfo.session.eventsValue) {
                object.entities.session = eventsMappingInfo.session.eventsValue;
            } else {
                // if (eventsMappingInfo.session.ezBIDSvalues.length > 0 && eventsMappingInfo.session.ezBIDSvalues.filter(e=>e != "").length > 0) {
                if (!eventsMappingInfo.session.eventsValue && sessions.length > 0) {
                    object.entities.session = 'XX' + randSesID.toString(); //set the sessionID to a new value, which user would then correct.
                    randSesID++;
                }
            }
        }

        if (object.entities.task === '') {
            object.entities.task = randTaskName; //set the task name to a new value, which user would then correct.
        }

        if (object.entities.run === '') {
            object.entities.run = randRunID.toString(); //set the runID to a new value, which user would then correct.
            randRunID++;
        }

        //update section_id, series_idx, and ModifiedSeriesNumber
        if (sessions.length > 0) {
            // series_id
            let section_id_object = ezbids.objects.find(
                (e) =>
                    e._entities.subject === eventsMappingInfo.subject.eventsValue &&
                    e._entities.session === eventsMappingInfo.session.eventsValue &&
                    e._entities.task === eventsMappingInfo.task.eventsValue &&
                    e._entities.run === eventsMappingInfo.run.eventsValue
            );
            if (section_id_object !== undefined) {
                section_id = section_id_object.analysisResults.section_id;
            } else {
                section_id = section_id;
            }

            // ModifiedSeriesNumber
            let ModifiedSeriesNumberObj = ezbids.objects.find(
                (e) =>
                    e._entities.subject === eventsMappingInfo.subject.eventsValue &&
                    e._entities.session === eventsMappingInfo.session.eventsValue &&
                    e._entities.task === eventsMappingInfo.task.eventsValue &&
                    e._entities.run === eventsMappingInfo.run.eventsValue &&
                    e._type === 'func/bold' &&
                    (e._entities.part === '' || e._entities.part === 'mag')
            );
            if (ModifiedSeriesNumberObj !== undefined) {
                ModifiedSeriesNumber = ModifiedSeriesNumberObj.ModifiedSeriesNumber;
            } else {
                ModifiedSeriesNumber = ModifiedSeriesNumber;
            }
        } else {
            // series_id
            let section_id_obj = ezbids.objects.find(
                (e) =>
                    e._entities.subject === eventsMappingInfo.subject.eventsValue &&
                    e._entities.task === eventsMappingInfo.task.eventsValue &&
                    e._entities.run === eventsMappingInfo.run.eventsValue
            );
            if (section_id_obj !== undefined) {
                section_id = section_id_obj.analysisResults.section_id;
            } else {
                section_id = section_id;
            }

            // ModifiedSeriesNumber
            let ModifiedSeriesNumberObj = ezbids.objects.find(
                (e) =>
                    e._entities.subject === eventsMappingInfo.subject.eventsValue &&
                    e._entities.task === eventsMappingInfo.task.eventsValue &&
                    e._entities.run === eventsMappingInfo.run.eventsValue &&
                    e._type === 'func/bold' &&
                    (e._entities.part === '' || e._entities.part === 'mag')
            );
            if (ModifiedSeriesNumberObj !== undefined) {
                ModifiedSeriesNumber = ModifiedSeriesNumberObj.ModifiedSeriesNumber;
            } else {
                ModifiedSeriesNumber = ModifiedSeriesNumber;
            }
        }
        object.analysisResults.section_id = section_id;
        object.ModifiedSeriesNumber = ModifiedSeriesNumber;

        eventObjects.push(object);
    });
    return eventObjects;
}

/*
this function receives one example event object. we will do our best to map the event keys (columns) and
map them to bids events.tsv column names. If an ezBIDS configuration (finalized.json) was uploaded, with
imaging data, those mappings are auto generated when user uploads new events timing files.
*/
export function mapEventColumns(ezbids_events: any, events: any) {
    if (ezbids_events.columns.onset != '') {
        // configuration file specified previous events mapping
        let expectedColumns: IBIDSEvent = ezbids_events.columns;
        let eventsColumns = events[0];

        for (const [key, value] of Object.entries(expectedColumns)) {
            // make sure currently upload events columns have what's expected from the configuration
            if (
                !Object.keys(eventsColumns).includes(value) &&
                !key.includes('Unit') &&
                !key.includes('Logic') &&
                value !== null
            ) {
                ezbids_events.columns[key] = null;
            }
        }
        return ezbids_events.columns;
    } else {
        // //we only have to return things that we found out.. (leave other things not set)
        // const columns = Object.values(Object.keys(events[0]))
        return {
            //type definitions are in store/index

            onsetLogic: 'eq',
            onset: null,
            onset2: null,
            onsetUnit: 'sec',

            durationLogic: 'eq',
            duration: null,
            duration2: null,
            durationUnit: 'sec',

            sampleLogic: 'eq',
            sample: null,
            sample2: null,
            sampleUnit: 'samples',

            trialType: null,

            responseTimeLogic: 'eq',
            responseTime: null,
            responseTime2: null,
            responseTimeUnit: 'sec',

            values: null,

            HED: null,

            stim_file: null,
        };
    }
}

export function fileLogicLink($root: IEzbids, o: IObject) {
    /* Imaging data implicitly has a part-mag (magnitude), though this doesn't need to be explicitly stated. 
    Any phase data (part-phase) is linked to the magnitude. If part entity is specified, make sure it's
    properly linked and has same entities (except for part) and exclusion criteria.
    */
    if (o._entities.part && !['mag', 'real'].includes(o._entities.part)) {
        let correspondingFuncMag = $root.objects.filter(
            (object: IObject) =>
                object._type === o._type &&
                object._entities.part === 'mag' &&
                ((object.idx === o.idx - 1 && object._type === 'func/bold') ||
                    (object.idx === o.idx - 2 && object._type === 'func/bold'))
        );

        if (correspondingFuncMag.length) {
            // should be no more than one
            correspondingFuncMag.forEach((boldMag: IObject) => {
                // o.analysisResults.section_id = boldObj.analysisResults.section_id
                for (let k in boldMag._entities) {
                    if (k !== 'part' && k !== 'echo') {
                        if (boldMag._entities[k] !== '') {
                            o._entities[k] = boldMag._entities[k];
                        } else {
                            o._entities[k] = '';
                        }
                    }
                    o.entities[k] = o._entities[k];
                }

                if (boldMag._exclude) {
                    o.exclude = true;
                    o._exclude = true;
                    o.validationWarnings = [
                        `The corresponding magnitude (part-mag) #${boldMag.series_idx} is currently set to exclude from BIDS conversion. \
                        Since this phase (part-phase) sequence is linked, it will also be excluded from conversion unless the corresponding
                        magnitude (part-mag) is unexcluded. If incorrect, please modify corresponding magnitude (part-mag) (#${boldMag.series_idx}).`,
                    ];
                } else {
                    o.exclude = false;
                    o._exclude = false;
                    o.validationWarnings = [];
                }
            });
        }
    }

    // func/sbref are implicitly linked to a corresponding func/bold; make sure these have same entities and exclusion criteria
    if (o._type === 'func/sbref') {
        let correspondingFuncBold = $root.objects.filter(
            (object: IObject) => object._type === 'func/bold' && o.idx === object.idx - 1
        ); // the func/sbref index (idx) should always be one less than the corresponding func/bold idx, since it comes right before, right?
        if (correspondingFuncBold.length) {
            // should be no more than one
            correspondingFuncBold.forEach((boldObj: IObject) => {
                o.analysisResults.section_id = boldObj.analysisResults.section_id;
                for (let k in boldObj._entities) {
                    if (boldObj._entities[k] !== '' && k !== 'echo') {
                        if (k === 'part' && boldObj._entities[k] === 'phase') {
                            //pass
                        } else {
                            o._entities[k] = boldObj._entities[k];
                        }
                    } else if (boldObj._entities[k] === '') {
                        o._entities[k] = '';
                    }
                    o.entities[k] = o._entities[k];
                }
                if (boldObj._exclude) {
                    o.exclude = true;
                    o._exclude = true;
                    o.validationWarnings = [
                        `The corresponding func/bold #${boldObj.series_idx} is currently set to exclude from BIDS conversion. \
                        Since this func/sbref is linked, it will also be excluded from conversion unless the corresponding
                        func/bold is unexcluded. If incorrect, please modify corresponding func/bold (#${boldObj.series_idx}).`,
                    ];
                } else {
                    o.exclude = false;
                    o._exclude = false;
                    o.validationWarnings = [];
                }
            });
        }
    }

    // func/events are implicitly linked to a func/bold; make sure these have same entities and exclusion criteria
    if (o._type === 'func/events') {
        let correspondingFuncBold = $root.objects.filter(
            (object: IObject) =>
                object._type === 'func/bold' &&
                !object._exclude &&
                object._entities.subject === o._entities.subject &&
                object._entities.session === o._entities.session &&
                object._entities.task === o._entities.task &&
                object._entities.run === o._entities.run &&
                ['', 'mag', 'real'].includes(object._entities.part)
        );

        if (correspondingFuncBold.length) {
            correspondingFuncBold.forEach((boldObj: IObject) => {
                if (!boldObj._exclude) {
                    o.exclude = false;
                    o._exclude = false;
                    o.validationWarnings = [];
                    o.ModifiedSeriesNumber = boldObj.ModifiedSeriesNumber;
                    o.analysisResults.section_id = boldObj.analysisResults.section_id;
                    for (let k in boldObj._entities) {
                        if (boldObj._entities[k] !== '') {
                            o._entities[k] = boldObj._entities[k];
                        } else {
                            o._entities[k] = '';
                        }
                        o.entities[k] = o._entities[k];
                    }
                } else {
                    o.exclude = true;
                    o._exclude = true;
                    // o._entities.run = ""
                    // o.entities.run = ""
                    o.validationWarnings = [
                        `The corresponding func/bold #${boldObj.series_idx} is currently set to exclude from BIDS conversion. \
                        Since this func/events is linked, it will also be excluded from conversion unless the corresponding
                        func/bold is unexcluded. If incorrect, please modify corresponding func/bold (#${boldObj.series_idx}).`,
                    ];
                }
            });
        }
    }
}

// // TODO, currently no validation on Participants Info page
// export function validateParticipantsInfo($root: IEzbids) {
//     let finalSubs = [] as number[];
//     $root._organized.forEach((sub: OrganizedSubject) => {
//         let use = false;
//         sub.sess.forEach((ses) => {
//             if (ses.objects.some((o) => !o._exclude)) use = true;
//         });
//         if (use) finalSubs.push(sub.subject_idx);
//     });

//     let errors: string[] = [];
//     let participantsInfo: any = $root.participantsInfo;
//     Object.entries($root.subjects).forEach(([key, value]) => {
//         let subject: string = value.subject;
//         let columnInfo: any = participantsInfo[key];
//         Object.entries(columnInfo).forEach(([col, val]) => {
//             let v: string | any = val;
//             if (!['PatientName', 'PatientID'].includes(col)) {
//                 if (val !== 'n/a') {
//                     if (col === 'age' && !/^[0-9]*$/.test(v)) {
//                         errors.push('Subject ' + subject + ': The age column has non-numeric values, please fix');
//                     } else if (
//                         col === 'sex' &&
//                         ![
//                             'male',
//                             'm',
//                             'M',
//                             'MALE',
//                             'Male',
//                             'female',
//                             'f',
//                             'F',
//                             'FEMALE',
//                             'Female',
//                             'other',
//                             'o',
//                             'O',
//                             'OTHER',
//                             'Other',
//                         ].includes(v)
//                     ) {
//                         errors.push('Subject ' + subject + ': The sex column has an improper term, please fix');
//                     } else if (
//                         col === 'handedness' &&
//                         ![
//                             'left',
//                             'l',
//                             'L',
//                             'LEFT',
//                             'Left',
//                             'right',
//                             'r',
//                             'R',
//                             'RIGHT',
//                             'Right',
//                             'ambidextrous',
//                             'a',
//                             'A',
//                             'AMBIDEXTROUS',
//                             'Ambidextrous',
//                         ].includes(v)
//                     ) {
//                         errors.push('Subject ' + subject + ': The handedness column has an improper term, please fix');
//                     }
//                 }
//             }
//         });
//     });
//     return errors;
// }

export function metadataAlerts(
    bidsDatatypeMetadata: MetadataFields,
    bidsMetadataInfo: any,
    $root: IEzbids,
    idx: number,
    type: string
): string[] {
    // First, get the current metadata from the sequence sidecars
    let sidecarMetadata: any = {};
    $root.objects.forEach((obj: IObject) => {
        if (obj.series_idx == idx) {
            //find the item in items with .json
            obj.items.forEach((item: any) => {
                if (item.name.includes('json') && item.sidecar_json) {
                    //load the json through sidecar_json
                    const json = JSON.parse(item.sidecar_json);
                    sidecarMetadata = json;
                }
            });
        }
    });

    // Second, find the required (and conditionally required) metadata fields, per BIDS spec
    let requiredFields: string[] = [];
    let datatype = type.split('/')[0];
    let suffix = type.split('/')[1];
    for (let key in bidsDatatypeMetadata) {
        const metadataEntry = bidsDatatypeMetadata[key];
        const selectors: any = metadataEntry.selectors;
        const fields = metadataEntry.fields;
        let proceed = 'no';
        // Need to ensure that we're dealing with the proper sequence datatype and suffix.
        if (selectors.length === 2) {
            // TODO - Can't always rely on this for important info (e.g. BolusCutOffFlag [ASL])
            // don't focus on other conditionals, those are in level_addendum
            if (
                selectors[0].includes('datatype') &&
                selectors[0].includes(datatype) &&
                selectors[1].includes('suffix') &&
                selectors[1].includes(suffix)
            ) {
                proceed = 'yes';
            }
        } else if (datatype === 'meg' && suffix === 'meg' && !selectors.includes('suffix == "coordsystem"')) {
            proceed = 'yes';
        } else if (datatype === 'func' && suffix === 'bold' && key === 'MRIFuncRepetitionTime') {
            proceed = 'yes';
        }
        if (proceed === 'yes') {
            for (let fieldName in fields) {
                if (fields.hasOwnProperty(fieldName) && !['IntendedFor', 'TaskName'].includes(fieldName)) {
                    let field = fields[fieldName];
                    let severity: any = '';
                    if (field.hasOwnProperty('level')) {
                        severity = field.level;
                    } else {
                        severity = field;
                    }

                    if (severity === 'required') {
                        if (!sidecarMetadata.hasOwnProperty(fieldName)) {
                            // Required based on datatype/suffix pairing, no conditionals
                            // BIDS metadata field not in sequence sidecar
                            requiredFields.push(fieldName);
                        }
                    }
                    if (field.hasOwnProperty('level_addendum')) {
                        let levelAddendum = field.level_addendum;
                        if (levelAddendum.includes('required if')) {
                            let bidsMetadataKey = levelAddendum.split('required if')[1].split('`')[1];
                            let bidsMetadataValue: string = '';
                            let context: string = '';

                            // setup some context stuff
                            if (levelAddendum.includes('does not contain')) {
                                bidsMetadataValue = 'none';
                                context = 'does not contain';
                            } else if (levelAddendum.includes('is in [')) {
                                bidsMetadataValue = levelAddendum
                                    .replace(/(^.*\[|\].*$)/g, '')
                                    .split('`')
                                    .filter((e: string) => !['', ','].includes(e));
                                context = 'is in';
                            } else {
                                bidsMetadataValue = levelAddendum.split('required if')[1].split('`')[3];
                                context = 'is';
                            }

                            // Perform check
                            if (context === 'is in') {
                                let sidecarMetadataKey = bidsMetadataKey;
                                let sidecarMetadataValue = sidecarMetadata[sidecarMetadataKey];
                                if (bidsMetadataValue.includes(sidecarMetadataValue)) {
                                    requiredFields.push(fieldName);
                                }
                            } else {
                                if (sidecarMetadata.hasOwnProperty(bidsMetadataKey)) {
                                    let sidecarMetadataKey = bidsMetadataKey;
                                    let sidecarMetadataValue = sidecarMetadata[sidecarMetadataKey];
                                    if (context === 'is' && sidecarMetadataValue === bidsMetadataValue) {
                                        // Required based on equality conditional between BIDS and sequence metadata
                                        requiredFields.push(fieldName);
                                    } else if (
                                        context === 'does not contain' &&
                                        sidecarMetadataValue.includes('none')
                                    ) {
                                        // Required based on contain conditional between BIDS and sequence metadata
                                        requiredFields.push(fieldName);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    //Third, flag any metadata fields values that contain improper BIDS format (e.g. Manufacturer can't be a number)
    let typoFields: string[] = [];

    for (let sidecarMetadataKey in sidecarMetadata) {
        let sidecarMetadataValue = sidecarMetadata[sidecarMetadataKey];
        if (bidsMetadataInfo.hasOwnProperty(sidecarMetadataKey)) {
            // Should mostly always be the case, but user could have non-BIDS specified metadata fields I suppose
            if (bidsMetadataInfo[sidecarMetadataKey].hasOwnProperty('anyOf')) {
                /* TODO - Passing for now, anyOf checking is complicated and already handled when clicking on the 
                Edit Metadata page. Downside is that user won't be alerted unless they click there, but the validator 
                will detect it. Not ideal, will return this this later.

                Also need to deal with additionalProperties and items.
                */
            } else {
                let bidsMetadataValueType = bidsMetadataInfo[sidecarMetadataKey].type;
                let sidecarMetadataValueType: string = typeof sidecarMetadataValue;
                if (sidecarMetadataValueType === 'object' && Array.isArray(sidecarMetadataValue)) {
                    sidecarMetadataValueType = 'array';
                }
                if (bidsMetadataValueType === 'integer' && sidecarMetadataValueType === 'number') {
                    if (Number.isInteger(sidecarMetadataValue)) {
                        sidecarMetadataValueType = 'integer';
                    }
                }

                // Does sequence metadata field key type match what BIDS expects
                if (sidecarMetadataValueType !== bidsMetadataValueType) {
                    typoFields.push(sidecarMetadataKey);
                } else {
                    // Deal with BIDS metadata value type conditionals (other than anyOf)
                    // format
                    if (bidsMetadataInfo[sidecarMetadataKey].hasOwnProperty('format')) {
                        let format = bidsMetadataInfo[sidecarMetadataKey].format;
                        if (format === 'time' && /^\d{2}:\d{2}:\d{2}$/.test(sidecarMetadataValue) === false) {
                            typoFields.push(sidecarMetadataKey);
                        }
                    }
                    //enum
                    if (bidsMetadataInfo[sidecarMetadataKey].hasOwnProperty('enum')) {
                        let Enum = bidsMetadataInfo[sidecarMetadataKey].enum;
                        if (typeof Enum[0] === 'object') {
                            let newEnum = [];
                            for (let d in Enum) {
                                let enumValue = Enum[d]['$ref'].split('.')[2];
                                // e.g. PhaseEncodingDirection
                                if (enumValue.includes('Minus')) {
                                    enumValue = enumValue.replace('Minus', '-');
                                }
                                // MRAcquisitionType
                                if (enumValue.includes('TwoD')) {
                                    enumValue = '2D';
                                }
                                if (enumValue.includes('ThreeD')) {
                                    enumValue = '3D';
                                }
                                newEnum.push(enumValue);
                            }
                            Enum = newEnum;
                        }
                        if (!Enum.includes(sidecarMetadataValue)) {
                            typoFields.push(sidecarMetadataKey);
                        }
                    }
                    //minimum
                    if (bidsMetadataInfo[sidecarMetadataKey].hasOwnProperty('minimum')) {
                        let min = bidsMetadataInfo[sidecarMetadataKey].minimum;
                        if (sidecarMetadataValue < min) {
                            typoFields.push(sidecarMetadataKey);
                        }
                    }
                    //maximum
                    if (bidsMetadataInfo[sidecarMetadataKey].hasOwnProperty('maximum')) {
                        let max = bidsMetadataInfo[sidecarMetadataKey].maximum;
                        if (sidecarMetadataValue > max) {
                            typoFields.push(sidecarMetadataKey);
                        }
                    }
                    //minItems
                    if (bidsMetadataInfo[sidecarMetadataKey].hasOwnProperty('minItems')) {
                        let minItems = bidsMetadataInfo[sidecarMetadataKey].minItems;
                        if (sidecarMetadataValue.length < minItems) {
                            typoFields.push(sidecarMetadataKey);
                        }
                    }
                    //maxItems
                    if (bidsMetadataInfo[sidecarMetadataKey].hasOwnProperty('maxItems')) {
                        let maxItems = bidsMetadataInfo[sidecarMetadataKey].maxItems;
                        if (sidecarMetadataValue.length > maxItems) {
                            typoFields.push(sidecarMetadataKey);
                        }
                    }
                }
            }
        }
    }

    let metadataAlertFields = requiredFields.concat(typoFields);
    // console.log('required', requiredFields);
    // console.log('typo', typoFields);
    return metadataAlertFields;
}

// //TODO: Need to work on this more
// export function updateParticipantsInfo($root: IEzbids) {
//     let participantsInfo: any = $root.participantsInfo;
//     console.log('participantsInfo', participantsInfo);
//     let finalSubs: any = [];
//     $root._organized.forEach((sub: OrganizedSubject) => {
//         let use = false;
//         sub.sess.forEach((ses) => {
//             if (ses.objects.some((o) => !o._exclude)) use = true;
//         });
//         if (use) finalSubs.push({ subIdx: sub.subject_idx, subID: sub.sess[0].objects[0]._entities.subject });
//     });

//     let newParticipantsInfo: any = {};
//     if (Object.keys(participantsInfo).length < finalSubs.length) {
//         // Only an issue when the final number of subjects is greater than the original participantsInfo length
//         let idx_counter = 0;

//         for (let key of Object.keys(finalSubs)) {
//             let info = finalSubs[key];
//             // console.log('info', info);
//             let participantsInfoRef = participantsInfo[info.subIdx];
//             // console.log(participantsInfoRef);
//             newParticipantsInfo[idx_counter] = participantsInfoRef;
//             idx_counter += 1;
//             let subObjs = $root.objects.filter((e) => e._entities.subject === info.subID);
//             let subObjsIdx = subObjs[0].subject_idx.toString();
//             if (subObjsIdx !== key) {
//                 subObjs.forEach((o: IObject) => {
//                     o.subject_idx = Number(key);
//                 });
//             }
//             $root._organized[key].subject_idx = Number(key);
//             console.log('new', newParticipantsInfo);
//         }
//     }
//     console.log('root', $root);
//     return newParticipantsInfo;
// }
