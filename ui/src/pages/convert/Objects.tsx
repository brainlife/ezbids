// @ts-nocheck
import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';

import { useAppSelector } from '../../store/hooks';
import {
    selectBIDSEntities,
    selectFindSubject,
    selectFindSession,
    selectFindSubjectFromString,
    type IObject,
    type IObjectItem,
    type IBIDSEvent,
    type OrganizedSession,
    type OrganizedSubject,
    type Session,
} from '../../store/slices/ezbidsSlice';

import {
    setRun,
    setIntendedFor,
    alignEntities,
    validateEntities,
    validate_B0FieldIdentifier_B0FieldSource,
    fileLogicLink,
    dwiQA,
    petQA,
    updateErrorMessages,
} from '../../libUnsafe';
import { prettyBytes } from '../../filters';

import Datatype from '../../components/Datatype';
import AsyncImageLink from '../../components/AsyncImageLink';

// ── Types ────────────────────────────────────────────────────────────

interface Section {
    [key: string]: IObject[];
}

interface ObjectsProps {
    onNiivue: (path: string) => void;
    onMapObjects: () => void;
    onUpdateObject: (o: IObject) => void;
}

export interface ObjectsHandle {
    isValid: (cb: (err?: string) => void) => void;
    validateAll: () => void;
}

// ── Component ────────────────────────────────────────────────────────

const Objects = forwardRef<ObjectsHandle, ObjectsProps>(({ onNiivue, onMapObjects, onUpdateObject }, ref) => {
    const ezbids = useAppSelector((s) => s.ezbids.data);
    const config = useAppSelector((s) => s.session.config);
    const bidsSchema = useAppSelector((s) => s.ezbids.bidsSchema);
    const getBIDSEntities = useAppSelector(selectBIDSEntities);
    const findSubject = useAppSelector(selectFindSubject);
    const findSession = useAppSelector(selectFindSession);
    const findSubjectFromString = useAppSelector(selectFindSubjectFromString);

    const [so, setSo] = useState<IObject | null>(null);
    const [sess, setSess] = useState<OrganizedSession | null>(null);

    // ── Helpers ──────────────────────────────────────────────────

    const isExcluded = useCallback((o: IObject): boolean => {
        if (o.exclude) return true;
        if (o._exclude) return true;
        if (o._type === 'exclude') return true;
        return false;
    }, []);

    const getSomeEntities = useCallback(
        (type: string): Record<string, string> => {
            const entities = Object.assign({}, getBIDSEntities(type));
            delete entities.subject;
            delete entities.session;
            return entities;
        },
        [getBIDSEntities]
    );

    const findSessionFromString = useCallback(
        (sub: string, ses: string): Session | undefined => {
            const subject = findSubjectFromString(sub);
            if (!subject) return undefined;
            return subject.sessions.find((s: Session) => s.session === ses);
        },
        [findSubjectFromString]
    );

    // ── Validation ──────────────────────────────────────────────

    const validate = useCallback(
        (o: IObject | null) => {
            if (!o) return;

            o.validationErrors = [];
            o.validationWarnings = [];

            validateEntities('Objects', o);
            validate_B0FieldIdentifier_B0FieldSource(o);
            fileLogicLink(ezbids, o);

            // update validationWarnings
            if (o.analysisResults.warnings?.length) {
                o.validationWarnings = o.analysisResults.warnings;
            }

            const entities_requirement = getBIDSEntities(o._type);
            for (const k in getSomeEntities(o._type)) {
                if (entities_requirement[k] === 'required') {
                    if (!o._entities[k]) {
                        o.validationErrors.push('entity: ' + k + ' is required.');
                    }
                }
            }

            // Clean up entities that don't belong to the current datatype/suffix
            for (const k in o._entities) {
                if (!['subject', 'session'].includes(k)) {
                    if (o.entities[k] !== '' && !entities_requirement[k]) {
                        o._entities[k] = '';
                        o.entities[k] = '';
                    }
                }
            }

            if (o._type.startsWith('func/')) {
                const series = ezbids.series[o.series_idx];
                if (entities_requirement['task'] && !o.entities.task && !series?.entities.task) {
                    o.validationErrors.push(
                        'task entity label is required for func/bold but not set on Series Mapping page, nor overridden.'
                    );
                }
            }

            if (o._type.startsWith('fmap/') || o._type === 'perf/m0scan') {
                if (o.IntendedFor && o.IntendedFor.length > 0) {
                    o.IntendedFor.forEach((i) => {
                        const series_idx = ezbids.objects[i]?.series_idx;
                        if (ezbids.objects[i]?._type.startsWith('fmap/')) {
                            o.validationErrors.push(
                                'The selected series (#' +
                                    series_idx +
                                    ") appears to be a field map (fmap), \
                                which isn't allowed in the IntendedFor mapping. Please remove this series, or, if it \
                                isn't a field map, please correct it."
                            );
                        }
                    });
                }
            }

            // Try parsing sidecar items
            o.items.forEach((item) => {
                if (item.sidecar) {
                    try {
                        item.sidecar = JSON.parse(item.sidecar_json);
                    } catch (err) {
                        console.error(err);
                        o.validationErrors.push('Failed to parse sidecar_json. Please check the syntax');
                    }
                }
            });
        },
        [ezbids, getBIDSEntities, getSomeEntities]
    );

    const validateAll = useCallback(() => {
        alignEntities(ezbids);
        dwiQA(ezbids);
        petQA(ezbids);
        setRun(ezbids);
        ezbids.objects.forEach(validate);
        setIntendedFor(ezbids); // keep this last
        updateErrorMessages(ezbids);
    }, [ezbids, validate]);

    // Run validation on mount
    useEffect(() => {
        validateAll();
    }, []);

    // ── Exposed API ─────────────────────────────────────────────

    useImperativeHandle(
        ref,
        () => ({
            isValid(cb: (err?: string) => void) {
                onMapObjects();
                validateAll();

                let err: string | undefined = undefined;
                ezbids.objects.forEach((o: IObject) => {
                    if (o.validationErrors.length > 0) err = 'Please correct all issues.';
                });

                const one = ezbids.objects.find((o: IObject) => !o._exclude);
                if (!one) {
                    err =
                        'All objects are excluded. Please update so that there is at least 1 object to output to BIDS';
                }

                return cb(err);
            },
            validateAll,
        }),
        [ezbids, onMapObjects, validateAll]
    );

    // ── Actions ─────────────────────────────────────────────────

    const excludeSubject = useCallback(
        (sub: string, b: boolean) => {
            const subject = findSubjectFromString(sub);
            if (subject !== undefined) {
                subject.exclude = b;
            } else {
                const o_subs = ezbids._organized.filter((e: OrganizedSubject) => e.sub === sub);
                o_subs.forEach((o_sub: OrganizedSubject) => {
                    o_sub.sess.forEach((ses) => {
                        ses.objects.forEach((obj) => {
                            obj.exclude = b;
                        });
                    });
                });
            }

            onMapObjects();
            validateAll();
        },
        [ezbids._organized, findSubjectFromString, onMapObjects, validateAll]
    );

    const excludeSession = useCallback(
        (sub: string, ses: string, b: boolean) => {
            const subject = findSubjectFromString(sub);
            const session = subject ? findSessionFromString(sub, ses) : undefined;
            if (subject !== undefined && session !== undefined) {
                session.exclude = b;
            } else {
                const o_subs = ezbids._organized.filter((e: OrganizedSubject) => e.sub === sub);
                o_subs.forEach((o_sub: OrganizedSubject) => {
                    const o_ses = o_sub.sess.filter((s) => s.sess === ses);
                    o_ses.forEach((sesObj) => {
                        sesObj.objects.forEach((obj) => {
                            obj.exclude = b;
                        });
                    });
                });
            }

            onMapObjects();
            validateAll();
        },
        [ezbids._organized, findSubjectFromString, findSessionFromString, onMapObjects, validateAll]
    );

    const groupSections = useCallback((sessObj: OrganizedSession): Section => {
        const sections: Section = {};
        sessObj.objects.forEach((o) => {
            const sectionId = o.analysisResults.section_id;
            if (!sections[sectionId]) sections[sectionId] = [];
            sections[sectionId].push(o);
        });
        return sections;
    }, []);

    const select = useCallback((o: IObject, sessObj: OrganizedSession) => {
        setSess(sessObj);
        setSo(o);
        window.scrollTo(0, 0);
    }, []);

    const update = useCallback(
        (o: IObject | null) => {
            if (!o) return;
            onUpdateObject(o);
        },
        [onUpdateObject]
    );

    const getDefault = useCallback(
        (o: IObject, entity: string): string => {
            if (entity === 'subject') {
                const subject = findSubject(o);
                return subject?.subject ?? '';
            } else if (entity === 'session') {
                const subject = findSubject(o);
                if (!subject) return '';
                const session = findSession(subject, o);
                return session?.session ?? '';
            } else {
                const objects = ezbids.objects[o.idx];
                if (!objects) return '';
                return objects._entities[entity] ?? '';
            }
        },
        [ezbids.objects, findSubject, findSession]
    );

    const intendedForLabel = useCallback(
        (o: IObject): string => {
            const series = ezbids.series[o.series_idx];
            if (!series) return 'no-series';
            let l = '#' + series.series_idx + ' ';
            l += o._type;
            for (const k in o._entities) {
                if (k === 'subject' || k === 'session') continue;
                if (!o._entities[k]) continue;
                l += ' ' + k + '-' + o._entities[k];
            }
            return l;
        },
        [ezbids.series]
    );

    // ── Render: left panel (BIDS structure tree) ────────────────

    const renderBadges = (o: IObject) => {
        if (isExcluded(o)) {
            return (
                <span>
                    {o.validationErrors.length > 0 && (
                        <span
                            className="inline-flex items-center justify-center ml-1.5 min-w-[18px] h-[18px] rounded-full bg-red-500 text-white text-xs px-1"
                            title="Validation errors"
                        >
                            {o.validationErrors.length}
                        </span>
                    )}
                </span>
            );
        }

        return (
            <span>
                {o.validationErrors.length > 0 && (
                    <span
                        className="inline-flex items-center justify-center ml-1.5 min-w-[18px] h-[18px] rounded-full bg-red-500 text-white text-xs px-1"
                        title="Validation errors"
                    >
                        {o.validationErrors.length}
                    </span>
                )}
                {o.validationWarnings.length > 0 && (
                    <span
                        className="inline-flex items-center justify-center ml-1.5 min-w-[18px] h-[18px] rounded-full bg-yellow-500 text-white text-xs px-1"
                        title="Validation warnings"
                    >
                        {o.validationWarnings.length}
                    </span>
                )}
                {o._type !== 'exclude' && o.analysisResults?.errors && o.analysisResults.errors.length > 0 && (
                    <span
                        className="inline-flex items-center justify-center ml-1.5 min-w-[18px] h-[18px] rounded-full bg-yellow-500 text-white text-xs px-1"
                        title="QC errors"
                    >
                        {o.analysisResults.errors.length}
                    </span>
                )}
            </span>
        );
    };

    const renderBIDSTree = () => (
        <div>
            {ezbids._organized.map((o_sub: OrganizedSubject) => (
                <div key={o_sub.sub} className="text-[90%] mb-2.5">
                    {o_sub.sub !== '' && (
                        <span className="block p-[3px] leading-[150%]">
                            <i className="mr-0.5">&#128100;</i>
                            <small>sub-</small>
                            <b>{o_sub.sub}</b>
                            &nbsp;
                            <label className="inline-flex items-center gap-1 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={!!findSubjectFromString(o_sub.sub.toString())?.exclude}
                                    onChange={(e) => excludeSubject(o_sub.sub.toString(), e.target.checked)}
                                />
                                <small>Exclude this subject</small>
                            </label>
                        </span>
                    )}
                    {o_sub.sess.map((o_ses: OrganizedSession) => (
                        <div
                            key={o_ses.sess}
                            className={o_ses.sess !== '' ? 'ml-[8.5px] pl-1 border-l-2 border-black/[0.07] pt-1' : ''}
                        >
                            {o_ses.sess && (
                                <span className="block p-[3px] leading-[150%]">
                                    <i className="mr-0.5">&#128337;</i>
                                    <small>ses-</small>
                                    <b>{o_ses.sess}</b>
                                    &nbsp;
                                    <small className="opacity-50">{o_ses.AcquisitionDate}</small>
                                    &nbsp;&nbsp;
                                    <label className="inline-flex items-center gap-1 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={
                                                !!findSessionFromString(o_sub.sub.toString(), o_ses.sess.toString())
                                                    ?.exclude
                                            }
                                            onChange={(e) =>
                                                excludeSession(
                                                    o_sub.sub.toString(),
                                                    o_ses.sess.toString(),
                                                    e.target.checked
                                                )
                                            }
                                        />
                                        <small>Exclude this session</small>
                                    </label>
                                </span>
                            )}
                            {Object.entries(groupSections(o_ses)).map(([sectionId, section]) => (
                                <div key={sectionId} className="relative">
                                    {section.length > 1 && (
                                        <div className="border-t border-dotted border-gray-400 w-full my-[9px]">
                                            <span className="float-right relative top-[-7px] bg-white text-gray-400 px-2.5 mr-2.5">
                                                section {sectionId}
                                            </span>
                                        </div>
                                    )}
                                    {section.map((o: IObject) => (
                                        <div
                                            key={o.idx}
                                            className={`p-0.5 min-h-[20px] cursor-pointer transition-colors duration-300 hover:bg-gray-300 ${
                                                so === o ? 'bg-blue-100' : ''
                                            } ${isExcluded(o) ? 'opacity-50' : ''}`}
                                            onClick={() => select(o, o_ses)}
                                        >
                                            {o.series_idx !== undefined && (
                                                <>
                                                    <span
                                                        className="inline-block bg-gray-200 text-gray-600 rounded text-xs px-1"
                                                        title={'Series#' + o.series_idx + ' ' + o._SeriesDescription}
                                                    >
                                                        #{o.series_idx}
                                                    </span>
                                                    &nbsp;
                                                </>
                                            )}
                                            <Datatype type={o._type} series_idx={o.series_idx} entities={o._entities} />
                                            {o._type === 'exclude' && <small>&nbsp;({o._SeriesDescription})</small>}
                                            {renderBadges(o)}
                                        </div>
                                    ))}
                                </div>
                            ))}
                        </div>
                    ))}
                </div>
            ))}
            <br />
            <br />
            <br />
            <br />
        </div>
    );

    // ── Render: right panel (object detail) ─────────────────────

    const renderEntityInputs = () => {
        if (!so) return null;
        const entities = getBIDSEntities(so._type);
        if (!entities) return null;

        return (
            <div className="w-[350px]">
                {Object.entries(entities).map(([entity, v]) => {
                    if (entity === 'subject' || entity === 'session') return null;
                    const entityInfo = bidsSchema.entities[entity];
                    if (!entityInfo) return null;
                    return (
                        <div key={entity} className="flex items-start mb-0 pr-[30px]">
                            <label className="w-[200px] shrink-0 text-right pr-3 py-1 text-sm text-gray-600">
                                {entityInfo.name}
                                {v === 'required' ? ' - *' : ' -'}
                            </label>
                            <div className="flex-1">
                                <input
                                    type="text"
                                    className="w-[200px] border border-gray-300 rounded px-2 py-1 text-sm"
                                    value={so.entities[entity] ?? ''}
                                    placeholder={getDefault(so, entity)}
                                    title={entityInfo.description}
                                    onChange={(e) => {
                                        so.entities[entity] = e.target.value;
                                        setSo({ ...so });
                                    }}
                                    onBlur={() => update(so)}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>
        );
    };

    const renderIntendedFor = () => {
        if (!so || !sess) return null;
        if (!so._type.startsWith('fmap/') && so._type !== 'perf/m0scan') return null;

        const nonExcludedObjects = sess.objects.filter((o) => !isExcluded(o));

        return (
            <div className="border-t border-gray-100 pt-0.5 mt-0.5">
                <br />
                <div className="flex items-start mb-0 pr-[30px]">
                    <label className="w-[200px] shrink-0 text-right pr-3 py-1 text-sm text-gray-600">IntendedFor</label>
                    <div className="flex-1">
                        <select
                            multiple
                            className="w-full border border-gray-300 rounded px-2 py-1 text-sm min-h-[80px]"
                            value={(so.IntendedFor ?? []).map(String)}
                            onChange={(e) => {
                                const selected = Array.from(e.target.selectedOptions, (opt) => Number(opt.value));
                                so.IntendedFor = selected;
                                update(so);
                            }}
                        >
                            {nonExcludedObjects.map((o) => (
                                <option key={o.idx} value={o.idx}>
                                    {intendedForLabel(o)}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
                <p className="ml-[200px]">
                    <small>
                        * IntendedFor information is used to specify which image this fieldmap is intended for. This is
                        recommended information according to the BIDS specification.
                    </small>
                </p>
            </div>
        );
    };

    const renderB0Fields = () => {
        if (!so) return null;
        if (!so._type || so._type.includes('exclude')) return null;

        const showB0 = !so._type.includes('events') && !so._type.startsWith('meg') && !so._type.startsWith('pet');

        return (
            <div className="border-t border-gray-100 pt-0.5 mt-0.5">
                <br />
                {showB0 && (
                    <>
                        <div className="border-t border-gray-100 pt-0.5 mt-0.5">
                            <div className="flex items-start mb-0 pr-[30px]">
                                <label className="w-[200px] shrink-0 text-right pr-3 py-1 text-sm text-gray-600">
                                    B0FieldIdentifier
                                </label>
                                <div className="flex-1">
                                    <input
                                        type="text"
                                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                                        placeholder="Enter text string (comma-separated for multiple)"
                                        value={(so.B0FieldIdentifier ?? []).join(', ')}
                                        onChange={(e) => {
                                            so.B0FieldIdentifier = e.target.value
                                                ? e.target.value
                                                      .split(',')
                                                      .map((s) => s.trim())
                                                      .filter(Boolean)
                                                : [];
                                            update(so);
                                        }}
                                    />
                                </div>
                            </div>
                            <p className="ml-[200px]">
                                <small>
                                    * <b>Recommended/Optional if no IntendedFor</b>: If this sequence will be used
                                    fieldmap correction, enter a text string of your choice. A good formatting
                                    suggestion is the "datatype_suffix[index]" format (e.g., <b>fmap_epi0</b>,{' '}
                                    <b>fmap_phasediff1</b>, etc). If another sequence will be used with this one for
                                    fieldmap correction, use the exact same text string there as well. Leave field if
                                    unclear.
                                </small>
                            </p>
                        </div>

                        <br />

                        <div className="border-t border-gray-100 pt-0.5 mt-0.5">
                            <div className="flex items-start mb-0 pr-[30px]">
                                <label className="w-[200px] shrink-0 text-right pr-3 py-1 text-sm text-gray-600">
                                    B0FieldSource
                                </label>
                                <div className="flex-1">
                                    <input
                                        type="text"
                                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                                        placeholder="Enter text string (comma-separated for multiple)"
                                        value={(so.B0FieldSource ?? []).join(', ')}
                                        onChange={(e) => {
                                            so.B0FieldSource = e.target.value
                                                ? e.target.value
                                                      .split(',')
                                                      .map((s) => s.trim())
                                                      .filter(Boolean)
                                                : [];
                                            update(so);
                                        }}
                                    />
                                </div>
                            </div>
                            <p className="ml-[200px]">
                                <small>
                                    * <b>Recommended/Optional if no IntendedFor</b>: If this sequence will be used
                                    fieldmap correction, enter a text string of your choice. A good formatting
                                    suggestion is the "datatype_suffix" format (e.g., fmap_epi, fmap_phasediff). If
                                    another sequence will be used with this one for fieldmap correction, use the same
                                    text string there as well. Leave field blank if unclear.
                                </small>
                            </p>
                        </div>
                    </>
                )}
            </div>
        );
    };

    const renderItems = () => {
        if (!so) return null;

        return so.items.map((item: IObjectItem, idx: number) => (
            <div key={idx} className="border-t border-gray-100 pt-0.5 mt-0.5">
                <div className="flex items-start mb-0 pr-[30px]">
                    <label className="w-[200px] shrink-0 text-right pr-3 py-1 text-sm text-gray-600">
                        {item.name || 'noname'}
                    </label>
                    <div className="flex-1">
                        <select
                            className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                            value={item.path}
                            onChange={(e) => {
                                item.path = e.target.value;
                                setSo({ ...so });
                            }}
                        >
                            {so.items.map((optItem, optIdx) => (
                                <option key={optIdx} value={optItem.path}>
                                    {optItem.path}
                                </option>
                            ))}
                        </select>
                        {item.path?.endsWith('.nii.gz') && (
                            <button
                                className="mt-1 px-2 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600"
                                onClick={() => onNiivue(item.path)}
                            >
                                <FontAwesomeIcon icon={['fas', 'eye']} /> NiiVue
                            </button>
                        )}
                    </div>
                </div>

                {item.sidecar && (
                    <div className="flex items-start mb-0 pr-[30px]">
                        <label className="w-[200px] shrink-0 text-right pr-3 py-1 text-sm text-gray-600">sidecar</label>
                        <div className="flex-1">
                            <textarea
                                className="w-full border border-gray-300 rounded px-2 py-1 text-sm font-mono"
                                rows={10}
                                value={item.sidecar_json}
                                onChange={(e) => {
                                    item.sidecar_json = e.target.value;
                                    setSo({ ...so });
                                }}
                                onBlur={() => update(so)}
                            />
                        </div>
                    </div>
                )}

                {item.headers && (
                    <div className="flex items-start mb-0 pr-[30px]">
                        <label className="w-[200px] shrink-0 text-right pr-3 py-1 text-sm text-gray-600">
                            Nifti Headers (read-only)
                        </label>
                        <div className="flex-1">
                            <pre className="h-[200px] overflow-auto leading-[1.5] rounded p-[5px_15px] font-sans text-inherit bg-gray-200 text-gray-400">
                                {JSON.stringify(item.headers, null, 2)}
                            </pre>
                        </div>
                    </div>
                )}

                {item.eventsBIDS && item.eventsBIDS.length > 0 && (
                    <div className="flex items-start mb-0 pr-[30px]">
                        <label className="w-[200px] shrink-0 text-right pr-3 py-1 text-sm text-gray-600">
                            eventsBIDS
                        </label>
                        <div className="flex-1 overflow-x-auto">
                            <table className="w-full border-collapse border border-gray-300 text-sm">
                                <thead>
                                    <tr className="bg-gray-100">
                                        <th className="border border-gray-300 px-2 py-1">onset</th>
                                        <th className="border border-gray-300 px-2 py-1">duration</th>
                                        {item.eventsBIDS[0].sample !== undefined && (
                                            <th className="border border-gray-300 px-2 py-1">sample</th>
                                        )}
                                        {item.eventsBIDS[0].trial_type !== undefined && (
                                            <th className="border border-gray-300 px-2 py-1">trial_type</th>
                                        )}
                                        {item.eventsBIDS[0].response_time !== undefined && (
                                            <th className="border border-gray-300 px-2 py-1">response_time</th>
                                        )}
                                        {item.eventsBIDS[0].value !== undefined && (
                                            <th className="border border-gray-300 px-2 py-1">value</th>
                                        )}
                                        {item.eventsBIDS[0].HED !== undefined && (
                                            <th className="border border-gray-300 px-2 py-1">HED</th>
                                        )}
                                        {item.eventsBIDS[0].stim_file !== undefined && (
                                            <th className="border border-gray-300 px-2 py-1">stim_file</th>
                                        )}
                                    </tr>
                                </thead>
                                <tbody>
                                    {item.eventsBIDS.map((ev: IBIDSEvent, evIdx: number) => (
                                        <tr key={evIdx}>
                                            <td className="border border-gray-300 px-2 py-1">{ev.onset}</td>
                                            <td className="border border-gray-300 px-2 py-1">{ev.duration}</td>
                                            {item.eventsBIDS![0].sample !== undefined && (
                                                <td className="border border-gray-300 px-2 py-1">{ev.sample}</td>
                                            )}
                                            {item.eventsBIDS![0].trial_type !== undefined && (
                                                <td className="border border-gray-300 px-2 py-1">{ev.trial_type}</td>
                                            )}
                                            {item.eventsBIDS![0].response_time !== undefined && (
                                                <td className="border border-gray-300 px-2 py-1">{ev.response_time}</td>
                                            )}
                                            {item.eventsBIDS![0].value !== undefined && (
                                                <td className="border border-gray-300 px-2 py-1">{ev.value}</td>
                                            )}
                                            {item.eventsBIDS![0].HED !== undefined && (
                                                <td className="border border-gray-300 px-2 py-1">{ev.HED}</td>
                                            )}
                                            {item.eventsBIDS![0].stim_file !== undefined && (
                                                <td className="border border-gray-300 px-2 py-1">{ev.stim_file}</td>
                                            )}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
                <br />
            </div>
        ));
    };

    const renderAnalysisResults = () => {
        if (!so) return null;
        if (!so.analysisResults.filesize) return null;

        return (
            <div className="mt-1.5 p-1.5 bg-gray-100" style={{ fontSize: '90%' }}>
                <p>
                    Volumes: <b>{so.analysisResults.NumVolumes}</b> &nbsp;&nbsp; Orientation:{' '}
                    <b>{so.analysisResults.orientation}</b> &nbsp;&nbsp; File Size:{' '}
                    <b>{prettyBytes(so.analysisResults.filesize)}</b>
                </p>
                {ezbids.objects[so.idx]?.items.map((item: IObjectItem, itemIdx: number) => (
                    <div key={itemIdx}>
                        {item.pngPaths?.map((path: string, pIdx: number) => (
                            <div key={pIdx}>
                                <pre className="mb-0">{path}</pre>
                                <AsyncImageLink path={path} />
                            </div>
                        ))}
                    </div>
                ))}
            </div>
        );
    };

    const renderDetailPanel = () => {
        if (!so || !sess) {
            return (
                <div className="p-5">
                    <div className="p-4 bg-blue-50 border border-blue-200 rounded text-blue-700">
                        <p>Please make sure all subject/session/series mappings are correctly applied to your data.</p>
                        <p>
                            By default, entities specified in the <b>Series</b> page will be used as defaults for all
                            objects. On this page you can override those entities.
                        </p>
                        <div className="bg-white p-2.5 text-gray-500">
                            &#8592; Please select an object to view/edit in the BIDS Structure list
                        </div>
                    </div>
                </div>
            );
        }

        return (
            <div>
                <div className="p-2">
                    {/* Exclude checkbox */}
                    <div className="mb-0 pr-[30px]">
                        <label className="inline-flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={so.exclude}
                                onChange={(e) => {
                                    so.exclude = e.target.checked;
                                    update(so);
                                    setSo({ ...so });
                                }}
                            />
                            Exclude this object
                        </label>
                    </div>

                    {isExcluded(so) && (
                        <div className="mb-1.5 p-2 bg-blue-50 border border-blue-200 rounded text-blue-700 text-sm">
                            This object will be excluded from the BIDS output
                        </div>
                    )}

                    {/* Series Description */}
                    {so.series_idx !== undefined && (
                        <div className="flex items-start mb-0 pr-[30px]">
                            <label className="w-[200px] shrink-0 text-right pr-3 py-1 text-sm text-gray-600">
                                Series Desc
                            </label>
                            <div className="flex-1 py-1">{so._SeriesDescription}</div>
                        </div>
                    )}

                    {/* Validation errors */}
                    <div className="mb-1.5">
                        {so.validationErrors.map((error, idx) => (
                            <div
                                key={idx}
                                className="flex items-center gap-2 p-2 mb-1 bg-red-50 border border-red-200 rounded text-red-700 text-sm"
                            >
                                <span>&#9888;</span>
                                {error}
                            </div>
                        ))}
                    </div>

                    {/* Validation warnings */}
                    <div className="mb-1.5">
                        {so.validationWarnings.map((warning, idx) => (
                            <div
                                key={idx}
                                className="flex items-center gap-2 p-2 mb-1 bg-yellow-50 border border-yellow-200 rounded text-yellow-700 text-sm"
                            >
                                <span>&#9888;</span>
                                {warning}
                            </div>
                        ))}
                    </div>

                    {/* QC / analysis errors */}
                    <div className="mb-1.5">
                        {so.analysisResults.errors?.map((error: string, idx: number) => (
                            <div
                                key={idx}
                                className="flex items-center gap-2 p-2 mb-1 bg-yellow-50 border border-yellow-200 rounded text-yellow-700 text-sm"
                            >
                                <span>&#9888;</span>
                                {error}
                            </div>
                        ))}
                    </div>

                    {/* Datatype/Suffix selector */}
                    <div className="flex items-start mb-0 pr-[30px]">
                        <label className="w-[200px] shrink-0 text-right pr-3 py-1 text-sm text-gray-600">
                            Datatype/Suffix
                        </label>
                        <div className="flex-1">
                            <select
                                className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                                value={so.type ?? ''}
                                onChange={(e) => {
                                    so.type = e.target.value;
                                    update(so);
                                    setSo({ ...so });
                                }}
                            >
                                <option value="">(Use Series Default)</option>
                                {Object.entries(bidsSchema.datatypes).map(([key, dtype]: [string, any]) => (
                                    <optgroup key={key} label={dtype.label}>
                                        {dtype.options.map((subtype: any) => (
                                            <option key={subtype.value} value={subtype.value}>
                                                {dtype.label} / {subtype.label}
                                            </option>
                                        ))}
                                    </optgroup>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* Entity inputs */}
                    {renderEntityInputs()}

                    {/* IntendedFor */}
                    {renderIntendedFor()}

                    {/* B0 fields */}
                    {renderB0Fields()}

                    {/* Items */}
                    {renderItems()}

                    {/* Analysis results */}
                    {renderAnalysisResults()}

                    {config.debug && <pre className="mt-4 text-xs">{JSON.stringify(so, null, 2)}</pre>}
                </div>
                <br />
                <br />
                <br />
            </div>
        );
    };

    // ── Main render ─────────────────────────────────────────────

    return (
        <div className="fixed top-0 bottom-[60px] left-40 right-0">
            <PanelGroup direction="horizontal">
                <Panel defaultSize={30} minSize={20} className="overflow-y-auto p-2.5 text-[90%]">
                    {renderBIDSTree()}
                </Panel>
                <PanelResizeHandle className="w-1.5 bg-gray-200 hover:bg-gray-400 transition-colors cursor-col-resize" />
                <Panel className="overflow-y-auto">{renderDetailPanel()}</Panel>
            </PanelGroup>
        </div>
    );
});

Objects.displayName = 'Objects';

export default Objects;
