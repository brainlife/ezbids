import { Plugin } from 'vue';
import axios from '../axios.instance';
import { v4 as uuid } from 'uuid';
import { EzbidsProcessingMode, IEZBIDS, ISession } from '../store/store.types';
import store from '../store';

const apihost = import.meta.env.VITE_APIHOST || '/api/ezbids';

export interface API {
    getSessionById: (
        sessionId: string
    ) => Promise<{ session: Partial<ISession> | null; ezbidsProcessingMode: EzbidsProcessingMode }>;
    createNewSession: () => Promise<{ session: Partial<ISession> }>;
    getEZBIDSCoreJSONFile: (sessionId: string) => Promise<IEZBIDS | null>;
    getEZBIDSUpdated: (sessionId: string) => Promise<IEZBIDS | null>;
}

const apiInstance: API = {
    getSessionById: async (sessionId: string) => {
        if (!sessionId) throw new Error('no session id');
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');

        try {
            if (processingMode === 'EDGE') {
                const session = localStorage.getItem(sessionId);
                if (!session) throw new Error('no session'); // jump to catch
                const parsedSession = JSON.parse(session);
                return new Promise((resolve) => resolve({ session: parsedSession, ezbidsProcessingMode: 'EDGE' }));
            } else {
                // found the session in the database, we are computing using SERVER mode
                const res = await axios.get<{ session: ISession }>(`${apihost}/session/${sessionId}`);
                return {
                    session: res.data.session,
                    ezbidsProcessingMode: res.data.session ? 'SERVER' : null,
                };
            }
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
            return new Promise((resolve) => resolve({ session: newSession }));
        } else {
            const res = await axios.post<{ session: ISession }>(`${apihost}/session`, {
                headers: { 'Content-Type': 'application/json' },
            });
            return res.data;
        }
    },
    getDeface: async (sessionId: string) => {
        // TODO: implement
    },
    getDefaceFailed: async (sessionId: string) => {
        // TODO: implement
    },
    cancelDeface: async () => {
        // TODO: implement
    },
    resetDeface: async () => {
        // TODO: implement
    },
    downloadFile: async () => {
        // TODO: implement
    },
    markAsUploaded: async () => {
        // TODO: implement, update session data in local storage
    },
    /**
     * TODO-ANIBAL: confirm that this function is necessary, remove if not
     * I'm honestly not sure that this function is even used...
     * @param sessionId
     * @returns the JSON of IEZBIDS.updated
     * @returns null if not found
     */
    getEZBIDSUpdated: async (sessionId: string) => {
        const processingMode = store.state.ezbidsProcessingMode;
        if (!processingMode) throw new Error('no processing mode');

        try {
            if (processingMode === 'EDGE') {
                // ANIBAL-TODO: implement returning ezBIDS_updated.json file
                return Promise.resolve(null);
            } else {
            }
        } catch (e) {
            console.error(e);
            return Promise.resolve(null);
        }
    },
    /**
     *
     * @param sessionId
     * @returns null - not found or error
     * @returns IEZBIDS - the contents of ezbids_core.json
     */
    getEZBIDSCoreJSONFile: async (sessionId: string) => {
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
};

const api = {
    install(app, ...options) {
        app.config.globalProperties.api = { ...apiInstance } as API;
    },
    ...apiInstance,
} as Plugin & API;

export default api;
