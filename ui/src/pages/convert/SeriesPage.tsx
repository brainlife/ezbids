import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';

import { useAppSelector } from '../../store/hooks';
import { selectBIDSEntities, type Series, type IObject, type IEzbids } from '../../store/slices/ezbidsSlice';

import Datatype from '../../components/Datatype';
import ShowFile from '../../components/ShowFile';
import AsyncImageLink from '../../components/AsyncImageLink';
// import ModalityForm from '../../components/ModalityForm'

import { prettyBytes } from '../../filters';
import { validateEntities, validate_B0FieldIdentifier_B0FieldSource, metadataAlerts } from '../../libUnsafe';

import anatYaml from '../../assets/schema/rules/sidecars/anat.yaml';
import funcYaml from '../../assets/schema/rules/sidecars/func.yaml';
import fmapYaml from '../../assets/schema/rules/sidecars/fmap.yaml';
import dwiYaml from '../../assets/schema/rules/sidecars/dwi.yaml';
import aslYaml from '../../assets/schema/rules/sidecars/asl.yaml';
import petYaml from '../../assets/schema/rules/sidecars/pet.yaml';
import megYaml from '../../assets/schema/rules/sidecars/meg.yaml';
import metadataInfo from '../../assets/schema/rules/sidecars/metadata.yaml';

// ── Types ─────────────────────────────────────────────────────────────

interface SeriesPageProps {
    onNiivue: (path: string) => void;
}

interface SeriesPageHandle {
    isValid: (cb: (err?: string) => void) => void;
}

// ── Component ─────────────────────────────────────────────────────────

const SeriesPage = forwardRef<SeriesPageHandle, SeriesPageProps>(function SeriesPage({ onNiivue }, ref) {
    const ezbids = useAppSelector((s) => s.ezbids.data);
    const config = useAppSelector((s) => s.session.config);
    const bidsSchema = useAppSelector((s) => s.ezbids.bidsSchema);
    const getBIDSEntities = useAppSelector(selectBIDSEntities);

    const [ss, setSs] = useState<Series | null>(null);
    const [, forceUpdate] = useState(0);

    // ── Helpers ───────────────────────────────────────────────────

    const getObjectsFromSeries = useCallback(
        (series: Series): IObject[] => {
            const idx = ezbids.series.indexOf(series);
            return ezbids.objects.filter((o) => o.series_idx === idx);
        },
        [ezbids.series, ezbids.objects]
    );

    const getSomeEntities = useCallback(
        (type: string): Record<string, string> => {
            const entities = Object.assign({}, getBIDSEntities(type)) as Record<string, string>;
            delete entities.subject;
            delete entities.session;
            return entities;
        },
        [getBIDSEntities]
    );

    // ── BIDS URI toggle ──────────────────────────────────────────

    const handleBIDSURI = useCallback(
        (checked: boolean) => {
            (ezbids as any).BIDSURI = checked;
            localStorage.setItem('checkboxState', checked ? 'true' : 'false');
        },
        [ezbids]
    );

    // ── Validation ───────────────────────────────────────────────

    const validate = useCallback(
        (s: Series | null) => {
            if (!s) return;

            s.validationErrors = [];
            s.validationWarnings = [];

            if (s.type !== 'exclude') {
                validateEntities('Series', s);
                validate_B0FieldIdentifier_B0FieldSource(s);
            }

            // Metadata alerts
            let bidsDatatypeMetadata = {} as any;
            if (['perf/asl', 'perf/m0scan'].includes(s.type)) {
                bidsDatatypeMetadata = aslYaml;
            } else if (s.type.startsWith('pet')) {
                bidsDatatypeMetadata = petYaml;
            } else if (s.type.startsWith('func')) {
                bidsDatatypeMetadata = funcYaml;
            } else if (s.type.startsWith('fmap')) {
                bidsDatatypeMetadata = fmapYaml;
            } else if (s.type.startsWith('dwi')) {
                bidsDatatypeMetadata = dwiYaml;
            } else if (s.type.startsWith('anat')) {
                bidsDatatypeMetadata = anatYaml;
            } else if (s.type.startsWith('meg')) {
                bidsDatatypeMetadata = megYaml;
            }

            const alertFields = metadataAlerts(bidsDatatypeMetadata, metadataInfo, ezbids, s.series_idx, s.type);
            if (alertFields.length) {
                s.validationWarnings.push(
                    `'Required metadata is missing, provided metadata field values have improper
                format. Please click on the "Edit Metadata" button below to resolve. You may skip fields for which you
                do not know the proper value, but you will not have a fully BIDS-compliant dataset.'`
                );
            }

            // Check required entities
            const entitiesRequirement = getBIDSEntities(s.type) as Record<string, string>;
            for (const k in getSomeEntities(s.type)) {
                if (entitiesRequirement[k] === 'required') {
                    if (!s.entities[k]) {
                        s.validationErrors.push('entity: ' + k + ' is required.');
                    }
                }
            }

            // Remove entities not allowed by current datatype/suffix
            for (const k in s.entities) {
                if (!['subject', 'session'].includes(k)) {
                    if (s.entities[k] !== '' && !entitiesRequirement[k]) {
                        s.entities[k] = '';
                    }
                }
            }

            // IntendedFor validation for fmap / perf/m0scan
            if (s.type.startsWith('fmap/') || s.type === 'perf/m0scan') {
                if (!s.IntendedFor) s.IntendedFor = [];
                if (s.IntendedFor.length === 0) {
                    if (s.type.startsWith('fmap/')) {
                        s.validationWarnings.push(
                            'It is recommended that field map (fmap) images have IntendedFor set to at least 1 series ID. This is necessary if you plan on using processing BIDS-apps such as fMRIPrep'
                        );
                    } else if (s.type === 'perf/m0scan') {
                        s.validationErrors.push(
                            'It is required that perfusion m0scan images have IntendedFor set to at least 1 series ID.'
                        );
                    }
                }
                if (s.IntendedFor.length > 0) {
                    s.IntendedFor.forEach((i) => {
                        if (ezbids.series[i].type.startsWith('fmap/') || ezbids.series[i].type === 'perf/m0scan') {
                            s.validationErrors.push(
                                'The selected series (#' +
                                    i +
                                    ") appears to be a field map (fmap), which isn't allowed in the IntendedFor mapping. Please remove this series, or, if it isn't a field map, please correct it."
                            );
                        }
                    });
                }
            }

            // DWI b0map warning
            if (s.type === 'dwi/dwi') {
                if (s.message.includes('fmap/epi')) {
                    s.validationWarnings.push(
                        'This sequence is believed to be a DWI b0map, which in BIDS corresponds to fmap/epi. If this sequence is not a DWI b0map, please proceed. Otherwise, please reconsider.'
                    );
                }
            }
        },
        [ezbids, getBIDSEntities, getSomeEntities]
    );

    const validateAll = useCallback(() => {
        ezbids.series.forEach(validate);
        forceUpdate((n) => n + 1);
    }, [ezbids.series, validate]);

    // ── Mount ────────────────────────────────────────────────────

    useEffect(() => {
        validateAll();
    }, []);

    // ── Expose isValid ───────────────────────────────────────────

    useImperativeHandle(
        ref,
        () => ({
            isValid(cb: (err?: string) => void) {
                validateAll();
                let err: string | undefined;
                ezbids.series.forEach((s: Series) => {
                    if (s.validationErrors.length > 0) err = 'Please correct all issues';
                });
                return cb(err);
            },
        }),
        [ezbids.series, validateAll]
    );

    // ── Handlers ─────────────────────────────────────────────────

    const handleTypeChange = useCallback(
        (value: string) => {
            if (!ss) return;
            ss.type = value;
            validateAll();
        },
        [ss, validateAll]
    );

    const handleEntityChange = useCallback(
        (entity: string, value: string) => {
            if (!ss) return;
            ss.entities[entity] = value;
            validateAll();
        },
        [ss, validateAll]
    );

    const handleIntendedForChange = useCallback(
        (values: number[]) => {
            if (!ss) return;
            ss.IntendedFor = values;
            validateAll();
        },
        [ss, validateAll]
    );

    const handleB0FieldIdentifierChange = useCallback(
        (values: string[]) => {
            if (!ss) return;
            ss.B0FieldIdentifier = values;
            validateAll();
        },
        [ss, validateAll]
    );

    const handleB0FieldSourceChange = useCallback(
        (values: string[]) => {
            if (!ss) return;
            ss.B0FieldSource = values;
            validateAll();
        },
        [ss, validateAll]
    );

    // ── Build datatype options for select ────────────────────────

    const datatypeOptions = Object.values(bidsSchema.datatypes).flatMap((dt) =>
        dt.options.map((opt) => ({
            group: dt.label,
            value: opt.value,
            label: `${dt.label} / ${opt.label}`,
        }))
    );

    // ── Render ───────────────────────────────────────────────────

    return (
        <PanelGroup direction="horizontal" className="fixed top-0 bottom-[60px] left-40 right-0">
            {/* ── Left pane: series list ─────────────────────────── */}
            <Panel defaultSize={30} minSize={20} className="p-2.5 text-[90%] overflow-y-auto">
                {ezbids.series.map((s, seriesIdx) => (
                    <div
                        key={seriesIdx}
                        className={`p-0.5 cursor-pointer transition-colors duration-300 hover:bg-gray-300 ${
                            ss === s ? 'bg-blue-100' : ''
                        } ${s.type === 'exclude' ? 'opacity-50' : ''}`}
                        onClick={() => setSs(s)}
                    >
                        <span
                            className="inline-block bg-gray-200 text-gray-600 text-xs rounded px-1"
                            title="Series index"
                        >
                            #{seriesIdx}
                        </span>{' '}
                        <Datatype type={s.type} series_idx={seriesIdx} entities={s.entities} />
                        <small className="opacity-70">({s.SeriesDescription})</small>{' '}
                        <span
                            className="inline-block border border-gray-300 text-gray-500 text-xs rounded px-1"
                            title="Number of objects"
                        >
                            {getObjectsFromSeries(s).length} objs
                        </span>{' '}
                        {s.validationErrors.length > 0 && (
                            <span className="inline-block bg-red-500 text-white text-xs rounded-full px-1.5 ml-1">
                                {s.validationErrors.length}
                            </span>
                        )}
                        {s.validationWarnings.length > 0 && (
                            <span className="inline-block bg-yellow-500 text-white text-xs rounded-full px-1.5 ml-1">
                                {s.validationWarnings.length}
                            </span>
                        )}
                    </div>
                ))}
                {config.debug && <pre>{JSON.stringify(ezbids.series, null, 2)}</pre>}
            </Panel>

            <PanelResizeHandle className="w-1.5 bg-gray-200 hover:bg-gray-400 transition-colors" />

            {/* ── Right pane: series detail ──────────────────────── */}
            <Panel className="overflow-y-auto">
                {!ss ? (
                    <div className="p-5">
                        <div className="text-gray-500">
                            <p>
                                Please update (if necessary) how you'd like to map each dicom SeriesDescription to BIDS
                                datatype, suffix, entities.
                            </p>
                            <p>
                                The information you specify here will be applied to all subjects that uses matching
                                SeriesDescription. You can also override this information later for each subject.
                            </p>
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={!!ezbids.BIDSURI}
                                    onChange={(e) => handleBIDSURI(e.target.checked)}
                                />
                                <small>Use BIDS URI format for IntendedFor metadata mapping (if applicable)</small>
                            </label>
                            <div className="bg-white p-2.5 text-gray-500 mt-2">
                                <FontAwesomeIcon icon="arrow-left" /> Please select a series to view/edit
                            </div>
                        </div>
                    </div>
                ) : (
                    <div>
                        <h5 className="px-5">BIDS Datatype, Suffix, Entities</h5>

                        <div className="px-5">
                            {/* Messages */}
                            {ss.message && (
                                <div className="bg-blue-50 border border-blue-200 text-blue-700 px-4 py-2 rounded mb-1 text-sm flex items-center gap-2">
                                    <FontAwesomeIcon icon="info-circle" />
                                    {ss.message}
                                </div>
                            )}

                            {/* Validation errors */}
                            {ss.validationErrors.map((error, idx) => (
                                <div
                                    key={`err-${idx}`}
                                    className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded mb-1 text-sm flex items-center gap-2"
                                >
                                    <FontAwesomeIcon icon="exclamation-circle" />
                                    {error}
                                </div>
                            ))}

                            {/* Validation warnings */}
                            {ss.validationWarnings.map((warn, idx) => (
                                <div
                                    key={`warn-${idx}`}
                                    className="bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-2 rounded mb-1 text-sm flex items-center gap-2"
                                >
                                    <FontAwesomeIcon icon="exclamation-triangle" />
                                    {warn}
                                </div>
                            ))}

                            {/* Datatype / Suffix selector */}
                            <div className="mb-4 mt-2">
                                <label className="block text-sm font-medium text-gray-700 mb-1 w-[150px] inline-block">
                                    Datatype/Suffix
                                </label>
                                <select
                                    className="border border-gray-300 rounded px-2 py-1 text-sm w-[80%]"
                                    value={ss.type}
                                    onChange={(e) => handleTypeChange(e.target.value)}
                                >
                                    <option value="exclude">(Exclude from BIDS conversion)</option>
                                    {datatypeOptions.map((opt) => (
                                        <option key={opt.value} value={opt.value}>
                                            {opt.label}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Entity editors */}
                            {ss.type &&
                                Object.entries(getSomeEntities(ss.type)).map(([entity, requirement]) => (
                                    <div key={entity} className="mb-1" style={{ width: 350 }}>
                                        <label className="inline-block w-[150px] text-sm text-gray-700">
                                            {entity}
                                            {requirement === 'required' ? ' *' : ''}
                                        </label>
                                        <input
                                            className="border border-gray-300 rounded px-2 py-1 text-sm"
                                            value={ss.entities[entity] ?? ''}
                                            title={
                                                bidsSchema.entities[entity]
                                                    ? `${bidsSchema.entities[entity].name}: ${bidsSchema.entities[entity].description}`
                                                    : ''
                                            }
                                            required={requirement === 'required'}
                                            onChange={(e) => handleEntityChange(entity, e.target.value)}
                                        />
                                    </div>
                                ))}

                            {/* IntendedFor (fmap / perf/m0scan) */}
                            {ss.type && (ss.type.startsWith('fmap/') || ss.type === 'perf/m0scan') && (
                                <div className="mb-4">
                                    <label className="block text-sm font-medium text-gray-700 mb-1 w-[150px] inline-block">
                                        IntendedFor
                                    </label>
                                    <select
                                        className="border border-gray-300 rounded px-2 py-1 text-sm w-[80%]"
                                        multiple
                                        value={(ss.IntendedFor ?? []).map(String)}
                                        onChange={(e) => {
                                            const selected = Array.from(e.target.selectedOptions, (o) =>
                                                parseInt(o.value)
                                            );
                                            handleIntendedForChange(selected);
                                        }}
                                    >
                                        {ezbids.series.map((series, idx) => (
                                            <option key={idx} value={idx}>
                                                (#{idx}) {series.type}
                                            </option>
                                        ))}
                                    </select>
                                    <p className="mt-0 text-sm">
                                        <small>
                                            * <b>Recommended (Required if perf/m0scan)</b>: select Series that this
                                            sequence should be applied to.
                                        </small>
                                    </p>
                                </div>
                            )}

                            {/* B0FieldIdentifier / B0FieldSource */}
                            {ss.type &&
                                !ss.type.includes('exclude') &&
                                !ss.type.startsWith('meg') &&
                                !ss.type.startsWith('pet') && (
                                    <>
                                        <div className="mb-4">
                                            <label className="block text-sm font-medium text-gray-700 mb-1 w-[150px] inline-block">
                                                B0FieldIdentifier
                                            </label>
                                            <input
                                                className="border border-gray-300 rounded px-2 py-1 text-sm w-[80%]"
                                                placeholder="Enter text string (comma-separated for multiple)"
                                                value={(ss.B0FieldIdentifier ?? []).join(', ')}
                                                onChange={(e) => {
                                                    const vals = e.target.value
                                                        .split(',')
                                                        .map((v) => v.trim())
                                                        .filter(Boolean);
                                                    handleB0FieldIdentifierChange(vals);
                                                }}
                                            />
                                            <p className="mt-0 text-sm">
                                                <small>
                                                    * <b>Recommended/Optional if no IntendedFor</b>: If this sequence
                                                    will be used for fieldmap/distortion correction, enter a text string
                                                    of your choice. A good formatting suggestion is the
                                                    "datatype_suffix[index]" format (e.g., <b>fmap_epi0</b>,{' '}
                                                    <b>fmap_phasediff1</b>, etc). If another sequence will be used with
                                                    this one for fieldmap/distortion correction, use the exact same text
                                                    string there as well. Leave field blank if unclear.
                                                </small>
                                            </p>
                                        </div>
                                        <div className="mb-4">
                                            <label className="block text-sm font-medium text-gray-700 mb-1 w-[150px] inline-block">
                                                B0FieldSource
                                            </label>
                                            <input
                                                className="border border-gray-300 rounded px-2 py-1 text-sm w-[80%]"
                                                placeholder="Enter text string (comma-separated for multiple)"
                                                value={(ss.B0FieldSource ?? []).join(', ')}
                                                onChange={(e) => {
                                                    const vals = e.target.value
                                                        .split(',')
                                                        .map((v) => v.trim())
                                                        .filter(Boolean);
                                                    handleB0FieldSourceChange(vals);
                                                }}
                                            />
                                            <p className="mt-0 text-sm">
                                                <small>
                                                    * <b>Recommended/Optional if no IntendedFor</b>: If
                                                    fieldmap/distortion correction will be applied to this image, enter
                                                    the identical text string from the B0FieldIdentifier field of the
                                                    sequence(s) used to create the fieldmap/distortion estimation. Leave
                                                    field blank if unclear.
                                                </small>
                                            </p>
                                        </div>
                                    </>
                                )}

                            {/* Common metadata tags */}
                            <div className="mb-2">
                                <label className="block text-sm font-medium text-gray-700 mb-1 w-[150px] inline-block">
                                    Common Metadata
                                </label>
                                <small>All objects under this series contain the following common metadata.</small>
                                <p className="mt-0 mb-0">
                                    <span className="inline-block bg-gray-100 text-gray-600 text-xs rounded px-1 mr-1">
                                        SeriesDescription: {ss.SeriesDescription}
                                    </span>
                                    <span className="inline-block bg-gray-100 text-gray-600 text-xs rounded px-1 mr-1">
                                        EchoTime: {ss.EchoTime}
                                    </span>
                                    <span className="inline-block bg-gray-100 text-gray-600 text-xs rounded px-1 mr-1">
                                        ImageType: {ss.ImageType}
                                    </span>
                                    <span className="inline-block bg-gray-100 text-gray-600 text-xs rounded px-1 mr-1">
                                        RepetitionTime: {ss.RepetitionTime}
                                    </span>
                                </p>
                            </div>

                            {/* Relevant Metadata / ModalityForm placeholder */}
                            {ss.type &&
                                (['perf/asl', 'perf/m0scan'].includes(ss.type) ||
                                    ss.type.startsWith('pet') ||
                                    ss.type.startsWith('func') ||
                                    ss.type.startsWith('fmap') ||
                                    ss.type.startsWith('dwi') ||
                                    ss.type.startsWith('anat') ||
                                    ss.type.startsWith('meg')) && (
                                    <div className="mb-2">
                                        <label className="block text-sm font-medium text-gray-700 mb-1 w-[150px] inline-block">
                                            Relevant Metadata
                                        </label>
                                        {/* TODO: ModalityForm component not yet converted to React */}
                                        <span className="text-gray-400 text-sm">[ModalityForm placeholder]</span>
                                    </div>
                                )}
                        </div>

                        {/* ── Objects belonging to this series ── */}
                        <p className="border-t border-gray-200 px-5 py-2.5">
                            <small>The following objects belongs to this series.</small>
                        </p>
                        {getObjectsFromSeries(ss).map((object) => (
                            <div key={object.idx} className="px-5 mb-5">
                                <FontAwesomeIcon icon="caret-right" />
                                &nbsp;
                                {object._entities &&
                                    Object.entries(object._entities).map(([k, v]) =>
                                        v ? (
                                            <span key={`${object.idx}.${k}`} className="inline-block text-[85%] mr-2.5">
                                                {k}-<b>{v as string}</b>
                                            </span>
                                        ) : null
                                    )}
                                <div className="float-right">
                                    <span className="inline-block bg-gray-100 text-gray-600 text-xs rounded px-1 mr-1">
                                        volumes: {ezbids.objects[object.idx]?.analysisResults?.NumVolumes}
                                    </span>
                                    <span className="inline-block bg-gray-100 text-gray-600 text-xs rounded px-1 mr-1">
                                        filesize:{' '}
                                        {prettyBytes(ezbids.objects[object.idx]?.analysisResults?.filesize ?? 0)}
                                    </span>
                                    <span className="inline-block bg-gray-100 text-gray-600 text-xs rounded px-1 mr-1">
                                        orientation: {ezbids.objects[object.idx]?.analysisResults?.orientation}
                                    </span>
                                    <span className="inline-block bg-gray-100 text-gray-600 text-xs rounded px-1 mr-1">
                                        direction: {ezbids.objects[object.idx]?.PED}
                                    </span>
                                </div>
                                <div className="ml-6 clear-both">
                                    {ezbids.objects[object.idx]?.items.map((item, itemIdx) => (
                                        <div key={`img-${itemIdx}`}>
                                            {item.pngPaths && (
                                                <div>
                                                    {item.pngPaths.map((path, pIdx) => (
                                                        <div key={pIdx}>
                                                            <pre>{path}</pre>
                                                            <AsyncImageLink path={path} />
                                                        </div>
                                                    ))}
                                                    <button
                                                        className="bg-gray-200 hover:bg-gray-300 text-sm px-3 py-1 rounded"
                                                        onClick={() => onNiivue(item.path)}
                                                    >
                                                        <FontAwesomeIcon icon="eye" /> NiiVue
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    ))}

                                    <small>
                                        <b>Files</b>
                                    </small>
                                    {ezbids.objects[object.idx]?.items.map((item, idx) => (
                                        <div key={`file-${idx}`}>
                                            <pre>{item.path}</pre>
                                            {['json', 'bval', 'bvec'].includes(item.path.split('.').pop() ?? '') && (
                                                <ShowFile path={item.path} />
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </Panel>
        </PanelGroup>
    );
});

export default SeriesPage;
