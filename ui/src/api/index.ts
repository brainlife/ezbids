import { Plugin } from 'vue';
import axios from '../axios.instance';
import { v4 as uuid } from 'uuid';
import { EzbidsProcessingMode, IEZBIDS, IEZBIDSUpdateSchema, IObject, ISession } from '../store/store.types';
import store from '../store';
import { apihost, getShortLivedJWTToken } from './helpers';
import { AxiosError } from 'axios';
import Convert from 'ansi-to-html';

const convert = new Convert();

export interface API {
    getSessionById: (
        sessionId: string
    ) => Promise<{ session: Partial<ISession> | null; ezbidsProcessingMode: EzbidsProcessingMode }>;
    createNewSession: () => Promise<Partial<ISession>>;
    getEZBIDSCoreJSONFile: (sessionId: string) => Promise<IEZBIDS | null>;
    getEZBIDSUpdated: (sessionId: string) => Promise<IEZBIDSUpdateSchema['updated'] | null>;
    getDefaceStatus: (sessionId: string) => Promise<{ defaceContents: string; status: 'FINISHED' | 'FAILED' } | null>;
    cancelDeface: (sessionId: string) => Promise<string>;
    resetDeface: (sessionId: string) => Promise<string>;
    runDeface: (
        sessionId: string,
        anatObjectList: { idx: number; path: string | undefined }[],
        defacingMethod: string
    ) => Promise<string>;
    runFinalize: (
        sessionId: string,
        args: {
            subjects: IEZBIDS['subjects'];
            series: IEZBIDS['series'];
            defacingMethod: IEZBIDS['defacingMethod'];
            includeExcluded: IEZBIDS['includeExcluded'];
            objects: IEZBIDS['objects'];
            BIDSURI: IEZBIDS['BIDSURI'];
            events: IEZBIDS['events'];
            entityMappings: { [key: string]: string };
            datasetDescription: IEZBIDS['datasetDescription'];
            readme: IEZBIDS['readme'];
            participantsColumn: IEZBIDS['participantsColumn'];
            participantInfo: IEZBIDS['participantsInfo'];
        }
    ) => Promise<string>;
    downloadFile: (sessionId: string, pathName: string) => Promise<void>;
    storeFiles: (
        sessionId: string,
        onComplete: () => void,
        serverVariables?: {
            files: any[];
            uploaded: any[];
            failed: any[];
            ignoreCount: number;
            batches: any[];
        }
    ) => Promise<void>;
    getDCM2NIIXError: (sessionId: string) => Promise<string | null>;
    retrieveFileContents: (sessionId: string, path: string) => Promise<string>;
}

const apiInstance: API = {
    getSessionById: async (sessionId) => {
        // The processing mode may not be set in the store yet. We derive its value by checking
        // both the local storage and the database.
        if (!sessionId) throw new Error('no session id');
        try {
            const session = localStorage.getItem(sessionId);
            if (session) {
                const parsedSession = JSON.parse(session);
                return new Promise((resolve) => resolve({ session: parsedSession, ezbidsProcessingMode: 'EDGE' }));
            }

            const res = await axios.get<ISession>(`${apihost}/session/${sessionId}`);
            return {
                session: res.data,
                ezbidsProcessingMode: res.data ? 'SERVER' : null,
            };
        } catch (e) {
            return new Promise((resolve) =>
                resolve({
                    session: null,
                    ezbidsProcessingMode: null,
                })
            );
        }
    },
    createNewSession: async () => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');
        if (processingMode === 'EDGE') {
            const newSession: Partial<ISession> = {
                _id: uuid(),
                ownerId: 0,
                allowedUsers: [],
                create_date: new Date().toISOString(), //"2021-08-27T21:24:21.610Z"
            };
            localStorage.setItem(`${newSession._id}`, JSON.stringify(newSession));
            return new Promise((resolve) => resolve(newSession));
        } else {
            const res = await axios.post<ISession>(`${apihost}/session`, {
                headers: { 'Content-Type': 'application/json' },
            });
            return res.data;
        }
    },
    getDefaceStatus: async (sessionId) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');
        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement
                return Promise.reject('not yet implemented');
            } else {
                let jwt = await getShortLivedJWTToken(sessionId);
                const finished = await axios.get<string>(
                    `${apihost}/download/${sessionId}/deface.finished?token=${jwt.data}`
                );
                if (finished.status === 200 && !!finished.data) {
                    // the deface.finished file should always exist?
                    const finishedText = finished.data;
                    return {
                        defaceContents: finishedText,
                        status: 'FINISHED',
                    };
                }

                jwt = await getShortLivedJWTToken(sessionId);
                const failed = await axios.get<string>(
                    `${apihost}/download/${sessionId}/deface.failed?token=${jwt.data}`
                );
                if (failed.status === 200 && !!failed.data) {
                    // the deface.failed file exists meaning defacing failed
                    const failedText = failed.data;
                    return {
                        defaceContents: failedText,
                        status: 'FAILED',
                    };
                }

                return null;
            }
        } catch (e) {
            if ((e as AxiosError)?.response?.status === 404) {
                return null;
            }
            throw new Error('error getting deface status');
        }
    },
    cancelDeface: async (sessionId) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');

        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement
                return Promise.reject('not yet implemented');
            } else {
                const res = await axios.post<string>(`${apihost}/session/${sessionId}/canceldeface`);
                return res.data;
            }
        } catch (e) {
            throw new Error('error canceling deface');
        }
    },
    resetDeface: async (sessionId: string) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');
        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement
                return Promise.reject('not yet implemented');
            } else {
                const res = await axios.post<string>(`${apihost}/session/${sessionId}/resetdeface`);
                return res.data;
            }
        } catch (e) {
            throw new Error('error resetting deface');
        }
    },
    runDeface: async (sessionId, anatObjectList, defacingMethod) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');
        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement
                return Promise.reject('not yet implemented');
            } else {
                const res = await axios.post<string>(`${apihost}/session/${sessionId}/deface`, {
                    list: anatObjectList,
                    method: defacingMethod,
                });
                return res.data;
            }
        } catch (e) {
            throw new Error('error running deface');
        }
    },
    runFinalize: async (sessionId, args) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');
        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement
                return Promise.reject('not yet implemented');
            } else {
                const res = await axios.post<string>(`${apihost}/session/${sessionId}/finalize`, args);
                return res.data;
            }
        } catch (e) {
            throw new Error('error running finalize');
        }
    },
    downloadFile: async (sessionId, pathName) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');
        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement
                return Promise.reject('not yet implemented');
            } else {
                const jwt = await getShortLivedJWTToken(sessionId);
                window.location.href = `${apihost}/download/${sessionId}/${pathName}?token=${jwt.data}`;
            }
        } catch (e) {
            console.error(e);
            throw new Error('error downloading file');
        }
    },
    retrieveFileContents: async (sessionId, path) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');
        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement
                return Promise.reject('not yet implemented');
            } else {
                const jwt = await getShortLivedJWTToken(sessionId);
                const res = await axios.get(`${apihost}/download/${sessionId}/${path}?token=${jwt.data}`);
                return convert.toHtml(res.data);
            }
        } catch (e) {
            console.error(e);
            throw new Error('error retrieving file contents');
        }
    },
    storeFiles: async function (sessionId, onComplete, serverVariables) {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');
        if (processingMode === 'EDGE') {
            // ANIBAL-TODO: implement storing files in the browser
            // Can we just dump the file contents into local storage? Not
            // quite sure how one would store non text files (like DICOMs) however

            // Note: serverVariables is an optional argument that is used to track/update
            // state in the Upload.vue component. I think EDGE mode can ignore this as writes to
            // local storage should be synchronous?
            return Promise.reject('not yet implemented');
        } else {
            if (serverVariables === undefined) throw new Error('Server variables are required');
            const { files, failed, batches, ignoreCount, uploaded } = serverVariables;

            //find next files to upload
            let data = new FormData();
            let fileidx: any[] = [];
            let batchSize = 0;

            for (let i = 0; i < files.length; ++i) {
                let file = files[i];
                if (uploaded.includes(i)) continue;
                if (file.uploading) continue;
                if (file.ignore) continue;
                if (file.try > 5) {
                    if (!failed.includes(i)) failed.push(i);
                    continue; //TODO we should abort upload?
                }
                batchSize += file.size;

                //limit batch size (3000 files causes network error - probably too many?)
                if (fileidx.length > 0 && (fileidx.length >= 500 || batchSize > 1024 * 1014 * 300)) break;

                //let's proceed!
                file.uploading = true;
                fileidx.push(i);
                data.append('files', file);

                //file doesn't contains the real path and lastModifiedDate. I need to pass this separately
                data.append('paths', file.path);
                data.append('mtimes', file.lastModified);
            }

            if (fileidx.length == 0) {
                return;
            }

            //prepare a batch
            let batch = { fileidx, evt: {}, status: 'uploading', size: batchSize };
            batches.push(batch);
            const that = this;

            axios
                .post(`${apihost}/upload-multi/${sessionId}`, data, {
                    onUploadProgress: (evt) => {
                        //count++;
                        batch.evt = evt;
                    },
                })
                .then(async (res) => {
                    let msg = res.data;
                    if (msg === 'ok') {
                        batch.status = 'done';
                        fileidx.forEach((idx) => {
                            uploaded.push(idx);
                        });

                        if (uploaded.length + ignoreCount === files.length) {
                            await axios.patch(`${apihost}/session/uploaded/${sessionId}`, {
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                            });
                            onComplete();
                        } else {
                            //handle next batch
                            that.storeFiles(sessionId, onComplete, serverVariables);
                        }
                    } else {
                        //server side error?
                        batch.status = 'failed';
                        console.error(res);
                    }
                })
                .catch((err) => {
                    batch.status = 'failed';
                    //retry these files on a different batch
                    fileidx.forEach((idx) => {
                        files[idx].try++;
                    });
                    setTimeout(() => that.storeFiles(sessionId, onComplete, serverVariables), 1000 * 13);
                })
                .then(() => {
                    fileidx.forEach((idx) => {
                        files[idx].uploading = false;
                    });
                });

            //see how many batches we are currently uploading
            let uploadingBatches = batches.filter((b) => b.status == 'uploading');
            if (uploadingBatches.length < 4) {
                setTimeout(() => that.storeFiles(sessionId, onComplete, serverVariables), 1000 * 3);
            }
        }
    },
    /**
     * ANIBAL-TODO: double check that this function is necessary, remove if not
     * I'm honestly not sure that this function is even used...
     */
    getEZBIDSUpdated: async (sessionId) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');

        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement returning ezBIDS_updated.json file
                return Promise.resolve(null);
            } else {
                const res = await axios.get(`${apihost}/session/${sessionId}/updated`);
                if (res.status === 200) {
                    return res.data;
                }

                throw new Error('error getting ezBIDS update');
            }
        } catch (e) {
            console.error(e);
            return Promise.resolve(null);
        }
    },
    getEZBIDSCoreJSONFile: async (sessionId) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');

        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement returning ezBIDS_core.json file
                return Promise.resolve(null);
            } else {
                const jwtRes = await axios.get(`${apihost}/download/${sessionId}/token`);
                const res = await axios.get<IEZBIDS>(
                    `${apihost}/download/${sessionId}/ezBIDS_core.json?token=${jwtRes.data}`
                );
                return res.status === 200 ? res.data : null;
            }
        } catch (e) {
            console.error(e);
            return Promise.resolve(null);
        }
    },
    getDCM2NIIXError: async (sessionId) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');

        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement
                return Promise.reject('not yet implemented');
            } else {
                const jwt = await axios.get<string>(`${apihost}/download/${sessionId}/token`);
                const res = await axios.get<string>(
                    `${apihost}/download/${sessionId}/dcm2niix_error?token=${jwt.data}`
                );
                return res.status === 200 ? res.data : null;
            }
        } catch (e) {
            console.error(e);
            return 'Failed to load dcm2niix error log';
        }
    },
};

const api = {
    install(app, ...options) {
        app.config.globalProperties.api = { ...apiInstance } as API;
    },
    ...apiInstance,
} as Plugin & API;

export default api;
