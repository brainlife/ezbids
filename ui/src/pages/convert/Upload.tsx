import { useState, useRef, useCallback, forwardRef, useImperativeHandle } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import toast from 'react-hot-toast';

import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { setSession } from '../../store/slices/sessionSlice';
import { updateDDName, type IObject } from '../../store/slices/ezbidsSlice';
import axios from '../../axios.instance';
import { formatNumber } from '../../filters';
import AnalysisErrors from '../../components/AnalysisErrors';

// ── Types ─────────────────────────────────────────────────────────────

interface UploadFile {
    file: File; // the actual File object for FormData
    path: string;
    size: number;
    lastModified: number;
    uploading: boolean;
    ignore: boolean;
    try: number;
}

interface Batch {
    fileidx: number[];
    evt: { loaded?: number; total?: number };
    status: 'uploading' | 'done' | 'failed';
    size: number;
}

export interface UploadHandle {
    isValid: (cb: (err: string | null) => void) => void;
}

// ── Component ─────────────────────────────────────────────────────────

const Upload = forwardRef<UploadHandle>(function Upload(_props, ref) {
    const dispatch = useAppDispatch();
    const session = useAppSelector((s) => s.session.data);
    const config = useAppSelector((s) => s.session.config);
    const ezbids = useAppSelector((s) => s.ezbids.data);

    const [dragging, setDragging] = useState(false);
    const [starting, setStarting] = useState(false);
    const [opened, setOpened] = useState<number[]>([]);

    // Use refs for mutable upload state (avoids stale closures — mirrors Vue's this.data)
    const filesRef = useRef<UploadFile[]>([]);
    const uploadedRef = useRef<number[]>([]);
    const failedRef = useRef<number[]>([]);
    const batchesRef = useRef<Batch[]>([]);
    const totalSizeRef = useRef(0);
    const ignoreCountRef = useRef(0);
    const doneUploadingRef = useRef(false);
    const sessionIdRef = useRef<string | null>(null);

    // A single counter to trigger re-renders when upload state changes
    const [renderTick, setRenderTick] = useState(0);
    const rerender = useCallback(() => setRenderTick((t) => t + 1), []);

    useImperativeHandle(ref, () => ({
        isValid(cb: (err: string | null) => void) {
            cb(null);
        },
    }));

    // ── Helpers ───────────────────────────────────────────────────────

    function toggleObject(idx: number) {
        setOpened((prev) => (prev.includes(idx) ? prev.filter((i) => i !== idx) : [...prev, idx]));
    }

    function itemPath(items: IObject['items']) {
        let str = '';
        items.forEach((item) => {
            if (str === '') {
                str = item.path;
            } else {
                const strtokens = str.split('.');
                const pathtokens = item.path.split('.');
                str += ' / ';
                for (let i = 0; i < pathtokens.length; ++i) {
                    if (pathtokens[i] === strtokens[i]) continue;
                    else str += '.' + pathtokens[i];
                }
            }
        });
        return str;
    }

    function batchStatusColor(batch: Batch): string {
        switch (batch.status) {
            case 'done':
                return 'bg-green-500';
            case 'failed':
                return 'bg-red-500';
            default:
                return 'bg-blue-500';
        }
    }

    // ── File listing (drag & drop) ────────────────────────────────────

    function wrapFile(f: File, path: string): UploadFile {
        return { file: f, path, size: f.size, lastModified: f.lastModified, uploading: false, ignore: false, try: 0 };
    }

    async function listDropFiles(items: DataTransferItemList): Promise<UploadFile[]> {
        const result: UploadFile[] = [];

        async function readAllDirectoryEntries(directoryReader: any): Promise<any[]> {
            const entries: any[] = [];
            let readEntries = await readEntriesPromise(directoryReader);
            while (readEntries.length > 0) {
                entries.push(...readEntries);
                readEntries = await readEntriesPromise(directoryReader);
            }
            return entries;
        }

        async function readEntriesPromise(directoryReader: any): Promise<any[]> {
            try {
                return await new Promise((resolve, reject) => {
                    directoryReader.readEntries(resolve, reject);
                });
            } catch (err) {
                console.error(err);
                return [];
            }
        }

        async function getFile(fileEntry: any): Promise<File> {
            return new Promise((resolve, reject) => fileEntry.file(resolve, reject));
        }

        const queue: any[] = [];
        for (let i = 0; i < items.length; i++) {
            queue.push(items[i].webkitGetAsEntry());
        }

        while (queue.length > 0) {
            const entry = queue.shift()!;
            if (entry.isFile) {
                const file = await getFile(entry);
                result.push(wrapFile(file, entry.fullPath.substring(1)));
            } else if (entry.isDirectory) {
                queue.push(...(await readAllDirectoryEntries(entry.createReader())));
            }
        }

        return result;
    }

    // ── Core upload logic (uses refs to avoid stale closures) ─────────

    function processFiles() {
        const files = filesRef.current;
        const sid = sessionIdRef.current;
        if (!sid) return;

        const data = new FormData();
        const fileidx: number[] = [];
        let batchSize = 0;

        for (let i = 0; i < files.length; ++i) {
            const file = files[i];
            if (uploadedRef.current.includes(i)) continue;
            if (file.uploading) continue;
            if (file.ignore) continue;
            if (file.try > 5) {
                if (!failedRef.current.includes(i)) failedRef.current.push(i);
                continue;
            }
            batchSize += file.size;

            if (fileidx.length > 0 && (fileidx.length >= 500 || batchSize > 1024 * 1014 * 300)) break;

            file.uploading = true;
            fileidx.push(i);
            data.append('files', file.file);
            data.append('paths', file.path);
            data.append('mtimes', String(file.lastModified));
        }

        if (fileidx.length === 0) return;

        const batch: Batch = { fileidx, evt: {}, status: 'uploading', size: batchSize };
        batchesRef.current.push(batch);
        rerender();

        axios
            .post(config.apihost + '/upload-multi/' + sid, data, {
                onUploadProgress: (evt: any) => {
                    batch.evt = evt;
                    // Throttle re-renders: only every ~200ms via requestAnimationFrame
                    requestAnimationFrame(rerender);
                },
            })
            .then((res) => {
                if (res.data === 'ok') {
                    batch.status = 'done';
                    fileidx.forEach((idx) => {
                        uploadedRef.current.push(idx);
                    });

                    if (uploadedRef.current.length + ignoreCountRef.current === files.length) {
                        done();
                    } else {
                        processFiles();
                    }
                } else {
                    batch.status = 'failed';
                    console.error(res);
                }
                rerender();
            })
            .catch(() => {
                batch.status = 'failed';
                fileidx.forEach((idx) => {
                    files[idx].try++;
                });
                rerender();
                setTimeout(processFiles, 1000 * 13);
            })
            .finally(() => {
                fileidx.forEach((idx) => {
                    files[idx].uploading = false;
                });
            });

        // Allow up to 4 concurrent batches
        const uploadingCount = batchesRef.current.filter((b) => b.status === 'uploading').length;
        if (uploadingCount < 4) {
            setTimeout(processFiles, 1000 * 3);
        }
    }

    async function done() {
        if (doneUploadingRef.current) return;
        doneUploadingRef.current = true;

        const sid = sessionIdRef.current;
        if (!sid) return;

        await axios.patch(`${config.apihost}/session/uploaded/${sid}`, {
            headers: { 'Content-Type': 'application/json' },
        });

        const f = filesRef.current[0];
        if (f) {
            const tokens = f.path.split('/');
            dispatch(updateDDName(tokens[0]));
        }
    }

    async function startUpload(files: UploadFile[]) {
        setStarting(false);
        doneUploadingRef.current = false;

        let size = 0;
        for (const file of files) {
            size += file.size;
        }

        totalSizeRef.current = size;
        filesRef.current = files;
        uploadedRef.current = [];
        failedRef.current = [];
        batchesRef.current = [];
        ignoreCountRef.current = 0;

        // Create session
        const res = await axios.post(`${config.apihost}/session`, {
            headers: { 'Content-Type': 'application/json' },
        });
        dispatch(setSession(res.data));
        sessionIdRef.current = res.data._id;

        rerender();
        processFiles();
    }

    // ── Event handlers ──────────────────────────────────────────────

    function handleDragOver(e: React.DragEvent) {
        e.preventDefault();
        setDragging(true);
    }

    function handleDragLeave() {
        setDragging(false);
    }

    async function handleDrop(e: React.DragEvent) {
        e.preventDefault();
        setDragging(false);
        setStarting(true);
        const files = await listDropFiles(e.dataTransfer.items);
        startUpload(files);
    }

    function handleSelectFiles(e: React.ChangeEvent<HTMLInputElement>) {
        const target = e.target;
        if (!target.files) return;
        setStarting(true);
        setTimeout(() => {
            const files: UploadFile[] = [];
            for (let i = 0; i < target.files!.length; i++) {
                const f = target.files![i];
                files.push(wrapFile(f, (f as any).webkitRelativePath));
            }
            startUpload(files);
        }, 1000);
    }

    // ── Download / Debug ──────────────────────────────────────────────

    async function downloadFile(fileName: string) {
        if (!fileName || !session) return;
        try {
            const res = await axios.get(`${config.apihost}/download/${session._id}/token`);
            window.location.href = `${config.apihost}/download/${session._id}/${fileName}?token=${res.data}`;
        } catch (e) {
            console.error(e);
            toast.error('There was an error downloading the file');
        }
    }

    function dump() {
        const element = document.createElement('a');
        element.setAttribute(
            'href',
            'data:text/plain;charset=utf-8,' + encodeURIComponent(JSON.stringify(ezbids, null, 4))
        );
        element.setAttribute('download', 'root.json');
        element.style.display = 'none';
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
    }

    // ── Derived values for render (read from refs) ───────────────────

    void renderTick; // consume to avoid unused warning
    const files = filesRef.current;
    const uploaded = uploadedRef.current;
    const failed = failedRef.current;
    const batches = batchesRef.current;
    const totalSize = totalSizeRef.current;
    const ignoreCount = ignoreCountRef.current;
    const ignoredFiles = files.filter((f) => f.ignore);
    const uploadedPercentage = files.length > 0 ? parseFloat(((uploaded.length / files.length) * 100).toFixed(1)) : 0;

    return (
        <div className="p-5">
            {/* No session yet - show upload UI */}
            {!session && (
                <div>
                    <p>
                        Welcome to{' '}
                        <b>
                            <span style={{ letterSpacing: '-2px', opacity: 0.5 }}>ez</span>BIDS
                        </b>{' '}
                        - an online imaging data to BIDS conversion / organizing tool.
                    </p>

                    {!starting && (
                        <>
                            <div
                                className={`relative z-0 rounded text-center overflow-hidden ${
                                    dragging ? 'bg-gray-400 text-white' : 'bg-black/5 text-gray-400'
                                }`}
                                style={{
                                    padding: '25px',
                                    paddingTop: '100px',
                                    height: '300px',
                                    boxSizing: 'border-box',
                                    fontSize: '125%',
                                }}
                                onDrop={handleDrop}
                                onDragLeave={handleDragLeave}
                                onDragOver={handleDragOver}
                            >
                                <div
                                    className="absolute top-0 left-0 right-0 -z-10 opacity-10"
                                    style={{ fontSize: '25vh', padding: '30px 0', filter: 'blur(0.5vh)' }}
                                >
                                    <b>
                                        <span style={{ letterSpacing: '-4vh' }}>ez</span>BIDS
                                    </b>
                                </div>
                                <div>
                                    <b>Drag &amp; Drop DICOM (or dcm2niix) data here to start</b>
                                    <br />
                                    <br />
                                    or
                                    <br />
                                    <br />
                                    <input
                                        type="file"
                                        /* @ts-expect-error webkitdirectory is non-standard */
                                        webkitdirectory=""
                                        multiple
                                        className="text-sm w-[400px] bg-white/20 p-1"
                                        onChange={handleSelectFiles}
                                    />
                                </div>
                            </div>

                            <div className="mt-6">
                                <h2 className="text-xl font-bold">Information</h2>
                                <ul className="list-disc ml-5 leading-8">
                                    <li>
                                        If you are new to ezBIDS, please view our{' '}
                                        <a
                                            href="https://brainlife.io/docs/tutorial/ezBIDS/"
                                            target="_blank"
                                            rel="noreferrer"
                                            className="font-bold text-blue-600 underline"
                                        >
                                            ezBIDS tutorial
                                        </a>{' '}
                                        and{' '}
                                        <a
                                            href="https://brainlife.io/docs/using_ezBIDS/"
                                            target="_blank"
                                            rel="noreferrer"
                                            className="font-bold text-blue-600 underline"
                                        >
                                            user documentation
                                        </a>
                                        .
                                    </li>
                                    <li>
                                        If uploading anonymized data, please organize subject data into <i>sub-</i>
                                        formatted folder names (e.g. <b>sub-01</b>). If you have multi-session data,
                                        place in <i>ses-</i>formatted folders (e.g. <b>ses-A</b>) within the subject
                                        folders.
                                    </li>
                                    <li>See below for a brief ezBIDS tutorial video.</li>
                                </ul>
                                <iframe
                                    width="640"
                                    height="360"
                                    src="https://www.youtube.com/embed/L8rWA8qgnpo"
                                    title="YouTube video player"
                                    frameBorder="0"
                                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                    allowFullScreen
                                    className="mt-4"
                                />
                            </div>
                            <br />
                            <br />
                            <br />
                        </>
                    )}

                    {starting && (
                        <div>
                            <h3 className="text-lg font-semibold">Initializing ...</h3>
                        </div>
                    )}
                </div>
            )}

            {/* Session exists */}
            {session && (
                <div>
                    {/* Uploading */}
                    {session.status === 'created' && (
                        <div>
                            <h3 className="text-lg font-semibold">
                                Uploading <FontAwesomeIcon icon="spinner" pulse />
                            </h3>
                            <small>Please do not close or refresh this page until all files are uploaded.</small>

                            {failed.length > 0 && (
                                <div>
                                    <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded mt-2">
                                        Permanently failed to upload some files, please email pestilli@utexas.edu for
                                        assistance
                                    </div>
                                    {failed.map((idx) => (
                                        <pre key={idx} className="text-xs">
                                            {files[idx]?.path}
                                        </pre>
                                    ))}
                                </div>
                            )}

                            <p className="mt-2">
                                <small>Total size {formatNumber(totalSize / (1024 * 1024))} MB</small>
                                <small> | {files.length} Files </small>
                                <small> ({uploaded.length} uploaded) </small>
                                {ignoreCount > 0 && <small>({ignoreCount} ignored) </small>}
                            </p>
                            <div className="w-full bg-gray-200 rounded-full h-6 mt-1">
                                <div
                                    className="bg-green-500 h-6 rounded-full text-xs text-white flex items-center justify-center transition-all"
                                    style={{ width: `${uploadedPercentage}%` }}
                                >
                                    {uploadedPercentage}%
                                </div>
                            </div>

                            {batches.map((batch, idx) =>
                                batch.status !== 'done' ? (
                                    <div key={idx} className="font-mono text-sm mt-1">
                                        <b className="uppercase">{batch.status}</b> batch {idx + 1}.{' '}
                                        {batch.fileidx.length} files
                                        <span> ({formatNumber(batch.size / (1024 * 1024))} MB) </span>
                                        {batch.evt.total && (
                                            <div className="w-full bg-gray-200 rounded-full h-4">
                                                <div
                                                    className={`${batchStatusColor(
                                                        batch
                                                    )} h-4 rounded-full text-xs text-white flex items-center justify-center transition-all`}
                                                    style={{
                                                        width: `${((batch.evt.loaded! / batch.evt.total) * 100).toFixed(
                                                            1
                                                        )}%`,
                                                    }}
                                                >
                                                    {((batch.evt.loaded! / batch.evt.total) * 100).toFixed(1)}%
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ) : null
                            )}
                        </div>
                    )}

                    {/* Preprocessing / Uploaded */}
                    {['preprocessing', 'uploaded'].includes(session.status) && (
                        <div>
                            {session.dicomDone === undefined && (
                                <h3 className="text-lg font-semibold">
                                    Inflating <FontAwesomeIcon icon="spinner" pulse />
                                </h3>
                            )}
                            {session.dicomDone !== undefined && session.dicomDone < session.dicomCount && (
                                <div>
                                    <h3 className="text-lg font-semibold">
                                        Converting DICOMS to NIfTI <FontAwesomeIcon icon="spinner" pulse />
                                    </h3>
                                    <div className="w-full bg-gray-200 rounded-full h-6 mt-1">
                                        <div
                                            className="bg-green-500 h-6 rounded-full text-xs text-white flex items-center justify-center transition-all"
                                            style={{
                                                width: `${((session.dicomDone * 100) / session.dicomCount).toFixed(
                                                    1
                                                )}%`,
                                            }}
                                        >
                                            {((session.dicomDone * 100) / session.dicomCount).toFixed(1)}%
                                        </div>
                                    </div>
                                    <br />
                                </div>
                            )}
                            {session.dicomDone !== undefined && session.dicomDone >= session.dicomCount && (
                                <h3 className="text-lg font-semibold">
                                    Analyzing <FontAwesomeIcon icon="spinner" pulse />
                                </h3>
                            )}
                            <pre className="bg-gray-600 text-white h-[300px] overflow-auto p-2.5 mt-0 mb-1 rounded">
                                {session.status_msg}
                            </pre>
                            <small>
                                * Depending on the size of your dataset, this process might take several hours. You can
                                shutdown your computer while we process your data (please bookmark the URL for this page
                                to come back to it)
                            </small>
                        </div>
                    )}

                    {/* Failed */}
                    {session.status === 'failed' && (
                        <div>
                            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded">
                                ezBIDS failed.. Please check the Debug logs and contact the ezBIDS team
                                (pestilli@utexas.edu).
                            </div>
                            <br />
                            <pre className="bg-gray-600 text-white h-[300px] overflow-auto p-2.5 mt-0 mb-1 rounded">
                                {session.status_msg}
                            </pre>
                        </div>
                    )}

                    {/* Analysis complete */}
                    {session.pre_finish_date && (
                        <div>
                            {ezbids.notLoaded && (
                                <div>
                                    <h3 className="text-lg font-semibold">
                                        Loading analysis results <FontAwesomeIcon icon="spinner" pulse />
                                    </h3>
                                </div>
                            )}

                            {!ezbids.notLoaded && ezbids.objects.length > 0 && (
                                <div>
                                    <h2 className="text-xl font-bold">Analysis complete!</h2>
                                    <AnalysisErrors />
                                    <h3 className="text-lg font-semibold">
                                        Object List <small>({ezbids.objects.length})</small>
                                    </h3>
                                    <p>
                                        <small>
                                            We have identified the following files (objects) that can be organized into
                                            BIDS structure.
                                        </small>
                                    </p>
                                    {ezbids.objects.map((object, idx) => (
                                        <div key={idx} className="pb-0.5">
                                            <p className="m-0">
                                                <button
                                                    className="text-blue-600 underline text-sm text-left"
                                                    onClick={() => toggleObject(idx)}
                                                >
                                                    <span className="bg-gray-200 text-gray-600 text-xs px-1 rounded mr-1">
                                                        {idx}
                                                    </span>
                                                    {itemPath(object.items)}
                                                </button>
                                            </p>
                                            {opened.includes(idx) && (
                                                <pre className="bg-gray-600 text-white h-[300px] overflow-auto p-2.5 mt-0 mb-1 rounded text-sm">
                                                    {JSON.stringify(object, null, 2)}
                                                </pre>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}

                            {!ezbids.notLoaded && ezbids.objects.length === 0 && (
                                <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded">
                                    We couldn't find any objects. Please upload data that contains at least 1 object.
                                    Contact the ezBIDS team (pestilli@utexas.edu or
                                    https://github.com/brainlife/ezbids/issues) for support
                                </div>
                            )}
                        </div>
                    )}

                    <br />

                    {/* Debug */}
                    <details className="border rounded p-2">
                        <summary className="cursor-pointer font-semibold text-gray-700">Debug (Download)</summary>
                        <div className="mt-2">
                            <ul className="list-none p-0 flex flex-wrap gap-2">
                                {[
                                    'preprocess.log',
                                    'preprocess.err',
                                    'dcm2niix_error',
                                    'pet2bids_error',
                                    'list',
                                    'ezBIDS_core.json',
                                ].map((name) => (
                                    <li key={name}>
                                        <button
                                            className="bg-yellow-500 hover:bg-yellow-600 text-white text-xs px-3 py-1 rounded"
                                            onClick={() => downloadFile(name)}
                                        >
                                            {name === 'list' ? 'data list' : name}
                                        </button>
                                    </li>
                                ))}
                            </ul>
                            <button
                                className="bg-gray-500 hover:bg-gray-600 text-white text-xs px-3 py-1 rounded mt-2"
                                onClick={dump}
                            >
                                Dump state
                            </button>
                            {ignoredFiles.length > 0 && (
                                <div className="mt-3">
                                    <b>Ignored Files</b>
                                    <ul className="list-disc ml-5">
                                        {ignoredFiles.map((file, idx) => (
                                            <li key={idx}>
                                                <pre className="text-sm">{file.path}</pre>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    </details>
                    <br />
                    <br />
                    <br />
                </div>
            )}
        </div>
    );
});

export default Upload;
