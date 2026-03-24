import { forwardRef, useCallback, useImperativeHandle, useState } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import toast from 'react-hot-toast';

import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { loadSession } from '../../store/slices/sessionSlice';
import axios from '../../axios.instance';
import { hasAuth } from '../../lib';
import ShowFile from '../../components/ShowFile';

// ── Types ─────────────────────────────────────────────────────────────

interface FinalizeHandle {
    isValid: (cb: (err?: string) => void) => void;
}

// ── Component ─────────────────────────────────────────────────────────

const Finalize = forwardRef<FinalizeHandle>(function Finalize(_props, ref) {
    const dispatch = useAppDispatch();
    const session = useAppSelector((s) => s.session.data);
    const config = useAppSelector((s) => s.session.config);
    const ezbids = useAppSelector((s) => s.ezbids.data);
    const bidsSchema = useAppSelector((s) => s.ezbids.bidsSchema);

    const [submitting, setSubmitting] = useState(false);
    const [activeLogs, setActiveLogs] = useState<string[]>([]);

    const isAuthEnabled = hasAuth();

    // ── Expose isValid ───────────────────────────────────────────────

    useImperativeHandle(
        ref,
        () => ({
            isValid(cb: (err?: string) => void) {
                if (session?.status !== 'finished') {
                    return cb('Please finalize the page first');
                }
                cb();
            },
        }),
        [session?.status]
    );

    // ── Finalize ─────────────────────────────────────────────────────

    const dofinalize = useCallback(
        (cb: (err: string | null) => void) => {
            // Build entity mappings from bids schema
            const entityMappings: Record<string, string> = {};
            for (const key in bidsSchema.entities) {
                entityMappings[key] = bidsSchema.entities[key].entity;
            }

            axios
                .post(`${config.apihost}/session/${session?._id}/finalize`, {
                    subjects: ezbids.subjects,
                    series: ezbids.series,
                    defacingMethod: ezbids.defacingMethod,
                    includeExcluded: ezbids.includeExcluded,
                    objects: ezbids.objects,
                    BIDSURI: ezbids.BIDSURI,
                    events: (ezbids as any).events,
                    entityMappings,
                    datasetDescription: ezbids.datasetDescription,
                    readme: ezbids.readme,
                    participantsColumn: ezbids.participantsColumn,
                    participantInfo: ezbids.participantsInfo,
                })
                .then((res) => {
                    cb(res.data === 'ok' ? null : res.data);
                });
        },
        [config.apihost, session?._id, ezbids, bidsSchema.entities]
    );

    const finalize = useCallback(() => {
        if (!session) return; // Mutate session status to trigger converting UI
        (session as any).status = 'finalized';
        delete (session as any).finalize_begin_date;
        delete (session as any).finalize_finish_date;

        setSubmitting(true);
        dofinalize((err) => {
            if (err) {
                toast.error('Failed to finalize: ' + err);
                console.error(err);
            }
            setSubmitting(false);
            dispatch(loadSession());
        });
    }, [session, dofinalize, dispatch]);

    // ── Download ─────────────────────────────────────────────────────

    const download = useCallback(
        async (fileName: string) => {
            if (!fileName || !session?._id) return;
            try {
                const res = await axios.get(`${config.apihost}/download/${session._id}/token`);
                const shortLivedJWT = res.data;
                window.location.href = `${config.apihost}/download/${session._id}/${fileName}?token=${shortLivedJWT}`;
            } catch (e) {
                console.error(e);
                toast.error('There was an error downloading the file');
            }
        },
        [config.apihost, session?._id]
    );

    const downloadSubjectMapping = useCallback(() => {
        const data = JSON.stringify(ezbids.subjects, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'subject_mappings.json';
        link.click();
        URL.revokeObjectURL(link.href);
    }, [ezbids.subjects]);

    // ── Send to external services ────────────────────────────────────

    const sendBrainlife = useCallback(
        (pipeline?: 'DWI') => {
            const pipelineString = pipeline ? `&pipeline=${pipeline}` : '';
            window.open(
                `https://brainlife.io/projects#ezbids=${session?._id}${pipelineString}`,
                `_brainlife.${session?._id}`
            );
        },
        [session?._id]
    );

    const sendOpenneuro = useCallback(async () => {
        if (!session?._id) return;
        try {
            const res = await axios.get(`${config.apihost}/download/${session._id}/token`);
            const shortLivedJWT = res.data;
            const url = `${config.apihost}/download/${session._id}/bids/${ezbids.datasetDescription.Name}?token=${shortLivedJWT}`;
            const fullurl = new URL(url, document.baseURI).href;
            window.open('https://openneuro.org/import?url=' + encodeURI(fullurl));
        } catch (e) {
            console.error(e);
            toast.error('There was an error downloading the data');
        }
    }, [config.apihost, session?._id, ezbids.datasetDescription.Name]);

    // ── Collapse toggle ──────────────────────────────────────────────

    const toggleLog = (name: string) => {
        setActiveLogs((prev) => (prev.includes(name) ? prev.filter((l) => l !== name) : [...prev, name]));
    };

    // ── Rerun finalize ───────────────────────────────────────────────

    const rerunFinalize = useCallback(() => {
        if (!session) return;
        (session as any).status = 'analyzed';
    }, [session]);

    // ── Render ───────────────────────────────────────────────────────

    return (
        <div className="p-5">
            {/* Ready to finalize */}
            {(session?.status === 'analyzed' || session?.status === 'defaced') && (
                <div>
                    <p>
                        Your dataset is now ready to be converted to BIDS! Please click the button below to generate
                        BIDS structure.
                    </p>
                    <p>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={!!ezbids.includeExcluded}
                                onChange={(e) => {
                                    (ezbids as any).includeExcluded = e.target.checked;
                                }}
                            />
                            Save all acquisitions set to 'exclude' in an excluded directory in output BIDS structure
                        </label>
                    </p>
                    <br />
                    <button
                        className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded"
                        onClick={finalize}
                        disabled={submitting}
                    >
                        Finalize
                    </button>
                </div>
            )}

            {/* Converting in progress */}
            {(session?.status === 'finalized' ||
                ((session as any)?.finalize_begin_date && !(session as any)?.finalize_finish_date)) &&
                session?.status !== 'analyzed' &&
                session?.status !== 'defaced' && (
                    <div>
                        <h3>
                            Converting to BIDS <FontAwesomeIcon icon="spinner" spin />
                        </h3>
                        <p>
                            <small>
                                <i>{session?.status_msg}</i>
                            </small>
                        </p>
                    </div>
                )}

            {/* All done */}
            {(session as any)?.finalize_finish_date &&
                session?.status !== 'analyzed' &&
                session?.status !== 'defaced' &&
                session?.status !== 'finalized' && (
                    <div>
                        <div className="rounded-lg bg-gray-200 p-5 text-[85%]">
                            <br />
                            <button
                                className="float-right bg-green-500 hover:bg-green-600 text-white px-3 py-1 rounded text-sm"
                                onClick={rerunFinalize}
                            >
                                Rerun Finalize Step
                            </button>
                            <h3 className="mt-0">All Done!</h3>
                            <p>Please download the BIDS formatted data to your local computer</p>
                            <button
                                className="w-[250px] bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded mr-2"
                                onClick={() => download(`bids/${ezbids.datasetDescription.Name}`)}
                            >
                                Download BIDS
                            </button>
                            <button
                                className="w-[250px] bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded"
                                onClick={() => download('finalized.json')}
                            >
                                Download configuration/template
                            </button>
                            <p>Or send the dataset to other cloud resources.</p>
                            <p className="flex items-center gap-2">
                                {isAuthEnabled && (
                                    <span className="relative inline-block mr-2.5">
                                        <details className="inline-block">
                                            <summary className="cursor-pointer bg-white hover:bg-gray-100 border border-gray-300 rounded px-3 py-1.5 text-sm">
                                                Send to <b>Brainlife.io</b> <FontAwesomeIcon icon="angle-down" />
                                            </summary>
                                            <div className="absolute left-0 mt-1 bg-white border border-gray-200 rounded shadow-lg z-10 min-w-[280px]">
                                                <button
                                                    className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-100"
                                                    onClick={() => sendBrainlife()}
                                                >
                                                    Send to brainlife
                                                </button>
                                                <button
                                                    className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-100"
                                                    onClick={() => sendBrainlife('DWI')}
                                                >
                                                    Send to brainlife and run DWI Pipeline
                                                </button>
                                            </div>
                                        </details>
                                    </span>
                                )}
                                <button
                                    className="bg-white hover:bg-gray-100 border border-gray-300 rounded px-3 py-1.5 text-sm"
                                    onClick={sendOpenneuro}
                                >
                                    Send to <b>OpenNeuro</b>
                                </button>
                            </p>

                            <div className="bg-black/5 p-5 pt-2.5">
                                If you have re-named the original DICOM patient names for your BIDS subject/session
                                names, you can download the mapping file.
                                <button
                                    className="text-blue-500 hover:underline bg-transparent border-none cursor-pointer"
                                    onClick={downloadSubjectMapping}
                                >
                                    Download Subject Mapping (.json)
                                </button>
                                <br />
                                <small>
                                    * may contain sensitive PHI data. Please make sure to store the mapping file in a
                                    secure location.
                                </small>
                            </div>

                            <h3>Citation</h3>
                            <div className="bg-black/5 p-5 pt-2.5">
                                <p>
                                    Levitas, D., Hayashi, S., Vinci-Booher, S., Heinsfeld, A., Bhatia, D., Lee, N., ...
                                    & Pestilli, F. (2024). ezBIDS: Guided standardization of neuroimaging data
                                    interoperable with major data archives and platforms. Scientific data, 11(1), 179.{' '}
                                    <a
                                        href="https://doi.org/10.1038/s41597-024-02959-0"
                                        target="_blank"
                                        rel="noreferrer"
                                    >
                                        https://doi.org/10.1038/s41597-024-02959-0
                                    </a>
                                </p>
                            </div>
                        </div>

                        {/* BIDS structure and validator output */}
                        <div className="grid grid-cols-2 gap-4 mt-4">
                            <div>
                                <h4>BIDS Structure</h4>
                                <ShowFile path="tree.log" tall />
                            </div>
                            <div>
                                <h4>bids-validator output</h4>
                                <ShowFile path="validator.log" tall />
                            </div>
                        </div>
                    </div>
                )}

            {/* Failed */}
            {session?.status === 'failed' && (
                <div>
                    <p>Failed to convert to BIDS</p>
                    <button
                        className="float-right bg-green-500 hover:bg-green-600 text-white px-3 py-1 rounded text-sm"
                        onClick={finalize}
                    >
                        Rerun Finalize Step
                    </button>
                    <p>
                        <small>
                            <i>{session?.status_msg}</i>
                        </small>
                    </p>
                </div>
            )}

            {/* Debugging section */}
            <br />
            <br />
            <h4>Debugging</h4>
            <div className="border border-gray-200 rounded">
                {session?.status === 'finished' && (
                    <>
                        <div
                            className="border-b border-gray-200 px-4 py-2 cursor-pointer hover:bg-gray-50 font-medium"
                            onClick={() => toggleLog('bids.log')}
                        >
                            BIDS Conversion Log
                        </div>
                        {activeLogs.includes('bids.log') && (
                            <div className="p-4">
                                <ShowFile path="bids.log" />
                            </div>
                        )}

                        <div
                            className="border-b border-gray-200 px-4 py-2 cursor-pointer hover:bg-gray-50 font-medium"
                            onClick={() => toggleLog('bids.err')}
                        >
                            BIDS Conversion Error Log
                        </div>
                        {activeLogs.includes('bids.err') && (
                            <div className="p-4">
                                <ShowFile path="bids.err" />
                            </div>
                        )}
                    </>
                )}
                <div
                    className="border-b border-gray-200 px-4 py-2 cursor-pointer hover:bg-gray-50 font-medium"
                    onClick={() => toggleLog('session')}
                >
                    Session
                </div>
                {activeLogs.includes('session') && (
                    <div className="p-4">
                        <pre className="whitespace-pre-wrap text-sm">{JSON.stringify(session, null, 2)}</pre>
                    </div>
                )}
            </div>
            <br />
            <br />
        </div>
    );
});

export default Finalize;
