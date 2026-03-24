// @ts-nocheck
import React, { forwardRef, useImperativeHandle, useCallback } from 'react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { addObject, type IObject } from '../../store/slices/ezbidsSlice';
import { updateEvents, resetEvents } from '../../store/slices/eventsSlice';
import ColumnSelecter from '../../components/ColumnSelecter';
import { createEventObjects, mapEventColumns } from '../../libUnsafe';

import eventsDirectoryExample from '../../assets/images/events_directoryUpload_example.png';

// ── Types ────────────────────────────────────────────────────────────

interface IPathAndData {
    path: string;
    data: string;
}

interface EventsProps {
    onMapObjects: () => void;
}

export interface EventsHandle {
    isValid: (cb: (err?: string) => void) => void;
}

// ── Helpers ──────────────────────────────────────────────────────────

const LOGIC_OPTIONS = [
    { label: '=', value: 'eq' },
    { label: 'Subtract', value: 'subtract' },
    { label: 'Add', value: 'add' },
];

// ── Component ────────────────────────────────────────────────────────

const Events = forwardRef<EventsHandle, EventsProps>(({ onMapObjects }, ref) => {
    const dispatch = useAppDispatch();
    const ezbids = useAppSelector((state) => state.ezbids.data);
    const events = useAppSelector((state) => state.events);
    const columns = events.columns;
    const trialTypes = events.trialTypes;
    const columnKeys = events.columnKeys ?? [];
    const sampleValues = events.sampleValues;

    // ── Validation exposed to parent ────────────────────────────────
    useImperativeHandle(ref, () => ({
        isValid(cb: (err?: string) => void) {
            let err: string | undefined;
            if (events.loaded) {
                if (!columns.onset) err = 'Please specify onset column';
                if (columns.onsetLogic !== 'eq' && !columns.onset2) err = 'Please specify 2nd operand for onset';
                if (!columns.duration) err = 'Please specify duration column';
                if (columns.durationLogic !== 'eq' && !columns.duration2)
                    err = 'Please specify 2nd operand for duration';
            }
            cb(err);
        },
    }));

    // ── Column update helper ────────────────────────────────────────
    const setColumn = useCallback(
        (field: string, value: string | null) => {
            dispatch(
                updateEvents({
                    columns: { ...columns, [field]: value },
                })
            );
        },
        [dispatch, columns]
    );

    const setTrialTypes = useCallback(
        (patch: Partial<typeof trialTypes>) => {
            dispatch(updateEvents({ trialTypes: { ...trialTypes, ...patch } }));
        },
        [dispatch, trialTypes]
    );

    // ── Reset ───────────────────────────────────────────────────────
    const reset = useCallback(() => {
        // remove existing func/events objects — handled via ezbids reducer
        // For now we filter in-place through addObject pattern; a dedicated
        // reducer would be cleaner but matches the Vue behaviour:
        dispatch(resetEvents());
    }, [dispatch]);

    // ── Open directory & parse ───────────────────────────────────────
    const open = useCallback(
        async (event: React.ChangeEvent<HTMLInputElement>) => {
            const element = event.currentTarget;
            const files: IPathAndData[] = [];
            const filesIgnore: string[] = [];
            if (!element.files) return;

            for (const file of Array.from(element.files)) {
                const fileExt = file.webkitRelativePath.split('.').pop();
                if (
                    fileExt !== 'tsv' &&
                    fileExt !== 'csv' &&
                    fileExt !== 'txt' &&
                    fileExt !== 'out' &&
                    fileExt !== 'xlsx'
                ) {
                    filesIgnore.push(file.webkitRelativePath);
                } else {
                    files.push({
                        path: file.webkitRelativePath,
                        data: await file.text(),
                    });
                }
            }

            // Reset first
            dispatch(resetEvents());

            try {
                if (filesIgnore.length) {
                    alert(
                        'The following files contain an unsupported extension and will be ignored:\n\n' +
                            filesIgnore.join('\n')
                    );
                }

                // Create new event objects
                const eventObjects = createEventObjects(ezbids, files);

                eventObjects.forEach((object: any) => {
                    dispatch(addObject(object));
                });

                onMapObjects();

                // Enumerate all possible column headers from first example
                const example = ezbids.objects.find((o: IObject) => o._type === 'func/events');
                if (!example) return;
                const tsvItem = eventObjects[0].items.find(
                    (i: any) =>
                        i.name === 'csv' ||
                        i.name === 'out' ||
                        i.name === 'txt' ||
                        i.name === 'tsv' ||
                        i.name === 'xlsx'
                );
                if (!tsvItem) return;

                const firstEvent = tsvItem.events[0];
                const newColumnKeys = Object.keys(firstEvent);

                // Construct sample values
                const newSampleValues: Record<string, string[]> = {};
                newColumnKeys.forEach((key: string) => {
                    const samples: string[] = [];
                    tsvItem.events.forEach((rec: any) => {
                        if (!samples.includes(rec[key]) && samples.length < 30) samples.push(rec[key]);
                    });
                    newSampleValues[key] = samples;
                });

                const columnMappings = mapEventColumns(
                    { columns: events.columns, trialTypes: events.trialTypes },
                    tsvItem.events
                );

                dispatch(
                    updateEvents({
                        columnKeys: newColumnKeys,
                        sampleValues: newSampleValues,
                        columns: { ...columns, ...columnMappings },
                        loaded: true,
                    })
                );

                console.log('successfully processed event files');
            } catch (err) {
                console.error(err);
                alert('failed to parse/map event files: ' + err);
            }
        },
        [dispatch, ezbids, events, columns, onMapObjects]
    );

    // ── Render: column mapping row ──────────────────────────────────
    const renderMappingRow = (
        label: string,
        required: boolean,
        logicField: string | null,
        mainField: string,
        secondField: string | null,
        unitField: string | null,
        description: string
    ) => {
        const logicValue = logicField ? (columns as any)[logicField] : null;
        const showSecond = logicValue && ['subtract', 'add'].includes(logicValue);

        return (
            <tr key={mainField}>
                <th className="align-top p-1.5 pr-5 min-w-[170px] text-right opacity-70">
                    {label}
                    {required && '*'}
                </th>
                <td className="align-top">
                    {logicField && (
                        <>
                            <select
                                className="text-sm border border-gray-300 rounded px-2 py-1 w-[100px]"
                                value={logicValue}
                                onChange={(e) => setColumn(logicField, e.target.value)}
                            >
                                {LOGIC_OPTIONS.map((opt) => (
                                    <option key={opt.value} value={opt.value}>
                                        {opt.label}
                                    </option>
                                ))}
                            </select>
                            &nbsp;
                        </>
                    )}
                    <ColumnSelecter
                        value={(columns as any)[mainField] ?? ''}
                        onChange={(v) => setColumn(mainField, v || null)}
                        columnKeys={columnKeys}
                        sampleValues={sampleValues}
                    />
                    {showSecond && (
                        <>
                            <span>&nbsp;{logicValue === 'subtract' ? '-' : '+'}&nbsp;</span>
                            <ColumnSelecter
                                value={(columns as any)[secondField!] ?? ''}
                                onChange={(v) => setColumn(secondField!, v || null)}
                                columnKeys={columnKeys}
                                sampleValues={sampleValues}
                            />
                        </>
                    )}
                    {unitField && (
                        <>
                            &nbsp;
                            <select
                                className="text-sm border border-gray-300 rounded px-2 py-1 w-[120px]"
                                value={(columns as any)[unitField]}
                                onChange={(e) => setColumn(unitField, e.target.value)}
                            >
                                <option value="ms">millisecond</option>
                            </select>
                        </>
                    )}
                    <p className="text-[90%] opacity-80">{description}</p>
                    <br />
                </td>
            </tr>
        );
    };

    // ── Render: not loaded (upload) ─────────────────────────────────
    if (!events.loaded) {
        return (
            <div className="p-5">
                <p>
                    If you'd like to include task events/timing data with your BIDS datasets, you can upload them here.
                </p>
                <p>
                    Please skip this page if working with MEG data, if you do not have events data, or if your events
                    data are not set up where each row pertains to an individual trial. An exception is E-Prime txt
                    files, which are allowed for functional BOLD data.
                </p>
                <p>
                    Only the following file extensions will be accepted by ezBIDS: <b>.csv</b>, <b>.tsv</b>, <b>.txt</b>
                    , <b>.out</b>, and <b>.xlsx</b>. Uploaded files with other extensions will be ignored.
                </p>

                <br />

                <input
                    type="file"
                    /* @ts-expect-error webkitdirectory is non-standard */
                    webkitdirectory=""
                    /* @ts-expect-error mozdirectory is non-standard */
                    mozdirectory=""
                    placeholder="Select Directory"
                    onChange={open}
                />

                <br />
                <br />
                <br />
                <div className="bg-gray-50 border border-gray-200 rounded p-4">
                    <h2 className="text-lg font-semibold">Hint</h2>
                    <p>
                        To ensure proper mapping of events to their imaging files, please have subject, (session), task,
                        and run information in the event file columns, or have the information in the file paths. An
                        example of the latter can be found below.
                    </p>
                    <div className="clearfix">
                        <img src={eventsDirectoryExample} width="600" alt="Events directory upload example" />
                    </div>
                </div>
                <br />
                <br />
                <br />
            </div>
        );
    }

    // ── Render: loaded (column mapping) ─────────────────────────────
    return (
        <div className="p-5">
            <button
                className="float-right bg-yellow-500 hover:bg-yellow-600 text-white px-4 py-2 rounded"
                onClick={reset}
            >
                Reset
            </button>
            <h3 className="text-lg font-semibold">Column Mapping</h3>
            <p>Please correct the column mappings.</p>

            <table>
                <tbody>
                    {renderMappingRow(
                        'Onset',
                        true,
                        'onsetLogic',
                        'onset',
                        'onset2',
                        'onsetUnit',
                        'Onset of the event measured from the beginning of the acquisition of the first volume in the corresponding task imaging data file. If any acquired scans have been discarded before forming the imaging data file, ensure that a time of 0 corresponds to the first image stored. In other words negative numbers in "onset" are allowed.'
                    )}
                    {renderMappingRow(
                        'Duration',
                        true,
                        'durationLogic',
                        'duration',
                        'duration2',
                        'durationUnit',
                        'Duration of the event (measured from onset). Must always be either zero or positive. A "duration" value of zero implies that the delta function or event is so short as to be effectively modeled as an impulse.'
                    )}
                    {renderMappingRow(
                        'Sample',
                        false,
                        'sampleLogic',
                        'sample',
                        'sample2',
                        null,
                        'Onset of the event according to the sampling scheme of the recorded modality (that is, referring to the raw data file that the events.tsv file accompanies).'
                    )}
                    {renderMappingRow(
                        'Response Time',
                        false,
                        'responseTimeLogic',
                        'responseTime',
                        'responseTime2',
                        'responseTimeUnit',
                        'Response time measured in seconds. A negative response time can be used to represent preemptive responses and "n/a" denotes a missed response.'
                    )}

                    {/* Trial Type — special row */}
                    <tr>
                        <th className="align-top p-1.5 pr-5 min-w-[170px] text-right opacity-70">Trial Type</th>
                        <td className="align-top">
                            <ColumnSelecter
                                value={columns.trialType ?? ''}
                                onChange={(v) => setColumn('trialType', v || null)}
                                columnKeys={columnKeys}
                                sampleValues={sampleValues}
                            />

                            <p className="text-[90%] opacity-80">
                                Primary categorisation of each trial to identify them as instances of the experimental
                                conditions. For example: for a response inhibition task, it could take on values "go"
                                and "no-go" to refer to response initiation and response inhibition experimental
                                conditions.
                            </p>

                            {columns.trialType && (
                                <div>
                                    <div className="flex items-center border border-gray-300 rounded overflow-hidden mb-2">
                                        <span className="bg-gray-100 px-3 py-1 text-sm border-r border-gray-300">
                                            longName
                                        </span>
                                        <input
                                            className="flex-1 px-2 py-1 text-sm outline-none"
                                            value={trialTypes.longName}
                                            onChange={(e) => setTrialTypes({ longName: e.target.value })}
                                        />
                                    </div>
                                    <div className="flex items-center border border-gray-300 rounded overflow-hidden mb-2">
                                        <span className="bg-gray-100 px-3 py-1 text-sm border-r border-gray-300">
                                            Description
                                        </span>
                                        <input
                                            className="flex-1 px-2 py-1 text-sm outline-none"
                                            value={trialTypes.desc}
                                            onChange={(e) => setTrialTypes({ desc: e.target.value })}
                                        />
                                    </div>

                                    <span>Levels</span>
                                    {sampleValues[columns.trialType]?.map((value) => (
                                        <div key={value} className="mt-1">
                                            <div className="flex items-center border border-gray-300 rounded overflow-hidden">
                                                <span className="bg-gray-100 px-3 py-1 text-sm border-r border-gray-300">
                                                    {value}
                                                </span>
                                                <input
                                                    className="flex-1 px-2 py-1 text-sm outline-none"
                                                    placeholder="desc"
                                                    value={trialTypes.levels[value] ?? ''}
                                                    onChange={(e) =>
                                                        setTrialTypes({
                                                            levels: {
                                                                ...trialTypes.levels,
                                                                [value]: e.target.value,
                                                            },
                                                        })
                                                    }
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                            <br />
                        </td>
                    </tr>

                    {/* Value */}
                    <tr>
                        <th className="align-top p-1.5 pr-5 min-w-[170px] text-right opacity-70">Value</th>
                        <td className="align-top">
                            <ColumnSelecter
                                value={columns.value ?? ''}
                                onChange={(v) => setColumn('value', v || null)}
                                columnKeys={columnKeys}
                                sampleValues={sampleValues}
                            />
                            <p className="text-[90%] opacity-80">
                                Marker value associated with the event (for example, the value of a TTL trigger that was
                                recorded at the onset of the event).
                            </p>
                            <br />
                        </td>
                    </tr>

                    {/* HED */}
                    <tr>
                        <th className="align-top p-1.5 pr-5 min-w-[170px] text-right opacity-70">HED</th>
                        <td className="align-top">
                            <ColumnSelecter
                                value={columns.HED ?? ''}
                                onChange={(v) => setColumn('HED', v || null)}
                                columnKeys={columnKeys}
                                sampleValues={sampleValues}
                            />
                            <p className="text-[90%] opacity-80">
                                Hierarchical Event Descriptor (HED) Tag. See{' '}
                                <a href="https://bids-specification.readthedocs.io/en/stable/99-appendices/03-hed.html">
                                    BIDS Specification / Appendix 3
                                </a>
                            </p>
                            <br />
                        </td>
                    </tr>

                    {/* stim_file */}
                    <tr>
                        <th className="align-top p-1.5 pr-5 min-w-[170px] text-right opacity-70">stim_file</th>
                        <td className="align-top">
                            <ColumnSelecter
                                value={columns.stim_file ?? ''}
                                onChange={(v) => setColumn('stim_file', v || null)}
                                columnKeys={columnKeys}
                                sampleValues={sampleValues}
                            />
                            <p className="text-[90%] opacity-80">
                                Represents the location of the stimulus file (such as an image, video, or audio file)
                                presented at the given onset time. There are no restrictions on the file formats of the
                                stimuli files, but they should be stored in the /stimuli directory (under the root
                                directory of the dataset; with OPTIONAL subdirectories). The values under the stim_file
                                column correspond to a path relative to /stimuli. For example images/cat03.jpg will be
                                translated to /stimuli/images/cat03.jpg. See{' '}
                                <a href="https://bids-specification.readthedocs.io/en/stable/99-appendices/03-hed.html">
                                    BIDS Specification / Appendix 3
                                </a>
                            </p>
                            <br />
                        </td>
                    </tr>
                </tbody>
            </table>

            <br />
            <br />
            <br />
        </div>
    );
});

Events.displayName = 'Events';

export default Events;
