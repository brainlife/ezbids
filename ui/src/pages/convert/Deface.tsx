import React, { forwardRef, useImperativeHandle, useEffect, useMemo, useCallback } from 'react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { loadDefaceStatus, type IObject } from '../../store/slices/ezbidsSlice';
import { loadSession } from '../../store/slices/sessionSlice';
import axios from '../../axios.instance';
import toast from 'react-hot-toast';
import Datatype from '../../components/Datatype';
import AsyncImageLink from '../../components/AsyncImageLink';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faEye, faSpinner } from '@fortawesome/free-solid-svg-icons';

// ── Types ────────────────────────────────────────────────────────────

interface DefaceProps {
    onNiivue: (path: string) => void;
}

export interface DefaceHandle {
    isValid: (cb: (err?: string) => void) => void;
}

// ── Component ────────────────────────────────────────────────────────

const Deface = forwardRef<DefaceHandle, DefaceProps>(({ onNiivue }, ref) => {
    const dispatch = useAppDispatch();
    const ezbids = useAppSelector((state) => state.ezbids.data);
    const session = useAppSelector((state) => state.session.data);
    const config = useAppSelector((state) => state.session.config);

    const anatObjects = useMemo(
        () => ezbids.objects.filter((o: IObject) => o._type.startsWith('anat') && !o._exclude),
        [ezbids.objects]
    );

    const isDefacing = useMemo(() => {
        if (!session) return false;
        return ['deface', 'defacing'].includes(session.status);
    }, [session]);

    // Initialize all anat objects to use defaced image by default
    useEffect(() => {
        anatObjects.forEach((o: IObject) => {
            if (!o.defaceSelection) {
                o.defaceSelection = 'defaced';
            }
        });
    }, [anatObjects]);

    // Poll deface status while defacing
    useEffect(() => {
        if (!isDefacing) return;
        const interval = setInterval(() => {
            dispatch(loadDefaceStatus());
            dispatch(loadSession());
        }, 3000);
        return () => clearInterval(interval);
    }, [isDefacing, dispatch]);

    // ── Validation exposed to parent ────────────────────────────────
    useImperativeHandle(ref, () => ({
        isValid(cb: (err?: string) => void) {
            if (!ezbids.defacingMethod) return cb();
            if (!session?.deface_begin_date) {
                return cb('Please run deface');
            }
            if (session.deface_begin_date && session.status === 'failed') {
                let err: string | undefined;
                anatObjects.forEach((o: IObject) => {
                    if (o.defaceSelection === 'defaced' && !o.defaced)
                        err = 'Please set to use original image for deface-failed images';
                });
                return cb(err);
            }
            if (!session.deface_finish_date) {
                return cb('Please wait for defacing to finish');
            }
            cb();
        },
    }));

    // ── Helpers ─────────────────────────────────────────────────────
    const getDefacedURL = useCallback((anat: IObject): string | null => {
        const item = anat.items.find((i) => i.path.endsWith('.nii.gz'));
        if (!item) return null;
        return item.path + '.defaced.nii.gz';
    }, []);

    const changeMethod = useCallback(
        (method: string) => {
            // Direct mutation on ezbids data (matches Vue store pattern with serializableCheck: false)
            ezbids.defacingMethod = method;
            if (method) {
                anatObjects.forEach((o: IObject) => {
                    o.defaceSelection = 'defaced';
                });
            } else {
                anatObjects.forEach((o: IObject) => {
                    o.defaceSelection = 'original';
                });
            }
        },
        [ezbids, anatObjects]
    );

    const runDeface = useCallback(() => {
        if (!session) return;
        const list = anatObjects.map((o: IObject) => ({
            idx: o.idx,
            path: o.items.find((i) => i.path?.endsWith('.nii.gz'))?.path,
        }));

        // Reset current status
        anatObjects.forEach((o: IObject) => {
            delete o.defaced;
        });

        axios
            .post(`${config.apihost}/session/${session._id}/deface`, {
                list,
                method: ezbids.defacingMethod,
            })
            .then((res) => {
                if (res.data !== 'ok') {
                    toast.error('Failed to submit deface request');
                }
                dispatch(loadSession());
            });
    }, [anatObjects, config.apihost, dispatch, ezbids.defacingMethod, session]);

    const cancel = useCallback(() => {
        if (!session) return;
        axios.post(`${config.apihost}/session/${session._id}/canceldeface`).then((res) => {
            if (res.data !== 'ok') {
                toast.error('Failed to cancel defacing');
            } else {
                toast.success('Requested to cancel defacing..');
            }
            dispatch(loadSession());
        });
    }, [config.apihost, dispatch, session]);

    const resetDeface = useCallback(() => {
        if (!session) return;
        axios.post(`${config.apihost}/session/${session._id}/resetdeface`).then((res) => {
            if (res.data !== 'ok') {
                toast.error('Failed to reset defacing');
            }
            anatObjects.forEach((anat: IObject) => {
                delete anat.defaced;
                delete anat.defaceFailed;
                anat.defaceSelection = 'defaced';
            });
            dispatch(loadSession());
        });
    }, [anatObjects, config.apihost, dispatch, session]);

    // ── Render ──────────────────────────────────────────────────────
    return (
        <div className="p-5">
            {/* Method selection form — shown when there are anat objects and not currently defacing */}
            {anatObjects.length > 0 && !isDefacing && (
                <div>
                    <p>
                        If you'd like to deface all anatomical images, please select a defacing method and click{' '}
                        <b>Run Deface</b> button. Otherwise, you can skip this page.
                    </p>
                    <p>
                        Defaced images will be reoriented via FSL's <i>reorient2std</i> function to ensure proper
                        defacing.
                    </p>

                    <div className="mb-0">
                        <b>Defacing Method </b>
                        <br />
                        <select
                            className="border border-gray-300 rounded px-3 py-2 w-[300px]"
                            value={ezbids.defacingMethod}
                            onChange={(e) => changeMethod(e.target.value)}
                        >
                            <option value="">Don't Deface (use original)</option>
                            <option value="quickshear">Quickshear (recommended)</option>
                            <option value="pydeface">pyDeface (more common but takes much longer time)</option>
                        </select>
                    </div>

                    {ezbids.defacingMethod === 'quickshear' && (
                        <p>
                            <small>* Use ROBEX and QuickShear Average processing time. ~1 min per image</small>
                        </p>
                    )}
                    {ezbids.defacingMethod === 'pydeface' && (
                        <p>
                            <small>* pydeface uses FSL to align facial mask template. ~5 min per image</small>
                        </p>
                    )}
                </div>
            )}

            {/* Action buttons */}
            <div className="mb-0">
                {!isDefacing && ezbids.defacingMethod && !session?.deface_finish_date && (
                    <button
                        className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded"
                        onClick={runDeface}
                    >
                        Run Deface
                    </button>
                )}
                {isDefacing && (
                    <button className="bg-yellow-500 hover:bg-yellow-600 text-white px-4 py-2 rounded" onClick={cancel}>
                        Cancel Defacing
                    </button>
                )}
                {session?.deface_begin_date && session?.deface_finish_date && (
                    <button
                        className="bg-gray-200 hover:bg-gray-300 text-gray-700 px-4 py-2 rounded"
                        onClick={resetDeface}
                    >
                        Reset Deface
                    </button>
                )}
            </div>

            <br />

            {/* No anatomy files warning */}
            {anatObjects.length === 0 && (
                <div className="bg-yellow-50 border border-yellow-300 text-yellow-800 px-4 py-3 rounded">
                    No anatomy files to deface. Please skip this step.
                </div>
            )}

            {/* Status display while defacing */}
            {anatObjects.length > 0 && ezbids.defacingMethod && (
                <>
                    {(session?.status === 'deface' || session?.status === 'defacing') && (
                        <div>
                            <h3 className="text-lg font-semibold">
                                Running <b>{ezbids.defacingMethod}</b> ...
                            </h3>
                            <pre className="bg-gray-700 text-white h-[125px] overflow-auto p-2.5 mb-1 rounded">
                                {session.status_msg}
                            </pre>
                        </div>
                    )}
                    {session?.deface_finish_date && (
                        <div className="bg-green-50 border border-green-300 text-green-800 px-4 py-3 rounded flex items-center gap-2">
                            Defacing completed! Please check the defacing results and proceed to the next page.
                        </div>
                    )}
                    {session?.status === 'failed' && (
                        <div>
                            Failed!
                            <pre className="bg-gray-700 text-white h-[125px] overflow-auto p-2.5 mb-1 rounded">
                                {session.status_msg}
                            </pre>
                        </div>
                    )}
                </>
            )}

            {/* Anat objects table */}
            {session?.deface_begin_date && (
                <table className="w-full border-collapse">
                    <thead>
                        <tr>
                            <th className="text-left p-1"></th>
                            <th className="text-left p-1">Original</th>
                            <th className="text-left p-1">Defaced</th>
                        </tr>
                    </thead>
                    <tbody>
                        {anatObjects.map((anat) => (
                            <tr key={anat.idx} className="border-t border-gray-200">
                                <td className="align-top pt-1">
                                    <div className="mb-0 text-[85%] leading-[200%]">
                                        <span>
                                            <small>sub</small> {anat._entities.subject}{' '}
                                        </span>
                                        {anat._entities.session && (
                                            <span>
                                                / <small>ses</small> {anat._entities.session}{' '}
                                            </span>
                                        )}
                                    </div>
                                    <span className="inline-block bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded">
                                        #{anat.series_idx}
                                    </span>
                                    &nbsp;
                                    <Datatype type={anat._type} series_idx={anat.series_idx} entities={anat.entities} />
                                </td>

                                {/* Original column */}
                                <td className="w-[40%] align-top relative pt-1">
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="radio"
                                            name={`deface-${anat.idx}`}
                                            checked={anat.defaceSelection === 'original'}
                                            onChange={() => {
                                                anat.defaceSelection = 'original';
                                            }}
                                        />
                                        Use Original
                                    </label>
                                    {anat.items.map(
                                        (item, itemIdx) =>
                                            item.pngPaths && (
                                                <div key={itemIdx}>
                                                    <AsyncImageLink path={item.pngPaths[0]} />
                                                    <button
                                                        className="absolute top-[50px] left-[5px] bg-gray-500 hover:bg-gray-600 text-white text-sm px-3 py-1 rounded"
                                                        onClick={() => onNiivue(item.path)}
                                                    >
                                                        <FontAwesomeIcon icon={faEye} /> NiiVue
                                                    </button>
                                                </div>
                                            )
                                    )}
                                </td>

                                {/* Defaced column */}
                                <td className="w-[40%] align-top relative pt-1">
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="radio"
                                            name={`deface-${anat.idx}`}
                                            checked={anat.defaceSelection === 'defaced'}
                                            onChange={() => {
                                                anat.defaceSelection = 'defaced';
                                            }}
                                        />
                                        Use Defaced (when finish defacing)
                                    </label>
                                    {anat.defaced && (
                                        <div>
                                            <AsyncImageLink path={`${getDefacedURL(anat)}.png`} />
                                            <button
                                                className="absolute top-[50px] left-[5px] bg-gray-500 hover:bg-gray-600 text-white text-sm px-3 py-1 rounded"
                                                onClick={() => {
                                                    const url = getDefacedURL(anat);
                                                    if (url) onNiivue(url);
                                                }}
                                            >
                                                <FontAwesomeIcon icon={faEye} /> NiiVue
                                            </button>
                                        </div>
                                    )}
                                    {session.status === 'defacing' && !anat.defaced && (
                                        <p className="bg-gray-100 px-5 py-2.5 m-0">
                                            <small>
                                                Defacing <FontAwesomeIcon icon={faSpinner} pulse />
                                            </small>
                                        </p>
                                    )}
                                    {anat.defaceFailed && (
                                        <p className="bg-red-500 text-white px-5 py-2.5 m-0">
                                            <small>Defacing Failed</small>
                                        </p>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    );
});

Deface.displayName = 'Deface';

export default Deface;
