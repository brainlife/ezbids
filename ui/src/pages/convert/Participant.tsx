import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useState } from 'react';
import { useAppSelector } from '../../store/hooks';
import type { OrganizedSubject } from '../../store/slices/ezbidsSlice';

interface ParticipantHandle {
    isValid: (cb: (err?: string) => void) => void;
}

const Participant = forwardRef<ParticipantHandle>(function Participant(_props, ref) {
    const ezbids = useAppSelector((s) => s.ezbids.data);
    const [newcolumn, setNewcolumn] = useState('');
    const [, forceUpdate] = useState(0);

    // Initialize participantsInfo for each organized subject
    useEffect(() => {
        ezbids._organized.forEach((o: OrganizedSubject) => {
            if (!ezbids.participantsInfo[o.subject_idx]) {
                ezbids.participantsInfo[o.subject_idx] = {};
            }
        });
    }, []);

    useImperativeHandle(
        ref,
        () => ({
            isValid(cb: (err?: string) => void) {
                console.log('todo - validate participant');
                cb();
            },
        }),
        []
    );

    // Only show subjects that are really used (not excluded)
    const finalSubs = useMemo(() => {
        const result: number[] = [];
        ezbids._organized.forEach((sub: OrganizedSubject) => {
            let use = false;
            sub.sess.forEach((ses) => {
                if (ses.objects.some((o) => !o._exclude)) use = true;
            });
            if (use) result.push(sub.subject_idx);
        });
        return result;
    }, [ezbids._organized]);

    const addNewColumn = useCallback(() => {
        if (!newcolumn) return;
        if (ezbids.participantsColumn && ezbids.participantsColumn[newcolumn]) return;
        ezbids.participantsColumn[newcolumn] = {
            Description: '',
            Units: '',
            Levels: {},
        };
        setNewcolumn('');
        forceUpdate((n) => n + 1);
    }, [newcolumn, ezbids.participantsColumn]);

    const removeColumn = useCallback(
        (key: string) => {
            delete ezbids.participantsColumn[key];
            forceUpdate((n) => n + 1);
        },
        [ezbids.participantsColumn]
    );

    const handleColumnDescriptionChange = useCallback(
        (key: string, value: string) => {
            ezbids.participantsColumn[key].Description = value;
            forceUpdate((n) => n + 1);
        },
        [ezbids.participantsColumn]
    );

    const handleColumnUnitsChange = useCallback(
        (key: string, value: string) => {
            ezbids.participantsColumn[key].Units = value;
            forceUpdate((n) => n + 1);
        },
        [ezbids.participantsColumn]
    );

    const handleParticipantInfoChange = useCallback(
        (subjectIdx: number, key: string, value: string) => {
            if (!ezbids.participantsInfo[subjectIdx]) {
                ezbids.participantsInfo[subjectIdx] = {};
            }
            ezbids.participantsInfo[subjectIdx][key] = value.trim();
            forceUpdate((n) => n + 1);
        },
        [ezbids.participantsInfo]
    );

    const columnKeys = Object.keys(ezbids.participantsColumn || {});

    return (
        <div className="p-5">
            <p>You can store metadata/phenotypical data for each participant in this dataset.</p>
            <p>Please skip this step if you do not wish to store any phenotypical data.</p>

            <h5 className="text-base font-semibold mt-4">Phenotype Columns</h5>
            <small className="text-gray-500">Define phenotypical keys stored for this study (recommended).</small>
            <br />
            <br />

            <div className="flex flex-wrap gap-2.5">
                {/* Column Editors */}
                {columnKeys.map((key) => {
                    const column = ezbids.participantsColumn[key];
                    return (
                        <div key={key} className="bg-gray-50 mb-2.5 p-4 rounded w-[300px] text-center">
                            <span className="float-right">
                                <button
                                    className="px-2 py-0.5 bg-red-500 hover:bg-red-600 text-white text-xs rounded"
                                    onClick={() => removeColumn(key)}
                                >
                                    &#10005;
                                </button>
                            </span>
                            <b>{key}</b>
                            <br />
                            <br className="clear-both" />

                            <div className="mb-2 text-left">
                                <label className="block text-sm text-gray-600 mb-1">Description</label>
                                <textarea
                                    className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                                    placeholder="Description"
                                    value={column.Description || ''}
                                    onChange={(e) => handleColumnDescriptionChange(key, e.target.value)}
                                />
                            </div>

                            <div className="mb-2 text-left">
                                <label className="block text-sm text-gray-600 mb-1">Units</label>
                                <input
                                    type="text"
                                    className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                                    placeholder="Units"
                                    value={column.Units || ''}
                                    onChange={(e) => handleColumnUnitsChange(key, e.target.value)}
                                />
                            </div>

                            <div className="mb-2 text-left">
                                <label className="block text-sm text-gray-600 mb-1">Levels</label>
                                <small className="text-gray-400">TODO.. (levels)</small>
                            </div>
                        </div>
                    );
                })}

                {/* Add New Column */}
                <div className="bg-gray-50 p-4 rounded w-[200px] text-center">
                    <div className="flex">
                        <input
                            type="text"
                            className="border border-gray-300 rounded-l px-2 py-1 text-sm flex-1 min-w-0"
                            placeholder="Add New Column"
                            value={newcolumn}
                            onChange={(e) => setNewcolumn(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') addNewColumn();
                            }}
                        />
                        <button
                            className="px-3 py-1 bg-blue-500 hover:bg-blue-600 text-white text-sm rounded-r"
                            onClick={addNewColumn}
                        >
                            Add
                        </button>
                    </div>
                    <div className="mt-2">
                        <a
                            href="https://bids-specification.readthedocs.io/en/stable/03-modality-agnostic-files.html#participants-file"
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-500 text-sm"
                        >
                            See here for suggestions
                        </a>
                    </div>
                </div>
            </div>

            <br className="clear-both" />

            <h5 className="text-base font-semibold mt-4">participants.tsv</h5>
            <small className="text-gray-500">Enter phenotypical data associated with each participant.</small>
            <br />
            <br />

            <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-[90%]">
                    <thead className="bg-gray-100 text-gray-600">
                        <tr>
                            <th className="p-1.5 px-2.5 text-left">participant_id</th>
                            {columnKeys.map((key) => (
                                <th key={key} className="p-1.5 px-2.5 text-left">
                                    {key}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {finalSubs.map((subjectIdx) => (
                            <tr key={subjectIdx}>
                                <th className="p-1.5 px-2.5 text-left font-normal">
                                    sub-{ezbids.subjects[subjectIdx]?.subject}
                                </th>
                                {columnKeys.map((key) => (
                                    <td key={key} className="p-1.5 px-2.5">
                                        <input
                                            type="text"
                                            className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                                            value={ezbids.participantsInfo[subjectIdx]?.[key] || ''}
                                            onChange={(e) =>
                                                handleParticipantInfoChange(subjectIdx, key, e.target.value)
                                            }
                                        />
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
});

export default Participant;
