import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit';
import axios from '../../axios.instance';
import type { RootState } from '../index';

export interface ISession {
    _id: string;
    ownerId: number;
    allowedUsers: number[];
    create_date: string;
    dicomCount: number;
    dicomDone: number;
    request_headers: any;
    status: string;
    status_msg: string;
    update_date: string;
    upload_finish_date?: string;
    pre_begin_date?: string;
    pre_finish_date?: string;
    deface_begin_date?: string;
    deface_finish_date?: string;
    finalize_begin_date?: string;
    finalize_finish_date?: string;
}

interface SessionState {
    data: ISession | null;
    config: {
        apihost: string;
        authhost: string;
        authSignIn: string;
        authSignOut: string;
        debug: boolean;
    };
}

// Electron preload exposes window.env with API_HOST
const windowEnv = (window as any).env || {};

const initialState: SessionState = {
    data: null,
    config: {
        apihost: windowEnv.API_HOST || import.meta.env.VITE_APIHOST || '/api/ezbids',
        authhost: import.meta.env.MODE === 'development' ? 'http://localhost:8080/api/auth' : '/api/auth',
        authSignIn: '/auth/#!/signin',
        authSignOut: '/auth/#!/signout',
        debug: import.meta.env.MODE === 'development',
    },
};

export const loadSession = createAsyncThunk('session/loadSession', async (_, { getState }) => {
    const state = getState() as RootState;
    if (!state.session.data) return null;
    const res = await axios.get(`${state.session.config.apihost}/session/${state.session.data._id}`);
    return res.data;
});

const sessionSlice = createSlice({
    name: 'session',
    initialState,
    reducers: {
        setSession(state, action: PayloadAction<ISession | null>) {
            state.data = action.payload;
            // Only set hash for session ID in BrowserRouter (web) mode.
            // In HashRouter (Electron/file:// protocol), hash is used for routing.
            if (action.payload?._id && window.location.protocol !== 'file:') {
                window.location.hash = action.payload._id;
            }
        },
        updateAllowedUsers(state, action: PayloadAction<number[]>) {
            if (state.data) {
                state.data.allowedUsers = action.payload;
            }
        },
        resetSession(state) {
            state.data = null;
        },
    },
    extraReducers: (builder) => {
        builder.addCase(loadSession.fulfilled, (state, action) => {
            if (action.payload) {
                state.data = action.payload;
            }
        });
    },
});

export const { setSession, updateAllowedUsers, resetSession } = sessionSlice.actions;
export default sessionSlice.reducer;
