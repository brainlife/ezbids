import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export interface IEvents {
    columns: {
        onsetLogic: string;
        onset: string | null;
        onset2: string | null;
        onsetUnit: string;
        durationLogic: string;
        duration: string | null;
        duration2: string | null;
        durationUnit: string;
        sampleLogic: string;
        sample: string | null;
        sample2: string | null;
        sampleUnit: string;
        trialType: string | null;
        responseTimeLogic: string;
        responseTime: string | null;
        responseTime2: string | null;
        responseTimeUnit: string;
        value: string | null;
        HED: string | null;
        stim_file: string | null;
    };
    trialTypes: {
        longName: string;
        desc: string;
        levels: Record<string, string>;
    };
    columnKeys: string[] | null;
    sampleValues: Record<string, string[]>;
    loaded: boolean;
}

const initialState: IEvents = {
    columns: {
        onsetLogic: 'eq',
        onset: null,
        onset2: null,
        onsetUnit: 'sec',
        durationLogic: 'eq',
        duration: null,
        duration2: null,
        durationUnit: 'sec',
        sampleLogic: 'eq',
        sample: null,
        sample2: null,
        sampleUnit: 'samples',
        trialType: null,
        responseTimeLogic: 'eq',
        responseTime: null,
        responseTime2: null,
        responseTimeUnit: 'sec',
        value: null,
        HED: null,
        stim_file: null,
    },
    trialTypes: {
        longName: 'Event category',
        desc: 'Indicator of type of action that is expected',
        levels: {},
    },
    columnKeys: null,
    sampleValues: {},
    loaded: false,
};

const eventsSlice = createSlice({
    name: 'events',
    initialState,
    reducers: {
        updateEvents(state, action: PayloadAction<Partial<IEvents>>) {
            Object.assign(state, action.payload);
        },
        resetEvents(state) {
            Object.assign(state, {
                columnKeys: null,
                sampleValues: {},
                loaded: false,
            });
        },
    },
});

export const { updateEvents, resetEvents } = eventsSlice.actions;
export default eventsSlice.reducer;
